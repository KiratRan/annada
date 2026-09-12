#!/usr/bin/env python3
"""..."""
from __future__ import annotations
import argparse, os, re, sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
try:
    import yaml
except ImportError:
    yaml = None

# Runtime contract. Canonical household data lives under HOUSEHOLD_ROOT;
# the external Obsidian vault is provided via OBSIDIAN_VAULT and never
# falls back to a machine-specific path.
def _household_root():
    root = os.environ.get("HOUSEHOLD_ROOT", "").strip()
    if not root:
        raise RuntimeError(
            "HOUSEHOLD_ROOT must be set to the household data root.")
    root = Path(root).expanduser()
    if not (root / "recipes").is_dir():
        raise RuntimeError(
            f"HOUSEHOLD_ROOT={root} has no recipes/ directory (not a household root?).")
    return root

def _obsidian_vault():
    vault = os.environ.get("OBSIDIAN_VAULT", "").strip()
    if not vault:
        raise RuntimeError(
            "OBSIDIAN_VAULT must be set to the external Obsidian vault path "
            "(publishing requires it).")
    return Path(vault).expanduser()

DEFAULT_RECIPES_DIR = None       # resolved lazily from HOUSEHOLD_ROOT
DEFAULT_VAULT_DIR = None         # resolved lazily from OBSIDIAN_VAULT
DEFAULT_PLAN_FILE = None         # derived from the vault (Meals/This Week.md)
BEGIN = "<!-- BEGIN HERMES GENERATED CONTENT -->"
END = "<!-- END HERMES GENERATED CONTENT -->"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

def extract_frontmatter(text):
    if yaml is None:
        raise RuntimeError("PyYAML required. pip install pyyaml")
    m = FRONTMATTER_RE.match(text)
    if not m:
        return None, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML frontmatter: {exc}") from exc
    return (data if isinstance(data, dict) else {}), text[m.end():]

def resolve_field(fm, key, default=""):
    val = fm.get(key, default)
    if val is None: return default
    if isinstance(val,(list,tuple)):
        if not val: return default
        val = val[0]
    return str(val).strip() if val else default

def list_field(fm, key):
    val = fm.get(key, [])
    if val is None: return []
    if not isinstance(val,(list,tuple)): val=[val]
    return [str(x).strip() for x in val if str(x).strip()]

_UNIT_WORDS = {"lb","lbs","pound","pounds","oz","ounce","ounces","kg","kilo","kilogram","kilograms","gram","grams","g","mg","cup","cups","tablespoon","tablespoons","tbsp","tbsps","teaspoon","teaspoons","tsp","tsps","ml","milliliter","milliliters","liter","liters","l","quart","quarts","qt","pint","pints","gallon","gallons","gal","inch","inches","in","slice","slices","clove","cloves","bunch","bunches","head","heads","pinch","dash","dashes","can","cans","package","packages","pkg","stick","sticks","sprig","sprigs","strip","strips","handful","drop","drops","drizzle","to","taste"}
_INGREDIENT_RE = re.compile(r"^[-*+]\s*")

def parse_ingredient_line(line):
    s = line.strip()
    if not s or s.startswith("#"): return "", s
    s = _INGREDIENT_RE.sub("", s, count=1)
    if not s: return "", s
    tokens = re.findall(r"\([^)]*\)|\S+", s)
    if not tokens: return "", s
    if not re.match(r"^\d", tokens[0]): return "", s
    i=0; qty=[]
    while i<len(tokens) and re.match(r"^\d",tokens[i]):
        qty.append(tokens[i]); i+=1
    while i<len(tokens) and tokens[i].strip(".,;:)(").lower() in _UNIT_WORDS:
        qty.append(tokens[i]); i+=1
    if i<len(tokens) and tokens[i].startswith("(") and re.search(r"\d",tokens[i]):
        qty.append(tokens[i]); i+=1
    return " ".join(qty), " ".join(tokens[i:])

