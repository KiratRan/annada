#!/usr/bin/env python3
"""Deterministic ingredient identity matching for the household pantry.

Stage 2 — ingredient identity layer.

Answers: "Does this pantry item represent the same underlying ingredient
as this recipe ingredient?"

Does NOT answer: "Do we have enough of it?"
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALIASES_PATH = Path(__file__).parent / "ingredient-aliases.yaml"

UNITS = frozenset({
    "tsp", "teaspoon", "teaspoons",
    "tbsp", "tablespoon", "tablespoons", "tbs",
    "cup", "cups",
    "oz", "ounce", "ounces",
    "lb", "lbs", "pound", "pounds",
    "kg", "kilogram", "kilograms",
    "g", "gram", "grams", "gm",
    "ml", "milliliter", "milliliters",
    "l", "liter", "liters",
    "pinch", "dash", "clove", "cloves",
    "can", "cans", "bunch", "bunches",
    "head", "heads", "slice", "slices",
    "pod", "pods",
    "inch", "inches",
})

PREP_NEUTRAL = frozenset({
    "diced", "minced", "sliced", "chopped",
    "grated", "shredded", "julienned", "dice",
    "thinly", "finely", "roughly", "freshly",
    # prep / condition descriptors that do NOT affect shopping identity
    "soaked", "beaten", "divided", "peeled", "cut", "torn",
    "halved", "halves", "quartered", "crushed", "trimmed",
    "segments", "links", "piece", "pieces", "chunks",
    "skin", "more",
    # usage descriptors that never name an ingredient
    "garnish", "cubed", "frying",
    # quantity/tail annotations that never belong in the identity.
    # NOTE: "juice" is intentionally NOT here (lemon juice / tomato juice are
    # their own ingredients); only the prep "juiced" and the modifier "juices"
    # ("diced tomatoes, with juices") are stripped.
    "juiced", "juices",
    "stems", "stem",
    "cracked",
    "needed", "desired",
    "taste",
    "serving",
    "uncooked",
    "sprig", "sprigs",
    "spice",
    "as",
})

FORM_SIGNIFICANT = frozenset({
    "fresh", "whole", "dried", "ground", "powder", "paste",
    "raw", "frozen", "canned", "pickled", "fermented",
    "sweet", "sour", "bitter", "ripe",
    "skin", "boneless", "bone-in", "bone", "skinless",
    "seeds", "seed",
    "leaves", "leaf",
    "green", "red", "black", "white", "yellow", "brown", "pink",
    "light", "dark",
    "kosher", "sea", "table",
    "unsalted", "salted",
    "full-fat", "low-fat", "non-fat", "skim",
    "ground",
})

SIZE_NEUTRAL = frozenset({
    "small", "medium", "large",
    "thin", "thick",
    "tiny", "jumbo",
})

STOP_WORDS = frozenset({"and", "or", "to", "of", "with", "for", "about",
    "into", "if", "in"})

_NUM_RE = re.compile(r"^\d+(\.\d+)?(/\d+(\.\d+)?)?$")

# Spoken quantity words that never belong in a shopping identity
# ("a pinch", "one onion", "plus more").  "one" also covers mixed-number
# phrasings written as words.  "half" is deliberately excluded so that
# "half and half" (a dairy product) survives as an identity.
_QUANTITY_WORDS = frozenset({"a", "an", "one", "plus", "quarter"})

# Numeric range like 2-3 / 3-4 / 1-1/2, and measurement such as 1/4-inch,
# 2-inch.  Accept en/em dashes too.
_RANGE_RE = re.compile(r"^\d+(\.\d+)?(/\d+)?[-\u2013\u2014]\d+(\.\d+)?(/\d+)?$")
_MEASURE_RE = re.compile(r"^\d+(\.\d+)?(/\d+)?[-\u2013\u2014][a-z]+$")

# Unicode vulgar-fraction glyphs recognized as quantity/fraction tokens.  Map
# each glyph to its ASCII equivalent so a mixed number like "1 ½" is one value
# and never leaks a stray glyph into the ingredient identity.
_UNICODE_FRACTIONS = {
    "½": "1/2", "¼": "1/4", "¾": "3/4",
    "⅓": "1/3", "⅔": "2/3", "⅛": "1/8",
}

# Curly/double inch or prime marks (" 1/8” pieces ", "1.5″") denote a
# measurement belonging to a preparation instruction, never an ingredient
# quantity or identity.
_INCH_MARK_MEASURE_RE = re.compile(
    r"^\d+(\.\d+)?(/\d+)?[\u201d\u2033\u201c\"]$"
)
_FRAC_GLYPH = "[%s]" % "".join(_UNICODE_FRACTIONS)
_GLYPH_MEASURE_RE = re.compile(rf"^{_FRAC_GLYPH}(-\d+|[-\u2013\u2014][a-z]+)?$")

# A trailing count like "1." / "2." ("Fried egg, 1.") is a quantity, not
# identity.  This catches the full-stopped count form.
_COUNT_PERIOD_RE = re.compile(r"^\d+\.$")

# Markdown link heads: "7[makrut lime leaves](https://...)"" carries the
# quantity immediately before the "[label]".  Recover the leading quantity and
# the plain label, dropping the URL and link brackets entirely.
_MARKDOWN_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")

# Fused quantity directly attached to the name/unit head:
#   "1jalapeño", "⅔cup mayonnaise", "3guajillochiles", "500g", "2½ cups"
# Split into "<qty> <name|unit>" so the leading quantity is recoverable and
# never glues onto the ingredient identity.  The second group must be a letter
# or another vulgar fraction (so "2½" -> "2 ½"), never a digit/dash (so
# "2-3", "0.5", "1/2", "1/8”" are untouched).
_FUSED_PREFIX_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:/\d+)?|[½¼¾⅓⅔⅛])([A-Za-zà-ÿÀ-Ý]|[½¼¾⅓⅔⅛])"
)

# Split an abbreviation period that glues onto the next word: "Tbs.rock salt"
# -> "Tbs. rock salt".  Only for known unit abbreviations, so sentence periods
# in ingredient text are left alone.
_ABBREV_DOT_RE = re.compile(
    r"\b(Tbs|Tbsp|tbs|tbsp|Tbl|tbl|oz|lb|lbs|g|gm|kg|ml|cm|in)\.(?=[A-Za-z])"
)


def _strip_markdown(text: str) -> str:
    return _MARKDOWN_RE.sub(lambda m: f" {m.group(1)}", text)


def _split_fused_quantity(text: str) -> str:
    return _FUSED_PREFIX_RE.sub(r"\1 \2", text)


def _prep_line(raw: str) -> str:
    """Shared pre-processing for both normalize() and parse_ingredient_line().

    Recovers Markdown-link ingredient heads, splits fused quantity/unit/name
    tokens (and abbreviation periods), so the leading quantity is cleanly
    extractable and never glued onto the identity.
    """
    text = _strip_markdown(raw)
    text = _split_fused_quantity(text)
    text = _ABBREV_DOT_RE.sub(lambda m: m.group(1) + ". ", text)
    return text


def _is_quantity_token(t: str) -> bool:
    """True for a number, a numeric range (2-3), a measurement (1/4-inch),
    a Unicode vulgar fraction (½, ¾), or a measurement with a curly inch/prime
    mark (1/8”).  These are quantity/range/unit expressions and never belong
    in the shopping identity.
    """
    return bool(
        _NUM_RE.match(t)
        or _RANGE_RE.match(t)
        or _MEASURE_RE.match(t)
        or _INCH_MARK_MEASURE_RE.match(t)
        or _GLYPH_MEASURE_RE.match(t)
        or t in _UNICODE_FRACTIONS
    )


def _frac_value(t: str) -> str | None:
    """ASCII value of a Unicode vulgar-fraction token (½→'1/2'), else None."""
    return _UNICODE_FRACTIONS.get(t)


_CHILI_CANON = "chilli"
# All orthographic variants of the chili family that represent the same
# fresh/chili ingredient head resolve to the canonical spelling "chilli".
# Covers the singulars (chili/chilli/chile), the "chilly" mis-spelling, and
# the plural forms (chilies/chillies/chiles).
_CHILI_VARIANTS = {
    "chili": _CHILI_CANON,
    "chilli": _CHILI_CANON,
    "chile": _CHILI_CANON,
    "chilies": _CHILI_CANON,
    "chillies": _CHILI_CANON,
    "chiles": _CHILI_CANON,
    "chilly": _CHILI_CANON,
}

# Heads for which "ground" is treated as a shopping-neutral modifier (the
# household treats ground pepper and whole pepper as the same pantry item).
# Ground is otherwise a form distinction and is PRESERVED (ground ginger !=
# ginger, ground turmeric != turmeric, ground cumin != cumin seeds).
GROUND_NEUTRAL_HEADS = frozenset({"pepper"})

GENERIC_AMBIGUOUS_HEADS = frozenset({"onion", "oil", "tomato"})

# Tomato PRODUCT FORMS the shopper distinguishes on the shelf (canned diced,
# crushed).  These must NOT collapse to a generic "tomato" identity because
# they are not freely substitutable for one another or for whole tomatoes.
_TOMATO_HEADS = frozenset({"tomato"})
_TOMATO_FORM_KEEP = frozenset({"diced", "crushed"})

# Narrow, household-confirmed equivalences: "ground <spice>" == "<spice> powder"
# for these ground spices.  This is NOT a broad rule — fresh/whole forms
# (fresh ginger, cumin seeds) remain distinct and are handled elsewhere.
_SPICE_GROUND_TO_POWDER = frozenset({"turmeric", "cumin", "coriander"})

# Parenthetical FORM information that is part of the shopping identity and
# must be retained (macaroni (elbow) == elbow macaroni).
_PAREN_FORM_KEEP = frozenset({"elbow"})

# Heads for which a "default" descriptor is shopping-neutral.
_YOGURT_HEADS = frozenset({"yogurt"})
_PARMESAN_HEADS = frozenset({"parmesan"})

_PLURAL_KEEP = frozenset({"seeds", "leaves", "cloves"})

_NEUTRAL_SET = UNITS | PREP_NEUTRAL | SIZE_NEUTRAL | STOP_WORDS


# ---------------------------------------------------------------------------
# Singularization
# ---------------------------------------------------------------------------

def _singularize(word: str) -> str:
    if not word or not word.isalpha():
        return word
    w = word.lower()
    if w in _PLURAL_KEEP:
        return w
    if w.endswith("ses") and len(w) > 4:
        return w[:-2]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    # potato(s) / tomato(es)
    if w.endswith("atoes") and len(w) > 6:
        return w[:-2]
    if w.endswith("ves") and len(w) > 4:
        return w[:-3] + "f"
    if w.endswith("s") and not w.endswith("ss") and len(w) > 3:
        return w[:-1]
    return w


# ---------------------------------------------------------------------------
# Core normalizer — returns just the key string
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Deterministic identity normalization.  Returns canonical key string."""
    key, _ = _normalize_with_flags(text)
    return key


