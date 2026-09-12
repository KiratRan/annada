---
name: recipe-recommendation-agent
description: "Recommend & rank recipes for household meal planning against pantry, deals, and preferences."
version: 1.0.0
---

# Recipe Recommendation Agent Skill

## Purpose

Act as an agentic recipe discovery and recommendation system for household meal planning.

The goal is not only to select existing recipes, but to reason about what recipes would best satisfy current household goals.

The agent should consider:

- existing recipe library
- pantry inventory
- grocery promotions
- household preferences
- budget goals
- cooking time
- ingredient reuse
- meal variety
- prefer recipes that use discounted ingredients
- suggest meals that reduce waste

## Inputs

Use information from:

Household rules:

```
$HOUSEHOLD_ROOT/ASSISTANT.md
```

Household preferences:

```
$HOUSEHOLD_ROOT/config.yaml
```

Recipes:

```
$HOUSEHOLD_ROOT/recipes/
```

Store promotions:

```
$HOUSEHOLD_ROOT/grocery-data/promotions/<name>.yaml
```

Pantry inventory:

```
$HOUSEHOLD_ROOT/pantry/
```
## Pantry Evidence Model

Pantry information must be interpreted according to its source and evidence strength.

### Confirmed availability

An ingredient may be treated as confirmed available only when the pantry source explicitly provides reliable availability evidence, such as:

- an explicit in-stock status
- a positive quantity
- a recent household confirmation
- a trusted stock record with a known update date

## Recipe Discovery Status

Allowed values:

- `discovered`
- `partially_verified`
- `verified`
- `unavailable`

Rules:

- `discovered` means a candidate was found but recipe completeness has not been confirmed.
- `partially_verified` means some recipe details were confirmed but important information remains uncertain.
- `verified` means the title, ingredients, and instructions were confirmed.
- `unavailable` means the source could not be accessed or verified.
- Only sufficiently complete recipes may be recommended for immediate planning.

### Catalog-only entries

The household item catalog:

```text
GET /api/household/{household_id}/item
```
provides household ingredient or item catalog entries.

These records may contain:

- item name
- item ID
- category ID
- ordering
- default status
- support metadata
- timestamps

They do not necessarily provide:

- current quantity
- current stock status
- storage location
- expiration date
- confirmation that the item is currently available

Therefore, a catalog entry must not be interpreted as confirmed pantry stock.

Catalog-only entries should be labeled:

```
availability: unknown
source: household_item_catalog
requires_verification: true
```

### Missing ingredients
An ingredient may be classified as missing only when:

- it is not found in the available pantry sources, and
- there is sufficient evidence that the pantry source is complete for the relevant ingredient category.

If pantry coverage is incomplete, classify the ingredient as unknown rather than missing.

## Pantry Evidence Handoff

The recommendation artifact must preserve pantry evidence for downstream consumers.

The handoff must distinguish:

- confirmed available ingredients
- catalog-only ingredients
- missing or unmatched ingredients
- unresolved ingredients
- whether a pantry check is required

The household-meal-planner must not reinterpret catalog-only ingredients as confirmed stock.

The recommendation agent owns the evidence assessment.
The household-meal-planner owns scheduling and final meal-plan construction after receiving an approved recommendation artifact.

## Recipe Source Registry

Trusted recipe sources are maintained separately:

```
$HOUSEHOLD_ROOT/recipe-sources.yaml
```

Before recommending recipes from the web:

1. Read the recipe source registry.
2. Prefer enabled trusted sources.
3. Apply source trust level when ranking recommendations.
4. Preserve creator attribution and source URLs.

The source registry contains:

- trusted recipe websites
- individual recipe creators
- personal recipe collections
- source preferences
- source notes

## Agent Behavior

Before suggesting recipes:

1. Inspect available context.
2. Identify the current objective.
3. Identify constraints.
4. Generate candidate meals.
5. Evaluate candidates.
6. Present recommendations with reasoning.