def render_ingredient(line):
    qty, rest = parse_ingredient_line(line)
    if not qty: return f"- {rest}"
    return f"- **{qty}** {rest}"

_BAD_VERBS = {"add","put","place"}
_NEUTRAL = {"Season with salt.","Salt to taste.","Season with pepper.","Season and finish.","Serve.","Serve hot."}
_ADVERBS = {"meanwhile","then","next","finally","first","last","lastly","afterwards","immediately","once","when","as","after","second","to"}
_STOP_WORDS = {"and","or","in","on","for","the","a","an","over","with","to","until","then","if","while","when","where","from","about","around","through","degrees","minute","minutes","seconds","seconds","heat","off","until"}
def _clean_token(tok): return re.sub(r"[^A-Za-z]","",re.sub(r"[()]","",tok))
def _summarise_step(step_text):
    text = step_text.strip()
    text = re.sub(r"^[-0-9A-Z]+[).]\s*","",text,flags=re.I).strip().rstrip(".")
    if not text: return "Step"
    for n in _NEUTRAL:
        if step_text.strip().rstrip(".").lower() == n.lower(): return n
    first = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text)[0]
    # strip adverbial phrases: "Meanwhile, heat..." / "To serve, scoop..."
    first = re.sub(rf"^({'|'.join(_ADVERBS)}),?\s+", "", first, flags=re.I)
    # strip trailing comma-led phrases: "prepare, ..."
    first = re.sub(r",\s*(?:in|over|for|on|and|then|with).*", "", first)
    m = re.match(r"^([A-Za-z]+)\s+(.*)$", first)
    if not m: return "Finish and season"
    verb, core = m.group(1), m.group(2)
    v = _clean_token(verb)
    if v.endswith("ing") and len(v) > 5:
        v = v[:-3] + ("e" if v.endswith("ting") else "")
    if v.lower() in _BAD_VERBS: v = "Cook"
    core = re.sub(r"^(a|an|the)\s+", "", core)
    core = re.sub(r"^(in|into|to|with|over|for|on|at|under|until|while|where)+,?\s+", "", core, flags=re.I)
    words = []
    for w in core.split():
        cw = _clean_token(w)
        if not cw or cw.lower() in _BAD_VERBS: continue
        if cw.lower() in _STOP_WORDS: break
        words.append(w)
        if len(words) >= 3: break
    # strip trailing stop/punctuation tokens
    while words and _clean_token(words[-1]).lower() in _STOP_WORDS:
        words.pop()
    # strip trailing commas and empty tokens
    while words and (words[-1].rstrip(",") != words[-1] or not words[-1].strip()):
        words[-1] = words[-1].rstrip(",")
        if not words[-1].strip(): words.pop()
        else: break
    if not words: return f"{v.capitalize()} the ingredients"
    return f"{v.capitalize()} {' '.join(words)}"

_WIKILINK_RE = re.compile(r"\[\[Recipes/([^\]|#]+)(?:\|[^\]]+)?\]\]")
def scheduled_recipe_ids(plan_path):
    """Extract recipe IDs from an approved plan YAML."""
    if plan_path is None or not plan_path.exists(): return []
    try: text = plan_path.read_text(encoding="utf-8")
    except OSError: return []
    try:
        raw = yaml.safe_load(text) or {}
    except Exception:
        return []
    ids=[]
    seen=set()
    meals = raw if isinstance(raw, list) else raw.get("meals", raw.get("plan",{}).get("meals",[]))
    for meal in meals:
        if not isinstance(meal, dict): continue
        recipe = meal.get("recipe")
        if isinstance(recipe, dict):
            rid = (recipe.get("id") or recipe.get("recipe_id") or "").strip()
        elif isinstance(recipe, str):
            rid = recipe.strip()
        else:
            continue
        if rid and rid not in seen:
            seen.add(rid)
            ids.append(rid)
    return ids

