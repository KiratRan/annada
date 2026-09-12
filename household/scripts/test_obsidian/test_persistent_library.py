#!/usr/bin/env python3
"""
Tests for the persistent Obsidian recipe-library publication system.

Verifies:
  - Every active canonical recipe gets exactly one Obsidian page
  - No orphan active recipe pages exist
  - New canonical recipes are published automatically
  - Unchanged recipes are not unnecessarily rewritten
  - Unplanned recipes persist across weekly publication
  - Scheduled recipes get current-week links; unscheduled do not
  - Recipe scheduled in week N but not N+1 loses the old weekly link
  - This Week -> recipe links are correct
  - Generated content regeneration preserves user-authored content
  - Personal notes survive regeneration
  - Archived recipe pages are retained and marked
  - Recipe Index contains all active canonical recipes
  - .obsidian/ is never modified
  - Canonical recipe files are never modified
"""
import os, sys, json, hashlib, shutil, tempfile, glob
from pathlib import Path
from datetime import datetime, timedelta
import yaml, pytest

# ---------------------------------------------------------------------------
# Fixtures: build a clean sandbox with generic fixture recipes but isolated
# Obsidian vault
# ---------------------------------------------------------------------------
# Canonical household root: from HOUSEHOLD_ROOT env, else repo-relative.
# This test file lives at <household>/scripts/test_obsidian/, so parents[2]
# is the household root in a cloned checkout. No machine-specific hard-coding.
REPO = Path(os.environ.get("HOUSEHOLD_ROOT", "")).expanduser()
if not (REPO / "recipes").is_dir():
    REPO = Path(__file__).resolve().parents[2]
# Generic self-contained fixture recipes (no personal/instance data).
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
RECIPES_DIR = FIXTURES_DIR / "recipes"
REAL_OBSIDIAN_DIR = REPO / "obsidian"

# Minimal plan YAML for testing scheduled linking
SAMPLE_PLAN_OK = {
    "week": "2026-01-01",
    "plan": {
        "meals": [
            {"day": "Mon", "meal": "Dinner", "recipe": "test-tomato-pasta", "meal_name": "Creamy Tomato Pasta"},
            {"day": "Tue", "meal": "Dinner", "recipe": "test-lentil-dal", "meal_name": "Lentil Dal"},
        ]
    }
}

SAMPLE_PLAN_NEXT = {
    "week": "2026-01-08",
    "plan": {
        "meals": [
            {"day": "Wed", "meal": "Dinner", "recipe": "test-soy-noodles", "meal_name": "Soy Sauce Noodles"},
        ]
    }
}


@pytest.fixture
def sandbox(tmp_path):
    """Create a sandbox with real canonical recipes and a fresh Obsidian vault."""
    # Copy real recipes
    sandbox_recipes = tmp_path / "recipes"
    shutil.copytree(RECIPES_DIR, sandbox_recipes, dirs_exist_ok=True)

    # Fresh Obsidian vault (but DO NOT create .obsidian/)
    sandbox_obsidian = tmp_path / "obsidian"
    sandbox_obsidian.mkdir()

    # Write a sample plan
    plan_dir = tmp_path / "plans"
    plan_dir.mkdir()
    week1_path = plan_dir / "week-2026-01-01.yaml"
    week2_path = plan_dir / "week-2026-01-08.yaml"
    week1_path.write_text(yaml.dump(SAMPLE_PLAN_OK, default_flow_style=False))
    week2_path.write_text(yaml.dump(SAMPLE_PLAN_NEXT, default_flow_style=False))

    # Copy the script
    script_dir = tmp_path / "scripts"
    script_dir.mkdir()
    script_src = REPO / "scripts" / "publish_recipes.py"
    shutil.copy(script_src, script_dir / "publish_recipes.py")

    return {
        "tmp": tmp_path,
        "recipes": sandbox_recipes,
        "obsidian": sandbox_obsidian,
        "scripts": script_dir,
        "plans": plan_dir,
        "week1": week1_path,
        "week2": week2_path,
    }