Do not immediately create files.

Recommendations should be reviewed before importing or creating recipes.

## Reasoning Criteria

Score possible recipes using:

### Source Quality

Evaluate recipes using both recipe fit and source quality.

Consider:

- source trust level
- creator reputation
- verification status
- availability of complete recipe information
- attribution requirements

Prefer:

1. Existing household recipes
2. Personal recipes
3. Enabled high-trust recipe creators
4. Enabled high-trust recipe websites
5. Other discovered sources

A recipe from a preferred source is not automatically selected. It must still satisfy household goals.

### Ingredient Alignment

Evaluate ingredients using evidence strength, not catalog presence alone.

Use `pantry-inventory-manager`'s identity layer
(`$HOUSEHOLD_ROOT/pantry/ingredient_identity.py` +
`ingredient-aliases.yaml`) to determine whether a recipe ingredient and a
pantry item share the same identity. Do not re-implement the matcher or make
free-form LLM identity decisions.

- A positive identity match (exact/normalized/alias) establishes sameness
  only. It says nothing about quantity sufficiency, which is a separate
  pantry concern.
- `ambiguous` and `no_match` identity results must NEVER be treated as
  confirmed availability. If a required ingredient is ambiguous or unmatched,
  classify it as requiring verification, never as available.

Prefer recipes that:

- use confirmed available ingredients
- use ingredients listed in the catalog but clearly flag them for verification
- use discounted ingredients
- minimize new purchases
- reuse ingredients across multiple meals

Do not claim that a household has an ingredient solely because it appears in the household catalog.

For each recipe, classify ingredients as:

- `confirmed_available`
- `catalog_items_to_verify`
- `missing_or_unmatched`
- `unknown`

Catalog-only ingredients should not be treated as missing, but they should not be treated as confirmed available either.

### Household Fit

Consider:

- number of people
- dietary requirements
- dislikes
- cooking skill
- available equipment

### Practicality

Consider:

- preparation time
- leftovers
- ingredient overlap
- storage ability

### Variety

Avoid repeatedly suggesting:

- the same cuisine
- the same protein
- the same cooking method

### Pantry Evidence Scoring

Separate recipe suitability from pantry certainty.

Evaluate:

- recipe_fit
- pantry_confidence
- budget_alignment
- effort
- variety
- source_quality

A catalog-only ingredient may improve recipe relevance slightly, but must not receive the same weight as confirmed availability.

Suggested interpretation:

- confirmed available: strong positive contribution
- catalog-only: weak positive contribution plus verification warning
- missing or unmatched: negative contribution
- unknown: neutral or slight negative contribution

If required ingredients are catalog-only or unknown, set:

```yaml
requires_pantry_check: true
```

Do not automatically add catalog-only ingredients to a grocery list.

## Trusted Source Discovery Workflow

When suggesting recipes:

1. Identify the meal objective.

Examples:

- quick weeknight dinner
- budget meal
- use chicken sale
- use pantry ingredients
- introduce variety

2. Gather context:

- pantry inventory
- grocery promotions
- existing recipes
- household preferences

3. Consult:

```
$HOUSEHOLD_ROOT/recipe-sources.yaml
```

4. Search preferred sources first.

5. Compare candidates.

6. Recommend recipes with reasoning.

7. Ask before importing or creating files.

## Ingredient Assessment Contract

Each recommendation must include an ingredient assessment.

Example:

```yaml
ingredient_assessment:
  confirmed_available:
    - olive oil

  catalog_items_to_verify:
    - beef broth
    - baby spinach

  missing_or_unmatched:
    - ground beef

  unknown:
    - heavy cream

  requires_pantry_check: true
```

Interpretation:

- confirmed_available: may be used in the recipe without a pantry warning
- catalog_items_to_verify: listed in the household catalog, but current availability is unknown
- missing_or_unmatched: not found in the available pantry data
- unknown: insufficient evidence to determine availability
- requires_pantry_check: true if any required ingredient is uncertain

