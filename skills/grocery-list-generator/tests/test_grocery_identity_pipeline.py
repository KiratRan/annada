#!/usr/bin/env python3
"""Integration tests for grocery-list-generator's Stage 3B identity pipeline.

These verify the pipeline's separation of identity / sufficiency / aggregation
/ alternatives WITHOUT re-implementing or overriding the identity layer's
deterministic match() decisions. They run the real household modules
(ingredient_identity + grocery_identity_pipeline).
"""

from __future__ import annotations

import os
import sys
import unittest

# Add the pipeline module and the identity layer.
_PIPELINE_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
# Pantry lives at $HOUSEHOLD_ROOT/pantry; fall back to the repo-relative
# <repo>/household/pantry (this test sits at
# <repo>/skills/grocery-list-generator/tests/).
_HOUSEHOLD_ROOT = os.environ.get("HOUSEHOLD_ROOT", "").strip()
_PANTRY_DIR = os.path.join(_HOUSEHOLD_ROOT, "pantry") if _HOUSEHOLD_ROOT else ""
if not (_PANTRY_DIR and os.path.isdir(_PANTRY_DIR)):
    _PANTRY_DIR = os.path.normpath(
        os.path.join(_TEST_DIR, "..", "..", "..", "household", "pantry"))
for _d in (_PIPELINE_DIR, _PANTRY_DIR):
    if _d not in sys.path:
        sys.path.insert(0, _d)

from grocery_identity_pipeline import POSITIVE_STATUSES  # noqa: E402


