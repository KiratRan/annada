# Pantry Inventory Manager Skill

## Purpose

Maintain household pantry records and provide reliable ingredient availability
information for meal planning.

This skill owns the household pantry record. It does not treat external
catalogs or shopping applications as authoritative pantry inventory.

## Household Workspace

The household workspace is:

```
$HOUSEHOLD_ROOT
```

Follow:

```
$HOUSEHOLD_ROOT/ASSISTANT.md
```

before modifying household files.

## Canonical Data Source

The canonical pantry inventory is:

```
$HOUSEHOLD_ROOT/pantry/inventory.yaml
```

This file is the sole authoritative source for pantry state.

All planning skills — recommendation-agent, meal-planner,
grocery-list-generator — read pantry state from this file.

No other location is authoritative for pantry inventory.

## Read Operations

When any skill requests pantry information:

1. Read `$HOUSEHOLD_ROOT/pantry/inventory.yaml`.
2. If the file does not exist or `items` is empty, report that no
   pantry inventory is on file. Do not invent items.
3. For each requested ingredient, search `items` by name.
4. Return the matching item's status, quantity, location, source,
   and `requires_verification` flag.
5. If no match is found, report the ingredient as `unknown`.

Never infer, estimate, or fabricate pantry entries.

## Write Operations

Modifying `inventory.yaml` requires explicit user authorization.

Follow the approval configuration in:

```
$HOUSEHOLD_ROOT/config.yaml
```

Under `automation.approvals.require_confirmation`, the entry
`modify_pantry_inventory` governs whether a confirmation is needed.

Before writing:

1. Read `ASSISTANT.md`.
2. Read the current `inventory.yaml`.
3. Present the proposed change to the user.
4. Wait for authorization.
5. Apply the change.
6. Report what changed.

Do not:

- add items without user authorization
- delete items without user authorization
- overwrite existing records without presenting the change
- invent quantities, locations, or statuses
- silently convert shopping-list items into pantry entries
- automatically import KitchenOwl catalog entries as confirmed stock

## Responsibilities

Maintain:

- available ingredients
- quantities
- expiration information
- storage locations
- storage notes
- availability status
- inventory confidence
- inventory source
- inventory update information

Interpret inventory evidence from:

- user-provided information
- explicitly confirmed household information
- approved inventory records
- future supported inventory events

## Data Ownership

The household pantry record is authoritative for planning.

KitchenOwl provides:

- shopping execution state
- shopping-list state
- household item catalog data
- future inventory events, when supported

KitchenOwl catalog entries do not establish current pantry availability.

The pantry-inventory-manager owns the interpretation and maintenance of
household pantry records.

## Availability Evidence

Every inventory record should distinguish availability from catalog presence.

## Confirmed available

Use `confirmed_available` only when current availability is explicitly
supported by:

- a user statement
- a confirmed inventory update
- a reliable stock record
- a supported inventory event

## Catalog-only

A KitchenOwl catalog item may indicate that the household uses or has
considered an ingredient.

It does not prove that the ingredient is currently available.

Catalog-only evidence should be represented as:
```
availability: unknown
source: kitchenowl_item_catalog
requires_verification: true
```

Do not describe catalog-only items as:

- available
- on hand
- stocked
- confirmed in the pantry

## Missing

Use `missing` only when:

- the ingredient is explicitly reported as unavailable, or
- the pantry record reliably establishes that it is absent

If the pantry record is incomplete, use `unknown` instead of `missing`.

## Expired

Use `expired` only when expiration information or a reliable household
report supports that conclusion.

An expired item must not be treated as available for meal planning.

## Inventory Record Format

When maintaining structured pantry records, prefer:

```
name: beef broth
quantity: null
unit: null
availability: unknown
status: unknown
location: null
source: kitchenowl_item_catalog
requires_verification: true
last_confirmed: null
notes:
  - Listed in KitchenOwl catalog.
  - Current stock has not been confirmed.
```

For confirmed inventory:
```
name: olive oil
quantity: 1
unit: bottle
availability: confirmed_available
status: available
location: pantry
source: user_confirmation
requires_verification: false
last_confirmed: YYYY-MM-DD
```

## Rules
- Never assume pantry staples exist.
- Never treat a KitchenOwl catalog entry as confirmed stock.
- Use only supported inventory evidence.
- Preserve uncertainty when availability is unknown.
- Do not classify an ingredient as missing when pantry coverage is incomplete.
- Ask before deleting inventory entries.
- Do not overwrite existing inventory records without authorization.
- Do not invent quantities, expiration dates, or storage locations.
- Do not silently convert shopping-list items into pantry inventory.
- Do not automatically import KitchenOwl catalog entries into confirmed pantry records.
- All inventory modifications require user authorization (see Write Operations).


## Ingredient Identity Matching (Stage 2)

This skill owns the ingredient identity matching layer, in addition to the
pantry record itself.