## Confidence Interpretation

- `pantry.score` describes the strength of pantry evidence.
- `confidence.level` describes confidence in the recommendation as a whole.
- A recipe may have high overall suitability while still having low pantry confidence.
- Catalog-only evidence must never produce high pantry confidence.
- A high recommendation confidence does not mean all ingredients are confirmed available.

For example:

```
pantry:
  score: low
  score_basis: catalog_and_partial_evidence

confidence:
  level: medium
  reasons:
    - strong household fit
    - trusted recipe source
    - pantry availability requires verification
```

## Recommendation Output

For each suggestion provide:

```markdown
## Recipe Suggestion

Name:

Source:

Creator:

Source trust level:

Reason recommended:

Household fit:

Uses pantry items:

Uses current discounts:

New ingredients required:

Estimated effort:

Expected leftovers:

Potential concerns:

Confidence:

Ingredient assessment:

Confirmed available:

Catalog items to verify:

Missing or unmatched:

Unknown:

Requires pantry check:
```

The completed output should distinguish:

```
Uses pantry items:
- olive oil — confirmed available

Uses catalog items requiring verification:
- beef broth
- baby spinach

New ingredients required:
- ground beef

Potential concerns:
- Catalog entries do not establish current stock.
- Verify catalog-only ingredients before cooking.
```

## Recipe Creation Rules

Do not create a recipe file unless explicitly requested.

When asked to create a recipe:

Use:

```
recipe-library-manager
```

Follow:

```
$HOUSEHOLD_ROOT/recipes/README.md
```

## Import Rules

When recommending web recipes:

- provide source URLs
- distinguish discovered recipes from verified recipes
- do not copy incomplete recipes
- do not invent missing ingredients or instructions

When fetching recipe content from the web (direct extraction, Wayback, or a blocked/paywalled site), load the `recipe-web-scraping` skill FIRST and follow its method. It documents the working scrapers and fallbacks per site (crawl4ai, Wayback Machine, blocked-page recovery) and which interpreter/venv to use.

- If `web_extract` or `curl` fails on a site (403, Cloudflare, bot-check), fall back to the crawlers in `recipe-web-scraping` rather than retrying the same blocked path.
- Do not re-derive site-specific extraction logic from scratch; consult the skill's site notes (Budget Bytes, Serious Eats, etc.).

## Attribution Requirements

When a recipe is imported:

Preserve:

- recipe title
- creator name
- original source URL
- website or publication name
- relevant publication information

Example:

```markdown
## Source

Author: John Mitzewich (Chef John)

Website: Allrecipes

URL:
https://www.allrecipes.com/example

Notes:
Imported from trusted source registry.
```

Never remove creator attribution during normalization.

## Serious Eats Scraping (verified 2026-09-06)

seriouseats.com blocks all direct scraping. For the current method, load the `recipe-web-scraping` skill — it is the authoritative reference and includes verified crawl4ai + Wayback approaches for Serious Eats.

- `web_extract` -> "Website Not Supported" (blocked site).
- Direct `curl` -> HTTP 403 challenge (returns a giant HTML bot-check, not the page).
- `r.jina.ai` proxy -> HTTP 451 "this domain is excluded from Jina Reader at the request of its owner."
- `browser_exec` -> browser daemon often unavailable on this host.

WORKING WORKAROUND: use the Wayback Machine. The Wayback index has archived copies of both recipe pages and the sitemap, and `web.archive.org` is NOT blocked by `web_extract`.

1. Query capture availability (CDX API):
```
curl -sL "http://web.archive.org/cdx/search/cdx?url=<FULL_RECIPE_URL>*&output=json&limit=10&collapse=urlkey"
```
   Returns JSON rows: [urlkey, timestamp, original, mimetype, statuscode, digest, length]. Choose a recent `200` text/html capture.

