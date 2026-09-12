# Annada

Annada is a **local-first, agent-driven household food-management and meal-planning framework**.

It is a *framework*, not a standalone web application. Annada provides reusable framework code, skills, workflows, schemas, scripts, tests, and documentation that an agent (such as Hermes) operates on behalf of a household. A **household instance** holds that household's private data. The framework is intended to evolve under Git source control while the private household data remains outside Git.

---

## Project Overview

Annada consolidates the automation that runs a household's food planning: recipe acquisition and normalization, pantry and ingredient tracking, grocery promotion (ad) collection, meal planning, grocery-list generation, recommendation generation, recipe publishing, and the standing approval workflow that gates changes to canonical data.

The core idea:

- **Annada provides reusable framework code, skills, workflows, schemas, scripts, tests, and documentation.**
- **A household instance contains private household data** — recipes, pantry inventory, stores, meal plans, grocery lists, recommendations, and approvals.
- **An agent such as Hermes operates the framework** by reading the household instructions and invoking the appropriate skills and scripts.
- **Annada is intended to evolve under Git source control, while private household data remains outside Git.**

---

## Architecture

The repository is split into two top-level trees:

- `household/` — the framework's canonical data model, schemas, documentation, and code.
- `skills/` — the ten Hermes skills that drive the workflows over that data.

The key separation is between two distinct concepts:

### Framework repository — `~/annada`

This repository contains all the **reusable, version-controlled implementation**:

- skills
- scripts
- workflow logic
- schemas / configuration conventions
- documentation
- tests
- generic fixtures/examples
- reusable normalization vocabulary (e.g. `household/pantry/ingredient-aliases.yaml`)

### Private household instance — `$HOUSEHOLD_ROOT`

The household instance holds the **private, household-specific data**. It is populated by the household that clones this repository, on its own machine, outside Git. The instance contains:

- recipes
- recipe index
- stores
- pantry inventory
- meal plans
- grocery lists
- recommendations
- approvals
- other runtime/household-specific data

### Why the split matters

Private household data is **intentionally excluded from Git**. `.gitignore` excludes the instance-data paths while continuing to track all framework source code (Python, tests, `SKILL.md` files, workflow definitions, READMEs, schemas, and generic fixtures). A household instance is exactly that — an *instance* of the Annada framework. A different household clones this repository and populates its own private data outside Git.

All framework paths resolve from `$HOUSEHOLD_ROOT` at runtime. The repository never contains a machine-specific household path: `HOME`, `~`, or absolute paths to a particular user's instance are not the source of truth.

---

## Repository Layout

```
household/
  ASSISTANT.md          household operator instructions (read first)
  config.yaml           shared runtime configuration (generic template)
  recipe-sources.yaml   configured recipe source registry
  approvals/            standing decision records gating canonical changes
  archive/              historical / superseded artifacts
  grocery-data/         store definitions + advertisement (ads) data and promotions
  grocery-lists/        generated weekly grocery lists
  pantry/               inventory + ingredient identity/alias logic and tests
  plans/                weekly meal plans
  recipe-imports/       non-canonical ingestion boundary (see below)
  recipes/              canonical normalized recipe library
  recommendations/      generated weekly meal recommendations
  scripts/              support scripts (e.g. recipe publishing)
  workflows/            workflow documentation
skills/
  grocery-ad-scraper/
  grocery-store-config-check/
  grocery-list-generator/
  household-meal-planner/
  household-workflow/
  pantry-inventory-manager/
  recipe-library-manager/
  recipe-recommendation-agent/
  recipe-web-scraping/
  obsidian-integration/
```

---

## Prerequisites

Annada requires an **agent runtime**, but it does not install or bundle the agent. Hermes (or an equivalent agent that can invoke skills and run local scripts) is the normal runtime dependency and is expected to be available on `PATH`. **Do not introduce `HERMES_BIN`** — the agent is a standard `PATH` dependency.

### Required: agent / runtime infrastructure

