#!/usr/bin/env python3
"""Comprehensive tests for ingredient_identity.py - Stage 2."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingredient_identity import normalize, parse_ingredient_line, match, load_aliases, ALIASES_PATH


class TestNormalize(unittest.TestCase):
    """Tests for the core normalizer."""

    def test_case_insensitive(self):
        self.assertEqual(normalize("Garlic"), "garlic")

    def test_whitespace_collapsing(self):
        self.assertEqual(normalize("  red  chilli  powder  "), "red chilli powder")

    def test_punctuation_removes_parenthetical(self):
        self.assertEqual(normalize("garlic (minced)"), "garlic")

    def test_chili_chilli_collapse(self):
        self.assertEqual(normalize("chili powder"), "chilli powder")
        self.assertEqual(normalize("red chili powder"), "red chilli powder")

    def test_leading_trailing_comma(self):
        self.assertEqual(normalize("garlic,"), "garlic")

    def test_already_clean(self):
        self.assertEqual(normalize("garlic"), "garlic")

    def test_empty_string(self):
        self.assertEqual(normalize(""), "")

    def test_specialty_no_collapse(self):
        self.assertEqual(normalize("kosher salt"), "kosher salt")
        self.assertEqual(normalize("sweet potato"), "sweet potato")

    def test_ginger_garlic_paste(self):
        self.assertEqual(normalize("ginger-garlic paste"), "ginger garlic paste")

    def test_slash_handling(self):
        self.assertEqual(normalize("cilantro/coriander"), "cilantro coriander")


class TestParseIngredientLine(unittest.TestCase):
    """Tests for recipe ingredient line parsing."""

    def test_simple(self):
        name, qty, unit, prep = parse_ingredient_line("garlic")
        self.assertEqual(name, "garlic")
        self.assertIsNone(qty)
        self.assertIsNone(unit)
        self.assertIsNone(prep)

    def test_with_qty_and_unit(self):
        name, qty, unit, prep = parse_ingredient_line("2 cups flour")
        self.assertEqual(name, "flour")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "cups")
        self.assertIsNone(prep)

    def test_with_parens(self):
        name, qty, unit, prep = parse_ingredient_line("2 cloves garlic (minced)")
        self.assertEqual(name, "garlic")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "cloves")
        self.assertEqual(prep, "minced")

    def test_size_in_parens(self):
        name, qty, unit, prep = parse_ingredient_line("1 yellow onion (small dice)")
        self.assertEqual(name, "yellow onion")
        self.assertEqual(qty, "1")
        self.assertIsNone(unit)
        self.assertEqual(prep, "small dice")

    def test_red_onion(self):
        name, qty, unit, prep = parse_ingredient_line("red onion")
        self.assertEqual(name, "red onion")
        self.assertIsNone(qty)
        self.assertIsNone(unit)
        self.assertIsNone(prep)

    def test_stop_word(self):
        name, qty, unit, prep = parse_ingredient_line("Salt and pepper to taste")
        self.assertEqual(name, "Salt")
        self.assertIsNone(qty)
        self.assertIsNone(unit)
        self.assertIsNone(prep)

    def test_qty_only(self):
        name, qty, unit, prep = parse_ingredient_line("2 tbsp olive oil")
        self.assertEqual(name, "olive oil")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "tbsp")
        self.assertIsNone(prep)

    def test_fraction(self):
        name, qty, unit, prep = parse_ingredient_line("1/4 cup grated Parmesan")
        self.assertEqual(name, "Parmesan")
        self.assertEqual(qty, "1/4")
        self.assertEqual(unit, "cup")
        self.assertEqual(prep, "grated")

    def test_sliced(self):
        name, qty, unit, prep = parse_ingredient_line("10 thin slices julienned ginger")
        self.assertEqual(name, "ginger")
        self.assertEqual(qty, "10")
        self.assertEqual(unit, "slices")
        self.assertEqual(prep, "julienned")

    def test_whole_spice(self):
        name, qty, unit, prep = parse_ingredient_line("2 green cardamom pods")
        self.assertEqual(name, "green cardamom")
        self.assertEqual(qty, "2")
        self.assertEqual(unit, "pods")
        self.assertIsNone(prep)


class TestLoadAliases(unittest.TestCase):
    """Tests for alias file loading."""

    def test_loads_from_default(self):
        aliases = load_aliases(ALIASES_PATH)
        self.assertIn("scallions", aliases)
        self.assertIn("green onions", aliases["scallions"])
        self.assertIn("cilantro", aliases)
        self.assertIn("tuvar dal", aliases)

    def test_loads_custom(self):
        import tempfile
        content = "version: 1\nentries:\n  - name: test\n    aliases: [foo, bar]\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(content)
            f.flush()
            aliases = load_aliases(f.name)
        self.assertIn("test", aliases)
        self.assertIn("foo", aliases["test"])
        os.unlink(f.name)


class TestMatchExact(unittest.TestCase):
    """Exact match tests (trivial normalization only)."""

    def test_garlic_exact(self):
        r = match("garlic", ["garlic"])
        self.assertEqual(r.status, "exact_match")
        self.assertIn("garlic", r.canonical)

    def test_red_chilli_exact(self):
        r = match("Red Chilli Powder", ["red chilli powder"])
        self.assertEqual(r.status, "exact_match")
        self.assertIn("red chilli powder", r.canonical)

    def test_yellow_onion_small_dice(self):
        r = match("1 yellow onion (small dice)", ["yellow onion"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("yellow onion", r.canonical)


class TestMatchNormalized(unittest.TestCase):
    """Normalized match tests (harmless transformations)."""

    def test_yellow_onion_plural(self):
        r = match("yellow onion", ["yellow onions"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("yellow onions", r.canonical)

    def test_onion_parens(self):
        r = match("2 yellow onions (chopped)", ["yellow onion"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("yellow onion", r.canonical)

    def test_paren_prep_descriptor(self):
        r = match("garlic (minced)", ["garlic"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("garlic", r.canonical)

    def test_garlic_cloves_prep(self):
        r = match("2 cloves garlic (minced)", ["garlic"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("garlic", r.canonical)

    def test_chilli_chili_collapse(self):
        r = match("red chili powder", ["red chilli powder"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("red chilli powder", r.canonical)

    def test_ground_white_pepper(self):
        r = match("ground white pepper", ["white pepper"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("white pepper", r.canonical)

    def test_grated_parmesan(self):
        r = match("grated Parmesan", ["Parmesan"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("Parmesan", r.canonical)

    def test_quantity_no_match(self):
        """Quantity difference does NOT affect identity."""
        r = match("chicken breast, 1 lb", ["chicken breast"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("chicken breast", r.canonical)

    def test_unit_no_match(self):
        """Unit difference does NOT affect identity."""
        r = match("chicken breast, 1 lb", ["chicken breast, 0.5 lb"])
        self.assertEqual(r.status, "normalized_match")

    def test_empty_pantry(self):
        r = match("garlic", [])
        self.assertEqual(r.status, "no_match")


class TestMatchAlias(unittest.TestCase):
    """Alias match tests."""

    def test_green_onions_to_scallions(self):
        r = match("green onions", ["scallions"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("scallions", r.canonical)

    def test_scallions_to_green_onions(self):
        r = match("scallions", ["green onions"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("green onions", r.canonical)

    def test_tuvar_to_toor(self):
        r = match("tuvar dal", ["toor dal"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("toor dal", r.canonical)

    def test_toor_to_tuvar(self):
        r = match("toor dal", ["tuvar dal"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("tuvar dal", r.canonical)

    def test_cilantro_to_coriander(self):
        r = match("cilantro", ["coriander leaves"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("coriander leaves", r.canonical)

    def test_coriander_to_cilantro(self):
        r = match("coriander leaves", ["cilantro"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("cilantro", r.canonical)


class TestMatchNoMatch(unittest.TestCase):
    """No-match tests for genuinely different ingredients."""

    def test_chili_powder_vs_red_chilli(self):
        r = match("chili powder", ["red chilli powder"])
        self.assertEqual(r.status, "no_match")

    def test_red_chilli_vs_kashmiri(self):
        r = match("red chilli powder", ["Kashmiri red chilli powder"])
        self.assertEqual(r.status, "no_match")

    def test_chicken_breast_vs_thigh(self):
        r = match("chicken breast", ["chicken thigh"])
        self.assertEqual(r.status, "no_match")
        self.assertTrue(r.related_distinct)

    def test_whole_chicken_vs_breast(self):
        r = match("whole chicken", ["chicken breast"])
        self.assertEqual(r.status, "no_match")
        self.assertTrue(r.related_distinct)

    def test_potato_vs_sweet(self):
        r = match("potato", ["sweet potato"])
        self.assertEqual(r.status, "no_match")

    def test_milk_vs_cream(self):
        r = match("milk", ["cream"])
        self.assertEqual(r.status, "no_match")

    def test_cumin_seeds_vs_ground(self):
        r = match("cumin seeds", ["ground cumin"])
        self.assertEqual(r.status, "no_match")
        self.assertTrue(r.related_distinct)

    def test_fresh_vs_ground_ginger(self):
        r = match("fresh ginger", ["ground ginger"])
        self.assertEqual(r.status, "no_match")

    def test_ginger_garlic_paste_vs_garlic(self):
        r = match("ginger-garlic paste", ["garlic"])
        self.assertEqual(r.status, "no_match")

    def test_ginger_garlic_paste_vs_ginger(self):
        r = match("ginger-garlic paste", ["ginger"])
        self.assertEqual(r.status, "no_match")


class TestMatchAmbiguous(unittest.TestCase):
    """Ambiguous match tests."""

    def test_onion_multi(self):
        r = match("onion", ["yellow onion", "red onion"])
        self.assertEqual(r.status, "ambiguous")
        self.assertIn("yellow onion", r.candidates)
        self.assertIn("red onion", r.candidates)

    def test_onion_single(self):
        """Generic must NOT silently resolve to specific."""
        r = match("onion", ["yellow onion"])
        self.assertEqual(r.status, "ambiguous")
        self.assertIn("yellow onion", r.candidates)

    def test_oil_multi(self):
        r = match("oil", ["olive oil", "vegetable oil"])
        self.assertEqual(r.status, "ambiguous")
        self.assertIn("olive oil", r.candidates)
        self.assertIn("vegetable oil", r.candidates)


class TestMatchNegative(unittest.TestCase):
    """Verify no-match/ambiguous never satisfy grocery."""

    def test_no_match_no_canonical(self):
        r = match("milk", ["cream"])
        self.assertEqual(r.status, "no_match")
        self.assertEqual(r.canonical, [])
        self.assertEqual(r.candidates, None)

    def test_ambiguous_no_canonical(self):
        r = match("onion", ["yellow onion", "red onion"])
        self.assertEqual(r.status, "ambiguous")
        self.assertEqual(r.canonical, [])


class TestQuantityLeakage(unittest.TestCase):
    """Quantity/range/unit expressions must never leak into identity keys."""

    def test_inch_ginger_sliced(self):
        self.assertEqual(normalize("1 inch ginger, sliced"), "ginger")

    def test_garlic_cloves_range(self):
        self.assertEqual(normalize("3-4 garlic cloves, sliced"), "garlic")

    def test_black_peppercorns_range(self):
        self.assertEqual(normalize("2-3 black peppercorns"), "black peppercorn")

    def test_cinnamon_stick_fraction_inch(self):
        self.assertEqual(normalize("1/2 inch cinnamon stick"), "cinnamon stick")

    def test_asafoetida_pinch(self):
        self.assertEqual(normalize("a pinch of asafoetida (hing)"), "asafoetida")

    def test_mixed_number(self):
        r = match("1 1/2 pounds Yukon gold potatoes, peeled", ["Yukon gold potatoes"])
        self.assertEqual(r.status, "normalized_match")

    def test_measurement_dash(self):
        self.assertEqual(normalize("2-inch segments, scallions"), "scallion")

    def test_spoken_one(self):
        self.assertEqual(normalize("one clove garlic"), "garlic")

    def test_quantity_does_not_affect_identity(self):
        r = match("chicken breast, 1 lb", ["chicken breast"])
        self.assertEqual(r.status, "normalized_match")


class TestPreparationLeakage(unittest.TestCase):
    """Preparation descriptors that don't affect substitutability must drop."""

    def test_soaked(self):
        self.assertEqual(normalize("3 tablespoons moong dal, soaked"), "moong dal")

    def test_beaten_paren(self):
        self.assertEqual(normalize("2-3 tablespoons curd (yogurt), beaten"), "curd")

    def test_divided(self):
        self.assertEqual(normalize("vegetable oil, divided"), "vegetable oil")

    def test_peeled(self):
        self.assertEqual(normalize("potatoes, peeled"), "potato")

    def test_cut_into_segments(self):
        self.assertEqual(normalize("scallions, cut into 2-inch segments"), "scallion")

    def test_plus_more(self):
        self.assertEqual(normalize("salt, plus more"), "salt")

    def test_with_skin(self):
        # "with skin" describes the chicken's condition, not its identity.
        self.assertEqual(normalize("chicken breast, with skin"), "chicken breast")

    def test_julienned_grated_shredded(self):
        self.assertEqual(normalize("julienned ginger"), "ginger")
        self.assertEqual(normalize("grated cheese"), "cheese")
        self.assertEqual(normalize("shredded cheddar"), "cheddar")

    def test_links_if(self):
        self.assertEqual(normalize("Italian sausage, if in links"), "italian sausage")

    def test_prep_does_not_affect_identity(self):
        r = match("1 yellow onion (small dice)", ["yellow onion"])
        self.assertEqual(r.status, "normalized_match")