class IdentityResolutionTests(unittest.TestCase):
    """Core identity-matching behavior (exact/normalized/alias/no_match/ambig)."""

    def setUp(self):
        self.pantry = [
            "yellow onion",
            "garlic",
            "olive oil",
            "vegetable oil",
            "cooking oil",
            "ghee",
            "kosher salt",
            "tomato paste",
            "tomato puree",
            "tomato sauce",
            "whole dry Kashmiri red chillies",
            "Kashmiri red chilli powder",
            "ground cumin",
            "cumin seeds",
            "fresh ginger",
            "ground ginger",
            "fresh spinach",
            "macaroni",
            "whole chicken",
            "chicken breast",
            "chicken thighs",
            "curd",
            "yogurt",
        ]

    def test_exact_identity(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 tablespoon olive oil", self.pantry)
        self.assertEqual(r.identity.status, "exact_match")
        self.assertTrue(r.identity.is_positive)

    def test_normalized_identity(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1/2 lb uncooked macaroni", self.pantry)
        self.assertIn(r.identity.status, ("normalized_match", "exact_match"))
        self.assertTrue(r.identity.is_positive)

    def test_alias_identity(self):
        from grocery_identity_pipeline import resolve_ingredient
        # Real alias pair: green onions -> scallions (canonical in aliases.yaml)
        r = resolve_ingredient("2 green onions, sliced", ["scallions"])
        self.assertEqual(r.identity.status, "alias_match")
        self.assertTrue(r.identity.is_positive)

    def test_no_match(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 bunch kale", self.pantry)
        self.assertEqual(r.identity.status, "no_match")
        self.assertFalse(r.identity.is_positive)

    def test_ambiguous_generic_onion(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 medium onion, chopped", self.pantry)
        self.assertEqual(r.identity.status, "ambiguous")
        self.assertFalse(r.identity.is_positive)

    def test_ambiguous_generic_oil(self):
        from grocery_identity_pipeline import resolve_ingredient
        # No plain "oil" in pantry; generic oil must not auto-match olive/veg.
        r = resolve_ingredient("1 tablespoon oil", self.pantry)
        self.assertEqual(r.identity.status, "ambiguous")
        self.assertFalse(r.identity.is_positive)

    def test_unresolved_alternative(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("ghee or cooking oil", self.pantry)
        self.assertEqual(r.identity.status, "unresolved_alternative")
        self.assertFalse(r.identity.is_positive)

    def test_ghee_vs_alternative(self):
        from grocery_identity_pipeline import resolve_ingredient
        # ghee alone is a positive match; the alternative form is NOT.
        r = resolve_ingredient("ghee", self.pantry)
        self.assertTrue(r.identity.is_positive)
        r2 = resolve_ingredient("ghee or cooking oil", self.pantry)
        self.assertEqual(r2.identity.status, "unresolved_alternative")

    def test_benign_or_tail_stripped(self):
        from grocery_identity_pipeline import resolve_ingredient
        # "or as needed" is a benign tail the identity layer strips -> real match.
        r = resolve_ingredient("1 tablespoon olive oil, or as needed", self.pantry)
        self.assertIn(r.identity.status, ("exact_match", "normalized_match"))
        self.assertTrue(r.identity.is_positive)


class SufficiencyTests(unittest.TestCase):
    """Pantry sufficiency: only positive identities may be evaluated."""

    def setUp(self):
        self.pantry = ["olive oil", "yellow onion", "ghee", "curd"]

    def test_positive_identity_confirmed_available(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("olive oil", self.pantry,
                               pantry_status="confirmed_available",
                               pantry_quantity_sufficient=True)
        self.assertTrue(r.identity.is_positive)
        self.assertTrue(r.pantry.sufficient is True)
        self.assertEqual(r.pantry.pantry_status, "confirmed_available")
        self.assertFalse(r.goes_on_list)  # available -> excluded

    def test_positive_identity_insufficient(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("olive oil", self.pantry,
                               pantry_status="confirmed_available",
                               pantry_quantity_sufficient=False)
        self.assertTrue(r.pantry.sufficient is False)
        self.assertTrue(r.goes_on_list)  # remains a candidate

    def test_positive_identity_unknown_pantry(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("olive oil", self.pantry,
                               pantry_status="unknown")
        self.assertIsNone(r.pantry.sufficient)
        self.assertTrue(r.goes_on_list)

    def test_no_match_never_satisfies(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 bunch kale", self.pantry,
                               pantry_status="confirmed_available",
                               pantry_quantity_sufficient=True)
        self.assertEqual(r.identity.status, "no_match")
        self.assertEqual(r.pantry.pantry_status, "not_eligible")
        self.assertTrue(r.goes_on_list)

    def test_ambiguous_never_satisfies(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 tablespoon oil", self.pantry,
                               pantry_status="confirmed_available",
                               pantry_quantity_sufficient=True)
        self.assertEqual(r.identity.status, "ambiguous")
        self.assertEqual(r.pantry.pantry_status, "not_eligible")
        self.assertTrue(r.goes_on_list)

    def test_unresolved_alternative_never_satisfies(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("ghee or cooking oil", self.pantry,
                               pantry_status="confirmed_available",
                               pantry_quantity_sufficient=True)
        self.assertEqual(r.identity.status, "unresolved_alternative")
        self.assertEqual(r.pantry.pantry_status, "not_eligible")
        self.assertTrue(r.goes_on_list)


class AggregationTests(unittest.TestCase):
    """Quantity aggregation runs AFTER identity, only on compatible groups."""

    def setUp(self):
        self.pantry = ["olive oil", "yellow onion"]

    def test_aggregate_after_identity(self):
        from grocery_identity_pipeline import resolve_ingredient, aggregate_quantities
        lines = [
            "2 tablespoons olive oil",
            "1 tablespoon olive oil",
            "1 medium onion, chopped",
        ]
        resolved = [resolve_ingredient(l, self.pantry) for l in lines]
        groups = aggregate_quantities(resolved)
        # olive oil groups together; ambiguous onion stays isolated
        self.assertIn("olive oil", groups)
        self.assertGreaterEqual(len(groups["olive oil"]), 2)
        # any non-positive stays its own group, never merged into olive oil
        ambient = [k for k in groups if k != "olive oil"]
        self.assertNotIn("olive oil", [k for k in ambient])
        for k in ambient:
            self.assertNotEqual(k, "olive oil")

    def test_alternatives_never_aggregated(self):
        from grocery_identity_pipeline import resolve_ingredient, aggregate_quantities
        lines = ["ghee or cooking oil", "ghee", "1 tablespoon ghee"]
        resolved = [resolve_ingredient(l, self.pantry) for l in lines]
        groups = aggregate_quantities(resolved)
        # the unresolved alternative must stay its own isolated group
        alt_key = [k for k in groups if "or" in k]
        self.assertEqual(len(alt_key), 1)
        # and must NOT contain the plain ghee quantities
        self.assertIn("ghee", groups)
        self.assertNotIn("1 tablespoon ghee", alt_key)


class ProtectedBoundaryTests(unittest.TestCase):
    """Distinctions that must never regress."""

    def setUp(self):
        self.pantry = [
            "diced tomatoes", "crushed tomatoes", "tomato sauce",
            "tomato paste", "tomato puree",
            "chili powder", "red chilli powder",
            "whole dry Kashmiri red chillies", "Kashmiri red chilli powder",
            "cumin seeds", "ground cumin",
            "fresh ginger", "ground ginger",
            "garlic", "garlic powder",
            "olive oil", "vegetable oil", "cooking oil",
            "ginger-garlic paste", "ghee",
            "yellow onion", "Yukon gold potatoes",
            "chicken breast", "chicken thighs",
        ]

    def test_protected_tomato_forms(self):
        from grocery_identity_pipeline import resolve_ingredient
        self.assertEqual(resolve_ingredient("2 tablespoons tomato paste",
                                            self.pantry).identity.status, "exact_match")
        self.assertEqual(resolve_ingredient("1 cup tomato puree",
                                            self.pantry).identity.status, "exact_match")
        self.assertEqual(resolve_ingredient("8 oz tomato sauce",
                                            self.pantry).identity.status, "exact_match")
        # diced and crushed are distinct from each other and from sauce/paste
        self.assertNotEqual(resolve_ingredient("1 can diced tomatoes",
                                               self.pantry).identity.canonical_identities,
                            resolve_ingredient("1 can crushed tomatoes",
                                               self.pantry).identity.canonical_identities)

    def test_protected_chili_forms(self):
        from grocery_identity_pipeline import resolve_ingredient
        powder = resolve_ingredient("1/2 teaspoon Kashmiri red chilli powder",
                                    self.pantry)
        whole = resolve_ingredient("2-3 whole dry Kashmiri red chillies",
                                   self.pantry)
        # both positive matches
        self.assertTrue(powder.identity.is_positive)
        self.assertTrue(whole.identity.is_positive)
        # but powder and whole dry chillies are DISTINCT identities
        self.assertNotEqual(powder.identity.canonical_identities,
                            whole.identity.canonical_identities)
        self.assertIn("Kashmiri red chilli powder",
                      powder.identity.canonical_identities)
        # powder identity must NOT equal the whole-chilli identity
        self.assertNotIn("whole dry Kashmiri", powder.identity.canonical_identities)

    def test_cumin_seed_ground_distinction(self):
        from grocery_identity_pipeline import resolve_ingredient
        self.assertEqual(resolve_ingredient("1/2 teaspoon cumin seeds",
                                            self.pantry).identity.status, "exact_match")
        self.assertEqual(resolve_ingredient("1 teaspoon ground cumin",
                                            self.pantry).identity.status, "exact_match")

    def test_fresh_ground_ginger_distinction(self):
        from grocery_identity_pipeline import resolve_ingredient
        fresh = resolve_ingredient("1 inch ginger, sliced", self.pantry)
        ground = resolve_ingredient("1/2 teaspoon ground ginger", self.pantry)
        # both are positive matches
        self.assertTrue(fresh.identity.is_positive)
        self.assertTrue(ground.identity.is_positive)
        # but they map to DISTINCT canonical identities (protected boundary)
        self.assertNotEqual(fresh.identity.canonical_identities,
                            ground.identity.canonical_identities)
        self.assertIn("fresh ginger", fresh.identity.canonical_identities)
        self.assertIn("ground ginger", ground.identity.canonical_identities)

    def test_ghee_vs_cooking_oil(self):
        from grocery_identity_pipeline import resolve_ingredient
        self.assertEqual(resolve_ingredient("ghee", self.pantry).identity.status, "exact_match")
        self.assertEqual(resolve_ingredient("cooking oil",
                                            self.pantry).identity.status, "exact_match")
        # and the alternative is unresolved, not matched to either
        self.assertEqual(resolve_ingredient("ghee or cooking oil",
                                            self.pantry).identity.status, "unresolved_alternative")

    def test_generic_onion_blocked(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1 medium onion, chopped", self.pantry)
        self.assertEqual(r.identity.status, "ambiguous")
        self.assertNotIn("yellow onion", r.identity.canonical_identities or [])


class PolicyExclusionTests(unittest.TestCase):
    """Grocery-policy exclusions (water, salt variants) are NOT identity
    defects. Identity stays non-committal; pipeline flags policy."""

    def setUp(self):
        self.pantry = []  # empty pantry

    def test_water_is_non_shoppable_not_match(self):
        from grocery_identity_pipeline import resolve_ingredient
        r = resolve_ingredient("1/2 cup water", self.pantry)
        self.assertEqual(r.identity.status, "no_match")
        # policy: tap-water, not forced into identity
        self.assertTrue(r.goes_on_list)

    def test_kosher_salt_policy(self):
        from grocery_identity_pipeline import resolve_ingredient
        # The grocery list carries plain "salt" (not kosher salt); identity here
        # non-committal: kosher salt among groceries with no kosher -> no_match.
        r = resolve_ingredient("1 teaspoon kosher salt, or more to taste", ["salt"])
        self.assertEqual(r.identity.status, "no_match")
        # It is a policy decision (shopping), not an identity defect.
        self.assertTrue(r.goes_on_list)


if __name__ == "__main__":
    unittest.main()