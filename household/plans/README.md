# Meal Plans

This directory contains approved household meal plans.

Location:

$HOUSEHOLD_ROOT/plans

The household-wide operating instructions are:

$HOUSEHOLD_ROOT/ASSISTANT.md

---

# Purpose

Meal plans represent approved household decisions for future meals.

A meal plan defines:

- which recipes will be prepared
- when they will be prepared
- intended servings
- preparation notes
- planned leftover usage

A meal plan does not contain:

- recipe instructions
- recipe ingredients
- grocery lists
- pantry inventory
- purchased item state

---

# Ownership

Meal plans are maintained by:

household-meal-planner

The meal planner uses:

- recipe library
- household preferences
- available ingredients
- grocery promotions
- approved recommendations

---

---

# Workflow Relationship

Meal plans are created from approved decisions.

Typical lifecycle:

recipe-recommendation-agent

        |

        v

recommendation artifact

        |

        v

household-meal-planner

        |

        v

meal plan

        |

        v

grocery-list-generator


The meal plan is the first approved scheduling artifact.

Recommendations remain separate and are not converted directly into grocery lists.

# Directory Structure

plans/

README.md

week-YYYY-MM-DD.yaml

---

# Meal Plan Files

Meal plans use YAML format.

Each saved meal plan should contain:

- version
- metadata
- meals

Example structure:

version: 1

metadata:

  week_start: 2026-09-07

  household_size: 4

  status: approved

  planning_goal:
    -use_pantry
    -minimize_waste
    -use_sales
    -introduce_variety

  constraints:
    max_weeknight_minutes: 45
    dietary:
      - none

  created_by:
    skill: household-meal-planner

  source:
    recommendations_artifact:
        path: $HOUSEHOLD_ROOT/recommendations/week-YYYY-MM-DD.yaml
        approved: true

meals:

  - date: 2026-09-07

    meal_type: dinner

    recipe:

      id: chicken-tikka-masala

      servings: 4

    preparation_notes:

      - Prepare marinade ahead of cooking

    selection:
        reason:
            - uses existing recipe
            - matches household preferences
            - reduces grocery purchases
        confidence:
            level: high

    leftovers:

      planned: true

      usage:

        - Monday lunch

---

# Metadata

Required fields:

metadata:

  week_start:

  household_size:

  status:


---

# Week Start

The beginning date of the planning period.

Format:

YYYY-MM-DD

Example:

week_start: 2026-09-07

---

# Household Size

The number of people the plan is intended to serve.

Do not invent this value.

---

# Status

Allowed values:

draft

review

approved

completed

archived

Meaning:
  draft:
    Generated but not reviewed.

  review:
    Awaiting household approval.

  approved:
    Ready for grocery generation.

  completed:
    Meal period has passed.

  archived:
    Historical record.

Workflow:

recommendations

draft plan

human review

approved plan

grocery generation


Only approved meal plans should be used for automated grocery generation.

---

# Meals

Each meal entry represents one planned meal.

Required fields:

date

meal_type

recipe


---

# Meal Type

Allowed values:

breakfast

lunch

dinner

snack


---

# Recipe References

Recipes are referenced by ID.

Example:

recipe:

  id: chicken-tikka-masala

  servings: 4


Recipe IDs must exist in:

$HOUSEHOLD_ROOT/recipes/index.yaml


The meal plan must not duplicate recipe content.

Do not include:

- ingredients
- instructions
- source metadata

The recipe library remains authoritative.

---

# Recipe Servings

The servings value represents planned usage.

It does not modify the original recipe.

Example:

Recipe library:

servings: 6


Meal plan:

recipe:

  id: chili

  servings: 4


The original recipe file must remain unchanged.

---

# Preparation Notes

Preparation notes are household-specific planning information.

Examples:

- Cook rice ahead of time
- Prepare vegetables the night before

Do not duplicate recipe instructions.

---

# Leftovers

Leftovers describe planned reuse.

Example:

leftovers:

  planned: true

  usage:

    - Tuesday lunch


Leftovers do not represent inventory.

The canonical pantry inventory is maintained at:

$HOUSEHOLD_ROOT/pantry/inventory.yaml

---

# Validation Rules

Before saving:

Verify:

- YAML is valid
- recipe IDs exist
- referenced recipes exist
- dates are valid
- status is valid
- servings are provided when known
- recommendation references are valid when present
- recipe IDs match recipe library IDs
- meal dates fall within planning period


Do not:

- create missing recipes
- modify recipe files
- modify grocery lists
- update pantry inventory directly

---

---

# Grocery Generation Eligibility

Only meal plans with:

status: approved

may be used by:

grocery-list-generator


The grocery generator should:

- read recipe references
- retrieve ingredient data from recipes
- check pantry inventory
- create grocery lists


The meal plan must not contain:

- grocery quantities
- shopping state
- purchased status

# Relationship to Other Systems

Recipe library:

$HOUSEHOLD_ROOT/recipes


Meal plan:

$HOUSEHOLD_ROOT/plans


Grocery generation:

approved meal plan

becomes input for:

grocery-list-generator


Obsidian presentation:

approved meal plan

becomes input for:

obsidian-integration

(presentation layer; not authoritative)

---

# Data Ownership

Recipes:

recipe-library-manager

Meal plans:

household-meal-planner

Grocery lists:

grocery-list-generator

Shopping execution:

household consumer (grocery list)

Inventory:

pantry-inventory-manager

---

# Validation Summary

A valid meal plan must:

- reference existing recipes
- preserve recipe ownership boundaries
- contain approval status
- avoid duplicating recipe data
- avoid acting as inventory state
