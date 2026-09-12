# Grocery List Generator Skill

## Purpose

Create grocery lists from meal plans and recipes.

## Ownership and Boundaries

This skill owns:

- Grocery-list construction
- Quantity aggregation
- Pantry-based inclusion decisions
- YAML and Markdown grocery-list artifacts

This skill does NOT own:

- Ingredient identity matching — it uses `pantry-inventory-manager`'s
  identity layer (`ingredient_identity.py` + `ingredient-aliases.yaml`)
- Pantry record maintenance
- Recipe management
- Meal-plan creation
- Approval decisions
- Grocery purchasing
- Obsidian synchronization
- Marking items purchased

## Workflow

1. Read the requested meal plan.
2. Confirm its approval status.
3. Read every referenced recipe.
4. Extract required, optional, garnish, and substitution ingredients.
5. Resolve ingredient identities using `pantry-inventory-manager`'s identity
   layer (import `ingredient_identity.py` and call `match()`), not free-form
   LLM ingredient-identity judgment. Ambiguous and unmatched identities stay
   as grocery candidates with verification notes.
6. Aggregate compatible quantities.
7. Read pantry records from `pantry-inventory-manager`.
8. Classify each ingredient using pantry evidence.
9. Exclude only confirmed-available quantities.
10. Retain catalog-only and unknown items with verification notes.
11. Assign machine categories.
12. Generate canonical YAML.
13. Generate the human-readable Markdown checklist.
14. Present the result for review.
- Leave approval and Obsidian synchronization to `household-workflow`.

## Whole vs. Partial Item Review Gate (HOUSEHOLD RULE)

When generating a grocery list from a meal plan, the household wants to CHOOSE,
per item, at generation time whether to include items that come as either a
whole animal/product or as specific parts/cuts of it — e.g. whole chicken vs.
chicken breast/thighs, a whole fish vs. fillets, a whole pork shoulder vs.
individual chops.

- Present each such item separately with its quantity and ask:
  `Add to list? Yes / No` (per item).
- This is not chicken-specific: apply it to ANY item pair where the recipe can
  be satisfied by the whole form OR a specific part/cut (part vs. whole).
- Keep the whole-form item and the part/cut items as DISTINCT lines (they have
  different yields and uses; do not merge or collapse them).
- This gate is separate from the pantry-verification identity/substitution
  stage and applies on EVERY grocery-list generation, independent of whether
  the item was already confirmed available or needs buying.
- Do not treat a whole item as satisfying a part/cut line (or vice versa) unless
  the user explicitly confirms that substitution at generation time.

## Rules

- Do not mark items purchased.
- Do not assume ingredients are available.
- Preserve quantities when possible.
- Separate optional ingredients.
- Do not replace an ingredient with a substitute unless the recipe, meal plan, or user explicitly authorizes the substitution.
- Preserve optional ingredients as separate items with `optional: true`.
- Preserve “for serving,” garnish, and alternative ingredients in notes or separate optional items.
- Do not add pantry staples merely because a recipe mentions them unless they are required and their pantry status is unknown or unavailable.
- Preserve item identity separately from quantity.
- Preserve recipe notes separately from shopping item names.
- Do not include sale reasoning in item names.
- Do not generate a normal grocery list from a draft or unapproved meal plan.
- If the user explicitly requests a preview, label it as a draft grocery list.
- Preserve the source meal-plan path and approval status in the output metadata.
- The generator may create a draft or ready-for-review grocery list.
- Approval is owned by `household-workflow`.
- Obsidian synchronization is owned by `household-workflow`.
- This skill must not call any external service directly.
- This skill must not mark items purchased.

## Ingredient Identity Layer (Stage 2)

Use `pantry-inventory-manager`'s identity layer instead of relying on
free-form LLM ingredient identity decisions.

Invoke:

```python
import sys
import sys, subprocess, os
sys.path.insert(0, os.path.expandvars("$HOUSEHOLD_ROOT/pantry"))
from ingredient_identity import match
result = match(recipe_ingredient, pantry_names)
```

- Identity and sufficiency are separate concerns. A positive identity
  match (exact/normalized/alias) establishes SAMENESS only; it says nothing
  about whether the pantry quantity is enough.
