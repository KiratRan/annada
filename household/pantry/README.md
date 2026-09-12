# Pantry Inventory

This directory contains the canonical household pantry inventory.

Location:

$HOUSEHOLD_ROOT/pantry


The household-wide instructions are:

$HOUSEHOLD_ROOT/ASSISTANT.md


---

# Canonical Source of Truth

The canonical pantry inventory is:

$HOUSEHOLD_ROOT/pantry/inventory.yaml

This file is the sole authoritative source for pantry state.

All planning skills — recommendation-agent, meal-planner,
grocery-list-generator — read pantry state from inventory.yaml.

No other location is authoritative for pantry inventory.


---

# Ownership

The pantry-inventory-manager skill owns:

- inventory.yaml (read and write)
- pantry evidence interpretation
- inventory record creation, modification, and deletion

The pantry-inventory-manager does not:

- call KitchenOwl APIs
- synchronize KitchenOwl data
- treat KitchenOwl catalog entries as pantry availability
- modify KitchenOwl databases or storage

KitchenOwl provides:

- shopping execution state
- shopping-list management
- household item catalog data

KitchenOwl catalog entries do not establish pantry availability.


---

# Rules

Never:

- assume an ingredient exists without an inventory record
- invent pantry items, quantities, or locations
- treat KitchenOwl catalog entries as confirmed stock
- overwrite inventory records without authorization
- mark items consumed without a supported inventory event
- edit Obsidian pantry pages as a source of pantry state


---

# Directory Structure

pantry/

README.md

inventory.yaml


ingredient-aliases.yaml


ingredient_identity.py


test_ingredient_identity.py


---

# Data Sources

Allowed sources for inventory records:

user-provided:

source:
  type: user-provided

confirmed-household:

source:
  type: confirmed-household

kitchenowl-catalog:

source:
  type: kitchenowl-catalog

KitchenOwl catalog entries are informational only. They do not
establish that an item is available in the pantry.


Every inventory record must identify its source and distinguish
availability from catalog presence.


---

# Inventory Item Schema

Each item in inventory.yaml:

name: string
  Required. Canonical ingredient name.

quantity:
  amount: number | null
  unit: string | null

location: pantry | refrigerator | freezer | unknown
  Required. Storage location.

status: available | low | unavailable | unknown | expired
  Required. Planning availability status.

source: user-provided | confirmed-household | kitchenowl-catalog
  Required. Evidence provenance.

requires_verification: boolean
  Required. Whether this item needs a physical confirmation.

last_confirmed: string | null
  ISO-8601 date of last physical confirmation.

notes: string
  Optional. Additional context.


---

# Location

Allowed values:

pantry
refrigerator
freezer
unknown


---

# Status

Allowed values:

available
low
unavailable
unknown
expired

These values describe planning availability.


---

# Evidence Rules

Confirmed available:

Use only when current availability is explicitly supported by:

- a user statement
- a confirmed inventory update
- a reliable stock record

Catalog-only:

A KitchenOwl catalog item may indicate that the household uses or
has considered an ingredient.

It does not prove that the ingredient is currently available.

Catalog-only evidence should be represented as:

  status: unknown
  source: kitchenowl-catalog
  requires_verification: true

Missing:

Use only when:

- the ingredient is explicitly reported as unavailable, or
- the pantry record reliably establishes that it is absent

If the pantry record is incomplete, use unknown.


---

# Grocery List Usage

The grocery-list-generator reads inventory.yaml to:

- exclude confirmed-available ingredients from the shopping list
- flag low items for consideration
- retain unknown and unavailable items as shopping candidates

It must not:

- assume missing items exist
- mark items purchased
- update pantry state


---

# Ingredient Identity Matching (Stage 2)


The pantry workspace includes a deterministic ingredient identity layer,
owned by pantry-inventory-manager.


## Files


ingredient_identity.py


  Deterministic, importable Python module providing parsing,
  normalization, alias resolution, and identity matching.

ingredient-aliases.yaml


  Versioned, explicit, human-authored alias file. Canonical names map to
  recipe-facing aliases.


## What it answers


Whether a recipe ingredient and a pantry item share the same underlying
ingredient identity. It does NOT answer whether the pantry quantity is
sufficient — that is a separate pantry/grocery concern.


## Statuses


The matcher returns exactly one of:

- exact_match
- normalized_match
- alias_match
- no_match
- ambiguous


related_distinct is metadata on no_match, not a separate status.


## Conservative rules


- Ambiguous identity stays UNKNOWN; it never silently matches.
- Generic ingredients do not resolve to specific variants: recipe onion
  vs pantry yellow onion is ambiguous, not a match.
- Multiple plausible pantry candidates => ambiguous.
- no_match and ambiguous results never satisfy a grocery ingredient.
- Aliases are explicit, human-authored, and auditable. The matcher uses
  no LLM, fuzzy matching, or similarity scoring.


## Alias Approval


Aliases require the same approval as modify_pantry_inventory.


---


# Recipe Recommendation Usage

The recommendation-agent may read inventory.yaml to:

- rank recipes using confirmed-available ingredients higher
- identify recipes requiring new purchases
- prioritize pantry-use and waste reduction

It must distinguish:

Verified:
  Item exists in current pantry data.

Unknown:
  Inventory was not available or not confirmed.

Suggested:
  Recipe could use the ingredient.


---

# Validation Rules

Before using pantry data:

Verify:

- inventory.yaml exists and parses successfully
- item names are present
- quantities are preserved when available
- sources are identified

Do not:

- invent inventory
- merge conflicting inventories silently
- treat a snapshot as current without checking timestamps


---

# Data Ownership Summary

Recipes:
$HOUSEHOLD_ROOT/recipes

Meal plans:
$HOUSEHOLD_ROOT/plans

Recommendations:
$HOUSEHOLD_ROOT/recommendations

Grocery planning:
$HOUSEHOLD_ROOT/grocery-lists

Pantry inventory:
$HOUSEHOLD_ROOT/pantry/inventory.yaml
(owned by pantry-inventory-manager skill)

Obsidian presentation:
$OBSIDIAN_VAULT/Pantry/Status.md
(read-only view; never the source of pantry edits)


---

# Future Extensions

Possible future additions:

- expiration tracking
- freezer meal tracking
- leftover tracking
- consumption reconciliation
- KitchenOwl import as staging data (not authoritative)