class Recipe:
    def __init__(self, rid, title, fm, body, path):
        self.id=rid; self.title=title; self.fm=fm; self.body=body.strip(); self.path=path
    @property
    def cuisine(self): return resolve_field(self.fm,"cuisine")
    @property
    def title_low(self): return self.title.lower()

def load_recipes(recipes_dir):
    recipes=[]
    for path in sorted(recipes_dir.glob("*.md")):
        if path.name=="README.md" or path.name.lower().startswith("index."): continue
        try: text=path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"  !! cannot read {path}: {exc}", file=sys.stderr); continue
        try: fm, body = extract_frontmatter(text)
        except ValueError as exc:
            print(f"  !! {path.name}: {exc}", file=sys.stderr); continue
        rid = resolve_field(fm or {}, "id") if fm else ""
        if not rid: rid = path.stem
        title = resolve_field(fm or {}, "title", path.stem) if fm else path.stem
        recipes.append(Recipe(rid, title, fm or {}, body, path))
    return recipes

_SECTION_SPLIT_RE = re.compile(r"\n(?=##\s)", re.M)
def split_sections(body):
    sections=[]
    for part in _SECTION_SPLIT_RE.split(body):
        part=part.strip("\n")
        lines=part.splitlines()
        if not lines: continue
        head=lines[0].strip()
        if head.startswith("## "): name=head[3:].strip()
        elif head.startswith("# "): name="Title"
        else: name="Intro"
        sections.append((name, "\n".join(lines[1:]).strip("\n")))
    return sections

def render_ingredients_section(content):
    sections=[]; heading=None; items=[]
    for raw in content.splitlines():
        stripped=raw.strip()
        if stripped.startswith("### "):
            if items: sections.append((heading,items))
            items=[]; heading=stripped[4:].strip()
        elif stripped and not stripped.startswith("#") and stripped[0] in "-*+":
            items.append(render_ingredient(stripped))
        elif stripped and not stripped.startswith("#") and items:
            items[-1]+=" "+stripped
    if items: sections.append((heading,items))
    out=[]
    for h,it in sections:
        if h is not None: out.append(f"### {h}")
        out.extend(it)
    return "\n".join(out)

def render_instructions_section(content):
    chunks=re.split(r"\n\s*\n", content.strip())
    out=[]
    for chunk in chunks:
        chunk=chunk.strip()
        if not chunk: continue
        step_matches=re.findall(r"^\s*(\d+)[\.\)]\s+(.*)$", chunk, re.M)
        if step_matches:
            for num,step_text in step_matches:
                out.append(f"### {_summarise_step(step_text)}")
                out.append(step_text.strip())
        else:
            out.append(chunk)
    return "\n".join(out)