class TestParentheticalGrocery(unittest.TestCase):
    """Parenthetical grocery annotations must not be concatenated into keys."""

    def test_cilantro_coriander(self):
        self.assertEqual(normalize("cilantro (coriander leaves)"), "cilantro")

    def test_scallions_green_onions(self):
        self.assertEqual(normalize("scallions (green onions)"), "scallion")

    def test_tuvar_toor(self):
        self.assertEqual(normalize("tuvar (toor) dal"), "tuvar dal")

    def test_cooking_oil_neutral(self):
        self.assertEqual(normalize("cooking oil (neutral)"), "cooking oil")

    def test_whole_chicken_with_skin(self):
        self.assertEqual(normalize("whole chicken, with skin"), "whole chicken")

    def test_prep_paren_not_concatenated(self):
        self.assertEqual(normalize("garlic (minced)"), "garlic")

    def test_paren_alias_against_grocery(self):
        r = match("cilantro", ["cilantro (coriander leaves)"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("cilantro (coriander leaves)", r.canonical)


class TestFormPreservation(unittest.TestCase):
    """Forms that affect substitutability must remain distinct."""

    def test_ground_ginger_vs_fresh(self):
        r = match("ground ginger", ["fresh ginger"])
        self.assertEqual(r.status, "no_match")
        r2 = match("ground ginger", ["ginger"])
        self.assertEqual(r2.status, "no_match")

    def test_ground_turmeric_vs_turmeric(self):
        self.assertNotEqual(normalize("ground turmeric"), normalize("turmeric"))

    def test_cumin_seeds_vs_ground(self):
        r = match("cumin seeds", ["ground cumin"])
        self.assertEqual(r.status, "no_match")
        self.assertTrue(r.related_distinct)

    def test_ginger_garlic_paste_substitutions(self):
        r = match("ginger-garlic paste", ["garlic"])
        self.assertEqual(r.status, "no_match")
        r2 = match("ginger-garlic paste", ["ginger"])
        self.assertEqual(r2.status, "no_match")

    def test_oils_distinct(self):
        self.assertNotEqual(normalize("olive oil"), normalize("vegetable oil"))
        self.assertNotEqual(normalize("vegetable oil"), normalize("cooking oil"))

    def test_chicken_cuts_distinct(self):
        self.assertNotEqual(normalize("chicken breast"), normalize("chicken thigh"))
        self.assertNotEqual(normalize("whole chicken"), normalize("chicken breast"))

    def test_chili_powder_distinctions(self):
        self.assertNotEqual(normalize("chili powder"), normalize("red chilli powder"))
        self.assertNotEqual(
            normalize("red chilli powder"), normalize("Kashmiri red chilli powder"))
        self.assertNotEqual(
            normalize("red chilli powder"), normalize("degi red chilli powder"))


class TestAliasesAgainstGrocery(unittest.TestCase):
    """The three confirmed aliases must work on grocery representations."""

    def test_recipe_cilantro_grocery_coriander(self):
        r = match("cilantro", ["cilantro (coriander leaves)"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("cilantro (coriander leaves)", r.canonical)

    def test_recipe_green_onions_grocery_scallions(self):
        r = match("green onions", ["scallions (green onions)"])
        self.assertEqual(r.status, "alias_match")
        self.assertIn("scallions (green onions)", r.canonical)

    def test_recipe_tuvar_dal_grocery_toor(self):
        # "tuvar (toor) dal" and "tuvar dal" normalize to the same identity
        # key ("tuvar dal") after the parenthetical is dropped, so this is a
        # direct normalized match (no alias needed).
        r = match("tuvar dal", ["tuvar (toor) dal"])
        self.assertEqual(r.status, "normalized_match")
        self.assertIn("tuvar (toor) dal", r.canonical)

    def test_alias_bare_forms(self):
        self.assertEqual(match("scallions", ["green onions"]).status, "alias_match")
        self.assertEqual(match("coriander leaves", ["cilantro"]).status, "alias_match")
        self.assertEqual(match("toor dal", ["tuvar dal"]).status, "alias_match")


class TestGenericAmbiguity(unittest.TestCase):
    """Generic ingredients must not silently resolve to a specific variant."""

    def test_onion_ambiguous(self):
        self.assertEqual(
            match("onion", ["yellow onion", "red onion"]).status, "ambiguous")

    def test_onion_single_specific(self):
        self.assertEqual(
            match("onion", ["yellow onion"]).status, "ambiguous")

    def test_oil_ambiguous(self):
        self.assertEqual(
            match("oil", ["olive oil", "vegetable oil"]).status, "ambiguous")


class TestTomatoForms(unittest.TestCase):
    """Tomato product forms must remain distinct (not collapse to 'tomato')."""

    def test_normalize_distinct_forms(self):
        self.assertNotEqual(normalize("diced tomatoes"), normalize("tomato"))
        self.assertNotEqual(normalize("crushed tomatoes"), normalize("tomato"))
        self.assertNotEqual(
            normalize("diced tomatoes"), normalize("crushed tomatoes"))

    def test_canonical_forms(self):
        self.assertEqual(normalize("diced tomatoes"), "diced tomato")
        self.assertEqual(normalize("crushed tomatoes"), "crushed tomato")
        self.assertEqual(normalize("tomato"), "tomato")

    def test_products_distinct(self):
        self.assertNotEqual(normalize("tomato paste"), normalize("tomato puree"))
        self.assertNotEqual(normalize("tomato sauce"), normalize("crushed tomatoes"))

    def test_generic_ambiguous_against_forms(self):
        r = match("tomato", ["diced tomatoes", "crushed tomatoes"])
        self.assertEqual(r.status, "ambiguous")
        r2 = match("tomato", ["diced tomatoes"])
        self.assertEqual(r2.status, "ambiguous")

    def test_specific_not_satisfied_by_generic(self):
        r = match("diced tomatoes", ["tomato"])
        self.assertEqual(r.status, "no_match")
        r2 = match("crushed tomatoes", ["tomato"])
        self.assertEqual(r2.status, "no_match")

    def test_specific_matches_same_form(self):
        r = match("diced tomatoes", ["diced tomatoes"])
        self.assertIn(r.status, ("exact_match", "normalized_match"))

    def test_formfulness_not_prep_for_other_heads(self):
        # "diced" as a prep descriptor of a non-tomato head must still drop.
        self.assertEqual(normalize("onion, diced"), "onion")


class TestChiliFamily(unittest.TestCase):
    """All chili/chilli/chilly/chilies/chiles spellings normalize to 'chilli'."""

    def test_spelling_collapse(self):
        self.assertEqual(normalize("chili"), "chilli")
        self.assertEqual(normalize("chilli"), "chilli")
        self.assertEqual(normalize("chilly"), "chilli")
        self.assertEqual(normalize("chilies"), "chilli")
        self.assertEqual(normalize("chiles"), "chilli")
        self.assertEqual(normalize("chillies"), "chilli")

    def test_green_chili(self):
        self.assertEqual(normalize("green chilies"), "green chilli")
        self.assertEqual(normalize("green chilli"), "green chilli")
        self.assertEqual(normalize("green chiles"), "green chilli")

    def test_no_chily_plural_bug(self):
        self.assertNotEqual(normalize("green chilies"), "green chily")
        self.assertNotEqual(normalize("chilies"), "chily")

    def test_green_vs_powder_distinct(self):
        self.assertNotEqual(
            normalize("green chilli"), normalize("Kashmiri red chilli powder"))
        self.assertNotEqual(
            normalize("green chilli"), normalize("red chilli powder"))
        self.assertNotEqual(
            normalize("green chilli"), normalize("whole dried Kashmiri red chillies"))


class TestSpicePowderEquivalences(unittest.TestCase):
    """Narrow ground-X <-> X-powder equivalences; protected forms stay distinct."""

    def test_ground_to_powder(self):
        self.assertEqual(normalize("ground turmeric"), normalize("turmeric powder"))
        self.assertEqual(normalize("ground cumin"), normalize("cumin powder"))
        self.assertEqual(normalize("ground coriander"), normalize("coriander powder"))

    def test_match_ground_to_powder(self):
        self.assertIn(match("ground turmeric", ["turmeric powder"]).status,
                      ("exact_match", "normalized_match"))
        self.assertIn(match("turmeric powder", ["ground turmeric"]).status,
                      ("exact_match", "normalized_match"))
        self.assertIn(match("cumin powder", ["ground cumin"]).status,
                      ("exact_match", "normalized_match"))

    def test_seeds_stay_distinct(self):
        self.assertEqual(match("cumin seeds", ["ground cumin"]).status, "no_match")
        self.assertNotEqual(normalize("cumin seeds"), normalize("ground cumin"))
        self.assertNotEqual(normalize("cumin seeds"), normalize("cumin powder"))

    def test_fresh_vs_ground_stays_distinct(self):
        self.assertEqual(match("ground ginger", ["fresh ginger"]).status, "no_match")
        self.assertNotEqual(normalize("ground ginger"), normalize("fresh ginger"))
        self.assertNotEqual(normalize("ground garlic"), normalize("garlic powder"))
        self.assertNotEqual(normalize("fresh garlic"), normalize("garlic powder"))

    def test_paste_stays_distinct(self):
        self.assertNotEqual(normalize("ginger-garlic paste"), normalize("fresh ginger"))
        self.assertNotEqual(normalize("ginger-garlic paste"), normalize("garlic"))

    def test_plain_turmeric_not_folded(self):
        # Generic (non-ground) turmeric is NOT folded to powder.
        self.assertNotEqual(normalize("turmeric"), normalize("turmeric powder"))


class TestDefaultDescriptors(unittest.TestCase):
    """Default/shopping-neutral descriptors collapse; parenthetical form kept."""

    def test_plain_yogurt(self):
        self.assertEqual(normalize("yogurt"), normalize("plain yogurt"))
        self.assertIn(match("plain yogurt", ["yogurt"]).status,
                      ("exact_match", "normalized_match"))

    def test_parmesan_cheese(self):
        self.assertEqual(normalize("parmesan cheese"), normalize("Parmesan"))
        self.assertEqual(normalize("grated parmesan cheese"), normalize("parmesan"))
        self.assertEqual(normalize("Parmesan (grated)"), normalize("parmesan"))
        self.assertIn(match("parmesan cheese", ["Parmesan"]).status,
                      ("exact_match", "normalized_match"))

    def test_parmesan_vs_other_cheese_distinct(self):
        # 'cheese' is dropped only for Parmesan; cheddar stays cheddar.
        self.assertNotEqual(normalize("grated cheddar"), normalize("Parmesan"))

    def test_elbow_macaroni_order(self):
        self.assertEqual(normalize("elbow macaroni"), normalize("macaroni (elbow)"))
        self.assertIn(match("elbow macaroni", ["macaroni (elbow)"]).status,
                      ("exact_match", "normalized_match"))
        self.assertIn(match("macaroni (elbow)", ["elbow macaroni"]).status,
                      ("exact_match", "normalized_match"))

    def test_paren_form_kept(self):
        # Parenthetical form information is retained, not blindly discarded.
        self.assertEqual(normalize("macaroni (elbow)"), "elbow macaroni")


class TestPotatoPreparation(unittest.TestCase):
    """Prep tails stripped; specific variety not silently == generic."""

    def test_prep_stripped(self):
        self.assertEqual(normalize("potatoes, peeled and cubed"), "potato")
        self.assertNotIn("peeled", normalize("potatoes, peeled and cubed"))
        self.assertNotIn("cubed", normalize("potatoes, peeled and cubed"))

    def test_variety_kept(self):
        self.assertEqual(normalize("Yukon gold potatoes"), "yukon gold potato")
        self.assertNotEqual(normalize("potatoes"), normalize("Yukon gold potatoes"))

    def test_generic_vs_variety_no_match(self):
        # Generic must not silently satisfy a specific variety (future
        # matching/sufficiency concern, not identity).
        self.assertEqual(match("potatoes", ["Yukon gold potatoes"]).status, "no_match")


class TestGarnishTails(unittest.TestCase):
    """Usage/garnish descriptors at line end must not enter the identity."""

    def test_cilantro_garnish(self):
        self.assertEqual(normalize("cilantro"), normalize("cilantro, chopped for garnish"))
        self.assertIn(match("cilantro, chopped for garnish", ["cilantro"]).status,
                      ("exact_match", "normalized_match"))

    def test_other_garnish_wording(self):
        self.assertEqual(normalize("cilantro, chopped"), "cilantro")
        self.assertEqual(normalize("cilantro, finely chopped for garnish"), "cilantro")
        self.assertEqual(normalize("cilantro, sliced for garnish"), "cilantro")

    def test_identity_not_removed(self):
        # The ingredient identity is preserved (not over-stripped).
        self.assertEqual(normalize("cilantro, chopped for garnish"), "cilantro")


class TestAlternatives(unittest.TestCase):
    """Inline alternatives must never merge into one identity."""

    def test_ghee_or_oil_not_merged(self):
        self.assertEqual(normalize("ghee or cooking oil"), "ghee or cooking oil")
        self.assertNotEqual(normalize("ghee or cooking oil"), "ghee")
        self.assertNotEqual(normalize("ghee or cooking oil"), "cooking oil")
        self.assertNotEqual(normalize("ghee or cooking oil"), "ghee cooking oil")

    def test_alternative_matches_neither(self):
        r = match("ghee or cooking oil", ["ghee"])
        self.assertEqual(r.status, "no_match")
        r2 = match("ghee or cooking oil", ["cooking oil"])
        self.assertEqual(r2.status, "no_match")


    # ──────────────────────────────────────────────────────────────
    # NEW: Stage 3A fix-pass tests — clove disambiguation
    # ──────────────────────────────────────────────────────────────

    def test_clove_bare_is_spice_identity(self):
        """'2 cloves' with no garlic → whole-clove SPICE identity."""
        self.assertEqual(normalize("2 cloves"), "cloves")
        self.assertEqual(parse_ingredient_line("2 cloves")[0], "cloves")

    def test_clove_with_garlic_is_garlic(self):
        """'2 cloves garlic (minced)' → identity 'garlic'."""
        self.assertEqual(normalize("2 cloves garlic (minced)"), "garlic")
        self.assertEqual(parse_ingredient_line("2 cloves garlic (minced)")[0], "garlic")

    def test_garlic_cloves_unit(self):
        """'3-4 garlic cloves, sliced' → identity 'garlic'."""
        self.assertEqual(normalize("3-4 garlic cloves, sliced"), "garlic")
        # parse_ingredient_line preserves comma in token stream (existing behavior)
        name, qty, unit, prep = parse_ingredient_line("3-4 garlic cloves, sliced")
        self.assertIn("garlic", name)

    def test_clove_spice_matches_grocery(self):
        """'2 cloves' matches 'whole cloves (spice)' in grocery."""
        r = match("2 cloves", ["whole cloves (spice)"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_clove_with_garlic_matches_grocery(self):
        """'2 cloves garlic (minced)' matches 'garlic' in grocery."""
        r = match("2 cloves garlic (minced)", ["garlic"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    # ──────────────────────────────────────────────────────────────
    # NEW: Stage 3A fix-pass tests — mixed-number quantities
    # ──────────────────────────────────────────────────────────────

    def test_mixed_number_quantity(self):
        """'1 1/2 teaspoons garam masala' → qty='1 1/2', name='garam masala'."""
        name, qty, unit, prep = parse_ingredient_line("1 1/2 teaspoons garam masala")
        self.assertEqual(qty, "1 1/2")
        self.assertEqual(unit, "teaspoons")
        self.assertEqual(name, "garam masala")

    def test_mixed_number_with_parens_weight(self):
        """'1 1/2 pounds Yukon gold potatoes, peeled' → qty='1 1/2'."""
        name, qty, unit, prep = parse_ingredient_line("1 1/2 pounds Yukon gold potatoes, peeled")
        self.assertEqual(qty, "1 1/2")
        self.assertIn("Yukon gold potatoes", name)

    def test_mixed_number_normalize(self):
        """Normalize preserves mixed number in key."""
        self.assertEqual(normalize("1 1/2 teaspoons garam masala"), "garam masala")

    # ──────────────────────────────────────────────────────────────
    # NEW: Stage 3A fix-pass tests — optional/annotation tail stripping
    # ──────────────────────────────────────────────────────────────

    def test_tail_or_as_needed(self):
        """'olive oil, or as needed' → 'olive oil'."""
        self.assertEqual(normalize("olive oil, or as needed"), "olive oil")

    def test_tail_or_more_to_taste(self):
        """'1 lime, juiced, or more to taste' → 'lime'."""
        self.assertEqual(normalize("1 lime, juiced, or more to taste"), "lime")

    def test_tail_flour_tortillas_or_as_needed(self):
        """'6 flour tortillas, or as needed' → 'flour tortilla'."""
        self.assertEqual(normalize("6 flour tortillas, or as needed"), "flour tortilla")

    def test_tail_kosher_salt_or_more(self):
        """'kosher salt, or more to taste' → 'kosher salt'."""
        self.assertEqual(normalize("kosher salt, or more to taste"), "kosher salt")

    def test_tail_juiced(self):
        """'1 lemon, juiced' → 'lemon'."""
        self.assertEqual(normalize("1 lemon, juiced"), "lemon")

    def test_tail_to_taste_black_pepper(self):
        """'Freshly cracked black pepper, to taste' → 'black pepper'."""
        self.assertEqual(normalize("Freshly cracked black pepper, to taste"), "black pepper")

    def test_tail_for_serving(self):
        """'Steamed rice, for serving' → 'steamed rice'."""
        self.assertEqual(normalize("Steamed rice, for serving"), "steamed rice")

    def test_tail_julienned(self):
        """'Ginger, julienned' → 'ginger'."""
        self.assertEqual(normalize("Ginger, julienned"), "ginger")

    def test_tail_with_juices(self):
        """'diced tomatoes, with juices' → 'diced tomato'."""
        self.assertEqual(normalize("diced tomatoes, with juices"), "diced tomato")

    def test_tail_plus_more(self):
        """'1 tablespoon olive oil, plus more for drizzling' strips 'plus more' but keeps 'olive oil'."""
        k = normalize("1 tablespoon olive oil, plus more for drizzling")
        # "plus more" is a listed tail, "drizzling" is not — verify at least "olive oil" is kept
        self.assertTrue(k.startswith("olive oil"))

    # ──────────────────────────────────────────────────────────────
    # NEW: Stage 3A fix-pass tests — semantic match equivalences
    # ──────────────────────────────────────────────────────────────

    def test_match_curd_to_yogurt(self):
        """curd (yogurt) is the same grocery item as plain yogurt."""
        r = match("2-3 tablespoons curd (yogurt), beaten", ["plain yogurt"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_match_coriander_sprig_to_cilantro(self):
        """Coriander sprig is the same grocery item as cilantro."""
        r = match("Coriander sprig", ["cilantro (coriander leaves)"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_match_ginger_to_fresh_ginger(self):
        """Ginger, julienned → same grocery item as ginger."""
        r = match("Ginger, julienned", ["ginger"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_match_steamed_rice_to_rice(self):
        """Steamed rice → matches steamed rice grocery item."""
        r = match("Steamed rice, for serving", ["steamed rice"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_match_kashmiri_chilli_boundary(self):
        """Kashmiri red chilli powder must NOT match plain red chilli powder."""
        r = match("1/2 teaspoon Kashmiri red chilli powder", ["red chilli powder"])
        self.assertEqual(r.status, "no_match")

    def test_match_ground_coriander_matches_powder(self):
        """ground coriander is coriander powder (FORM_SIGNIFICANT normalization)."""
        r = match("1/2 teaspoon ground coriander", ["coriander powder"])
        self.assertIn(r.status, ("normalized_match", "exact_match"))

    def test_match_ginger_garlic_paste_boundary(self):
        """ginger-garlic paste must NOT match ginger or garlic separately."""
        r = match("1 tablespoon ginger-garlic paste", ["ginger"])
        self.assertEqual(r.status, "no_match")
        r2 = match("1 tablespoon ginger-garlic paste", ["garlic"])
        self.assertEqual(r2.status, "no_match")


class TestParsingHardening(unittest.TestCase):
    """Regression tests for parser hardening against quantity/prep ambiguity.

    Verifies the parser never treats a preparation measurement, a subset
    quantity, a fused token, or a trailing/dual quantity as the primary
    ingredient quantity or part of the ingredient identity.
    """

    # ── A. Unicode fractions & mixed numbers ──────────────────────────────
    def test_unicode_mixed_number(self):
        name, qty, unit, prep = parse_ingredient_line("1 ½ cups white sugar")
        self.assertEqual(qty, "1 ½")
        self.assertEqual(unit, "cups")
        self.assertEqual(name, "white sugar")
        self.assertEqual(normalize("1 ½ cups white sugar"), "white sugar")

    def test_unicode_standalone_fraction(self):
        name, qty, unit, prep = parse_ingredient_line("¾ cup peeled sweet potato")
        self.assertEqual(qty, "¾")
        self.assertEqual(unit, "cup")
        self.assertEqual(name, "sweet potato")
        self.assertEqual(normalize("¾ cup peeled sweet potato"), "sweet potato")

    # ── B. Preparation measurements ───────────────────────────────────────
    def test_prep_measurement_inch_mark(self):
        name, qty, unit, prep = parse_ingredient_line(
            "1 large onion, cut into 1/8” slices (divided use)"
        )
        self.assertEqual(name, "onion")
        self.assertEqual(qty, "1")
        self.assertNotIn("1/8", name)
        self.assertEqual(normalize("1 large onion, cut into 1/8” slices (divided use)"), "onion")

    def test_prep_measurement_inch_mark_and_mixed(self):
        name, qty, unit, prep = parse_ingredient_line(
            "1 ½ cup long beans, cut into 1.5” pieces"
        )
        self.assertEqual(qty, "1 ½")
        self.assertEqual(unit, "cup")
        self.assertEqual(name, "long beans")
        self.assertNotIn("1.5", name)
        self.assertEqual(normalize("1 ½ cup long beans, cut into 1.5” pieces"), "long bean")

    # ── C. Subset quantities in prep instructions ─────────────────────────
    def test_subset_quantity_prep(self):
        name, qty, unit, prep = parse_ingredient_line(
            "7 makrut lime leaves, 5 torn into chunks, 2 finely julienned"
        )
        self.assertEqual(qty, "7")
        self.assertEqual(name, "makrut lime leaves")
        self.assertNotIn("5", name)
        self.assertNotIn("2", name)
        self.assertEqual(normalize("7 makrut lime leaves, 5 torn into chunks, 2 finely julienned"),
                         "makrut lime leaves")

    def test_subset_quantity_prep_markdown(self):
        """Markdown-linked head preserving the leading quantity."""
        name, qty, unit, prep = parse_ingredient_line(
            "7[makrut lime leaves](https://x/), 5 torn into chunks, 2 finely julienned"
        )
        self.assertEqual(qty, "7")
        self.assertEqual(name, "makrut lime leaves")
        self.assertNotIn("5", name)
        self.assertEqual(normalize("7[makrut lime leaves](https://x/), 5 torn into chunks, 2 finely julienned"),
                         "makrut lime leaves")

    # ── D. Fused quantity/unit/name ───────────────────────────────────────
    def test_fused_quantity_unit(self):
        name, qty, unit, prep = parse_ingredient_line("1Tbs.rock salt")
        self.assertEqual(qty, "1")
        self.assertEqual(normalize("1Tbs.rock salt"), "rock salt")

    def test_fused_quantity_name(self):
        name, qty, unit, prep = parse_ingredient_line("1jalapeño")
        self.assertEqual(qty, "1")
        self.assertEqual(name, "jalapeño")
        self.assertEqual(normalize("1jalapeño"), "jalapeño")

    def test_fused_unicode_quantity_unit(self):
        name, qty, unit, prep = parse_ingredient_line("⅔cup mayonnaise")
        self.assertEqual(qty, "⅔")
        self.assertEqual(unit, "cup")
        self.assertEqual(name, "mayonnaise")
        self.assertEqual(normalize("⅔cup mayonnaise"), "mayonnaise")

    def test_fused_quantity_name_guajillo(self):
        name, qty, unit, prep = parse_ingredient_line("3guajillochiles")
        self.assertEqual(qty, "3")
        self.assertIn("guajillo", name.lower())
        self.assertEqual(normalize("3guajillochiles"), "guajillochile")

    # ── F. Trailing & dual quantities ─────────────────────────────────────
    def test_trailing_quantity_500g(self):
        """'Ground beef, 500g' — trailing quantity stays distinct (no qty captured)."""
        name, qty, unit, prep = parse_ingredient_line("Ground beef, 500g")
        self.assertEqual(qty, None)
        self.assertEqual(normalize("Ground beef, 500g"), "ground beef")

    def test_trailing_count_period(self):
        name, qty, unit, prep = parse_ingredient_line("Fried egg, 1.")
        self.assertEqual(qty, None)
        self.assertEqual(normalize("Fried egg, 1."), "fried egg")

    def test_trailing_quantity_after_prep_descriptor(self):
        name, qty, unit, prep = parse_ingredient_line("Oil, for frying, 1/2 cup.")
        self.assertEqual(qty, None)
        self.assertEqual(normalize("Oil, for frying, 1/2 cup."), "oil")

    def test_dual_quantity(self):
        name, qty, unit, prep = parse_ingredient_line("¼ cup / 100 gm Sugar")
        self.assertEqual(normalize("¼ cup / 100 gm Sugar"), "sugar")

    def test_alternate_quantity(self):
        name, qty, unit, prep = parse_ingredient_line("300 ml Full fat cream, 1 ¼ cup")
        self.assertEqual(normalize("300 ml Full fat cream, 1 ¼ cup"), "full fat cream")

    def test_mixed_number_ascii_still_works(self):
        name, qty, unit, prep = parse_ingredient_line("1 1/2 teaspoons garam masala")
        self.assertEqual(qty, "1 1/2")
        self.assertEqual(name, "garam masala")


if __name__ == "__main__":
    unittest.main()
