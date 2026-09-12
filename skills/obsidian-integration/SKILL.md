# Obsidian Integration Skill

## Purpose

Maintain the household's Obsidian vault as the human-facing interface for the Hermes household system.

The Obsidian vault is a synchronized presentation layer. It is not the authoritative source of household operational data.

## Locations

Obsidian vault (external — set via `OBSIDIAN_VAULT`):

`$OBSIDIAN_VAULT`

Canonical household workspace — set via `HOUSEHOLD_ROOT` (the household data root).

Canonical operational data (all under `$HOUSEHOLD_ROOT`):

- Recipes: `$HOUSEHOLD_ROOT/recipes`
- Meal plans: `$HOUSEHOLD_ROOT/plans`
- Grocery lists: `$HOUSEHOLD_ROOT/grocery-lists`
- Pantry: `$HOUSEHOLD_ROOT/pantry`
- Grocery/promotional data: `$HOUSEHOLD_ROOT/grocery-data`

Obsidian is synchronized with the Windows Obsidian vault through Syncthing.

Only `$OBSIDIAN_VAULT` is synchronized.

## Authority

The household workspace is authoritative.

Obsidian provides a human-readable interface to that data.

Do not create a second authoritative copy of:

- recipes
- meal plans
- grocery lists
- pantry inventory
- grocery data

When Hermes generates or modifies household operational data, the canonical household files must be updated first. Obsidian-facing Markdown may then be generated or updated from that canonical data.

Do not treat an Obsidian Markdown file as authoritative merely because a user edited it there.

## Responsibilities

This skill may:

1. Publish the current meal plan to:
   `$OBSIDIAN_VAULT/Meals/This Week.md`

2. Publish the current grocery list to:
   `$OBSIDIAN_VAULT/Grocery/Current List.md`

3. Publish the current pantry status to:
   `$OBSIDIAN_VAULT/Pantry/Status.md`

4. Maintain the household dashboard:
   `$OBSIDIAN_VAULT/Household/Dashboard.md`