def render_body(fm, body, scheduled=False, fallback_id=""):
    recipe_id=resolve_field(fm,"id") or resolve_field(fm,"recipe_id") or fallback_id
    title=resolve_field(fm,"title",recipe_id or "Recipe")
    category=resolve_field(fm,"category"); cuisine=resolve_field(fm,"cuisine")
    servings=resolve_field(fm,"servings"); difficulty=resolve_field(fm,"difficulty")
    tags=list_field(fm,"tags")
    tm=fm.get("time") if isinstance(fm.get("time"),dict) else {}
    prep=tm.get("prep_minutes"); cook=tm.get("cook_minutes"); total=tm.get("total_minutes")
    front=["---", f"recipe_id: {recipe_id}", f"title: {title}", "type: recipe"]
    if category: front.append(f"category: {category}")
    if cuisine: front.append(f"cuisine: {cuisine}")
    if servings: front.append(f"servings: {servings}")
    if prep: front.append(f"prep_time: {prep}")
    if cook: front.append(f"cook_time: {cook}")
    if total: front.append(f"total_time: {total}")
    if difficulty: front.append(f"difficulty: {difficulty}")
    front.append("tags:"); front.append("  - recipe")
    for tag in tags: front.append(f"  - {tag}")
    front.append("---")
    ing=instr=notes=""; misc=[]
    for name,content in split_sections(body):
        if name=="Ingredients": ing=content
        elif name=="Instructions": instr=content
        elif name=="Notes": notes=content
        elif name not in ("Title","Intro"): misc.append((name,content))
    out=["\n".join(front),"",BEGIN,"",f"# {title}","","> [!summary]"]
    summary=f"**{servings or '—'}** · **{prep or '—'} min prep** · **{cook or '—'} min cook**"
    out.append(f"> Servings: {summary}"); out.append(">")
    out.append(f"> {cuisine or '—'} · {difficulty or '—'}")
    out.extend(["", "## 🛒 Ingredients"])
    if ing:
        out.append(""); out.extend(render_ingredients_section(ing).splitlines())
    else: out.append("- *No ingredients listed.*")
    out.extend(["", "## 🍳 Method"])
    if instr:
        out.append(""); out.extend(render_instructions_section(instr).splitlines())
    else: out.append("- *No instructions listed.*")
    if notes:
        out.extend(["", "## 📝 Notes", ""]); out.extend(render_notes_section(notes).splitlines())
    for name,content in misc:
        if content.strip():
            out.extend(["", f"## {name}", ""]); out.extend(content.strip().splitlines())
    if scheduled:
        out.extend(["", "## 📅 This Week", "", "[[Meals/This Week]]", ""])
    out.append(END)
    return "\n".join(out)

def render_notes_section(content): return content.strip()

def render_index(recipes):
    body=[BEGIN,"","# 📚 Recipe Index","","Complete collection of recipes.",""]
    groups={}
    for r in recipes: groups.setdefault(r.cuisine or "Uncategorized",[]).append(r)
    for cuisine in sorted(groups,key=str.lower):
        body.append(f"### {cuisine}"); body.append("")
        for r in sorted(groups[cuisine],key=lambda x:x.title_low):
            body.append(f"- [[Recipes/{r.id}|{r.title}]]")
        body.append("")
    body.append(END); body.extend(["", "## 📝 Personal Notes", "", "*Add your personal notes here.*"])
    return "\n".join(body)

def personal_footer(user_tail=""):
    if user_tail.strip(): return "\n"+user_tail.strip("\n")+"\n"
    return "\n## 📝 Personal Notes\n\n*Add your personal cooking notes here.*\n"

# ---------------- Navigation pages (dashboard + by-category/cuisine/tag) ----------------

def display_label(label):
    """Capitalize first letter for a heading/link display label. Does not invent text."""
    label=label.strip()
    return label[:1].upper()+label[1:] if label else label

def _group_recipes(recipes, key_fn):
    groups={}
    for r in recipes:
        for k in key_fn(r):
            k=k.strip()
            if k: groups.setdefault(k,[]).append(r)
    return groups

def _sorted_recipes(group):
    return sorted(group, key=lambda x: x.title_low)

def _category_groups(recipes):  return _group_recipes(recipes, lambda r: list_field(r.fm,"category"))
def _cuisine_groups(recipes):   return _group_recipes(recipes, lambda r: list_field(r.fm,"cuisine"))
def _tag_groups(recipes):       return _group_recipes(recipes, lambda r: list_field(r.fm,"tags"))

def _by_page_body(title, subtitle, groups, page_name):
    body=[BEGIN,"",f"# {title}","",subtitle,""]
    for name in sorted(groups, key=str.lower):
        body.append(f"## {display_label(name)}"); body.append("")
        for r in _sorted_recipes(groups[name]):
            body.append(f"- [[Recipes/{r.id}|{r.title}]]")
        body.append("")
    body.append(END)
    return "\n".join(body)

def render_by_category(recipes):
    return _by_page_body("By Category","Browse recipes by category (meal/course/use).",
                          _category_groups(recipes),"_By Category.md")

def render_by_cuisine(recipes):
    return _by_page_body("By Cuisine","Browse recipes by cuisine (culinary tradition/region).",
                          _cuisine_groups(recipes),"_By Cuisine.md")

