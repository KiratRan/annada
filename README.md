# Annada

## Purpose

Annada is the reusable household-automation **framework** and its source-control repository. It consolidates the automation that runs a household: meal planning, pantry and ingredient tracking, grocery data and list generation, recipe acquisition and normalization, recommendation generation, recipe publishing, and the standing approval workflow that gates changes to canonical data.

The repository is split into two top-level trees:

- `household/` — the framework's canonical data model, schemas, documentation, and code.
- `skills/` — the ten Hermes skills that drive the workflows over that data.

## Repository Layout

```
household/
  ASSISTANT.md          household operator instructions
  config.yaml           shared runtime configuration (generic template)
  recipe-sources.yaml   configured recipe source list
  approvals/            standing decision records gating canonical changes
  archive/              historical / superseded artifacts
  grocery-data/         store definitions + advertisement (ads) data
  grocery-lists/        generated weekly grocery lists
  pantry/               inventory + ingredient identity code and tests
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

## Framework vs. Private Household Instance

Annada is a durable source-control boundary, not a disposable snapshot.

**Framework / version-controlled (in this repository):**

- skills
- scripts
- workflow logic
- schemas
- documentation
- tests
- generic fixtures
- framework configuration

**Private household instance data / NOT version-controlled (exists only in the household's own instance, e.g. `/home/kirat/household`):**

- recipes
- recipe index
- stores
- pantry inventory
- meal plans
- grocery lists
- approvals
- recommendations
- archived runtime data
- Obsidian
- generated/runtime artifacts

A household instance is exactly that — an *instance* of the Annada framework. A different household clones this repository and populates its own private data outside Git.

`.gitignore` excludes the instance-data paths above while continuing to track all framework source code (Python scripts, tests, `SKILL.md` files, workflow definitions, READMEs, schemas, and generic fixtures).

## Framework Development Flow

The framework is expected to evolve continuously through this repository. The intended flow:

1. Develop changes (skills, scripts, workflows, schemas, docs, tests).
2. Test them here.
3. Commit and push framework changes.
4. Deliberately deploy / update a private household instance separately.

No automatic sync, install, or deployment machinery is built yet; the repository is establishing the source-control boundary first, and instance updates remain deliberate and manual for now.

## recipe-imports/ — Ingestion Boundary

`household/recipe-imports/` is the non-canonical staging/inbox boundary for raw or externally sourced recipe material; `household/recipes/` is the canonical normalized recipe library.

`recipe-imports/` is deliberately NOT canonical. New recipes land here as raw/unprocessed material and are expected to pass through the recipe-library-manager / recipe-web-scraping ingestion pipeline, which normalizes and promotes them into `recipes/`. Personal import artifacts are not tracked; the committed contents are the directory skeleton (`.gitkeep`) and the deliberate generic test fixture `test-source.md`.

## Obsidian

Obsidian is an external presentation/reference layer over the household data. The vault (`household/obsidian/`, `.obsidian/`, `.stfolder/`, `KitchenOwl/`) is synced separately (e.g. Syncthing) and is **never committed** to this repository. It is fully excluded in `.gitignore`.

## Environment Variables

- `HOUSEHOLD_ROOT` — **required.** Absolute path to a household instance root (e.g. `~/household-automation` for this repository, or a household's own instance root). All skills, scripts, and docs resolve household paths relative to this.
- `OBSIDIAN_VAULT` — required **only** for Obsidian operations. Path to the external Obsidian vault.
- `CRAWL4AI_VENV` — required **only** where recipe-web-scraping needs its virtualenv.
- `CRAWL4AI_PROJECT` — required **only** where recipe-web-scraping needs its project/working directory.

Runtime contract:

```
HOUSEHOLD_ROOT required
OBSIDIAN_VAULT required only for Obsidian operations
CRAWL4AI_VENV required only for recipe-web-scraping
CRAWL4AI_PROJECT required only where recipe-web-scraping needs its project/working directory
```

Hermes is a normal `PATH` dependency. **Do not introduce `HERMES_BIN`.**

## Included Skills

Ten Hermes skills are included as normal directories under `skills/` (flat, not submodules):

`grocery-ad-scraper`, `grocery-store-config-check`, `grocery-list-generator`, `household-meal-planner`, `household-workflow`, `pantry-inventory-manager`, `recipe-library-manager`, `recipe-recommendation-agent`, `recipe-web-scraping`, `obsidian-integration`.

## Testing

Run from the repository root with `HOUSEHOLD_ROOT` set:

- Pantry ingredient-identity tests (`household/pantry/test_ingredient_identity.py`) — **167 passed** (no private data required).
- Pantry operation tests (`household/pantry/test_pantry_ops.py`) — some guards read the real `inventory.yaml`; in a clean checkout where no private inventory exists they error on the missing file (this is expected, since inventory is instance data). The identity/code unit tests pass independently.
- Grocery identity tests (`skills/grocery-list-generator/tests/`) — **25 passed**.
- Obsidian publisher tests (`household/scripts/test_obsidian/`) — build a sandbox but expect a private recipe library as fixtures, so the full suite requires the household's real recipes; the vault-independent parts pass without the personal vault.

## Portability

This repository is portable. No machine-specific paths or credentials are required at runtime; all household paths derive from `$HOUSEHOLD_ROOT`. The framework content is store- and instance-agnostic — a household configures its own stores, aliases, people, and preferences in its instance.

## Upstream

The intended upstream is a **private GitHub repository**. No remote URL or account is embedded here; the remote is configured at staging time.