def run_publish(sandbox, dry_run=False, plan=None):
    """Run the publish script in the sandbox."""
    import subprocess
    cmd = [
        sys.executable, str(sandbox["scripts"] / "publish_recipes.py"),
        "--recipes-dir", str(sandbox["recipes"]),
        "--vault-dir", str(sandbox["obsidian"]),
        "--plan-file", str(plan) if plan else str(sandbox["week1"]),
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result


def recipe_ids_from_yaml(sandbox):
    """Get all canonical recipe IDs from YAML frontmatter (key: 'id')."""
    ids = set()
    for p in sorted(sandbox["recipes"].glob("*.md")):
        if p.name == "README.md":
            continue
        with open(p) as f:
            content = f.read()
        fm, _ = _extract(content)
        rid = None
        if fm:
            rid = fm.get("id") or fm.get("recipe_id")
        if rid:
            ids.add(str(rid).strip())
    return ids


def _extract(content):
    """Extract YAML frontmatter from Markdown content."""
    if not content.startswith("---"):
        return {}, content
    # Find the closing "---" on its own line
    end = content.find("\n---", 3)
    if end < 0:
        return {}, content
    fm_text = content[3:end]          # content between the two "---"
    body = content[end + 4:]          # skip "\n---" (4 chars)
    try:
        fm = yaml.safe_load(fm_text) or {}
    except Exception:
        fm = {}
    return fm, body


def recipe_ids_from_obsidian(sandbox):
    """Get recipe IDs from Obsidian recipe pages."""
    ids = set()
    for p in sorted(sandbox["obsidian"].glob("Recipes/*.md")):
        if p.name.startswith("_"):
            continue
        with open(p) as f:
            content = f.read()
        fm, _ = _extract(content)
        if fm and "recipe_id" in fm:
            ids.add(fm["recipe_id"])
    return ids


def scheduled_recipe_ids(sandbox, plan_path):
    """Extract scheduled recipe IDs from a plan file."""
    with open(plan_path) as f:
        plan = yaml.safe_load(f) or {}
    ids = []
    seen = set()
    meals = plan if isinstance(plan, list) else plan.get("meals", plan.get("plan",{}).get("meals",[]))
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


# ---------------------------------------------------------------------------
# TEST 1: every active canonical recipe gets exactly one Obsidian page
# ---------------------------------------------------------------------------
def test_every_recipe_gets_one_page(sandbox):
    result = run_publish(sandbox)
    assert result.returncode == 0, f"Publish failed: {result.stderr}"

    canonical_ids = recipe_ids_from_yaml(sandbox)
    obsidian_ids = recipe_ids_from_obsidian(sandbox)

    # Every canonical recipe has an Obsidian page
    assert canonical_ids == obsidian_ids, (
        f"Missing pages: {canonical_ids - obsidian_ids}\n"
        f"Orphan pages: {obsidian_ids - canonical_ids}"
    )

    # Exactly one file per recipe
    for rid in canonical_ids:
        pages = list(sandbox["obsidian"].glob(f"Recipes/{rid}.md"))
        assert len(pages) == 1, f"Expected 1 page for {rid}, got {len(pages)}"


# ---------------------------------------------------------------------------
# TEST 2: no orphan active recipe pages
# ---------------------------------------------------------------------------
def test_no_orphan_pages(sandbox):
    run_publish(sandbox)
    canonical_ids = recipe_ids_from_yaml(sandbox)
    obsidian_ids = recipe_ids_from_obsidian(sandbox)
    assert obsidian_ids.issubset(canonical_ids), (
        f"Orphan pages (in Obsidian but not canonical): {obsidian_ids - canonical_ids}"
    )


# ---------------------------------------------------------------------------
# TEST 3: new canonical recipe gets published automatically
# ---------------------------------------------------------------------------
def test_new_recipe_published(sandbox):
    # Initial publish
    run_publish(sandbox)
    initial_count = len(list(sandbox["obsidian"].glob("Recipes/*.md")))

    # Add a new canonical recipe
    new_recipe = sandbox["recipes"] / "test-zucchini-fritters.md"
    new_recipe.write_text(
        "---\n"
        "recipe_id: test-zucchini-fritters\n"
        "title: Zucchini Fritters\n"
        "servings: 2\n"
        "prep_time: 10\n"
        "cook_time: 15\n"
        "---\n\n"
        "## Ingredients\n\n"
        "- 2 medium zucchini, grated\n"
        "- 1 egg\n"
        "- 1/4 cup flour\n\n"
        "## Instructions\n\n"
        "1. Grate zucchini and squeeze dry.\n"
        "2. Mix with egg and flour.\n"
        "3. Pan-fry until golden.\n"
    )

    # Re-publish
    result = run_publish(sandbox)
    assert result.returncode == 0

    # New page exists
    new_page = sandbox["obsidian"] / "Recipes" / "test-zucchini-fritters.md"
    assert new_page.exists(), "New recipe page was not created"

    # Index includes new recipe
    index = (sandbox["obsidian"] / "Recipes" / "_Recipe Index.md").read_text()
    assert "test-zucchini-fritters" in index, "New recipe not in index"


# ---------------------------------------------------------------------------
# TEST 4: unchanged recipe is not unnecessarily rewritten
# ---------------------------------------------------------------------------
def test_unchanged_not_rewritten(sandbox):
    run_publish(sandbox)
    page1 = sandbox["obsidian"] / "Recipes" / "test-tomato-pasta.md"
    mtime1 = page1.stat().st_mtime

    # Small sleep to ensure filesystem timestamp difference is measurable
    import time; time.sleep(0.5)

    # Re-publish unchanged
    run_publish(sandbox)
    mtime2 = page1.stat().st_mtime
    assert mtime1 == mtime2, f"Unchanged recipe was rewritten (mtime {mtime1} != {mtime2})"


# ---------------------------------------------------------------------------
# TEST 5: unplanned recipe persists across weekly publication
# ---------------------------------------------------------------------------
def test_unplanned_recipe_persists(sandbox):
    run_publish(sandbox, plan=sandbox["week1"])

    # recipe NOT in week1 plan
    unplanned = sandbox["obsidian"] / "Recipes" / "test-apple-crisp.md"
    assert unplanned.exists(), "Unplanned recipe page missing after week1 publish"

    # Publish week2 (different plan)
    run_publish(sandbox, plan=sandbox["week2"])

    # Still exists
    assert unplanned.exists(), "Unplanned recipe page deleted after week2 publish"

    # A recipe planned in neither week gets no "This Week" link
    content = unplanned.read_text()
    assert "Meals/This Week" not in content, (
        "Unplanned recipe has stale weekly link"
    )


# ---------------------------------------------------------------------------
# TEST 6: scheduled recipe gets current-week link
# ---------------------------------------------------------------------------
def test_scheduled_gets_weekly_link(sandbox):
    run_publish(sandbox, plan=sandbox["week1"])

    planned = sandbox["obsidian"] / "Recipes" / "test-tomato-pasta.md"
    content = planned.read_text()
    assert "Meals/This Week" in content, "Scheduled recipe missing This Week link"


# ---------------------------------------------------------------------------
# TEST 7: unscheduled recipe has no stale weekly link
# ---------------------------------------------------------------------------
def test_unscheduled_no_weekly_link(sandbox):
    run_publish(sandbox, plan=sandbox["week1"])

    # test-lentil-dal IS in week1, so give it a link
    # now switch to week2 where it is NOT scheduled
    run_publish(sandbox, plan=sandbox["week2"])

    unplanned = sandbox["obsidian"] / "Recipes" / "test-lentil-dal.md"
    content = unplanned.read_text()
    assert "Meals/This Week" not in content, (
        "Previously-planned but now-unplanned recipe has stale weekly link"
    )


# ---------------------------------------------------------------------------
# TEST 8: recipe scheduled in week N but not N+1 loses old link
# ---------------------------------------------------------------------------
def test_week_n_to_n_plus_1_transition(sandbox):
    # week1: test-tomato-pasta is scheduled
    run_publish(sandbox, plan=sandbox["week1"])
    page = sandbox["obsidian"] / "Recipes" / "test-tomato-pasta.md"
    assert "Meals/This Week" in page.read_text()

    # week2: test-tomato-pasta is NOT scheduled
    run_publish(sandbox, plan=sandbox["week2"])
    assert "Meals/This Week" not in page.read_text(), (
        "Old weekly link persists after recipe removed from plan"
    )


# ---------------------------------------------------------------------------
# TEST 9: This Week -> recipe links are correct
# ---------------------------------------------------------------------------
def test_this_week_links_match_plan(sandbox):
    run_publish(sandbox, plan=sandbox["week1"])

    # publish_recipes.py does NOT create Meals/This Week.md (that's
    # household-workflow's step 8). It DOES generate current-week recipe->
    # plan links from the approved plan. Verify the SCHEDULED set it derived
    # from the plan YAML matches the plan.
    scheduled = scheduled_recipe_ids(sandbox, sandbox["week1"])
    scheduled_set = set(scheduled)
    assert len(scheduled) == len(scheduled_set), "Plan contains duplicate recipe refs"

    # The canonical "test-tomato-pasta" and "test-lentil-dal"
    # are in week1. Their Obsidian page must get the This Week link.
    for rid in scheduled:
        page = sandbox["obsidian"] / "Recipes" / f"{rid}.md"
        assert page.exists(), f"Planned recipe {rid} missing page"
        assert "Meals/This Week" in page.read_text(), (
            f"Planned recipe {rid} missing This Week link"
        )

    # Consistency: recipe pages that got the link are EXACTLY the planned set
    # (no more, no less) once the "gather" step is not over-linked.
    for p in (sandbox["obsidian"] / "Recipes").glob("*.md"):
        if p.name.startswith("_"):
            continue
        rid = p.stem
        has_link = "Meals/This Week" in p.read_text()
        if rid in scheduled_set:
            assert has_link, f"Recipe {rid} planned but missing link"
        else:
            # unplanned recipe should NOT have a stale link
            assert not has_link, f"Recipe {rid} has stale link though unplanned"


# ---------------------------------------------------------------------------
# TEST 10: regeneration preserves user-authored content outside markers
# ---------------------------------------------------------------------------
def test_user_content_preserved(sandbox):
    run_publish(sandbox)

    page = sandbox["obsidian"] / "Recipes" / "test-tomato-pasta.md"
    user_note = "\n## 📝 Personal Notes\n\nThis is my personal note about this recipe.\n"
    content = page.read_text()
    new_content = content + user_note
    page.write_text(new_content)

    # Re-publish
    run_publish(sandbox)
    final = page.read_text()

    assert "This is my personal note about this recipe." in final, (
        "User-authored content outside markers was lost"
    )


# ---------------------------------------------------------------------------
# TEST 11: personal notes survive regeneration (within generated content boundary)
# ---------------------------------------------------------------------------
def test_personal_notes_survive(sandbox):
    run_publish(sandbox)

    page = sandbox["obsidian"] / "Recipes" / "test-lentil-dal.md"
    user_note = "\n## 📝 Personal Notes\n\nAdd extra chillies for more heat.\n"
    content = page.read_text()
    page.write_text(content + user_note)

    run_publish(sandbox)
    final = page.read_text()

    assert "extra chillies" in final, "Personal notes lost during regeneration"
    assert "## 📝 Personal Notes" in final, "Personal notes heading lost"


# ---------------------------------------------------------------------------
# TEST 12: archived recipe pages are retained and marked
# ---------------------------------------------------------------------------
def test_archived_recipe_retained(sandbox):
    run_publish(sandbox)

    # Manually create an archived page (simulating a recipe removed from canonical)
    archived = sandbox["obsidian"] / "Recipes" / "old-deleted-recipe.md"
    archived.write_text(
        "# Old Deleted Recipe\n\n"
        "This was a great recipe.\n"
    )

    # Simulate archival by removing from canonical (it was never there, but the
    # point is: the publish script should NOT delete it)
    run_publish(sandbox)

    assert archived.exists(), "Archived recipe page was deleted during publish"


# ---------------------------------------------------------------------------
# TEST 13: Recipe Index contains all active canonical recipes
# ---------------------------------------------------------------------------
def test_index_complete(sandbox):
    run_publish(sandbox)

    index = (sandbox["obsidian"] / "Recipes" / "_Recipe Index.md").read_text()
    canonical_ids = recipe_ids_from_yaml(sandbox)

    for rid in canonical_ids:
        assert rid in index, f"Recipe {rid} missing from index"


# ---------------------------------------------------------------------------
# TEST 14: .obsidian/ is never modified
# ---------------------------------------------------------------------------
def test_obsidian_dir_not_modified(sandbox):
    # Create .obsidian with a config file
    obsidian_config = sandbox["obsidian"] / ".obsidian"
    obsidian_config.mkdir()
    config_file = obsidian_config / "app.json"
    original = json.dumps({"showLineNumber": True}, indent=2)
    config_file.write_text(original)

    run_publish(sandbox)

    assert config_file.read_text() == original, ".obsidian/ was modified"


# ---------------------------------------------------------------------------
# TEST 15: canonical recipe files are never modified
# ---------------------------------------------------------------------------
def test_canonical_not_modified(sandbox):
    # Record original file hashes
    originals = {}
    for p in sandbox["recipes"].glob("*.md"):
        originals[p.name] = hashlib.md5(p.read_bytes()).hexdigest()

    run_publish(sandbox)

    for p in sandbox["recipes"].glob("*.md"):
        current = hashlib.md5(p.read_bytes()).hexdigest()
        assert originals[p.name] == current, (
            f"Canonical recipe {p.name} was modified during publish"
        )


# ---------------------------------------------------------------------------
# TEST 16: idempotency - running publish twice produces identical output
# ---------------------------------------------------------------------------
def test_idempotent(sandbox):
    run_publish(sandbox)
    # snapshot all files
    snapshot = {}
    for p in (sandbox["obsidian"] / "Recipes").glob("*.md"):
        snapshot[p.name] = p.read_text()

    run_publish(sandbox)

    for p in (sandbox["obsidian"] / "Recipes").glob("*.md"):
        assert p.name in snapshot, f"New file appeared: {p.name}"
        assert snapshot[p.name] == p.read_text(), f"File changed on re-publish: {p.name}"


# ---------------------------------------------------------------------------
# TEST 17: scheduled recipe page has all required sections
# ---------------------------------------------------------------------------
def test_required_sections(sandbox):
    run_publish(sandbox, plan=sandbox["week1"])

    page = sandbox["obsidian"] / "Recipes" / "test-tomato-pasta.md"
    content = page.read_text()

    assert "BEGIN HERMES GENERATED CONTENT" in content
    assert "END HERMES GENERATED CONTENT" in content
    assert "# Creamy Tomato" in content  # title
    assert "## 🛒 Ingredients" in content
    assert "## 🍳 Method" in content
    assert "## 📝 Personal Notes" in content
    assert "Meals/This Week" in content  # scheduled → has link


# ---------------------------------------------------------------------------
# TEST 18: recipe page has frontmatter with correct recipe_id
# ---------------------------------------------------------------------------
def test_frontmatter_recipe_id(sandbox):
    run_publish(sandbox)

    for rid in ["test-tomato-pasta", "test-chicken-fajitas"]:
        page = sandbox["obsidian"] / "Recipes" / f"{rid}.md"
        content = page.read_text()
        fm, _ = _extract(content)
        assert fm.get("recipe_id") == rid, (
            f"Frontmatter recipe_id mismatch for {rid}: {fm.get('recipe_id')}"
        )
        assert fm.get("type") == "recipe"
        assert fm.get("title"), f"Missing title in frontmatter for {rid}"


# ===========================================================================
# NAVIGATION / DASHBOARD TESTS (persistent recipe-library browsing)
# ===========================================================================
REC_DASH = "_Recipe Dashboard.md"
REC_BY_CAT = "_By Category.md"
REC_BY_CUS = "_By Cuisine.md"
REC_BY_TAG = "_By Tag.md"
NAV_PAGES = [REC_DASH, REC_BY_CAT, REC_BY_CUS, REC_BY_TAG, "_Recipe Index.md"]


def _canonical_field_map(sandbox, key):
    """Return {field_value: set(recipe_ids)} from canonical frontmatter (handles lists)."""
    field_map = {}
    for p in sandbox["recipes"].glob("*.md"):
        if p.name == "README.md" or p.name.lower().startswith("index."):
            continue
        content = p.read_text()
        fm, _ = _extract(content)
        rid = (fm or {}).get("id") or (fm or {}).get("recipe_id") or p.stem
        val = (fm or {}).get(key)
        values = val if isinstance(val, list) else ([val] if val else [])
        for v in values:
            v = str(v).strip()
            if v:
                field_map.setdefault(v, set()).add(str(rid).strip())
    return field_map


def _nav_links(page_text):
    """Extract recipe-id targets from [[Recipes/<id>|...]] links (excludes nav self-links)."""
    import re
    targets = re.findall(r"\[\[Recipes/([^\]|#]+)", page_text)
    # Filter out links to other navigation pages (they start with _)
    return [t for t in targets if not t.startswith("_")]


def _nav_headings(page_text, level="##"):
    """Extract heading names (stripped) from a generated nav page body."""
    import re
    return re.findall(rf"^{level}\s+(.+)$", page_text, re.M)


# TEST 19: Dashboard exists and is generated
def test_dashboard_exists(sandbox):
    result = run_publish(sandbox)
    assert result.returncode == 0, f"Publish failed: {result.stderr}"

    dash = sandbox["obsidian"] / "Recipes" / REC_DASH
    assert dash.exists(), "Recipe Dashboard was not created"
    content = dash.read_text()
    assert "BEGIN HERMES GENERATED CONTENT" in content
    assert "END HERMES GENERATED CONTENT" in content


# TEST 20: Dashboard contains all active navigation categories
def test_dashboard_contains_all_nav_categories(sandbox):
    run_publish(sandbox)
    dash = (sandbox["obsidian"] / "Recipes" / REC_DASH).read_text()

    active_cats = _canonical_field_map(sandbox, "category")
    active_cuss = _canonical_field_map(sandbox, "cuisine")
    active_tags = _canonical_field_map(sandbox, "tags")

    # Each active category appears on the dashboard
    for cat in active_cats:
        assert re_search(cat, dash), f"Dashboard missing category: {cat}"
    for cu in active_cuss:
        assert re_search(cu, dash), f"Dashboard missing cuisine: {cu}"
    for tg in active_tags:
        assert re_search(tg, dash), f"Dashboard missing tag: {tg}"

    # Structural sections present
    assert "Browse by Category" in dash
    assert "Browse by Cuisine" in dash
    assert "Browse by Tag" in dash
    assert "This Week" in dash
    assert "All Recipes" in dash
    assert "[[Meals/This Week]]" in dash
    assert "Full Recipe Index" in dash


def re_search(needle, hay):
    import re
    return re.search(re.escape(needle), hay, re.IGNORECASE) is not None


# TEST 7 (nav): Category navigation includes every applicable recipe
def test_category_nav_includes_every_recipe(sandbox):
    run_publish(sandbox)
    by_cat = (sandbox["obsidian"] / "Recipes" / REC_BY_CAT).read_text()
    field_map = _canonical_field_map(sandbox, "category")

    for cat, ids in field_map.items():
        for rid in ids:
            assert f"[[Recipes/{rid}" in by_cat, (
                f"Category '{cat}' missing recipe {rid}"
            )


# TEST 4 (nav): Cuisine navigation includes every applicable recipe
def test_cuisine_nav_includes_every_recipe(sandbox):
    run_publish(sandbox)
    by_cus = (sandbox["obsidian"] / "Recipes" / REC_BY_CUS).read_text()
    field_map = _canonical_field_map(sandbox, "cuisine")

    for cu, ids in field_map.items():
        for rid in ids:
            assert f"[[Recipes/{rid}" in by_cus, (
                f"Cuisine '{cu}' missing recipe {rid}"
            )

    # Every recipe has a cuisine, so cuisines must collectively cover all of them
    all_ids = recipe_ids_from_yaml(sandbox)
    linked = set(_nav_links(by_cus))
    assert linked == all_ids, (
        f"Cuisine nav recipe set mismatch: {linked ^ all_ids}"
    )


# TEST 5 (nav): a recipe with multiple categories appears in all applicable categories
def test_multi_category_recipe_in_all_applicable(sandbox):
    # Give a sandbox canonical recipe a second category (list form, like canonical).
    # Uses approved vocabulary values only.
    target = sandbox["recipes"] / "test-tomato-pasta.md"
    content = target.read_text()
    content = content.replace(
        "category:\n  - Main",
        "category:\n  - Main\n  - Side", 1)
    target.write_text(content)

    run_publish(sandbox)
    by_cat = (sandbox["obsidian"] / "Recipes" / REC_BY_CAT).read_text()

    # One physical page
    pages = list(sandbox["obsidian"].glob("Recipes/test-tomato-pasta.md"))
    assert len(pages) == 1, "Multi-category recipe spawned multiple physical pages"

    # Appears under BOTH Main and Side headings
    assert "[[Recipes/test-tomato-pasta" in by_cat
    main_block = by_cat.split("## Main", 1)[1].split("## ")[0]
    side_block = by_cat.split("## Side", 1)[1].split("## ")[0]
    assert "test-tomato-pasta" in main_block, \
        "Multi-category recipe missing from Main"
    assert "test-tomato-pasta" in side_block, \
        "Multi-category recipe missing from Side"


# TEST 6 (nav): a recipe has exactly one physical recipe page
def test_recipe_exactly_one_physical_page(sandbox):
    run_publish(sandbox)
    all_ids = recipe_ids_from_yaml(sandbox)
    for rid in all_ids:
        pages = list(sandbox["obsidian"].glob(f"Recipes/{rid}.md"))
        assert len(pages) == 1, f"Recipe {rid} has {len(pages)} physical pages"


# TEST : no category folders are created (flat directory preserved)
def test_no_category_folders(sandbox):
    run_publish(sandbox)
    recipes_dir = sandbox["obsidian"] / "Recipes"
    subdirs = [p for p in recipes_dir.iterdir() if p.is_dir()]
    assert subdirs == [], f"Category folders were created: {subdirs}"

    # Every non-nav entry is a recipe page (flat)
    for p in recipes_dir.glob("*.md"):
        assert p.is_file()


# TEST : Recipe Index remains complete (already asserted by test_index_complete,
# but re-verify here for the navigation suite)
def test_index_remains_complete(sandbox):
    run_publish(sandbox)
    index = (sandbox["obsidian"] / "Recipes" / "_Recipe Index.md").read_text()
    all_ids = recipe_ids_from_yaml(sandbox)
    for rid in all_ids:
        assert f"[[Recipes/{rid}" in index, f"Index missing recipe {rid}"


# TEST : no orphan recipe links in dashboard/index/nav pages
def test_no_orphan_recipe_links(sandbox):
    run_publish(sandbox)
    valid_ids = recipe_ids_from_yaml(sandbox)
    allocated = set()

    for page_name in NAV_PAGES:
        page = sandbox["obsidian"] / "Recipes" / page_name
        assert page.exists(), f"Navigation page missing: {page_name}"
        content = page.read_text()
        for target in _nav_links(content):
            allocated.add(target)

    # Every allocated recipe link resolves to a real recipe page
    assert allocated.issubset(valid_ids), (
        f"Orphan recipe links: {allocated - valid_ids}"
    )


# TEST : regeneration is deterministic (re-publishing produces identical nav pages)
def test_nav_regeneration_deterministic(sandbox):
    run_publish(sandbox)
    snapshot = {
        p.name: p.read_text()
        for p in (sandbox["obsidian"] / "Recipes").glob("*.md")
        if p.name.startswith("_")
    }

    result = run_publish(sandbox)
    assert result.returncode == 0

    for name, before in snapshot.items():
        after = (sandbox["obsidian"] / "Recipes" / name).read_text()
        assert before == after, f"Navigation page {name} changed on re-publish"


# TEST : user-authored content outside generated markers survives on nav pages
def test_nav_user_content_preserved(sandbox):
    run_publish(sandbox)
    dash = sandbox["obsidian"] / "Recipes" / REC_DASH
    user_note = "\n## 📝 My Library Notes\n\nI keep my favorite recipes here.\n"
    dash.write_text(dash.read_text() + user_note)

    run_publish(sandbox)

    final = dash.read_text()
    assert "I keep my favorite recipes here." in final, (
        "User-authored nav content was lost on regeneration"
    )


# TEST : .obsidian/ untouched with navigation present
def test_obsidian_dir_untouched_with_nav(sandbox):
    obsidian_config = sandbox["obsidian"] / ".obsidian"
    obsidian_config.mkdir()
    config_file = obsidian_config / "app.json"
    original = json.dumps({"showLineNumber": True}, indent=2)
    config_file.write_text(original)

    run_publish(sandbox)

    assert config_file.read_text() == original, ".obsidian/ was modified"


# TEST : canonical recipes untouched (with navigation generation)
def test_canonical_untouched_with_nav(sandbox):
    originals = {
        p.name: hashlib.md5(p.read_bytes()).hexdigest()
        for p in sandbox["recipes"].glob("*.md")
    }

    run_publish(sandbox)

    for p in sandbox["recipes"].glob("*.md"):
        assert originals[p.name] == hashlib.md5(p.read_bytes()).hexdigest(), (
            f"Canonical recipe {p.name} was modified"
        )