def render_by_tag(recipes):
    return _by_page_body("By Tag","Browse recipes by descriptive tag.",
                          _tag_groups(recipes),"_By Tag.md")

def render_dashboard(recipes):
    cats=_category_groups(recipes); cuss=_cuisine_groups(recipes); tgs=_tag_groups(recipes)
    body=[BEGIN,"",f"# \U0001f373 Recipe Library","",f"**{len(recipes)} recipes**",""]
    body.append("## Browse by Category"); body.append("")
    for name in sorted(cats, key=str.lower):
        body.append(f"- [[Recipes/_By Category#{display_label(name)}|{display_label(name)}]] ({len(cats[name])})")
    body.append("")
    body.append("## Browse by Cuisine"); body.append("")
    for name in sorted(cuss, key=str.lower):
        body.append(f"- [[Recipes/_By Cuisine#{display_label(name)}|{display_label(name)}]] ({len(cuss[name])})")
    body.append("")
    body.append("## Browse by Tag"); body.append("")
    for name in sorted(tgs, key=str.lower):
        body.append(f"- [[Recipes/_By Tag#{display_label(name)}|{display_label(name)}]] ({len(tgs[name])})")
    body.append("")
    body.append("## This Week"); body.append("")
    body.append("[[Meals/This Week]]"); body.append("")
    body.append("## All Recipes"); body.append("")
    body.append("[[Recipes/_Recipe Index|Full Recipe Index]]"); body.append("")
    body.append(END)
    return "\n".join(body)

_STALE_SCHEDULE_RE = re.compile(r"\n*## \U0001f4c5 This Week\n+\[\[Meals/This Week\]\]\n*", re.UNICODE)
def safe_write_recipe(path,new_generated):
    user_tail=""; existing=None
    if path.exists():
        try: existing=path.read_text(encoding="utf-8")
        except OSError: existing=None
    if existing is not None:
        idx=existing.find(END)
        if idx!=-1: user_tail=existing[idx+len(END):]
        # Strip the stale weekly schedule section so it doesn't accumulate
        user_tail=_STALE_SCHEDULE_RE.sub("\n", user_tail)
    final=new_generated+personal_footer(user_tail.strip())
    if existing==final: return False
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(final,encoding="utf-8")
    return True

def safe_write_index(path,new_index):
    if path.exists():
        try:
            if path.read_text(encoding="utf-8")==new_index: return False
        except OSError: pass
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(new_index,encoding="utf-8")
    return True

def safe_write_nav(path,new_generated):
    """Write a generated navigation page, preserving user-authored content after the END marker."""
    user_tail=""; existing=None
    if path.exists():
        try: existing=path.read_text(encoding="utf-8")
        except OSError: existing=None
    if existing is not None:
        idx=existing.find(END)
        if idx!=-1: user_tail=existing[idx+len(END):]
    final=new_generated+(("\n"+user_tail.strip()+"\n") if user_tail.strip() else "")
    if existing==final: return False
    path.parent.mkdir(parents=True,exist_ok=True); path.write_text(final,encoding="utf-8")
    return True