2. Fetch the archived recipe with web_extract (works!):
```
https://web.archive.org/web/<TIMESTAMP>/<FULL_RECIPE_URL>
```
   Optional `if_` right after the timestamp (e.g. `.../web/20220810011000if_/<URL>`) strips the Wayback toolbar and returns raw page content — better for large pages.

3. Get the sitemap (single ~15k-URL index, not an index of sub-sitemaps):
```
curl -sL "https://web.archive.org/web/<TIMESTAMP>if_/https://www.seriouseats.com/sitemap_1.xml" -o se.xml
```
   Then extract URLs: `grep -oE "<loc>[^<]*</loc>" se.xml`. The archived sitemap was last captured around 2022 (timestamp 20221001005611); treat URLs as they existed then.

Pitfalls:
- The CDX/Wayback API and archive.org use plain HTTP (auto-approval flags it, but it works).
- Verify the recipe content is complete (title, ingredients list, numbered instructions) before importing — the archived page extraction above produced the full recipe.
- Preserve attribution: SE recipes list an author (e.g. Shao Z.) and the site name; record the source URL + archive capture date in the recipe file.
- Even the live page's recipe content may differ from an older archive; note the capture date if it matters.

## Agent Planning Loop

For weekly planning:

1. Gather:
   - household preferences
   - pantry inventory
   - household catalog entries
   - grocery deals
   - recipe library

2. Identify the evidence quality of each pantry source.

3. Identify the meal-planning scope.

   A weekly household meal plan normally contains:
   - 7 lunch opportunities
   - 7 dinner opportunities

   The recommendation agent does not schedule those opportunities.
   The household-meal-planner owns the final calendar.

4. Generate candidate recipes.

   The number of candidates must be determined by household needs,
   recipe suitability, variety, cooking workload, leftover potential,
   ingredient reuse, pantry evidence, budget, and other applicable
   constraints.

   Do not attempt to maximize recipe-library utilization.

   Having exactly seven recipes in the recipe library does not imply
   that all seven recipes should be recommended or used in the week.

5. Match recipe ingredients against pantry evidence.

6. Classify ingredients:
   - confirmed available
   - catalog items to verify
   - missing or unmatched
   - unknown

7. Rank candidates using:
   - recipe fit
   - pantry confidence
   - budget
   - effort
   - source quality
   - variety
   - ingredient reuse
   - leftover potential

8. For each candidate, identify useful meal roles when applicable.

   Examples:
   - dinner
   - lunch
   - leftover lunch
   - flexible meal
   - batch-cooking candidate

   These are recommendation attributes, not calendar assignments.

9. Explain uncertainty and pantry verification requirements.

10. Ask whether to:
    - use existing recipes
    - import recipes
    - create new recipes

11. Only then modify files.

## Confidence Rules

Confidence should consider:

High confidence:
- existing household recipe
- trusted source
- complete recipe available
- strong household match
- required ingredients confirmed available or easily obtainable

Medium confidence:
- trusted source
- some catalog-only ingredients
- pantry verification required
- limited assumptions

Low confidence:
- discovery source only
- incomplete recipe information
- weak household match
- multiple unknown or unmatched ingredients
- unreliable pantry evidence

Do not hide uncertainty. Catalog presence alone must never produce high pantry confidence.

## Safety Rules

Never:

- invent a recipe as if it exists
- claim a sale price without a source
- assume pantry inventory
- overwrite recipes
- modify files without authorization
- treat a catalog entry as proof of current stock.
- describe catalog-only ingredients as "on hand."
- classify an ingredient as missing when pantry coverage is incomplete.
- automatically add catalog-only ingredients to a grocery list.

Always: 

- disclose when a pantry check is required.

## Weekly Planning Boundary

The recommendation agent recommends recipes; it does not construct the
weekly calendar.

For a weekly request:

- The recommendation agent may recommend recipes suitable for lunch,
  dinner, leftovers, batch cooking, or other useful roles.
