# household-automation

## Purpose

`household-automation` consolidates the automation that runs a two-person household: meal planning, pantry and ingredient tracking, grocery data and list generation, recipe acquisition and normalization, recommendation generation, and the standing approval workflow that gates changes to canonical data.

The repository is split into two top-level trees:

- `household/` — the canonical data and code that define the household system.
- `skills/` — the ten Hermes skills that drive the workflows over that data.

## Repository Layout

```
household/
  ASSISTANT.md          household operator instructions
  config.yaml           shared runtime configuration
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

## Canonical Data Model

The following directories are the canonical source of truth for the household system:

- `household/plans/` — weekly meal plans
- `household/grocery-lists/` — weekly grocery lists
- `household/approvals/` — approval records that gate changes to canonical data
- `household/recommendations/` — generated meal recommendations
- `household/pantry/inventory.yaml` — pantry inventory
- `household/recipes/` — the canonical recipe library (see below)

Changes to canonical data are gated by the approval workflow and must not be made directly.

## recipe-imports/ — Ingestion Boundary

`household/recipe-imports/` is the non-canonical staging/inbox boundary for raw or externally sourced recipe material; `household/recipes/` is the canonical normalized recipe library.

`recipe-imports/` is deliberately NOT canonical. New recipes land here as raw/unprocessed material and are expected to pass through the recipe-library-manager / recipe-web-scraping ingestion pipeline, which normalizes and promotes them into `recipes/`. Arbitrary transient import artifacts are not tracked; the committed contents are the directory skeleton (`.gitkeep`) and deliberate test fixtures (e.g. `test-source.md`).

## Obsidian

Obsidian is an external presentation/reference layer over the household data. The vault (`household/obsidian/`, `.obsidian/`, `.stfolder/`, `KitchenOwl/`) is synced separately (e.g. Syncthing) and is **never committed** to this repository. It is fully excluded in `.gitignore`.

## Environment Variables

- `HOUSEHOLD_ROOT` — **required.** Absolute path to the repository root (`~/household-automation`). All skills, scripts, and docs resolve household paths relative to this.
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

- Pantry tests (`household/pantry/`) — 221 passed
- Grocery identity tests (`skills/grocery-list-generator/tests/`) — 25 passed
- Obsidian publisher tests (`household/scripts/test_obsidian/`) — 31 passed, sandbox vault only

## Portability

This repository is portable. No machine-specific paths are required at runtime; all household paths derive from `$HOUSEHOLD_ROOT`. Any `/home/kirat` or host-specific reference that remains in included content is intentional historical/provenance data (canonical meal plans, grocery lists, approvals, recommendations, and archive records), not runtime configuration.

## Upstream

The intended upstream is a **private GitHub repository**. No remote URL or account is embedded here; the remote is configured at staging time.