def main(argv=None):
    parser=argparse.ArgumentParser(description="Generate Obsidian recipe presentation pages")
    parser.add_argument("--recipes-dir",default=DEFAULT_RECIPES_DIR)
    parser.add_argument("--vault-dir",default=DEFAULT_VAULT_DIR)
    parser.add_argument("--plan-file",default=None)
    parser.add_argument("--dry-run",action="store_true")
    parser.add_argument("--print-schedule",action="store_true")
    args=parser.parse_args(argv)
    # Resolve runtime-contract defaults lazily (only when the arg was not
    # explicitly provided), so listed args still win.
    recipes_arg = args.recipes_dir if args.recipes_dir else _household_root() / "recipes"
    vault_arg = args.vault_dir if args.vault_dir else _obsidian_vault()
    recipes_dir=Path(recipes_arg).expanduser().resolve()
    vault_dir=Path(vault_arg).expanduser().resolve()
    plan_file=(Path(args.plan_file).expanduser().resolve() if args.plan_file else vault_dir/"Meals"/"This Week.md")
    if not recipes_dir.is_dir(): print(f"ERROR: recipes dir not found: {recipes_dir}",file=sys.stderr); return 2
    def in_vault(p):
        try: return p.resolve().is_relative_to(vault_dir)
        except AttributeError: return str(p.resolve()).startswith(str(vault_dir)+os.sep)
    print(f"Reading recipes from: {recipes_dir}")
    recipes=load_recipes(recipes_dir); print(f"Recipes parsed: {len(recipes)}")
    scheduled=scheduled_recipe_ids(plan_file)
    if args.print_schedule or args.dry_run:
        print(f"Scheduled recipe IDs from {plan_file}:")
        for rid in scheduled: print(f"  - {rid}")
    out_dir=vault_dir/"Recipes"
    if not args.dry_run: out_dir.mkdir(parents=True,exist_ok=True)
    created=updated=unchanged=0; changes=[]
    for r in recipes:
        if not r.fm: continue
        page_path=out_dir/f"{r.id}.md"
        new_generated=render_body(r.fm,r.body, r.id in scheduled, fallback_id=r.id)
        if not in_vault(page_path):
            print(f"  !! refusing to write outside vault: {page_path}",file=sys.stderr); continue
        existed=page_path.exists()
        if args.dry_run:
            existing=None
            if existed:
                try: existing=page_path.read_text(encoding="utf-8")
                except OSError: existing=None
            if existing is not None and existing==new_generated+personal_footer(): unchanged+=1
            elif existed: updated+=1; changes.append(("update",page_path))
            else: created+=1; changes.append(("create",page_path))
            continue
        changed=safe_write_recipe(page_path,new_generated)
        if changed:
            if existed: updated+=1; changes.append(("update",page_path))
            else: created+=1; changes.append(("create",page_path))
        else: unchanged+=1
    index_path=out_dir/"_Recipe Index.md"; new_index=render_index(recipes); index_changed=False
    if in_vault(index_path):
        if args.dry_run:
            existing=None
            if index_path.exists():
                try: existing=index_path.read_text(encoding="utf-8")
                except OSError: existing=None
            index_changed=existing!=new_index
            if index_changed: changes.append(("index",index_path))
        else: index_changed=safe_write_index(index_path,new_index)
    else: print(f"  !! refusing to write index outside vault: {index_path}",file=sys.stderr)
    # Navigation pages: dashboard + by-category/cuisine/tag
    nav = {
        "_Recipe Dashboard.md": render_dashboard(recipes),
        "_By Category.md": render_by_category(recipes),
        "_By Cuisine.md": render_by_cuisine(recipes),
        "_By Tag.md": render_by_tag(recipes),
    }
    nav_changed={}
    for name,content in nav.items():
        p=out_dir/name
        if not in_vault(p):
            print(f"  !! refusing to write {name} outside vault: {p}",file=sys.stderr); continue
        if args.dry_run:
            existing=None
            if p.exists():
                try: existing=p.read_text(encoding="utf-8")
                except OSError: existing=None
            nav_changed[name]=existing!=content
            if nav_changed[name]: changes.append(("nav",p))
        else:
            nav_changed[name]=safe_write_nav(p,content)
    print("\n--- Summary ---")
    print(f"recipes parsed: {len(recipes)}")
    print(f"pages created: {created}")
    print(f"pages updated: {updated}")
    print(f"pages unchanged: {unchanged}")
    print(f"index updated: {'yes' if index_changed else 'no'}")
    print(f"navigation pages updated: {sum(1 for v in nav_changed.values() if v)}")
    if args.dry_run:
        print("[dry-run] would touch:")
        for kind,p in changes: print(f"  {kind}: {p}")
    return 0

if __name__=="__main__":
    sys.exit(main())