- Only a positive identity match AND sufficient quantity may exclude an
  ingredient from the grocery list.
- `no_match` and `ambiguous` results can NEVER satisfy a grocery ingredient.
  They stay on the list with a verification note.
- Do not re-implement normalization, alias resolution, or matching inside
  this skill. Read status from the module and apply inclusion decisions.

## Deterministic Identity Pipeline (Stage 3B)

The recommended integration is the wrapper module bundled with this skill:

```python
from grocery_identity_pipeline import (
    resolve_ingredient,
    evaluate_sufficiency,
    aggregate_quantities,
)
r = resolve_ingredient(recipe_line, pantry_names, pantry_status="unknown")
```

The pipeline sets its own import path: it resolves `ingredient_identity` from the
pantry module under `$HOUSEHOLD_ROOT/pantry`, and finds its own module from
`__file__`. No `sys.path` manipulation or working-directory dependency is needed.

The pipeline wraps the identity layer's `match()`, so it never re-implements
normalization or alias resolution, and never invents a second matching
mechanism. It classifies every recipe ingredient into exactly one of:

- exact_match
- normalized_match
- alias_match
- no_match
- ambiguous
- unresolved_alternative   (an explicit "X or Y" choice, never auto-chosen)

### Separation of concerns (non-negotiable)

- **Identity** (`resolve_ingredient`) only decides sameness. It uses the
  identity layer's statuses exactly.
- **Sufficiency** (`evaluate_sufficiency`) decides whether a confirmed-available
  pantry item covers the required quantity. It is never decided by identity.
- **Aggregation** (`aggregate_quantities`) combines quantities ONLY after
  identities are resolved and ONLY for positively-matched compatible units.
- **Alternatives** are never collapsed. `ghee or cooking oil` stays a
  two-operand choice; the pipeline reports it as `unresolved_alternative`
  and does not silently pick one.
- `no_match`, `ambiguous`, and `unresolved_alternative` NEVER satisfy a
  pantry requirement. Only `exact_match` / `normalized_match` / `alias_match`
  (positive) may proceed to sufficiency, and only a confirmed sufficient
  positive may exclude an item from the list.

### Generic ingredients stay ambiguous

- `onion -> yellow onion`, `oil -> olive oil`, etc. are reported as
  `ambiguous`, never auto-resolved. The grocery list keeps the generic wording
  with a note rather than silently narrowing it.
- Do NOT force `water`, `salt` variants, or other household staples into
  identity just to raise match coverage. Non-shoppable and staple items are a
  grocery-list/policy decision, not an identity requirement.

### Dry-run / preview

Stage 3B ships a non-destructive dry run against the current audited list:

```bash
HOUSEHOLD_ROOT="$HOUSEHOLD_ROOT" python3 "$HOUSEHOLD_ROOT/../skills/grocery-list-generator/scripts/dry_run_3b.py"
```

It emits the per-ingredient classification, sufficiency (inventory-driven),
quantity aggregation, and a regression audit (remains-unchanged / merged /
split / missing / additions) WITHOUT overwriting the canonical grocery list.

## Pantry Evidence

Classify each ingredient as one of:

- confirmed_available
- confirmed_unavailable
- catalog_only
- unknown
- expired
- unmatched

Rules:

- Exclude an ingredient from the grocery list only when confirmed available in sufficient quantity.
- Include confirmed unavailable ingredients.
- Include catalog_only and unknown ingredients unless the user explicitly chooses to omit them.
- Do not interpret a household catalog item as proof of current pantry stock.
- If quantity is unknown, preserve the ingredient as a shopping candidate and add a verification note.
- If an ingredient is expired, include it as a replacement candidate unless the user explicitly confirms it is still usable.

### Example:
    Bad:
        ```
        - name: "Italian sausage (chili mac) — on sale $3.79"
        ```
    Good:
        ```
        - name: "<item name>"
        - quantity: "<quantity>"
        - notes: "Sale opportunity from <store name>"
        ```

## Categories

Machine category values:

- produce
- meat
- dairy
- pantry
- frozen
- bakery
- household
- other

Group:

- Produce
- Meat and seafood
- Dairy and eggs
- Pantry
- Frozen
- Bakery
- Household
- Other

## Output

Generate two representations:

### Canonical format