### Canonical files

The identity layer consists of two files under the pantry workspace:

- `$HOUSEHOLD_ROOT/pantry/ingredient_identity.py`
  — deterministic, importable Python module.
- `$HOUSEHOLD_ROOT/pantry/ingredient-aliases.yaml`
  — versioned, explicit, human-authored alias file.

### Ownership

`pantry-inventory-manager` owns:

- the canonical pantry namespace (pantry item `name` strings in
  `inventory.yaml`)
- the canonical alias file
- the identity matcher mechanics (parsing, normalization, matching)

`grocery-list-generator` and `recipe-recommendation-agent` CONSUME this
layer via the module. They do not re-implement the matcher.

### What the matcher answers

It answers whether a recipe ingredient and a pantry item share the same
underlying ingredient identity. It does NOT decide quantity sufficiency —
that remains a separate pantry/grocery concern.

### Supported statuses

Exactly five match statuses:

- `exact_match`
- `normalized_match`
- `alias_match`
- `no_match`
- `ambiguous`

`related_distinct` is metadata on `no_match`, not a separate status.

### Conservative matching rules

- Ambiguous identity must remain UNKNOWN rather than silently matching.
- Generic ingredients must not silently resolve to a specific variant:
  recipe `onion` vs pantry `yellow onion` is `ambiguous`, not a match.
- Multiple plausible pantry candidates => `ambiguous`.
- `no_match` and `ambiguous` can NEVER satisfy a grocery ingredient.
- The matcher never uses an LLM, fuzzy matching, embeddings, similarity
  scoring, or implicit semantic guessing.

### Alias approval

Adding or modifying an alias entry in `ingredient-aliases.yaml` requires
the same approval semantics as `modify_pantry_inventory` (see
`$HOUSEHOLD_ROOT/config.yaml` and Write Operations).

### Identity vs sufficiency

The identity module returns only identity match status and a reason. It
never reports whether a pantry quantity is sufficient. Sufficiency
classification is owned by pantry/grocery decision logic, run after a
positive identity match.

## Meal Planning Use

Provide pantry evidence to:

- recipe-recommendation-agent
- household-meal-planner
- grocery-list-generator

Distinguish:

1. Confirmed available ingredients.
2. Catalog-only ingredients requiring verification.
3. Explicitly missing ingredients.
4. Unknown ingredients.

Prioritize:

1. Ingredients confirmed available.
2. Items nearing expiration.
3. Ingredients requiring verification when appropriate.
4. Grocery deals.
5. Additional purchases.

Catalog-only ingredients may influence recipe discovery, but must not be
treated as confirmed pantry items.

## Recipe Recommendation Integration

When providing pantry information to recipe-recommendation-agent:

- preserve the source of each ingredient
- preserve availability confidence
- distinguish catalog-only entries from confirmed stock
- identify ingredients requiring verification
- do not convert unknown availability into available status

The recommendation agent decides how pantry evidence affects recipe ranking.

## Meal Plan Integration

When providing pantry information to household-meal-planner:

- identify confirmed available ingredients
- identify uncertain ingredients
- identify ingredients requiring pantry verification
- identify explicit missing ingredients

The meal planner must preserve uncertainty in preparation notes.

## Grocery List Integration

When providing information to grocery-list-generator:

- confirmed missing ingredients may become grocery candidates
- catalog-only ingredients must become verification candidates
- confirmed available ingredients must not be added
- unknown ingredients must remain unresolved until verified

This skill does not generate or synchronize grocery lists.

## KitchenOwl Separation

KitchenOwl is not part of the active architecture. External catalog data, if
it becomes available, is staging input only — never authoritative.

This skill does not:

- call external application APIs
- modify external application databases
- modify external application storage
- synchronize shopping lists
- infer pantry availability from catalog entries
- treat external catalog entries as current pantry stock
## Reusable Pantry-Maintenance Capability

A deterministic, importable mutation module now exists alongside the canonical
data, mirroring `ingredient_identity.py`:

```
$HOUSEHOLD_ROOT/pantry/pantry_ops.py
$HOUSEHOLD_ROOT/pantry/pantry_mutations.log
$HOUSEHOLD_ROOT/pantry/test_pantry_ops.py
```

`pantry_ops.py` is the ONLY mechanism that mutates `inventory.yaml`. The skill
orchestrates it; the module supplies pure functions and a thin CLI.

### Supported operations

- add (purchased stock)
- consume (used stock)
- adjust (correct stock)
- mark unavailable
- mark low
- verify (read-only)
- batch (validate all, then commit all or none)

### Module API

```python
from pantry_ops import (
    Quantity,            # parse, is_numeric, is_compatible, +/-, to_dict/from_dict
    plan_operations,     # validate + compute proposed state -> Plan (no write)
    commit_plan,         # apply an AUTHORIZED plan + append audit log
    verify_item,         # read-only lookup
    resolve_item,        # identity resolution via ingredient_identity.match()
)
```

