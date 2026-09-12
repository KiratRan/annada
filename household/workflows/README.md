# Household Workflows

This directory documents household automation workflows.

Location:

$HOUSEHOLD_ROOT/workflows


The household-wide instructions are:

$HOUSEHOLD_ROOT/ASSISTANT.md


---

# Purpose

Workflows define how household skills cooperate.

A workflow:

- coordinates skills
- defines execution order
- defines approval points
- records expected artifacts

A workflow does not replace individual skills.

Each skill remains responsible for its own domain.


---

# Design Principles

Workflows must:

- use existing skills
- preserve ownership boundaries
- require approval before household changes
- use structured artifacts
- avoid duplicate sources of truth


Workflows must not:

- directly modify external application storage
- bypass specialized skills
- invent unavailable data
- silently create files


---

# Weekly Meal Planning Workflow

Command:

hermes household plan-week


Purpose:

Create an approved weekly meal plan and optionally generate a grocery list.


---

# Workflow Sequence


Step 1:

Load household instructions.


Source:

$HOUSEHOLD_ROOT/ASSISTANT.md



Step 2:

Inspect available household data.


Read:

recipes/

pantry/

grocery-data/

config.yaml



Step 3:

Collect external information when available.


Skills:

grocery-ad-scraper

pantry-inventory-manager



Step 4:

Generate meal recommendations.


Skill:

recipe-recommendation-agent


Output:

suggested recipes and reasoning


Status:

recommendation only


No files are modified.


---

Step 5:

Create meal plan.


Skill:

household-meal-planner


Input:

approved recipe selections


Output:

$HOUSEHOLD_ROOT/plans/week-YYYY-MM-DD.yaml


Status:

draft until approved.


---

Step 6:

Request user approval.


Required before:

- grocery generation
- publishing to the Obsidian presentation layer


Approved plan status:

approved


---

Step 7:

Generate grocery list.


Skill:

grocery-list-generator


Input:

approved meal plan


Output:

$HOUSEHOLD_ROOT/grocery-lists/*.yaml


---

Step 8:

Publish approved artifacts to the Obsidian presentation layer.


Skill:

obsidian-integration


Inputs:

- approved meal plan
- corrected grocery list


Output:

- Obsidian plan and grocery views (generated, read-only)


Purpose:

- human-facing visual presentation
- no pantry or inventory authority


---

# Artifact Ownership


Recipes:

Owner:

recipe-library-manager


Location:

$HOUSEHOLD_ROOT/recipes



Meal plans:

Owner:

household-meal-planner


Location:

$HOUSEHOLD_ROOT/plans



Grocery lists:

Owner:

grocery-list-generator


Location:

$HOUSEHOLD_ROOT/grocery-lists



Inventory:

Owner:

pantry-inventory-manager


Location:

$HOUSEHOLD_ROOT/pantry/inventory.yaml


---

# Approval Boundaries


No approval required:

- reading files
- analyzing recipes
- generating suggestions
- explaining options


Approval required:

- creating final meal plans
- modifying recipe files
- creating grocery lists for shopping
- publishing artifacts to the Obsidian presentation layer


---

# Failure Handling


If recipe data is missing:

Report:

- missing recipe
- available alternatives
- required action


Do not:

- create placeholder recipes automatically
- invent ingredients


---

If grocery data is unavailable:

Continue using:

- recipe library
- pantry data
- household preferences


Report:

- unavailable sources
- skipped optimization


---

If Obsidian presentation fails:

Preserve:

- canonical artifacts
- failure details


Do not:

- retry indefinitely
- modify canonical files to work around the failure
- modify pantry inventory locally


---

# Workflow State Model


States:


requested

↓

collecting-data

↓

recommendations-ready

↓

awaiting-approval

↓

approved

↓

artifacts-created

↓

published-to-obsidian


Failure state:


failed


---

# Future Extensions


Possible future workflows:
- pantry reconciliation
- leftover tracking
- freezer inventory planning
- seasonal recipe planning
- automatic shopping reminders


All extensions must preserve:
- household workspace as source of truth
- Obsidian as presentation layer only
- skill ownership boundaries
- explicit approval for mutations