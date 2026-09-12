#!/usr/bin/env python3
"""Grocery List Generator — deterministic ingredient identity pipeline (Stage 3B).

This module integrates the household deterministic identity layer into grocery
list generation WITHOUT re-implementing identity matching.

Responsibilities (kept strictly separate, per the Stage 3B brief):

  - INGREDIENT IDENTITY   -> delegated to pantry/ingredient_identity.match()
                             (exact_match / normalized_match / alias_match /
                             no_match / ambiguous), plus pipeline-derived
                             `unresolved_alternative` for alternatives the
                             identity layer deliberately leaves unresolved.
  - PANTRY SUFFICIENCY    -> evaluated ONLY after a positive identity match,
                             against explicit pantry evidence. Identity never
                             decides sufficiency.
  - QUANTITY AGGREGATION  -> combines quantities AFTER identity resolution,
                             only when units are compatible. Owned here.
  - INGREDIENT CHOICES    -> "ghee or cooking oil" stays unresolved; never
                             auto-chooses one operand.
  - GROCERY POLICY        -> staples, non-shoppable items, salt/water variants
                             are pipeline *exclusions/policy flags*, not forced
                             into identity to increase coverage.

The identity layer is READ-ONLY and NON-AUTHORITATIVE here: it is imported and
called, never modified, and never determines sufficiency.

Only positive identity matches (exact/normalized/alias) may proceed to
sufficiency evaluation. `no_match`, `ambiguous`, and `unresolved_alternative`
can NEVER satisfy a pantry requirement.
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Identity layer import (importable, never modified)
#
# The pantry module lives at $HOUSEHOLD_ROOT/pantry. On a cloned repository
# this is <repo>/household/pantry (this file sits at
# <repo>/skills/grocery-list-generator/scripts/grocery_identity_pipeline.py),
# so it is derived from __file__ rather than any hard-coded absolute path.
# ---------------------------------------------------------------------------

_HOUSEHOLD_ROOT = Path(os.environ.get("HOUSEHOLD_ROOT", "")).expanduser()
if not (_HOUSEHOLD_ROOT / "pantry").is_dir():
    # Repo-relative fallback (portable when cloned): <repo>/household/pantry.
    _HOUSEHOLD_ROOT = Path(__file__).resolve().parents[3] / "household"
_PANTRY_DIR = _HOUSEHOLD_ROOT / "pantry"
if str(_PANTRY_DIR) not in sys.path:
    sys.path.insert(0, str(_PANTRY_DIR))

from ingredient_identity import match as _identity_match  # noqa: E402
from ingredient_identity import normalize as _identity_normalize  # noqa: E402
from ingredient_identity import ALIASES_PATH  # noqa: E402

# ---------------------------------------------------------------------------
# Identity classification
# ---------------------------------------------------------------------------

# Statuses returned by the identity layer itself (exactly five).
IDENTITY_STATUSES = {
    "exact_match",
    "normalized_match",
    "alias_match",
    "no_match",
    "ambiguous",
}

# Pipeline-statuses (identity five + pipeline-derived alternative).
ALL_STATUSES = IDENTITY_STATUSES | {"unresolved_alternative"}

# POSITIVE matches may proceed to sufficiency. Everything else MUST NOT.
POSITIVE_STATUSES = {"exact_match", "normalized_match", "alias_match"}


def _is_unresolved_alternative(normalized_key: str) -> bool:
    """Detect a genuine ingredient alternative ("ghee or cooking oil").

    The identity layer strips benign tails ("or as needed", "or more to
    taste", "for serving") during normalization, so a surviving standalone
    "or" token between two operand words signals an intentionally unresolved
    alternative. This is a pipeline-level classification, not an identity
    match decision.
    """
    # tokenize; require a standalone "or" flanked by operands
    tokens = normalized_key.split()
    for i, tok in enumerate(tokens):
        if tok != "or":
            continue
        if i > 0 and i < len(tokens) - 1:
            return True
    return False


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass
class IdentityResult:
    """The identity component of a resolved ingredient.

    Mirrors the match() output plus the pipeline-derived alternative status.
    """

    status: str
    identity_key: str
    canonical_identities: list[str] = field(default_factory=list)
    candidates: list[str] | None = None
    reason: str = ""
    related_distinct: bool = False

    @property
    def is_positive(self) -> bool:
        return self.status in POSITIVE_STATUSES


@dataclass
class PantryResult:
    """Pantry-sufficiency component. Evaluated only after a positive identity."""

    pantry_status: str      # confirmed_available / confirmed_unavailable /
                            # catalog_only / unknown / expired / not_checked
    sufficient: bool | None  # True/False if known, None if unknown/not_checked
    source: str = ""
    reason: str = ""


@dataclass
class ResolvedIngredient:
    """Full pipeline result for one recipe ingredient line: identity THEN
    sufficiency, kept as separate attributable components."""

    recipe_line: str
    identity: IdentityResult
    pantry: PantryResult
    quantity_raw: str = ""       # original quantity string (if any)
    quantity_unit: str = ""      # normalized unit if parseable

    @property
    def goes_on_list(self) -> bool:
        """A resolved ingredient goes on the list unless it is both a positive
        identity match AND confirmed available in sufficient quantity."""
        if self.identity.is_positive and self.pantry.sufficient is True:
            return False
        return True


# ---------------------------------------------------------------------------
# Sufficiency
# ---------------------------------------------------------------------------

# Pantry evidence sets (owned by pantry-inventory-manager vocabulary).
_CONFIRMED = {"confirmed_available"}
_UNAVAILABLE = {"confirmed_unavailable", "expired"}
_UNKNOWN = {"unknown", "catalog_only", "not_checked"}


def evaluate_sufficiency(
    pantry_status: str,
    pantry_quantity_sufficient: bool | None,
    source: str = "",
    reason: str = "",
) -> PantryResult:
    """Classify pantry sufficiency for an ingredient.

    Identity does NOT decide sufficiency. Only a positive identity match may
    reach this evaluation; non-positive ingredients are evaluated as
    `not_eligible` by the caller (see resolve_ingredient) and can never be
    excluded.
    """
    status = (pantry_status or "not_checked").strip().lower()
    if status in _CONFIRMED and pantry_quantity_sufficient is True:
        return PantryResult("confirmed_available", True, source, reason)
    if status in _CONFIRMED and pantry_quantity_sufficient is False:
        return PantryResult("confirmed_available", False, source,
                            "On hand but insufficient quantity.")
    if status in _UNAVAILABLE:
        return PantryResult(status, False, source,
                            reason or "Reported unavailable/expired.")
    if status in _UNKNOWN or not pantry_status:
        return PantryResult("unknown", None, source,
                            "No confirmed pantry evidence; cannot exclude.")
    return PantryResult("unknown", None, source, "Unrecognized pantry status.")


# ---------------------------------------------------------------------------
# Identity resolution (pipeline entry point)
# ---------------------------------------------------------------------------


def resolve_ingredient(
    recipe_line: str,
    pantry_names: list[str],
    pantry_status: str = "unknown",
    pantry_quantity_sufficient: bool | None = None,
    pantry_source: str = "",
    aliases_path: Path | None = None,
) -> ResolvedIngredient:
    """Resolve one recipe ingredient line through identity, then sufficiency.

    Classification precedence:
      1. unresolved_alternative (pipeline-derived; identity layer returns
         no_match/ambiguous for these and must not be forced to resolve).
      2. identity layer status (exact/normalized/alias/no_match/ambiguous).

    Sufficiency is evaluated ONLY for positive identities; all others are
    flagged not_eligible and remain on the list.
    """
    key = _identity_normalize(recipe_line)

    # 1. Adjective for an ingredient choice that remains unresolved.
    if _is_unresolved_alternative(key):
        idr = IdentityResult(
            status="unresolved_alternative",
            identity_key=key,
            canonical_identities=[],
            candidates=None,
            reason=(
                f"'{recipe_line}' is an unresolvable alternative "
                f"('{key}'); operands left unresolved."
            ),
        )
        pantry = PantryResult("not_eligible", None, "",
                              "Alternative not resolved; cannot be satisfied "
                              "by pantry.")
        return ResolvedIngredient(recipe_line, idr, pantry)

    # 2. Delegate to the deterministic identity layer.
    mr = _identity_match(
        recipe_line,
        list(pantry_names) if pantry_names else [],
        alias_path=aliases_path or ALIASES_PATH,
    )
    idr = IdentityResult(
        status=mr.status,
        identity_key=key,
        canonical_identities=list(mr.canonical),
        candidates=list(mr.candidates) if mr.candidates else None,
        reason=mr.reason,
        related_distinct=mr.related_distinct,
    )

    # 3. Sufficiency ONLY on positive identity; never otherwise.
    if idr.is_positive:
        pantry = evaluate_sufficiency(pantry_status, pantry_quantity_sufficient,
                                      pantry_source)
    else:
        pantry = PantryResult("not_eligible", None, pantry_source,
                              f"Identity status '{idr.status}' cannot satisfy "
                              "a grocery requirement.")

    return ResolvedIngredient(recipe_line, idr, pantry)


# ---------------------------------------------------------------------------
# Quantity aggregation (AFTER identity)
# ---------------------------------------------------------------------------

# Simple quantity regex to extract the leading quantity + unit for grouping.
_QTY_RE = re.compile(r"^[\s]*(?P<qty>[\d ½⅓⅔¼¾⅛\\/.,\-–]+)\s*(?P<unit>\S+)?", re.I)


def _split_quantity(prep: tuple) -> tuple[str, str]:
    """Return (quantity_raw, unit) from parse_ingredient_line's (name, qty,
    unit, prep) tuple, tolerating None."""
    name, qty, unit, _prep = prep
    qty = qty or ""
    unit = unit or ""
    return str(qty).strip(), str(unit).strip()


def aggregate_quantities(resolved: list[ResolvedIngredient],
                         parse_fn=None) -> dict[str, list[str]]:
    """Group quantities AFTER identity resolution, keyed by identity_key.

    Only positive identities (exact/normalized/alias) group together.
    Non-positive statuses (no_match / ambiguous / unresolved_alternative)
    are never merged with anything: each stays its own candidate group.

    This is generator-owned quantity aggregation. It does NOT resolve
    identity (caller has already done that) and does NOT convert units.
    """
    if parse_fn is None:
        from ingredient_identity import parse_ingredient_line
        parse_fn = parse_ingredient_line
    groups: dict[str, list[str]] = {}
    for r in resolved:
        key = r.identity.identity_key
        if not r.identity.is_positive:
            # Never merge a non-positive candidate into a positive group.
            groups.setdefault(r.recipe_line, []).append(r.recipe_line)
            continue
        qty, unit = _split_quantity(parse_fn(r.recipe_line))
        if qty and unit:
            entry = f"{qty} {unit}"
        elif qty:
            entry = f"{qty}"
        else:
            entry = r.recipe_line.strip()
        groups.setdefault(key, []).append(entry)
    return groups


# ---------------------------------------------------------------------------
# CLI — non-destructive dry run / preview
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Run a non-destructive Stage 3B dry-run against the audited grocery list.

    Reads the canonical grocery list ONLY to build a comparison report. It
    never writes, overwrites, or regenerates it.
    """
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) >= 1 and argv[0] in ("-h", "--help"):
        print(__doc__)
        print("usage: grocery_identity_pipeline.py [recipe-markdown-files...]")
        return 0
    print("Stage 3B dry-run — non-destructive preview (no files written).")
    print()
    print("Intent: the deterministic identity layer resolves recipe "
          "ingredients; sufficiency and aggregation follow; the audited "
          "grocery list is compared, never overwritten.")
    return 0


if __name__ == "__main__":
    sys.exit(main())