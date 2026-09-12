# Household Meal Planner Skill

## Purpose

Create meal plans using the household recipe library, available ingredients, grocery deals, and user preferences.

The household workspace is:

`$HOUSEHOLD_ROOT` (the household data root, set via `HOUSEHOLD_ROOT`).

Follow:

- `$HOUSEHOLD_ROOT/ASSISTANT.md`
- `$HOUSEHOLD_ROOT/recipes/README.md`

before modifying household files.

## Responsibilities

- Create daily or weekly meal plans.
- Prefer recipes already in the recipe library.
- Use discounted grocery items when practical.
- Consider:
  - servings
  - leftovers
  - preparation time
  - ingredient reuse
  - variety
  - confirmed pantry items
  - catalog-only ingredients requiring verification
  - grocery deals

## Workflow

Before creating a meal plan:

1. Read household instructions.
2. Inspect available recipes.
3. Identify the approved recommendation artifact supplied by
   household-workflow.

   When invoked as part of household-workflow, an approved recommendation
   artifact is required.

   Do not create a meal plan directly from the recipe library when running
   under household-workflow.
4. Inspect available grocery deals.
5. Inspect pantry evidence, if available.
6. Identify confirmed ingredients and uncertain ingredients.
7. Ask for missing information when it materially affects planning.
8. Select and schedule meals.
9. Preserve pantry uncertainty in preparation notes.
10. Present the meal plan for review.

Required inputs when known:

- Number of people.
- Number of days.
- Meal type.
- Dietary restrictions.
- Confirmed available ingredients.
- Pantry or catalog ingredients requiring verification.
- Grocery deals.

Do not save files unless explicitly requested.

## Recipe Rules

- Never claim a recipe exists unless it is found in `$HOUSEHOLD_ROOT/recipes`.
- Never invent recipe files.
- If the recipe library lacks enough meals:
  - state what exists
  - identify what is missing
  - suggest additions

## Pantry Evidence

Pantry evidence must retain its source and certainty.

### Confirmed available

Ingredients may be treated as available only when the source explicitly confirms current stock, quantity, or availability.

### Catalog-only ingredients

Household catalog entries are not proof of current stock.

A catalog-only ingredient must be described as:

- listed in the household catalog
- availability unknown
- requiring pantry verification

Do not describe catalog-only ingredients as:

- available
- on hand
- already stocked
- confirmed in the pantry

### Missing or unmatched ingredients

An ingredient not found in pantry data may be considered missing only when the pantry source is sufficiently complete.

If pantry coverage is incomplete, classify the ingredient as unknown rather than missing.

### Pantry-check requirement

If a selected recipe contains catalog-only or otherwise uncertain ingredients:

```yaml
requires_pantry_check: true
```

The meal plan should include a preperation note indicating that those ingredients must be verified before cooking.

## Recommendation Artifact Integration

When a recommendation artifact is provided, use its evaluated recommendations and ingredient evidence.

The artifact may contain:

- selected recipe IDs
- servings
- reasoning
- source information
- confidence
- confirmed available ingredients
- catalog-only ingredients
- missing or unmatched ingredients
- pantry-check requirements

Do not reinterpret catalog-only ingredients as confirmed stock.

Only recommendations with:

```yaml
status:
  approved: approved
```

may proceed into the meal plan.

When invoked as part of household-workflow, do not create a meal plan if
there is no approved recommendation artifact.

Stop and report that recommendation approval is required.

Direct evaluation of the recipe library is permitted only when the
household-meal-planner is invoked independently, outside the
household-workflow approval pipeline.

## Weekly Meal Planning Rules

When creating a weekly plan with both lunch and dinner:

### Meal Slots

A standard weekly plan contains:

- 7 dinner slots, one dinner for each day.
- 7 lunch slots, one lunch for each day.
- Exactly one dinner per day.
- Every lunch slot must represent an actual planned meal.

Do not treat approval of a recommendation candidate pool as an instruction
to use every recommended recipe.

The planner must select the recipes that best satisfy the weekly plan based
on:

- meal coverage
- leftover efficiency
- variety
- preparation time
- ingredient reuse
- household size
- available evidence
- applicable constraints

A recipe may be approved but not selected.

### Lunch Planning

Prefer leftover portions from planned dinners for lunch when practical.

Leftovers must be chronologically valid:

- A dinner may provide leftovers only for meals occurring after that dinner.
- A lunch cannot consume leftovers from a future dinner.
- A dinner's planned servings must be sufficient to cover the dinner itself
  and every explicitly assigned leftover portion.