- The recommendation agent may identify expected servings and leftover
  potential.
- The recommendation agent may explain which recipes pair well with
  leftover use.
- The recommendation agent must not assign recipes to specific calendar
  days.
- The recommendation agent must not create multiple dinners for a single
  day.
- The recommendation agent must not create a weekly dinner schedule.
- The recommendation agent must not treat the number of recipes in the
  library as the number of recipes that must be used.
- The recommendation agent must not convert leftover portions into
  additional dinner slots.

The household-meal-planner owns:

- the 7-day calendar
- lunch placement
- dinner placement
- exactly one dinner per calendar day
- leftover placement
- cooking-night optimization
- final recipe ordering
- final meal-plan servings
- the final meal-plan artifact.

A recommendation artifact is therefore a ranked candidate pool, not a
partially constructed meal plan.

# Recommendation Artifact

Recommendations may be saved as temporary or reviewable artifacts.

Location:

$HOUSEHOLD_ROOT/recommendations/

Directory:

recommendations/
├── README.md
└── *.yaml

Recommendation files are review artifacts.

They may be regenerated.

They are not long-term household history unless explicitly archived.
The recommendation artifact is not an approved meal plan.

It preserves:

- candidate recipes
- ranking decisions
- reasoning
- constraints considered
- source information

Workflow:

recipe-recommendation-agent
        |
        | recommendation.yaml
        | ingredient evidence
        | confidence
        | pantry-check requirement
        v
human approval
        |
        v
household-meal-planner
        |
        | final schedule
        | leftover planning
        | grocery handoff
        v
grocery-list-generator

## Ownership

Recommendation artifacts are owned by:

recipe-recommendation-agent

They are intermediate decision records.

They are not authoritative household records.

Authority:

Recipes:
  recipe-library-manager

Meal plans:
  household-meal-planner

Grocery lists:
  grocery-list-generator

Shopping execution:
  household consumer (grocery list)

## Recommendation Artifact Schema

Example:

metadata:
  created: YYYY-MM-DD
  household_size: 2
  objective: weekly meal candidate selection
  meal_scope:
    lunches: 7
    dinners: 7
  planning_period:
    start: YYYY-MM-DD
    end: YYYY-MM-DD

inputs:
  recipe_library:
    path: $HOUSEHOLD_ROOT/recipes/index.yaml

  pantry:
    path: $HOUSEHOLD_ROOT/pantry/

  deals:
    path: $HOUSEHOLD_ROOT/grocery-data/

Candidates are discovered options.

Recommendations are evaluated candidates.

Only evaluated recommendations should appear in the artifact.

Recommendations must remain recipe-level candidates.

Do not represent recommendations as:
- Monday/Tuesday/etc. assignments
- a sequence of calendar meals
- a complete lunch schedule
- a complete dinner schedule
- a final weekly meal plan

Calendar placement belongs to household-meal-planner.

Do not store rejected search results unless needed for audit purposes.

recommendations:

  - recipe_id: example-recipe

    household:
      score: high

    pantry:
      score: medium
      score_basis: catalog_and_partial_evidence

      ```
      Suggested values:

        - `confirmed_evidence`
        - `partial_evidence`
        - `catalog_and_partial_evidence`
        - `unknown_evidence`
        - `no_matching_evidence`
      ```

      confirmed_available:
        - olive oil

      catalog_items_to_verify:
        - beef broth
        - baby spinach

      missing_or_unmatched:
        - ground beef

      unknown:
        - heavy cream

      requires_pantry_check: true

    budget:
      score: high

    effort:
      score: high

    source:
      type: household_recipe
      path: $HOUSEHOLD_ROOT/recipes/example-recipe.md
      url: null
      creator: null
      website: null
      trust_level: household
      verification_status: verified
    
    source:
      type: trusted_web_recipe
      path: null
      url: https://example.com/recipe
      creator: Example Creator
      website: Example Website
      trust_level: high
      verification_status: verified
    
    score:
      overall: high

    reasoning:
      - matches household preferences
      - uses available ingredients
      - fits preparation constraints

    considerations:

      pantry_usage:
        - ingredient

      new_ingredients:
        - ingredient

      leftovers:
        expected: true

    confidence:
      level: medium
      reasons:
        - trusted recipe source
        - strong household fit
        - several household catalog matches
        - current stock not confirmed