5. Maintain links between related Obsidian pages.
6. Ensure every active canonical recipe has a persistent generated recipe
   presentation page at `$OBSIDIAN_VAULT/Recipes/<recipe-id>.md`
   (a persistent reference/library, not just the current week's recipes).
7. Maintain the recipe library index at
   `$OBSIDIAN_VAULT/Recipes/_Recipe Index.md`.
8. Maintain current-week bidirectional meal-plan <-> recipe links.
9. Generate the recipe library navigation layer:
   - `Recipes/_Recipe Dashboard.md` — mobile landing page (browse by
     category/cuisine/tag, This Week, and full index links, with counts)
   - `Recipes/_By Category.md`, `Recipes/_By Cuisine.md`, `Recipes/_By Tag.md`
     — per-classification navigation views (headings + wikilinks, no tables)
   - Recipes that belong to multiple categories/cuisines/tags appear under
     EVERY applicable classification heading, but still share exactly one
     physical `Recipes/<id>.md` page (flat directory, no category folders).
10. Read Obsidian Markdown when a workflow explicitly requires information entered by the household user.
11. Verify files after writing them.

## Vault Structure

Current structure:

```text
obsidian/
├── .obsidian/
├── Household/
│   └── Dashboard.md
├── Meals/
│   └── This Week.md
├── Grocery/
│   └── Current List.md
├── Pantry/
│   └── Status.md
└── Recipes/
    ├── <recipe-id>.md          (persistent generated presentation pages)
    ├── _Recipe Index.md        (generated complete alphabetical inventory)
    ├── _Recipe Dashboard.md    (generated mobile navigation landing page)
    ├── _By Category.md         (generated per-category view)
    ├── _By Cuisine.md          (generated per-cuisine view)
    └── _By Tag.md              (generated per-tag view)
└── Welcome.md
```

Additional directories or notes may be introduced when a workflow requires them.

Do not create duplicate canonical data structures inside the vault.

## Obsidian Configuration

`.obsidian/` is managed by Obsidian.

Do not programmatically modify:


- `.obsidian/app.json`
- `.obsidian/appearance.json`
- `.obsidian/core-plugins.json`
- `.obsidian/graph.json`
- `.obsidian/workspace.json`


unless a workflow explicitly requires configuration changes and the user has approved them.

## File Safety

Before modifying Obsidian files:

1. Read `$HOUSEHOLD_ROOT/ASSISTANT.md`.
2. Confirm the target is inside `$OBSIDIAN_VAULT`.
3. Read the existing file when modifying an existing note.
4. Preserve useful user-authored content unless the workflow explicitly calls for replacement.
5. Do not overwrite or delete user-authored content without approval.
6. Verify the resulting file after writing.

Never write outside the Obsidian vault through this skill.

## Publishing Rules

Generated Obsidian pages should be:

- readable by a human
- concise
- organized with Markdown headings and lists
- linked to relevant household notes where useful
- derived from canonical household data
- safe to regenerate when the workflow explicitly owns the target section

Prefer clearly marked generated sections when a page may contain both generated and user-authored content.

For example:

```
## Hermes

<!-- BEGIN HERMES GENERATED CONTENT -->

...

<!-- END HERMES GENERATED CONTENT -->
```

Only modify content inside a Hermes-owned generated section when possible.

## Meal Plan Publishing

Canonical source:

`$HOUSEHOLD_ROOT/plans`

Destination:

`$OBSIDIAN_VAULT/Meals/This Week.md`

The Obsidian meal-plan page should present:

- dates
- planned meals
- recipe references when available
- useful preparation notes when available

Recipe-based meal entries link to their recipe presentation pages through
Obsidian wikilinks:

- `[[Recipes/<recipe-id>|Meal Name]]` for a scheduled meal or leftover entry
  that comes from a library recipe
- no link for external or unresolved meals

Do not make the Obsidian page the canonical meal-plan store.

## Grocery List Publishing

Canonical source:

`$HOUSEHOLD_ROOT/grocery-lists`

Destination:

`$OBSIDIAN_VAULT/Grocery/Current List.md`

The Obsidian grocery page should present the current actionable grocery list in a human-friendly format.

Do not independently maintain grocery state in Obsidian.

## Pantry Publishing

Canonical source:

`$HOUSEHOLD_ROOT/pantry`

Destination:

`$OBSIDIAN_VAULT/Pantry/Status.md`

The Obsidian pantry page should present a useful summary of household pantry state.

Do not make the Obsidian pantry page the inventory database.

## Dashboard

Destination:

`$OBSIDIAN_VAULT/Household/Dashboard.md`

The dashboard should provide a simple human-facing entry point to major household workflows.

Useful links include:

[[Meals/This Week]]
[[Grocery/Current List]]
[[Pantry/Status]]

The dashboard should not duplicate large amounts of canonical household data.

## Recipe Presentation Pages

The canonical recipe library remains:

`$HOUSEHOLD_ROOT/recipes`

Obsidian hosts generated recipe *presentation* pages — a persistent,
browsable/reference library, not a second authoritative recipe library:

`$OBSIDIAN_VAULT/Recipes/<recipe-id>.md`

The filename is the canonical recipe ID (frontmatter `id`, which matches the
canonical filename). Every active canonical recipe gets exactly one
presentation page. Pages persist across weeks; a recipe not used in the
current weekly plan is never deleted or hidden.

Each presentation page is generated from its canonical recipe file and is a
deliberately designed, mobile-first cooking/reference view (not a literal
copy of the canonical Markdown). It contains:

- frontmatter/properties (recipe_id, title, type: recipe, category, cuisine,
  servings, prep/cook/total time, difficulty, tags) — only fields supported
  by the canonical recipe, never invented
- a single summary callout (`> [!summary]`) with key metadata near the top
- a `## 🛒 Ingredients` section; quantities are visually prominent
  (`**2 lb** chicken`) and preserved exactly; ingredient subgroups are used
  only when the canonical recipe provides them
- a `## 🍳 Method` section where each numbered instruction is split into a
  short action-oriented heading (`### Brown the chicken`) plus one readable
  paragraph — so steps are visually distinct and scannable while cooking on a
  phone, without changing the cooking meaning/quantities/times
- a `## 📝 Notes` section with note content
- a source/attribution line
- a canonical-source reference making clear the page is generated and not
  authoritative
- only when the recipe is scheduled in the current approved plan, a
  `## 📅 This Week` section linking `[[Meals/This Week]]`

Everything Hermes generates is wrapped in HERMES generated-content markers
(`<!-- BEGIN/END HERMES GENERATED CONTENT -->`). A `## 📝 Personal Notes`
section lives OUTSIDE the generated markers so user-authored Obsidian notes
are never overwritten during regeneration.

Recipe presentation pages are regenerated only when their canonical recipe
changes. Unchanged pages are not rewritten every week.

### Recipe Library Navigation

The recipe library provides three complementary, all-generated navigation
views in `Recipes/` (flat directory — recipes are never split into category
subfolders; each recipe has exactly one physical `Recipes/<id>.md` page
regardless of how many classifications it belongs to):

- `_Recipe Index.md` — the complete flat, alphabetical inventory of every
  active canonical recipe.
- `_Recipe Dashboard.md` — the mobile-first landing/navigation page. It
  links to the per-category/cuisine/tag views (with recipe counts), to
  `[[Meals/This Week]]`, and to the full index. It is the navigation entry
  point; the index is the flat inventory.
- `_By Category.md`, `_By Cuisine.md`, `_By Tag.md` — alternate navigation
  views. Each has a heading per classification value with the recipe
  wikilinks that belong to it. A recipe appearing under multiple classifications
  (e.g. categories: [dessert, breakfast]) appears under EVERY applicable
  heading but still has only one physical page.

Classification values are derived only from canonical frontmatter
(`category`, `cuisine`, `tags`) — the schema already supports YAML lists.
Cuisine and tag views reflect only what canonical recipes actually declare;
nothing is invented or inferred from recipe names to fill gaps. Category is
kept distinct from cuisine (category = meal/course/use, cuisine =
culinary tradition/region, tags = granular descriptive labels).

All navigation pages use only ordinary Markdown (headings, lists,
wikilinks) — no Dataview, Bases, Recipe View/Box, custom CSS, or plugins.
They work in the standard Obsidian mobile app: short sections, easy tap
targets, human-readable recipe titles, no wide tables. Everything generated
is wrapped in HERMES generated-content markers; user-authored content on these
pages survives regeneration.

## Bidirectional Meal-Plan <-> Recipe Linking

Linking between the meal plan and recipes is bidirectional:

- plan -> recipe: each recipe-based meal in the meal-plan page wikilinks to
  its `Recipes/<id>.md` page (`[[Recipes/<id>|Meal Name]]`)
- recipe -> plan: each recipe presentation page used in the current week
  links back to the meal-plan page (`[[Meals/This Week]]`) so the recipe is
  reachable from the plan in both directions

The recipe -> plan link is CONDITIONAL and ephemeral:

- If a recipe is scheduled in the current approved weekly plan, its page
  shows a `## 📅 This Week` section linking `[[Meals/This Week]]`.
- If a recipe is NOT scheduled this week, that section is omitted entirely —
  no stale weekly link, no "not scheduled" clutter.
- The current week is derived from the approved meal-plan artifact
  (`Meals/This Week.md`), exactly as the existing workflow does.
- Recipe pages persist across weeks; only the current-week scheduling links
  change weekly. Historical weekly links are not accumulated on recipe pages.

External or unresolved meals never receive recipe links.

When the canonical recipe library changes (create/update), the matching
`Recipes/<id>.md` page is regenerated from the canonical source (handled in
coordination with `recipe-library-manager`).

### Archived / Removed Canonical Recipes

A canonical recipe removed or archived to `$HOUSEHOLD_ROOT/archive/`
does NOT cause its Obsidian page to be silently deleted. Default behavior:

- retain the Obsidian page
- mark it as archived / not currently in the active canonical recipe library
  (e.g. a note in the generated block)
- preserve user-authored content on the page
- exclude it from the Recipe Index
- permanently delete the Obsidian page only with explicit user approval

This lifecycle policy should be documented in the household workflow.

## Recipe Library Reconciliation

To build or refresh the persistent recipe library, run the Obsidian
publication script:

```text
python3 $HOUSEHOLD_ROOT/scripts/publish_recipes.py
```

This operation is additive and idempotent: it ensures every active canonical
recipe has exactly one page, keeps the Recipe Index and all navigation pages
(Dashboard, By Category/Cuisine/Tag) current, updates only pages whose
generated content changed, and never rewrites unchanged pages. Use `--dry-run`
to preview changes without writing.

## Syncthing

The Obsidian vault is synchronized bidirectionally between Ubuntu and Windows.

Ubuntu:

`$OBSIDIAN_VAULT`

Windows:

the configured Obsidian vault path on that machine (user-specific; not stored here)

Syncthing automatically watches the Ubuntu vault for filesystem changes.

Hermes does not need to invoke Syncthing manually after writing a file.

Do not modify Syncthing configuration from this skill.

## Workflow

For a workflow that publishes household information to Obsidian:

1. Read `ASSISTANT.md`.
2. Identify the canonical household source.
3. Read the canonical data.
4. Identify the appropriate Obsidian destination.
5. Read the existing Obsidian note.
6. Preserve user-authored content.
7. Update only the Hermes-owned content.
8. Verify the resulting Markdown.
9. Report what was published.

## Prohibited Behavior

Do not:

- treat Obsidian as the household database
- duplicate canonical recipe, pantry, grocery, or planning data unnecessarily
- modify .obsidian/ automatically
- modify Syncthing configuration
- write outside `$OBSIDIAN_VAULT`
- silently delete user-authored notes
- silently overwrite user-authored content
- invent household data
- use Obsidian as a replacement for the canonical household workspace

## Relationship to Other Skills

This skill provides the Obsidian presentation layer.

Other skills remain responsible for their canonical domains:

- `recipe-library-manager` → canonical recipes (may invoke this skill to
  regenerate `Recipes/<id>.md` presentation pages)
- `household-meal-planner` → meal planning
- grocery workflows → grocery lists and grocery data
- pantry workflows → pantry state

Those workflows may invoke this skill to publish their results to Obsidian.

The Obsidian integration must not become the owner of those domains.
