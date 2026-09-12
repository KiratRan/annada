# Household Workflow Skill

## Purpose

Coordinate household meal planning, grocery management, recipe management, pantry tracking, and grocery promotion workflows.

This skill acts as an orchestrator. It does not replace specialized skills. It determines which household skills should be used and ensures they follow the household rules.

## Household Workspace

The household workspace is:

```
$HOUSEHOLD_ROOT
```

Important locations:

```
$HOUSEHOLD_ROOT/
├── ASSISTANT.md
├── grocery-data/
├── recipes/
├── recipe-imports/
├── plans/
├── grocery-lists/
├── archive/
└── pantry/
```

Before performing household operations:

1. Read:

```
$HOUSEHOLD_ROOT/ASSISTANT.md
```

2. Read additional instructions relevant to the requested task.

Examples:

Recipe operations:

```
$HOUSEHOLD_ROOT/recipes/README.md
```

## Responsibilities

This skill coordinates:

- Grocery store configuration validation
- Grocery advertisement collection
- Pantry inventory management
- Recipe library operations
- Meal planning
- Grocery list generation
- Obsidian presentation publishing

Obsidian presentation publishing is handled by:
```
obsidian-integration
```

This skill only decides when publication should occur.
It does not directly write Obsidian files for niche cases.

Obsidian is the synced visual/presentation layer. Hermes maintains the
canonical household workspace and publishes generated views to Obsidian.

## Orchestration Contract

household-workflow is the entrypoint for household operations.

It:

- identifies the user's objective
- reads household instructions
- gathers required context
- selects specialized skills
- passes information between skills
- enforces approval boundaries
- reports artifacts and unavailable information

It does not:

- implement recipe normalization
- independently rank recipes
- maintain pantry records
- create grocery lists directly
- communicate with external application APIs
- modify files owned by another skill
- treat recommendations as approved
- treat catalog data as confirmed inventory

## Skill Routing

Use the appropriate skill for each task.

### Store validation

Use:

```
grocery-store-config-check
```

For:

- validating stores.yaml
- checking enabled stores
- checking source URLs
- reporting configuration problems

---

### Grocery promotions

Use:

```
grocery-ad-scraper
```

For:

- retrieving weekly ads
- extracting discounts
- identifying sale items
- finding promotional opportunities

Do not claim promotions exist unless they were retrieved or verified.

---

### Pantry management

Use:

```
pantry-inventory-manager
```

For:

- tracking available ingredients
- identifying ingredients already owned
- reducing unnecessary purchases

Do not assume pantry items exist unless recorded.

---

### Pantry Evidence and Availability

Use:

pantry-inventory-manager

for:

- confirmed pantry records
- pantry availability
- inventory updates
- interpreting inventory evidence

Use:

recipe-recommendation-agent

for:

- evaluating recipe ingredients against pantry evidence
- distinguishing confirmed, uncertain, and missing ingredients
- ranking recipes using pantry confidence

Use:

household-meal-planner

for:

- preserving pantry uncertainty in meal-plan notes
- identifying ingredients requiring verification
- scheduling approved recommendations

Do not use household catalog entries as a substitute for pantry records.

### Recipe management

Use:

```
recipe-library-manager
```

For:

- importing recipes
- creating recipes
- checking recipe availability
- maintaining recipe files

Follow:

```
$HOUSEHOLD_ROOT/recipes/README.md
```

before modifying recipe files.

---

### Recipe discovery and suggestions

Use:
```
recipe-recommendation-agent
```

For:

- "What should we eat?"
- "Suggest meals from this week's sales"
- "Find recipes using what we have"
- "What recipes should I add?"

The recommendation agent proposes options.

The meal planner converts approved options into a schedule.

### Meal planning

Use:

```
household-meal-planner
```

For:

- creating meal plans
- selecting recipes
- balancing variety
- considering leftovers
- using available ingredients

Meal plans must only reference recipes that actually exist unless new recipes are explicitly requested.

---

### Grocery lists

Use:

```
grocery-list-generator
```

For:

- generating shopping lists
- combining ingredients
- organizing purchases
- separating pantry staples from required purchases

Grocery list canonical format:

Machine-readable:
$HOUSEHOLD_ROOT/grocery-lists/*.yaml

Human-readable:
$HOUSEHOLD_ROOT/grocery-lists/*.md

The YAML file is authoritative for integrations.
Markdown files are generated views.

---

### Obsidian presentation publishing

Use:
```
obsidian-integration
```

Obsidian is the synced visual/presentation layer over the household
workspace. Its views are generated from canonical artifacts and are
read-only from the household pipeline's perspective.

The household workspace publishes to Obsidian:

- approved meal plans
- corrected, pantry-verified grocery lists
- recipe presentation pages

Hermes is used for:

- recipe discovery and recommendation
- pantry-aware reasoning
- meal-plan generation
- grocery-list generation
- promotion-aware planning
- work-flow orchestration
- publishing generated views to Obsidian

Responsibilities handled by obsidian-integration:

- generate presentation views from canonical artifacts
- link meal-plan entries to recipe pages
- maintain the bidirectional meal-plan/recipe links
- preserve user-authored Obsidian content
- never treat Obsidian as an authority or edit source

This skill must not:

- treat Obsidian as authoritative for household data
- edit Obsidian content as if it were a canonical source
- treat catalog entries as confirmed pantry stock
- silently overwrite user-authored Obsidian content

Generated Obsidian pages are safe to regenerate from canonical data.
User-authored Obsidian content must be preserved.

## Weekly meal planning

When asked:

"Plan dinners for next week using current sales"

Follow:

1. Validate store configuration.
2. Retrieve available grocery promotions.
3. Check pantry inventory.
4. Inspect recipe library.
5. Select suitable recipes.
6. Create meal plan.
7. Generate grocery list if requested.

---

### Grocery list creation

When asked:

"Make my grocery list"

Follow:

1. Read the active meal plan.
2. Read referenced recipes.
3. Check pantry inventory.
4. Remove items already available.
5. Generate categorized grocery list.
6. Save the list under:

```
$HOUSEHOLD_ROOT/grocery-lists/
```

7. Publish the generated list to Obsidian only if requested.

---

### Recipe import

When asked:

"Add this recipe"

Follow:

1. Use recipe-library-manager.
2. Check recipe instructions.
3. Check duplicates.
4. Normalize recipe format.
5. Save only after validation.

## File Safety

This skill must not:

- overwrite existing files without approval
- delete files
- modify application storage directly
- modify canonical artifacts to satisfy presentation needs
- invent recipes
- invent grocery prices
- claim unavailable information exists

Before creating or modifying files:

- verify the target path
- check for existing files
- follow the owning skill's instructions

## Data Ownership

The household workspace is authoritative for household data.

Obsidian is the presentation layer, generated from and subordinate to the
canonical workspace.

| Data | Owner |
|---|---|
| Normalized recipe files | recipe-library-manager |
| Recipe presentation pages (Obsidian, generated) | obsidian-integration |
| Recipe recommendations | recipe-recommendation-agent |
| Meal-plan artifacts | household-meal-planner |
| Meal-plan presentation pages (Obsidian, generated) | obsidian-integration |
| Grocery promotions | grocery-ad-scraper |
| Generated grocery-list artifacts | grocery-list-generator |
| Pantry interpretation and planning evidence | pantry-inventory-manager |
| Pantry records | pantry-inventory-manager |
| Household item catalog | household catalog (config) |
| Approval records | household-workflow |
| Obsidian sync state | obsidian-integration |

Obsidian views must not be silently edited to contradict canonical data.
Presentations are regenerated from canonical artifacts.

## Information Quality Rules

Always distinguish:

Verified:
- information directly found in files or sources

Unavailable:
- information that could not be retrieved

Suggested:
- recommendations or generated ideas

Never present suggestions as facts.

## Planning Rules

Meal plans should consider:

- household size
- available recipes
- pantry inventory
- current discounts
- ingredient reuse
- leftovers
- preparation time
- variety

If required information is missing:

- state what is missing
- make reasonable assumptions only when allowed
- do not silently invent data

## Output Behavior

When completing workflows:

Report:

- what was inspected
- what skills were used
- what files were created or modified
- exact paths of created files
- unknown or unavailable information

Do not claim completion of actions that were not performed.

---
## Household Artifact Lifecycle

Household workflows operate through explicit artifacts.

Lifecycle:

Configuration 
-> Recipe discovery 
-> Recommendation artifact 
-> Recommendation approval 
-> Draft Meal Plan 
-> Meal-plan Approval 
-> Optional Grocery List
-> Obsidian publication

Each artifact has a single owner.

Artifact ownership:

config.yaml
Owner: household configuration

recipes/*.md
Owner: recipe-library-manager

recipes/index.yaml
Owner: recipe-library-manager

recommendations/*.yaml
Owner: recipe-recommendation-agent

approvals/*.yaml
Owner: household-workflow

plans/*.yaml
Owner: household-meal-planner

grocery-lists/*.yaml
Owner: grocery-list-generator

Pantry records
Owner: pantry-inventory-manager

Household item catalog:
Owner: household catalog (config)

Shopping execution state:
Owner: household consumer (grocery list)


## Recommendation Approval

Recipe recommendations are suggestions only.

Workflow:

1. Generate recommendation artifact.
2. Present recommendations for review.
3. Record approval decision.
4. Pass approved selections to household-meal-planner.

Never:

- Treat recommendations as approved meals.
- Create meal plans from unapproved selections.
- Modify recipes during recommendation generation.


## Meal Plan Approval

Meal plans require approval before downstream actions.

Workflow:

household-meal-planner
creates plan

then

approval record

then

grocery-list-generator


Do not generate grocery lists from draft meal plans unless explicitly requested.


## Weekly Planning Orchestration

Command:

hermes household plan-week

Purpose:

Coordinate weekly meal planning through recommendation, human approval,
meal-plan creation, and optional grocery-list generation.

The command does not bypass approval requirements.

Step 1:
Load:

$HOUSEHOLD_ROOT/ASSISTANT.md

$HOUSEHOLD_ROOT/config.yaml


Step 2:
Inspect:

$HOUSEHOLD_ROOT/recipes/

$HOUSEHOLD_ROOT/pantry/

$HOUSEHOLD_ROOT/grocery-data/


Step 3:
Use:

recipe-recommendation-agent

Create:

$HOUSEHOLD_ROOT/recommendations/

Recommendation status:
pending

Recommendations must include:

- recipe references
- reasoning
- pantry influence
- deal influence
- ranking information

Step 4:

Request human approval.

Store approvals under:

$HOUSEHOLD_ROOT/approvals/

Only approved recommendations may be passed to:

household-meal-planner

Step 5:

Use:

household-meal-planner

Create a draft meal plan under:

$HOUSEHOLD_ROOT/plans/

Step 6:

Request meal-plan approval.

Store the meal-plan approval record under:

$HOUSEHOLD_ROOT/approvals/

Only an approved meal plan may proceed to downstream household operations.

Step 7:

If requested, use:

grocery-list-generator

Only generate the grocery list from an approved meal plan unless
the user explicitly requests otherwise. If an exception is requested,
label the resulting list as provisional.

Create the grocery list from the approved meal plan under:

$HOUSEHOLD_ROOT/grocery-lists/

The canonical grocery-list YAML artifact is authoritative for downstream
integrations. Any human-readable Markdown grocery list is a generated view.

Step 8:

Use:

obsidian-integration

Publish the approved household state to the Obsidian vault:

$OBSIDIAN_VAULT

The Obsidian publication should occur after the meal-plan approval and,
when requested, after grocery-list generation.

For weekly meal planning, publish:

- the approved meal plan to `Meals/This Week.md`
- ensure the persistent recipe library is reconciled: every active canonical
  recipe has exactly one persistent `Recipes/<id>.md` page (additive; pages
  are NOT created/deleted according to weekly plan membership)
- keep the Recipe Index (`Recipes/_Recipe Index.md`) current with all active
  canonical recipes
- the current grocery requirements to `Grocery/Current List.md` when a
  grocery list was generated
- the current pantry status to `Pantry/Status.md` when relevant
- the household dashboard as needed

Recipe library reconciliation is a separate, idempotent operation from the
current-week presentation. Weekly publication does NOT regenerate all recipe
pages — only pages whose canonical recipe changed are updated, so a large
persistent library is not rewritten every week when nothing changed.

Meal-plan <-> recipe linking is bidirectional:

- plan -> recipe: recipe-based meal entries in the meal-plan page wikilink
  to their `Recipes/<id>.md` presentation pages
- recipe -> plan: a recipe presentation page links back to `Meals/This Week`
  ONLY when that recipe is scheduled in the current approved plan; otherwise
  the `## 📅 This Week` section is omitted (no stale weekly links accumulate)

External or unresolved meals receive no recipe links.

When a canonical recipe is created or modified, `recipe-library-manager`
regenerates the matching `Recipes/<id>.md` so the Obsidian page stays in
sync with the canonical source.

Archived / removed canonical recipes: removing a recipe from the active
library must not silently delete its Obsidian page. The page is retained and
marked as archived (not in the active recipe library), excluded from the
Recipe Index, and permanently deleted only with explicit user approval.
Use `$HOUSEHOLD_ROOT/archive/` as the canonical archive context.

The Obsidian integration must read the canonical household artifacts and
generate human-readable views. It must not become the authoritative source
for meal plans, grocery lists, or pantry records.

Obsidian publication must not alter the canonical household artifacts.

Requirements:

- the relevant approved artifact exists
- presentation approval exists
- the user explicitly requested publication
- publication is additive or regenerates a generated view
- potentially destructive operations have explicit approval

## Updated Data Ownership

The household workspace is authoritative for all household data:

- recipes
- meal plans
- grocery plans
- preferences
- pantry records
- planning configuration
- household item catalog data
- generated Obsidian presentation pages

Obsidian provides:

- synced visual/presentation views generated from canonical data
- household-facing reading and navigation

Household catalog entries do not establish current pantry availability.

The pantry-inventory-manager owns:

- interpreting pantry evidence
- maintaining household pantry records
- recording confirmed availability
- recording uncertainty

Until inventory-event integration is implemented:

- do not infer pantry availability from an external catalog
- do not update pantry records automatically
- do not treat household catalog entries as confirmed stock