- **Hermes** (or equivalent skills-capable agent) available on `PATH`.
- **Python 3** with the standard library. Module dependencies are lightweight and documented per skill (e.g. `pyyaml` for YAML parsing, `pytest`/`unittest` for tests).
- **`HOUSEHOLD_ROOT`** environment variable — **required**. Absolute path to a household instance root. All skills, scripts, and docs resolve household paths relative to this. See [Installation](#installation).

Annada does **not** automatically install Hermes, Docker, KitchenOwl, Syncthing, Obsidian, or any other external system. The framework provides no install mechanism for these; they are separate, household-arranged components (see [Optional Integrations](#optional-integrations)).

### Optional integrations

- **Obsidian** — an external presentation/reference layer. Required **only** for Obsidian operations, via the `OBSIDIAN_VAULT` environment variable.
- **crawl4ai** — only where `recipe-web-scraping` needs its external virtualenv, via `CRAWL4AI_VENV` and `CRAWL4AI_PROJECT`.
- **Tesseract / rapidocr** — optional local OCR for grocery flyers, used by `grocery-ad-scraper` when image-only flyer pages need reading.

### Household-specific external services

- **Grocery stores** are configured per-household in the (instance-only) `grocery-data/stores.yaml`. There are no bundled store definitions.
- **KitchenOwl** is explicitly **not** part of the active architecture. External catalog data, if it becomes available, is staging input only and is never treated as authoritative pantry inventory or imported into `inventory.yaml`.

---

## Installation

Follow these steps to set up a new Annada household instance.

### A. Obtain Annada

Clone the repository:

```bash
git clone git@github.com:<your-name>/annada.git
# or, HTTPS alternative:
git clone https://github.com/<your-name>/annada.git
```

Annada is an evolving template; your clone is your own framework copy, kept under Git for expected future updates.

### B. Choose / create the household root

Decide where your private household data will live, and export it as `HOUSEHOLD_ROOT`. This must be a **separate directory from the repository** (or a deliberately distinct instance root), because your private data must never be committed.

```bash
export HOUSEHOLD_ROOT="$HOME/household"
```

`HOUSEHOLD_ROOT` is how every skill, script, and doc locates the household instance. Do **not** hard-code a specific user's path anywhere in the framework or your instance configuration — everything resolves from `$HOUSEHOLD_ROOT`.

### C. Establish the expected household directory structure

Create the canonical household root structure. The framework's `household/` tree documents the expected layout; your instance mirrors the data-owning directories:

```
$HOUSEHOLD_ROOT/
├── ASSISTANT.md
├── approvals/
├── archive/
├── grocery-data/
│   └── promotions/
├── grocery-lists/
├── pantry/
├── plans/
├── recipe-imports/
├── recipes/
├── recommendations/
├── scripts/
└── workflows/
```

Each data directory ships an instance-side README (and often a `.gitkeep`) documenting its role.

### D. Configure the household

The instance holds a `config.yaml` (typically copied from the framework template at `household/config.yaml`) — the household preference and behavior configuration. It is **not** recipe, inventory, meal-plan, grocery-list, or credential storage. Puzzle out its placeholders:

- `household.people` — household headcount.
- `preferences` — preferred cuisines, dislikes, allergies.
- `planning.cooking.max_weeknight_minutes` — target weeknight cook time.
- `stores.preferred_stores` — must reference entries in `grocery-data/stores.yaml`.
- `obsidian.vault_path` — **must remain `null`** here; the real vault path is an environment override (`OBSIDIAN_VAULT`) resolved at runtime. Never commit a machine-specific vault path.

**Framework configuration** (the template and its conventions, version-controlled) is distinct from **private instance data** (your household's filled-in values, outside Git). The template deliberately avoids machine-specific absolute paths — everything resolves against `$HOUSEHOLD_ROOT` at runtime.

### E. Make the skills available to the agent

The ten skills are included as **normal directories under `skills/`** (flat, not submodules):

```
grocery-ad-scraper
grocery-store-config-check
grocery-list-generator
household-meal-planner
household-workflow
pantry-inventory-manager
recipe-library-manager
recipe-recommendation-agent
recipe-web-scraping
obsidian-integration
```

Each skill is a `SKILL.md` describing what it owns, its workflow, and the household paths it reads. The framework documents the current expectation: skills are referenced as normal skill directories — copied, linked, or installed into the agent's skill directory by the household's own arrangement. The framework does **not** bundle an installer/uninstaller; the repository is the canonical source of the skill definitions, and making them available to a given agent is a household-side step.

Each skill is self-describing — read its `SKILL.md` for the exact household paths it uses and the ownership/approval boundaries it obeys.

---

## First-Run / Bootstrap

Before the agent can perform useful household operations, the household must provide:

1. **`ASSISTANT.md`** at `$HOUSEHOLD_ROOT` — the household's operating instructions for the agent (recipes, file-safety rules, meal-planning and grocery-list behavior).
2. **`config.yaml`** — the filled-in household configuration (see above).
3. **`grocery-data/stores.yaml`** — the household's configured stores (instance data; git-ignored).
4. **A recipe library** (`recipes/`) — either populated with household recipes or left empty (an empty library is valid; the agent will report what exists and what is missing rather than inventing recipes).
5. **`pantry/inventory.yaml`** — optional; if absent, ingredient availability is `unknown` and is reported as such (never assumed available).

### Framework templates/examples vs. household-owned data

The repository commits **templates and generic fixtures**, not household data:

| Kind | Examples in repository |
|---|---|
| Framework template | `household/config.yaml`, `household/recipe-sources.yaml`, `household/ASSISTANT.md`, directory `README.md` files |
| Generic fixtures | `household/recipe-imports/test-source.md`, `household/scripts/test_obsidian/fixtures/recipes/*.md`, generic pantry identity test data |
| Instance-owned (never committed) | actual recipes, recipe index, `stores.yaml`, `pantry/inventory.yaml`, meal plans, grocery lists, approvals, recommendations |

The bootstrap sequence the repository intends: create the instance root with the documented directories, copy the template config and fill it in, write `ASSISTANT.md`, configure stores, and populate (or intentionally leave empty) the recipe library and pantry inventory. The agent then operates only against `$HOUSEHOLD_ROOT`.

---

## Agentic Workflow

An agent operating Annada follows a deliberate, evidence-driven flow. The general pattern is:

```
household instructions
    → configuration
    → household data
    → specialized skill
    → scripts / tools
    → validation
    → generated household artifact
```

### Operating rules

An agent should:

- **Read `household/ASSISTANT.md` before household operations.** It is the operator's authority for file-safety, recipe, meal-planning, and grocery-list behavior, and it points to more specific per-directory READMEs (e.g. `recipes/README.md`).
- **Respect the household data boundaries.** `$HOUSEHOLD_ROOT` holds canonical household data. Obsidian is a read-only from-the-pipeline presentation layer, never a source of truth or an edit source.
- **Use canonical sources rather than duplicating state.** Each artifact has a single owner. The recipe Markdown is the source of truth for recipe content; `recipes/index.yaml` is generated and never hand-edited; `pantry/inventory.yaml` is the sole authoritative pantry source.
- **Invoke specialized skills for specialized operations.** `household-workflow` is the orchestrator; it routes to the owning skill rather than bypassing workflow logic.
- **Validate generated artifacts.** YAML vs. Markdown consistency, file existence, index/filename/title correspondence, and byte-preservation are checked before declaring a step complete.
- **Preserve user-authored content.** Generated Obsidian pages carry a generated-content marker (`<!-- BEGIN HERMES GENERATED CONTENT -->` ... `<!-- END HERMES GENERATED CONTENT -->`); user-authored content outside that span is preserved on regeneration.
- **Avoid inventing missing recipe quantities, times, instructions, or other structured data.** Unknown values are marked `Unknown` or `unknown`, never guessed.
- **Keep runtime/private data out of the framework repository.** Instance data belongs under `$HOUSEHOLD_ROOT`, never in Git.

### Autonomy boundaries

Annada does **not** overstate its autonomy. The current skills are explicitly conservative:

- Recommendations are **suggestions only**; nothing is scheduled until a human approves a recommendation artifact.
- Meal plans are created as **drafts** and require approval before grocery generation or Obsidian publication.
- **Approval is required** before: creating final meal plans, modifying recipe files, creating grocery lists for shopping, publishing to Obsidian, and modifying pantry inventory.
- **Approval is not required** for: reading files, analyzing recipes, generating suggestions, or explaining options.
- Agents must not silently invent data, treat a catalog entry as confirmed stock, or claim completion of actions not performed.

---

## Current Workflow Pipeline

Annada implements a **weekly meal-planning workflow** with an explicit artifact lifecycle and approval gates. The orchestration command is documented as:

```
hermes household plan-week
```

### Implemented sequence

```
Configuration
  → Recipe discovery
  → Recommendation artifact
  → Recommendation approval (human)
  → Draft meal plan
  → Meal-plan approval (human)
  → Optional grocery list
  → Obsidian publication
```

The concrete steps, per the household workflow and the weekly-planning orchestration:

1. **Load household instructions and configuration** — read `$HOUSEHOLD_ROOT/ASSISTANT.md` and `config.yaml`.
2. **Inspect household data** — `recipes/`, `pantry/`, `grocery-data/`.
3. **Collect external information when available** — `grocery-ad-scraper` (promotions) and `pantry-inventory-manager` (inventory). Promotions are evidence, never invented.
4. **Generate meal recommendations** — `recipe-recommendation-agent` produces `recommendations/*.yaml` with ranking, pantry evidence, promotion awareness, and confidence. Status: pending, no files modified beyond the artifact.
5. **Request human approval** — stored under `$HOUSEHOLD_ROOT/approvals/`. Only approved recommendations may proceed.
6. **Create a draft meal plan** — `household-meal-planner` writes `plans/week-YYYY-MM-DD.yaml` (canonical YAML) plus a human-readable Markdown view. Status: draft.
7. **Request meal-plan approval** — stored under `$HOUSEHOLD_ROOT/approvals/`. Only an approved plan may trigger downstream operations.
8. **Generate the grocery list (if requested)** — `grocery-list-generator` writes `grocery-lists/*.yaml` (authoritative) + a Markdown checklist, using pantry evidence. Approval status is required. If a user requests a grocery list from an unapproved plan, it must be labeled provisional.
9. **Publish approved artifacts to Obsidian (if requested)** — `obsidian-integration` renders the approved plan, grocery list, pantry status, dashboard, and recipe library into `$OBSIDIAN_VAULT`. Publication never alters canonical data and preserves user-authored content.

### Implemented vs. future/optional

**Implemented today:**

- Grocery-store configuration validation (`grocery-store-config-check`).
- Weekly-ad / circular promotion extraction (`grocery-ad-scraper`), normalized into YAML + Markdown with verification status.
- Catalog-only vs. confirmed-stock distinction (`pantry-inventory-manager`, `recipe-recommendation-agent`, `household-meal-planner`, `grocery-list-generator`).
- Deterministic ingredient identity matching (`household/pantry/ingredient_identity.py` + `ingredient-aliases.yaml`).
- Pantry mutation (`pantry_ops.py`) with plan/commit approval boundary.
- Recipe discovery, extraction, and normalization (`recipe-web-scraping`, `recipe-library-manager`).
- Recommendation ranking and evidence (`recipe-recommendation-agent`).
- Weekly meal planning with leftover and pantry-evidence handling (`household-meal-planner`).
- Grocery-list generation with identity/sufficiency/aggregation pipeline (`grocery-list-generator`).
- Obsidian presentation publishing (`obsidian-integration` + `scripts/publish_recipes.py`).

**Future / optional (documented as prospective, not shipped):** pantry reconciliation, expiration/freezer tracking, leftover tracking, consumption reconciliation, and KitchenOwl staging input. These are not yet implemented.

---

## Household Data Model

The household data-owning directories under `$HOUSEHOLD_ROOT`, per the repository's documented semantics:

```
household/
├── approvals/         explicit approval state gating canonical changes
├── archive/           historical / superseded artifacts
├── grocery-data/      grocery/deal data (ads, promotions) + store config
├── grocery-lists/     generated shopping artifacts
├── pantry/            household inventory + ingredient identity/alias logic
├── plans/             meal-planning artifacts
├── recipe-imports/    staging / inbox boundary for raw or external material
├── recipes/           canonical normalized recipe library
├── recommendations/   recommendation artifacts
├── scripts/           reusable household-side utilities
└── workflows/         workflow documentation / logic
```

Roles (as documented by the framework):

- **`recipe-imports/`** — the **staging/inbox boundary**. Raw, unprocessed, or externally sourced recipe material lands here first. It is deliberately **not** canonical. New recipes pass through ingestion/normalization into `recipes/`. Committed contents are only the skeleton (`.gitkeep`) and the deliberate generic test fixture `test-source.md`.
- **`recipes/`** — the **canonical normalized recipe library**. One complete normalized Markdown recipe per file, with YAML frontmatter. The generated `index.yaml` is derived, never hand-edited. The Markdown recipe files are the source of truth.
- **`pantry/`** — household **inventory** (`inventory.yaml`, the sole authoritative pantry source) plus the deterministic **ingredient identity/alias logic** (`ingredient_identity.py`, `ingredient-aliases.yaml`) and pantry mutation code (`pantry_ops.py`).
- **`plans/`** — **meal-planning artifacts**: `week-YYYY-MM-DD.yaml` (canonical) + a generated Markdown view.
- **`grocery-lists/`** — **generated shopping artifacts**: `*.yaml` (canonical) + a Markdown checklist.
- **`approvals/`** — **explicit approval state** (`approval-<timestamp>.yaml`) for recommendation, meal-plan, grocery, and pantry mutations.
- **`recommendations/`** — **recommendation artifacts** (reviewable, regenerable; not authoritative household history).
- **`grocery-data/`** — **grocery/deal data**: store definitions (`stores.yaml`, instance-only) and normalized `promotions/` YAML + Markdown.
- **`scripts/`** — **reusable household-side utilities** (e.g. `scripts/publish_recipes.py`).
- **`workflows/`** — **workflow documentation/logic**.

---

## Recipe Workflow

Annada's canonical recipe model:

- **Imported / staged recipes** live in `recipe-imports/` — the non-canonical inbox. Raw webpages, screenshots, PDFs, and unprocessed text belong here, not in the library.
- **Canonical normalized recipes** live in `recipes/` — one Markdown file per recipe with YAML frontmatter (id, title, category, cuisine, time, servings, difficulty, tags, source metadata). The `id` must match the filename without `.md`.
- **Recipe metadata / indexing** — `recipes/index.yaml` is a generated catalog (recipe ID, title, filename, category, cuisine, tags, timing, servings, normalized ingredients) built from the Markdown files by `recipe-library-manager`. It is never manually edited and contains no full instructions or duplicate recipe text.

The `recipe-library-manager` skill is responsible for importing, normalizing, creating recipe files, generating frontmatter, maintaining the index, checking duplicates, and regenerating Obsidian presentation pages from canonical files. Recipe files remain authoritative over the index; `recipe-web-scraping` documents the working extraction routes (crawl4ai, Wayback) for blocked sites, preserving source attribution.

**Extraction rule:** recipe content is never guessed. Missing quantities are recorded as `quantity not specified`; missing times as `Unknown`; incomplete recipes are recorded in Notes and never fabricated.

---

## Agent Operating Principles

Framed as Annada's actual operating rules (supported by `household/ASSISTANT.md`, the workflow, and the skills):

1. **Read `ASSISTANT.md` first.** It is the operator instructions; read it before any household operation.
2. **Treat canonical household files as authoritative.** `$HOUSEHOLD_ROOT` owns household data; Obsidian is a read-only presentation layer generated from it.
3. **Do not invent missing structured recipe information.** No fabricated quantities, times, instructions, or metadata.
4. **Preserve user-authored content.** Generated views are regenerated additively; user content outside the generated span survives.
5. **Keep private household data out of Git.** Instance data lives under `$HOUSEHOLD_ROOT`, never committed.
6. **Validate changes before declaring an operation complete.** Verify files exist, YAML parses, Markdown matches the canonical artifact, and no unrelated files changed.
7. **Use the appropriate specialized skill.** `household-workflow` orchestrates and routes; do not bypass established workflow logic or modify another skill's artifacts.
8. **Report unknowns instead of silently guessing.** Distinguish *verified*, *unavailable*, and *suggested*; never present a suggestion as a fact.

---

## Source Control

The Annada repository is source control for the **framework**:

- skills
- scripts
- tests
- schemas
- workflow logic
- documentation
- generic fixtures/examples
- reusable normalization vocabulary (such as `household/pantry/ingredient-aliases.yaml`)

**Private household instance data is never committed.** The household instance is a separate directory (`$HOUSEHOLD_ROOT`) that remains outside Git.

Framework code is changed through normal Git development (branch, commit, push, merge) in this repository. The household instance is separate and updated deliberately — there is no automatic sync/install/deployment machinery built yet.

The central distinction:

> **framework data ≠ household instance data**

Framework data (skills, scripts, tests, schemas, docs, fixtures, alias vocabulary) belongs in this repository. Household instance data (actual recipes, inventory, stores, plans, lists) does not.

---

## Testing

Run the framework's test suites from the repository. They are documented, deterministic suites covering the identity, pantry, grocery, and Obsidian publisher logic.

**Commands (run from the directory containing each suite):**

| Suite | Command | Current status |
|---|---|---|
| Pantry ingredient identity | `python3 -m pytest test_ingredient_identity.py` | 167 passed (no private data required) |
| Pantry operations | `python3 -m pytest test_pantry_ops.py` | see known limitation below |
| Grocery identity pipeline | `python3 -m unittest test_grocery_identity_pipeline.py` | 25 passed |
| Obsidian publisher | `python3 -m pytest test_persistent_library.py` | 31 passed (generic fixtures) |

### Known limitation

A subset of the pantry-operation tests (`test_pantry_ops.py`) guard against the real `inventory.yaml`. Because the pantry inventory is **instance data** (git-ignored and absent in a clean checkout), those tests error on the missing file in a fresh clone. This is expected and accepted: the identity/code unit tests pass independently, and a real household instance supplies its own inventory. The tests are **not** modified or weakened to force them to pass in a bare checkout.

Do not claim 100% of tests pass — the pantry-operation suite has accepted errors in a clean checkout, by design.

### Before committing

A contributor should validate changes by:

1. Running the relevant suites above.
2. Ensuring no personal/instance data or secrets are staged (`git diff --cached` review).
3. Verifying the working tree — the framework is expected to be portable, with no machine-specific paths or credentials; framework tests should run on any checkout without private household data where possible.

---

## Extending Annada

New functionality should be added as **portable, reusable framework code**:

- **A new skill** — add a directory under `skills/` with a `SKILL.md` documenting what it owns, its household paths (via `$HOUSEHOLD_ROOT`), and its ownership/approval boundaries. Perhaps also add a test under `skills/<skill>/tests/`.
- **A reusable script** — add under `household/scripts/` following the existing runtime contract (resolve everything from `$HOUSEHOLD_ROOT`; never hard-code a path).
- **A test** — add a `test_*.py` in the relevant suite directory (pantry, grocery pipeline, obsidian publisher). Prefer generic fixtures that run without private instance data.
- **Workflow documentation** — document a workflow in `$HOUSEHOLD_ROOT/workflows/` (instance side) or in this repository's `household/workflows/`.
- **A generic fixture** — add under `household/scripts/test_obsidian/fixtures/` (or the relevant suite's fixtures) that does **not** contain household-specific data.
- **A schema / configuration change** — edit `household/config.yaml` (template) or a skill's schema, keeping paths `$HOUSEHOLD_ROOT`-relative and machine-agnostic.

**Expectation:** new functionality must remain portable. It should not introduce household-specific paths, credentials, store names, personal recipes, or preferences into framework code. Instance specifics belong in the household's `$HOUSEHOLD_ROOT`, not the repository.

---

## Privacy / Data Boundary

Private household data must **never** be committed to this repository. Representative examples of what must stay out of Git:

- actual recipes
- recipe index (`recipes/index.yaml`)
- `stores.yaml`
- pantry inventory (`pantry/inventory.yaml`)
- meal plans
- grocery lists
- approvals
- recommendations
- runtime/archive artifacts

`.gitignore` is part of the protection — it excludes the instance-data paths above while tracking framework source. But `.gitignore` is **not a substitute for reviewing staged changes before committing.** Always review `git diff --cached` to confirm no instance data, credentials, or machine-specific paths have been accidentally staged.

---

## Optional Integrations

Only integrations represented by current repository code/skills are documented, and all are **optional**:

- **Obsidian** (`skills/obsidian-integration/`, `household/scripts/publish_recipes.py`) — an external presentation layer. Required only for Obsidian publication. The vault is synced separately (e.g. Syncthing) and accessed via `OBSIDIAN_VAULT`; it is never committed. It is a generated, read-only-from-the-pipeline view over canonical data, not a source of truth.
- **crawl4ai** (`skills/recipe-web-scraping/`) — optional web-scraping engine for recipe extraction on bot-walled sites, run via `CRAWL4AI_VENV` / `CRAWL4AI_PROJECT`.
- **Tesseract / rapidocr** — optional local OCR for image-only grocery flyer pages.

**KitchenOwl is not documented as a built-in integration.** The repository explicitly states KitchenOwl is not part of the active architecture; external catalog data is staging input only and is never authoritative pantry inventory.

---

## Troubleshooting

Practical issues a new household / agent is likely to hit, tied to Annada's actual structure:

### Household root / path configuration

- `HOUSEHOLD_ROOT` is **required** and must point at the household instance root. If a script/agent errors on "not a household root" or missing `HOUSEHOLD_ROOT`, check that the variable is set and points at the instance (not the framework repo root).
- All paths derive from `$HOUSEHOLD_ROOT`. If you hard-code an absolute path anywhere, that is a config error, not a framework feature. Keep paths relative to the root.

### Missing household files

- **`inventory.yaml` missing** → pantry availability is `unknown`; the agent reports it rather than assuming stock. That is expected behavior, not an error.
- **`stores.yaml` missing** → `grocery-store-config-check` reports an invalid configuration rather than inventing stores. Create the household's `stores.yaml`.
- **Recipes missing** → an empty library is valid; the agent reports what exists and what is missing instead of inventing recipes.

### Skill availability

- Skills are normal directories under `skills/`. If a skill is not available to the agent, it has not been linked/installed into the agent's skill environment — make the household-side arrangement (link, copy, or install) and confirm the `SKILL.md` is discoverable.

### Validation / test failures

- Pantry-operation tests may error in a clean checkout because `inventory.yaml` is absent (instance data). This is an accepted limitation; a populated instance supplies its own inventory.
- Obsidian tests build a sandbox with generic fixtures, not your hand-edited vault. If the full publisher suite fails on private data expectations, that is expected without a real vault.
- If a generated YAML and its Markdown view disagree, the YAML is authoritative; regenerate the Markdown rather than hand-editing it.

### Accidentally staged private data

- If you stage a recipe, `inventory.yaml`, `stores.yaml`, or a meal plan, unstage it. Prefer `git reset HEAD <file>` before a commit and always review `git diff --cached`. `.gitignore` helps but is not a substitute for a staged-change review.

---

## Development Status

Annada is an **evolving framework**. This repository is the source of truth for the reusable implementation: skills, scripts, workflows, schemas, tests, documentation, and generic fixtures. As the framework matures, it is updated here through normal Git development, and the household instance is updated deliberately and separately.

The implemented functionality described throughout this README is what the current repository actually provides. Prospective additions documented in the skills and workflow READMEs (pantry reconciliation, expiration/freezer tracking, leftover tracking, consumption reconciliation, KitchenOwl staging input) are not yet implemented and should not be treated as current features.