status:
  approved: pending

approval_requirements:
  - verify catalog-only ingredients before cooking

Allowed states:
    - pending
    - approved
    - rejected
    - expired

Only:

```approved```

recommendations may proceed to:

```household-meal-planner```

The `status.approved` field represents the approval state of the recommendation artifact.
The household-workflow skill owns the approval deicision and rppoval record. This skill may read and reflect that state but must not approve its own recommendation.


## Grocery Handoff Rules

The recommendation agent must not create or synchronize grocery lists.

When passing ingredient information to the grocery-list-generator:

- confirmed missing ingredients may be proposed as grocery candidates
- catalog-only ingredients must be passed as pantry verification candidates
- confirmed available ingredients must not be proposed for purchase
- unknown ingredients must remain unresolved until verified
- A `missing_or_unmatched` ingredient may become a grocery candidate only when pantry coverage is sufficient for that ingredient category.
- If pantry coverage is incomplete, pass the ingredient as an unresolved verification candidate instead.
- Catalog-only and unknown ingredients must not be silently converted into confirmed grocery requirements.

Example:

```yaml
grocery_candidates:
  - name: ground beef
    reason: not found in complete pantry data
    pantry_status: missing_or_unmatched

pantry_verification_candidates:
  - name: beef broth
    reason: catalog entry only
    pantry_status: catalog_only
    availability: unknown

unresolved_ingredients:
  - name: heavy cream
    reason: pantry coverage insufficient
    pantry_status: unknown
```

## Artifact Rules

The recommendation artifact:

May:

- rank recipes
- explain selections
- preserve source information
- record uncertainty

Must not:

- create meal plans
- create grocery lists
- modify recipes
- import recipes
- synchronize external systems

Handoff contract:

recipe-recommendation-agent
        |
        | approved recommendation artifact
        v
household-meal-planner

The meal planner receives:

- selected recipe IDs
- servings
- reasoning
- constraints considered
- confidence

The meal planner decides:

- final schedule
- ordering
- leftovers
- calendar placement

The recommendation agent must not create the final meal schedule.

## Promotion Evidence

Promotion data must be read from normalized YAML artifacts under:

`$HOUSEHOLD_ROOT/grocery-data/promotions/`

Consider a promotion only when:

- the store is configured and enabled;
- the source is identified;
- the promotion has a retrieval date;
- the promotion is verified or clearly marked as partially verified;
- the sale dates indicate that it is current or relevant to the planning period.

Treat promotions with missing or uncertain dates as unverified opportunities, not confirmed current sales.

Do not invent prices, package sizes, discounts, or sale dates.

Preserve:

- store
- location
- item identity
- package size
- sale price
- sale dates
- source URL
- verification status

Then add to the recommendation output:
```
promotions:
  - item: <product name>
    store: <store name>
    sale_price: "<price>"
    source: $HOUSEHOLD_ROOT/grocery-data/promotions/<current-week>-<store>.yaml
    verification_status: verified
```

This should be evidence, not a claim that the ingredient is available in the pantry.

## Promotion Ranking Rules

- Promotions may improve budget alignment and recommendation ranking.
- A sale must not override dietary restrictions, dislikes, equipment limitations, or major effort constraints.
- Prefer recipes that use a meaningful portion of a discounted ingredient.
- Avoid recommending a recipe solely because one ingredient is on sale.
- Consider package size and likely waste.
- Do not assume that a sale item is already in the pantry.
- Do not assume that a sale price applies to every store location.
- Do not place sale prices in recipe names or grocery item names.