### CLI

```
python3 pantry_ops.py verify ITEM
python3 pantry_ops.py plan OP ITEM_QTY [OP ITEM_QTY ...]    # no write
python3 pantry_ops.py commit PLAN.json --approval REF        # write after auth
```

`OP` is one of: `add` | `consume` | `adjust` | `unavailable` | `low`. Batch
ops are passed as repeated `OP ITEM_QTY` pairs (e.g.
`plan add '2 lb chicken breast' consume '1 lb butter'`).

### Mutation workflow (approval boundary)

1. `plan` — `pantry_ops.py` validates identity, units, and quantity arithmetic.
   It emits a plan (JSON) and computes the proposed state. **No write.**
2. Present the plan to the user.
3. Obtain `modify_pantry_inventory` authorization (see Write Operations). One
   approval covers one atomic batch.
4. `commit PLAN.json --approval REF` — only after authorization. The module
   re-validates staleness (inventory hash), applies the whole batch, writes
   `inventory.yaml` (after timestamped `.bak` backup), and appends audit lines.

`pantry_ops.py` NEVER invents quantities, never auto-approves, and never calls
the Hermes approval mechanism itself. Only after an explicit `modify_pantry_inventory`
authorization does the skill invoke `commit`.

### Quantity & identity policy

- Numeric arithmetic only on explicitly compatible units (mass lb/kg/oz/g;
  volume gal/L/ml/cup/tbsp/tsp/fl oz). Incompatible units are rejected with
  the two groups named.
- Coarse values (`full jar`, `1/4 bottle`, `low`, `full`) are preserved
  verbatim and never arithmetically combined.
- Unknown quantity stays unknown.
- Consumption past known available stock is rejected (no negative quantities).
- Existing aliases resolve to the canonical item via `ingredient_identity`.
- Ambiguous matches stay unresolved. No fuzzy/LLM matching.
- New items are flagged `needs_approval` and require the same
  `modify_pantry_inventory` gate.
- `ingredient-aliases.yaml` is never modified by stock operations.
- Canonical inventory records are never renamed by stock maintenance.

### Audit

Every committed mutation appends one JSONL line to
`pantry_mutations.log`: timestamp, operation, canonical item, before/after
state, delta, validation result, approval reference + status, and inventory
SHA-256 before/after. The log is append-only and never rewritten; a timestamped
`.bak` backup of `inventory.yaml` precedes every committed write.

### Tests

`test_pantry_ops.py` (pytest) covers quantity parsing, unit compatibility,
add/consume/adjust, unavailable/low transitions, identity resolution,
ambiguous identity, new items, over-consumption, atomic batch failure, audit
generation, alias-file immutability, plan-doesn't-write, and the approval/
commit boundary. Run with the identity suite:

```
python3 -m pytest test_pantry_ops.py test_ingredient_identity.py
```

## KitchenOwl Separation

KitchenOwl is not part of the active architecture. External catalog data, if
it becomes available, is staging input only — never authoritative.

This skill does not:

- call external application APIs
- modify external application databases
- modify external application storage
- synchronize shopping lists
- infer pantry availability from catalog entries
- treat external catalog entries as current pantry stock
- treat completed shopping items as proof of pantry availability

KitchenOwl / catalog data is staging input only and is never imported into
`inventory.yaml`; any real stock reconciliation goes through `pantry_ops.py`.

## File Safety

Before creating or modifying pantry files:

1. Read $HOUSEHOLD_ROOT/ASSISTANT.md.
2. Inspect the target path.
3. Check for existing records.
4. Follow the household file-safety rules.
5. Ask for authorization when required.

Do not:

- overwrite existing records without approval
- delete records without approval
- modify recipes
- modify meal plans
- modify grocery lists
- modify external application storage

## Output

When reporting pantry information, include:

- ingredient name
- availability
- quantity when known
- expiration when known
- storage location when known
- source
- confidence or uncertainty
- verification requirements

Example:

| Ingredient | Availability | Source | Action |
|---|---|---|---|
| Olive oil | Confirmed available | User confirmation | May be used |
| Beef broth | Unknown | External catalog | Verify pantry |
| Ground beef | Missing | Pantry record | Consider purchase |

## Information Quality

Always distinguish:

Verified:

- information directly supported by an inventory record or source

Unknown:

- information that could not be confirmed

Suggested:

- recommendations based on available evidence

Never present unknown availability as verified inventory.

## Ownership

Pantry records (inventory.yaml):
pantry-inventory-manager

Recipe recommendations:
recipe-recommendation-agent

Meal plans:
household-meal-planner

Grocery lists:
grocery-list-generator

Shopping execution:
household consumer (grocery list)

The pantry-inventory-manager owns the household pantry record, not the
external catalog.