def _normalize_with_flags(text: str) -> tuple[str, frozenset[str]]:
    """Returns (key, flags) for internal use by the matcher."""
    if not text:
        return "", frozenset()

    text = _prep_line(text)

    flags: set[str] = set()
    text = text.strip()

    if text != text.lower():
        flags.add("case")
    text = text.lower()

    if text != text.strip() or "  " in text:
        flags.add("whitespace")

    # Expand parens into separate tokens BEFORE punctuation regex.
    text = text.replace("(", " ( ").replace(")", " ) ")

    # Replace harmful punctuation with spaces, but PRESERVE dots that are
    # part of numbers (e.g. "0.5" must not become "0 5").
    text_clean = re.sub(r"(?<!\d)[.,;/\\-](?!\d)", " ", text)
    if text_clean != text:
        flags.add("punct")
    text = text_clean
    text = " ".join(text.split())

    tokens = text.split()
    # Drop a trailing full-stopped count ("Fried egg, 1." → the "1." is a
    # quantity, never part of the identity).
    if tokens and _COUNT_PERIOD_RE.match(tokens[-1]):
        tokens.pop()
        flags.add("quantity")
    had_paren = "(" in tokens
    key_added: set[str] = set()

    # Remove parenthetical groups.  Parenthetical content on grocery/recipe
    # lines is a secondary annotation (alternate name, shopping note,
    # preparation, condition) that never belongs in the identity key; the
    # identity is carried by the words OUTSIDE the parentheses.  A
    # "paren" flag records that a parenthetical was present.
    out: list[str] = []
    orig_out: list[str] = []
    paren_form: list[str] = []
    i = 0
    while i < len(tokens):
        if tokens[i] == "(":
            j = i + 1
            depth = 1
            while j < len(tokens):
                if tokens[j] == "(":
                    depth += 1
                elif tokens[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            # Drop the whole parenthetical group from the identity, EXCEPT
            # form tokens that distinguish the shopping item (e.g. macaroni
            # (elbow)); those are retained and moved to a canonical position.
            for tk in tokens[i + 1 : j]:
                if tk in _PAREN_FORM_KEEP:
                    paren_form.append(tk)
            i = j + 1
        else:
            out.append(tokens[i])
            orig_out.append(tokens[i])
            i += 1
    tokens = out
    if paren_form:
        # Canonical ordering: form-first, so "macaroni (elbow)" == "elbow macaroni"
        # both normalize to "elbow macaroni".
        tokens = paren_form + tokens
        had_paren = True

    # Strip leading numbers/ranges/measurements.
    if tokens and _is_quantity_token(tokens[0]):
        key_added.add(tokens.pop(0))

    # Disambiguate CLOVE before the unit strips: "clove"/"cloves" is both a
    # garlic-clove unit and the whole-clove SPICE head.  When the line has no
    # garlic head, the clove token is the SPICE and must be preserved (not
    # stripped as a unit) so the identity survives.
    clove_is_spice = (
        ("clove" in tokens or "cloves" in tokens)
        and not any(_singularize(t) == "garlic" for t in tokens)
    )

    # Strip leading unit tokens.
    if tokens and tokens[0] in UNITS and not (tokens[0] in ("clove", "cloves") and clove_is_spice):
        key_added.add(tokens.pop(0))

    # Strip neutral tokens and quantity tokens (at any position).
    reduced: list[str] = []
    pending_form: list[str] = []   # tomato form components to surface, in order
    _opt_tail = frozenset({"as", "needed", "more", "to", "taste", "for", "serving"})
    n = len(tokens)
    i = 0
    while i < n:
        t = tokens[i]
        if t in UNITS:
            # "clove"/"cloves" is a unit normally, but when the line has NO
            # garlic head it is the whole-clove SPICE and must be kept as the
            # identity ("2 cloves", "whole cloves", "clove spice" -> "cloves"),
            # not leaked away.
            if t in ("clove", "cloves") and clove_is_spice:
                reduced.append("cloves")
                i += 1
                continue
            key_added.add(t)
            flags.add("unit")
            i += 1
            continue
        if _is_quantity_token(t):
            key_added.add(t)
            flags.add("quantity")
            i += 1
            continue
        if t in _QUANTITY_WORDS:
            key_added.add(t)
            flags.add("quantity")
            i += 1
            continue
        if t in SIZE_NEUTRAL:
            key_added.add(t)
            i += 1
            continue
        if t == "or":
            # Inline alternatives (e.g. "ghee or cooking oil") must NEVER
            # merge into a single combined identity.  Preserve the "or"
            # marker so the key stays "ghee or cooking oil" — an explicit
            # alternative structure that matches neither operand alone.
            # Resolving alternatives is an ingredient-choice concern, not
            # identity.
            #
            # BUT "or" that begins an optional-quantity tail such as
            # "olive oil, or as needed", "salt, or more to taste",
            # "1 lime, juiced, or more to taste" is NOT an alternative — it
            # is an annotation ("you may need more").  Drop "or" plus the
            # whole optional tail, because it never names an ingredient.
            if i + 1 < n and tokens[i + 1] in _opt_tail:
                # consume "or" itself, then the optional-tail words.
                key_added.add(tokens[i])
                j = i + 1
                while j < n and (tokens[j] in _opt_tail or _is_quantity_token(tokens[j])):
                    key_added.add(tokens[j])
                    j += 1
                i = j
                continue
            reduced.append(t)
            flags.add("alternative")
            i += 1
            continue
        if t in PREP_NEUTRAL:
            # "diced"/"crushed" are form components when the head is tomato;
            # keep them (they distinguish shopping identity).  All other
            # prep/usage descriptors never name an ingredient and are dropped.
            if t in _TOMATO_FORM_KEEP:
                pending_form.append(t)
            else:
                key_added.add(t)
            i += 1
            continue
        if t in STOP_WORDS:
            key_added.add(t)
            i += 1
            continue
        reduced.append(t)
        i += 1
    tokens = reduced

    # Surface tomato form components in a canonical first position ONLY when
    # the head is actually tomato (otherwise "diced"/"crushed" is a prep
    # descriptor of some other item and must stay dropped).
    if pending_form and any(_singularize(t) in ("tomato", "tomatoes")
                            for t in tokens):
        tokens = pending_form + tokens

    # Chili / chilli normalization.
    for idx, t in enumerate(tokens):
        if t in _CHILI_VARIANTS:
            tokens[idx] = "chilli"
            if t != "chilli":
                key_added.add("spelling")

    # Garlic cloves: "2 cloves garlic" / "2 garlic cloves" / "garlic cloves"
    # -> "garlic".  A leading clove token only resolves to garlic when the
    # garlic head is present elsewhere in the line.  Bare "cloves"/"clove"
    # (whole-clove SPICE, e.g. "2 cloves" in a spice-list, "whole cloves",
    # "clove spice") must NOT collapse to garlic — the identity is preserved
    # as "cloves" (the clove spice) so it can match "whole cloves (spice)".
    # Ambiguity (clove-unit vs clove-spice) is a matcher-level concern and is
    # surfaced via the clove-spice handling in match(); it is never silently
    # resolved to garlic here.
    if tokens and _singularize(tokens[0]) == "clove":
        tokens.pop(0)

    # Ground folding: strip "ground" when a neutral head follows (pepper).
    if tokens and tokens[0] == "ground":
        if any(_singularize(t) in GROUND_NEUTRAL_HEADS for t in tokens[1:]):
            tokens.pop(0)
            key_added.add("ground")

    # Narrow spice-powder folding (FIXED list, by design — NOT a broad
    # "every ground X == X powder" rule): for the nominated ground spices
    # the household confirms interchangeable, "ground X" canonicalizes to
    # "X powder".  "<head> powder" is already canonical.  Plain head forms
    # ("turmeric", "cumin seeds") are NOT folded, so "ground turmeric" stays
    # distinct from "turmeric" and "cumin seeds" stays distinct from
    # "cumin powder".
    for base in _SPICE_GROUND_TO_POWDER:
        if "ground" in tokens and any(_singularize(t) == base for t in tokens):
            key_added.add("form")
            tokens = [base, "powder"]
            break

    # Default descriptors (narrow): "plain" is a shopping-neutral default for
    # yogurt; "cheese" is an optional head qualifier for Parmesan.  Neither is
    # a form/variety distinction, so both are dropped only for those heads.
    if "plain" in tokens and any(_singularize(t) == "yogurt" for t in tokens):
        tokens = [t for t in tokens if t != "plain"]
    if "cheese" in tokens and any(_singularize(t) in ("parmesan",) for t in tokens):
        tokens = [t for t in tokens if t != "cheese"]

    # Singularize only the last token.
    if tokens:
        last = tokens[-1]
        singular = _singularize(last)
        if singular != last:
            tokens[-1] = singular
            key_added.add("plural")

    key = " ".join(tokens).strip()

    # Compute flags.
    orig_tokens = [t for t in orig_out if not _NUM_RE.match(t) and t not in UNITS]
    key_tokens = key.split() if key else []
    diff = set(orig_tokens) - set(key_tokens)
    for d in diff:
        if _NUM_RE.match(d):
            flags.add("quantity")
        elif d in PREP_NEUTRAL:
            flags.add("prep")
        elif d in SIZE_NEUTRAL:
            flags.add("size")
        elif d in STOP_WORDS:
            flags.add("stop")
        elif d in UNITS:
            flags.add("unit")
        elif d in _CHILI_VARIANTS or "spelling" in key_added:
            flags.add("spelling")
        elif "ground" in key_added and d == "ground":
            flags.add("form")

    if "spelling" in key_added:
        flags.add("spelling")
    if "ground" in key_added:
        flags.add("form")
    if "plural" in key_added:
        flags.add("plural")
    if had_paren:
        flags.add("paren")

    return key, frozenset(flags)


# ---------------------------------------------------------------------------
# Ingredient-line parser
# ---------------------------------------------------------------------------

def parse_ingredient_line(raw: str) -> tuple[str, str | None, str | None, str | None]:
    """Parse recipe ingredient line: (name, qty, unit, prep).

    Preserves original case in the returned name.
    """
    text = _prep_line(raw).strip()
    if not text:
        return "", None, None, None

    t = text.replace("(", " ( ").replace(")", " ) ")
    tokens = t.split()
    lower_tokens = [tk.lower() for tk in tokens]

    qty: str | None = None
    if lower_tokens and _NUM_RE.match(lower_tokens[0]):
        qty = tokens.pop(0)
        lower_tokens.pop(0)

    # Mixed-number quantities with either form of fraction:
    #   "1 1/2 teaspoons" / "1 1/2 cups" / "1 ½ cups" (Unicode glyph)
    # A whole number immediately followed by a fraction is ONE quantity value
    # (1.5); consume both so the fraction never leaks into the name.
    if qty and lower_tokens:
        nxt = lower_tokens[0]
        if (_NUM_RE.match(nxt) and "/" in nxt) or nxt in _UNICODE_FRACTIONS:
            qty = f"{qty} {tokens.pop(0)}"
            lower_tokens.pop(0)

    # Standalone Unicode vulgar fraction as the quantity head: "¾ cup salt".
    if qty is None and lower_tokens and lower_tokens[0] in _UNICODE_FRACTIONS:
        qty = tokens.pop(0)
        lower_tokens.pop(0)

    # Ranged quantities: "1-2", "3-4", "2-3" (not covered by _NUM_RE).
    if qty is None and lower_tokens and _RANGE_RE.match(lower_tokens[0]):
        qty = tokens.pop(0)
        lower_tokens.pop(0)

    # Handle parenthetical content.
    prep_from_paren: str | None = None
    if "(" in lower_tokens:
        out_lower: list[str] = []
        out_orig: list[str] = []
        i = 0
        n = len(lower_tokens)
        while i < n:
            if lower_tokens[i] == "(":
                j = i + 1
                inner_l: list[str] = []
                inner_o: list[str] = []
                depth = 1
                while j < n:
                    if lower_tokens[j] == "(":
                        depth += 1
                    elif lower_tokens[j] == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    inner_l.append(lower_tokens[j])
                    inner_o.append(tokens[j])
                    j += 1
                if inner_l and all(x in _NEUTRAL_SET for x in inner_l):
                    prep_from_paren = " ".join(inner_l)
                else:
                    out_lower.extend(inner_l)
                    out_orig.extend(inner_o)
                i = j + 1
            else:
                out_lower.append(lower_tokens[i])
                out_orig.append(tokens[i])
                i += 1
        lower_tokens = out_lower
        tokens = out_orig

    # Truncate at first stop word OR at a comma boundary (a comma introduces
    # preparation/annotation text, not more of the ingredient name).  The comma
    # is usually glued to the preceding token ("leaves,"), so match both forms.
    stop_idx = len(lower_tokens)
    for idx, lt in enumerate(lower_tokens):
        if lt in STOP_WORDS:
            stop_idx = idx
            break
        if lt == "," or lt.endswith(","):
            stop_idx = idx + 1  # include the name token, drop the comma tail after it
            break
    lower_tokens = lower_tokens[:stop_idx]
    tokens = tokens[:stop_idx]

    # Extract units, prep, sizes; remaining = name.
    unit_found: str | None = None
    prep_found: str | None = prep_from_paren
    name_tokens: list[str] = []

    for lo, orig in zip(lower_tokens, tokens):
        # A measurement token (number with an inch/prime mark, or declared
        # measurement) inside the tail is prep text, never an ingredient
        # quantity or identity.
        if _INCH_MARK_MEASURE_RE.match(lo) or lo in _UNICODE_FRACTIONS:
            continue
        if lo in UNITS:
            # "clove"/"cloves" is normally a unit (garlic cloves); but when
            # the line has NO garlic head, the clove token IS the whole-clove
            # SPICE and must remain the name (e.g. "2 cloves", "whole cloves").
            if lo in ("clove", "cloves") and not any(
                _singularize(x) == "garlic" for x in lower_tokens
            ):
                name_tokens.append(orig)
                continue
            unit_found = lo
            continue
        if lo in PREP_NEUTRAL:
            if prep_found is None:
                prep_found = lo
            continue
        if lo in SIZE_NEUTRAL:
            continue
        if lo in STOP_WORDS:
            break
        name_tokens.append(orig)

    # Strip a trailing comma glued onto the final name token ("leaves,").
    if name_tokens:
        name_tokens[-1] = name_tokens[-1].rstrip(",")

    return " ".join(name_tokens).strip(), qty, unit_found, prep_found


# ---------------------------------------------------------------------------
# Alias loading
# ---------------------------------------------------------------------------

def load_aliases(path: str | Path | None = None) -> dict[str, list[str]]:
    """Load RAW alias mapping: {raw_canonical: [raw_alias, ...]}."""
    p = Path(path) if path else ALIASES_PATH
    if not p.exists():
        return {}
    with open(p, "r") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries", []) if data else []
    out: dict[str, list[str]] = {}
    for entry in entries:
        out[entry.get("name", "")] = list(entry.get("aliases", []))
    return out


def _load_alias_file(path: Path | None = None) -> tuple[dict[str, set[str]], dict[str, str]]:
    """Build normalized alias lookup tables."""
    p = path or ALIASES_PATH
    if not p.exists():
        return {}, {}
    with open(p, "r") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries", []) if data else []
    can_to_alias: dict[str, set[str]] = {}
    alias_to_canonical: dict[str, str] = {}
    for entry in entries:
        nc, _ = _normalize_with_flags(entry.get("name", ""))
        alias_set: set[str] = set()
        for raw_alias in entry.get("aliases", []):
            na, _ = _normalize_with_flags(raw_alias)
            alias_set.add(na)
            alias_to_canonical[na] = nc
        can_to_alias[nc] = alias_set
    return can_to_alias, alias_to_canonical


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

def _tier(flags_a: frozenset[str], flags_b: frozenset[str]) -> str:
    both = flags_a | flags_b
    if not both:
        return "exact_match"
    if both <= {"case", "whitespace", "punct"}:
        return "exact_match"
    if "alias" in both:
        return "alias_match"
    return "normalized_match"


# Narrow, household-confirmed semantic equivalences applied ONLY by the
# matcher (they never rewrite the identity key).  Each entry maps a normalized
# key to the canonical match form.  These collapse ingredient forms that the
# household treats as the same shopping item, WITHOUT broad fuzzy matching or
# arbitrary token deletion, and WITHOUT touching the protected form
# distinctions (fresh vs ground ginger, diced vs crushed tomato, chili powder
# vs whole/dry chili, cumin seeds vs ground cumin, chicken breast vs thigh,
# olive/vegetable/cooking oil).
_MATCH_EQUIV = {
    # fresh ginger is the default ginger; unqualified ginger is the same item.
    "fresh ginger": "ginger",
    # curd (Indian/Central-Asian yogurt) is plain yogurt.
    "curd": "yogurt",
    # a coriander SPROG / fresh coriander IS cilantro.  "sprig"/"stems" are
    # stripped in normalize, so bare "coriander" (the fresh herb garnish) maps
    # to cilantro.  "coriander powder" and "ground coriander" remain distinct
    # (their keys carry "powder"), so this never collapses the spice.
    "coriander": "cilantro",
    "fresh cilantro": "cilantro",
    "cilantro with stems": "cilantro",
    # word-order / form variants of the same shopping item.
    "mild italian sausage": "italian sausage",
    "whole dry kashmiri red chilli": "kashmiri red chilli",
    # The whole-clove SPICE.  "cloves"/"clove" without a garlic head is the
    # spice and refers to the grocery item "whole cloves (spice)".  (Garlic
    # cloves always resolve to a "garlic" key, so a bare "cloves"/"clove" key
    # is unambiguous: it is the spice, never garlic.)
    "cloves": "whole cloves",
    "clove": "whole cloves",
}


def _match_canonical(key: str) -> str:
    """Matcher-layer canonical form of a normalized key (identity unchanged)."""
    if not key:
        return key
    # Salad/annotation-free descriptor tails already handled by normalize.
    # macaroni: when the line is plain "macaroni", it refers to the household's
    # elbow macaroni; the elbow form is preserved when explicitly present.
    if key == "elbow macaroni":
        return "macaroni"
    if key == "macaroni":
        return "macaroni"
    return _MATCH_EQUIV.get(key, key)


@dataclass
class MatchResult:
    status: str
    canonical: list[str]
    reason: str
    related_distinct: bool = False
    candidates: list[str] | None = None


def match(
    recipe_ingredient: str,
    pantry_names: list[str],
    alias_path: str | Path | None = None,
) -> MatchResult:
    if not pantry_names:
        return MatchResult(
            status="no_match", canonical=[],
            reason="Pantry is empty; no candidates to compare.",
        )

    p = Path(alias_path) if alias_path else ALIASES_PATH
    _, alias_to_canonical = _load_alias_file(p)

    key_r, flags_r = _normalize_with_flags(recipe_ingredient)
    if key_r in alias_to_canonical:
        key_r = alias_to_canonical[key_r]
        flags_r = flags_r | frozenset(["alias"])
    key_r = _match_canonical(key_r)

    @dataclass
    class PI:
        raw: str
        key: str
        flags: frozenset[str]

    pantry_items: list[PI] = []
    for raw in pantry_names:
        key, flags = _normalize_with_flags(raw)
        if key in alias_to_canonical:
            key = alias_to_canonical[key]
            flags = flags | frozenset(["alias"])
        key = _match_canonical(key)
        pantry_items.append(PI(raw=raw, key=key, flags=flags))

    # Positive matches.
    positives = [(p, p.flags) for p in pantry_items if key_r == p.key]

    # Generic-ambiguous candidates.
    ambiguous_cands = []
    for p in pantry_items:
        if key_r == p.key:
            continue
        recipe_parts = set(key_r.split())
        pantry_parts = set(p.key.split())
        if key_r in GENERIC_AMBIGUOUS_HEADS and pantry_parts > recipe_parts:
            ambiguous_cands.append(p)

    # Disjoint items for related_distinct.
    pos_keys = {pp.key for pp, _ in positives}
    disjoint = [p for p in pantry_items if p.key not in pos_keys and p not in ambiguous_cands]

    if positives and not ambiguous_cands:
        canonical = [p.raw for p, _ in positives]
        combined = frozenset().union(*(fl for _, fl in positives))
        tier = _tier(flags_r, combined)
        return MatchResult(
            status=tier, canonical=canonical,
            reason=f"Recipe key '{key_r}' matches pantry key '{canonical[0]}'.",
        )

    if ambiguous_cands and not positives:
        cands = [p.raw for p in ambiguous_cands]
        return MatchResult(
            status="ambiguous", canonical=[],
            reason=f"Generic '{recipe_ingredient}' (key '{key_r}'); pantry has specific variant(s): {cands}.",
            candidates=cands,
        )

    if positives and ambiguous_cands:
        cands = [p.raw for p in ambiguous_cands]
        return MatchResult(
            status="ambiguous", canonical=[],
            reason=f"Partial match plus ambiguous variants: {cands}.",
            candidates=cands,
        )

    related = any(bool(set(key_r.split()) & set(p.key.split())) for p in disjoint)
    return MatchResult(
        status="no_match", canonical=[],
        reason=f"No pantry item matches key '{key_r}'. Pantry keys: {[p.key for p in pantry_items]}",
        related_distinct=related,
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <ingredient>", file=sys.stderr)
        sys.exit(1)
    ing = " ".join(sys.argv[1:])
    key = normalize(ing)
    pl = parse_ingredient_line(ing)
    print(f"input:   {ing}")
    print(f"key:     {key}")
    print(f"parsed:  name={pl[0]!r} qty={pl[1]!r} unit={pl[2]!r} prep={pl[3]!r}")