Machine-readable YAML:
```
$HOUSEHOLD_ROOT/grocery-lists/<name>.yaml
```


The YAML file is the authoritative grocery list source for integrations.

Schema:

```yaml
metadata:
  name: weekly-grocery-list
  week: YYYY-MM-DD
  household_size: number
  source_plan: $HOUSEHOLD_ROOT/plans/example.yaml
  source_plan_status: approved
  generated_at: optional ISO-8601 timestamp
  pantry_checked: true
  pantry_source: $HOUSEHOLD_ROOT/pantry/
  status: draft

items:
  - name: item name
    quantity: amount
    category: category
    optional: false
    notes: optional notes
    pantry_status: confirmed_available
    pantry_source: optional source path or system
    verification_required: false
```

Recommended allowed `pantry_status` values:
- confirmed_available
- confirmed_unavailable
- catalog_only
- unknown
- expired
- unmatched
- not_checked

Example
```
- name: <item name>
  quantity: <quantity>
  category: meat
  optional: false
  notes: Sale opportunity from <store name>
  pantry_status: catalog_only
  pantry_source: household item catalog
  verification_required: true
```

Suggested `status` values:
- draft
- ready_for_review
- approved
- synchronized

## Ingredient Aggregation

- Normalize equivalent ingredient names before combining them.
- Preserve item identity separately from quantity and unit.
- Combine quantities only when the units and ingredient identity are compatible.
- Do not combine ingredients when preparation, variety, or substitution meaningfully differs.
- Preserve recipe-specific notes separately from the normalized shopping item.
- If quantities cannot be safely combined, retain separate quantity entries or explain the ambiguity in notes.
- Do not silently convert uncertain units or package sizes.

Example


```
- name: onion
  quantity: 2 medium
  category: produce
  optional: false
  notes: Used by chili and tacos
```

But these should remain distinct when appropriate


```
- name: green onions
  quantity: 1 bunch
  category: produce
  optional: false
```

### Human format

Markdown checklist

```
$HOUSEHOLD_ROOT/grocery-lists/<name>.md
```

The Markdown file is generated for human review
Do not use Markdown parsing for integrations when a YAML grocery list exists.

---

## Persistence

- By default, return a preview without writing files.
- Write the YAML and Markdown artifacts only when the user or workflow explicitly requests generation.
- When saving, write both representations together.
- Never write only the Markdown representation when a YAML artifact is expected.
- Do not overwrite an existing grocery list without explicit authorization.
- If the target filename already exists, ask whether to replace it or create a new version.

---

The next useful addition after these would be a **`meal-suggestion-engine` skill** that specifically bridges:

`grocery deals → recipe library → meal plan`

without mixing scraping, recipe management, or list generation responsibilities.

## Promotion safeguards (Stage 3D)

- Empty pantry does NOT mean zero identity candidates: `resolve_ingredient` takes `pantry_names` as the identity VOCABULARY. In `dry_run_3b.py` the candidate vocabulary = the audited grocery items with `pantry_status='unknown'` (empty inventory = sufficiency unknown, nothing excluded). Passing a literally empty `[]` candidates makes every line `no_match` — that is the WRONG invocation.
- If the Stage 3C verdict is YES and the preview equals the baseline (0 additions/removals/renames/quantity-changes/merges/splits), faithful promotion writes the validated baseline BYTES back. Do NOT re-serialize YAML via `yaml.dump` (reorders/requotes) or hand-rebuild the Markdown (alters formatting); byte copy preserves the auditable SHA-256.
- Pre-promotion: verify both canonical SHA-256 prefixes == the Stage 3C baseline; on mismatch print `NO — canonical baseline changed; promotion aborted` and stop. Back up to `archive/grocery-lists/<timestamp>/` first, never overwriting an existing backup.
- Post-promotion: run `python3 -m unittest test_ingredient_identity` (151) and `python3 dry_run_3b.py` (25/integration); confirm YAML parses with 67 items, Markdown table data-rows == 67 (the raw row count includes 6 `| Item | Quantity | Notes |` header rows and the `---` separators — exclude those), and the YAML↔MD (identity, quantity) sets are identical; all items `pantry_status=unknown` + `verification_required=true`; `inventory.yaml` still empty; no new KitchenOwl references.