- Do not assign the same leftover portion to multiple meals.

Prefer fresh leftovers over older leftovers.

Do not plan a leftover for a lunch several days after preparation when a
fresher practical option exists.

If a leftover must be frozen to make a later lunch practical, explicitly
record the freezing requirement in the meal plan rather than treating the
portion as ordinary refrigerated leftovers.

### First-Day Lunch

If the planning period begins with no available leftovers and the recipe
library contains no suitable lunch recipe, do not invent a recipe.

The lunch must instead be represented as an explicit external meal or
unresolved lunch requiring user input, according to the meal-plan schema.

Do not use:

```yaml
recipe:
  id: null
```
as an implicit substitute for a planned meal unless the schema explicitly
defines null as a valid external/unresolved meal.

If the current schema cannot represent an external or unresolved lunch,
stop and report that the schema needs to be extended rather than silently
creating an incomplete meal entry.

### Leftover Allocation

When selecting dinner recipes, calculate their usable leftover capacity.

For a household of two:

- A 2-serving dinner normally produces no planned leftovers.
- A 4-serving dinner can provide one additional 2-person lunch.
- A 6-serving dinner can provide two additional 2-person lunches.

Do not assume that a large batch should be stretched across the week.

Use the minimum number of leftover portions necessary to provide practical
lunch coverage while maintaining variety and freshness.

A recipe's stated serving count must reconcile with:

- dinner servings
- all planned leftover servings
- any explicitly retained or frozen servings

### Candidate Pool Selection

The approved recommendation artifact is a candidate pool, not a schedule.

The planner may select a subset of approved candidates.

Do not:

- schedule every approved candidate merely because it was approved
- maximize recipe-library utilization
- create multiple dinner slots for one day
- convert leftover portions into additional dinner slots
- treat approval as a requirement that every candidate appear in the plan

## Pantry Uncertainty

When pantry inventory is unavailable or incomplete:

- ingredient availability remains UNKNOWN
- do not classify unknown ingredients as missing
- do not assume ingredients are available
- preserve the uncertainty in the meal plan

Pantry verification requirements must not change the meal schedule unless
the workflow explicitly provides new pantry evidence.

## Grocery Deal Integration

When grocery deals are available:

- Prefer recipes using discounted ingredients.
- Do not select meals only because ingredients are discounted.
- Avoid unnecessary purchases.
- Mention which deals influenced recommendations.

## Output

The meal planner produces two views of the meal plan:

1. A canonical machine-readable YAML artifact.
2. A human-readable Markdown view.

The YAML artifact is authoritative for downstream integrations. The Markdown
file is a generated human-readable view and must not become a second source of
truth.

### Weekly Plan Structure

When the requested planning period is a full week with lunch and dinner:

- Create exactly 7 lunch entries.
- Create exactly 7 dinner entries.
- Create exactly one dinner entry for each calendar day.
- Create exactly one lunch entry for each calendar day.
- Do not omit a meal slot merely because the recipe library lacks a suitable
  recipe.
- Do not invent a library recipe to fill a missing slot.
- Use an external or unresolved meal entry when necessary.

### Canonical YAML Artifact

Create the canonical meal plan under:

`$HOUSEHOLD_ROOT/plans/`

using the filename:

`week-YYYY-MM-DD.yaml`

where `YYYY-MM-DD` is the Monday week-start date.

The meal plan must contain:

```yaml
version: 1

metadata:
  week_start: YYYY-MM-DD
  household_size: <number>
  status: draft
  planning_goal:
    - <goal>
  constraints:
    max_weeknight_minutes: <number>
    dietary:
      - <constraint>
  created_by:
    skill: household-meal-planner
  source:
    recommendations_artifact:
      path: $HOUSEHOLD_ROOT/recommendations/week-YYYY-MM-DD.yaml
      approved: true

meals:
    # Normal recipe-backed meal
  - date: YYYY-MM-DD
    meal_type: dinner
    meal_source: recipe
    recipe:
      id: <recipe-id>
      servings: <number>
```
Meal entries normally reference a recipe from the household recipe library.

For meals that cannot be represented by a library recipe, the `recipe`
field may instead be omitted and the meal must explicitly declare its type:

```
    # Meal that is intentionally outside the recipe library
  - date: YYYY-MM-DD
    meal_type: lunch
    meal_source: external
    servings: 2
    description: <meal description>
```

If the planner cannot determine an appropriate meal:

```
    # Meal slot exists, but planner cannot determine the meal
  - date: YYYY-MM-DD
    meal_type: lunch
    meal_source: unresolved
    servings: 2
    description: <reason the meal is unresolved>
```

meal_source values:

recipe — meal references a recipe in the household recipe library.
external — meal is intentionally outside the recipe library.
unresolved — a meal slot exists but the planner cannot determine the
meal from available evidence.

When meal_source is recipe, the meal must contain:

```
recipe:
  id: <recipe-id>
  servings: <number>
```

The recipe ID must reference an existing recipe.

When meal_source is external or unresolved, do not invent a recipe ID.

An external or unresolved meal must be clearly represented in the Markdown
view and must not be treated as a household recipe.

Do not use:

```
recipe:
  id: null
```

to represent an external or unresolved meal.

```
    preparation_notes:
      - <note>
    selection:
      reason:
        - <reason>
      confidence:
        level: high
    leftovers:
      planned: true
      usage:
        - <usage>
```

Required metadata:

- week_start
- household_size
- status

Allowed meal-plan statuses:

- draft
- review
- approved
- completed
- archived

The initial meal plan created by the planner must have:
`status: draft`

The planner must not mark a meal plan as approved. Approval is handled by
`household-workflow`.

Each meal must include:

- date
- meal type
- servings

Recipe meals must additionally include a valid recipe reference.

External and unresolved meals must include a `meal_source` and a clear description.

When applicable, include:

- preparation notes
- selection reasons
- confidence
- leftover planning
- ingredients requiring pantry verification

Recipe IDs must reference recipes that actually exist in:

`$HOUSEHOLD_ROOT/recipes/`

Do not copy recipe instructions, ingredient lists, or source metadata into the
meal-plan artifact. The recipe library remains authoritative for recipe
content.

### Human-Readable Markdown View

Also create a human-readable Markdown view under:

`$HOUSEHOLD_ROOT/plans/`

using the filename:

`week-YYYY-MM-DD.md`

The Markdown view should contain:

- week/date range
- household size
- scheduled meals
- recipe names
- servings
- preparation notes
- confirmed available ingredients
- ingredients requiring pantry verification
- new ingredients required
- leftover suggestions when useful

Example:


```
## Monday

Meal: Creamy Beef and Spinach Pasta

Servings: 2

Preparation notes:
- Verify beef broth and baby spinach before cooking.
- Ground beef is not confirmed in the available pantry data.

Confirmed available:
- olive oil

Ingredients requiring pantry verification:
- beef broth
- baby spinach

New ingredients required:
- ground beef
- pasta
- heavy cream

Leftovers:
- Suitable for one additional lunch portion.
```

The Markdown view is generated from the meal-plan data and must remain
consistent with the canonical YAML artifact.

Do not treat the Markdown view as authoritative for downstream integrations.

## Artifact Safety

When invoked as part of `household-workflow`, creating the meal-plan artifacts
is part of the planner's normal responsibility and does not require a separate
request to save them.

Before creating either artifact:

1. Check whether the target file already exists.
2. Preserve useful existing information unless the workflow explicitly owns
the content being regenerated.
3. Do not silently overwrite an existing approved meal plan.
4. Do not delete existing meal-plan artifacts.
5. Verify both artifacts after writing.

A draft meal plan may be regenerated while it remains under planner ownership.
An approved meal plan must not be replaced without explicit authorization.

The YAML artifact is the authoritative meal-plan artifact for downstream
workflow steps.

The Markdown artifact is a generated human-readable view.

## Grocery Handoff

The meal planner does not assume that uncertain ingredients are missing.

- Confirmed missing ingredients may be passed to grocery-list-generator.
- Catalog-only ingredients should be passed as pantry verification candidates.
- Confirmed available ingredients should not be proposed for purchase.
- Unknown ingredients require clarification or verification.

The meal planner does not directly synchronize any external system.

## Ownership

Recipe authority:
recipe-library-manager

Recommendation authority:
recipe-recommendation-agent

Meal-plan authority:
household-meal-planner

Grocery-list authority:
grocery-list-generator

Shopping execution:
household consumer (grocery list)

The meal planner creates schedules from approved recommendations and available evidence. It does not modify recipes, approve recommendations, or execute shopping.

household catalog
    ↓
Catalog-only pantry evidence
    ↓
recipe-recommendation-agent
    ↓
Evaluated recommendation artifact
    ↓
Human approval
    ↓
household-meal-planner
    ↓
Meal plan
    ↓
grocery-list-generator
    ↓
household consumer (grocery list)
