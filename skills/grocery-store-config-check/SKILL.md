# Grocery Store Configuration Validator

## Purpose

Validate the household grocery store configuration before grocery data collection.

This skill checks:

- YAML syntax
- Required fields
- Enabled stores
- Store locations
- Configured data sources
- Supported source types

This skill does not:

- Fetch websites
- Scrape advertisements
- Modify recipes
- Modify grocery data
- Create or delete household files

## Household workspace

The household workspace is:

`$HOUSEHOLD_ROOT` (the household data root)

## Configuration location

Read:

`$HOUSEHOLD_ROOT/grocery-data/stores.yaml`

## Required structure

Each store must contain:

- name
- location
  - city
  - state
  - zip
- enabled
- sources

Each source must contain:

- type
- url

## Supported source types

Currently supported:

- weekly_ad
- circular

Unknown source types should be reported as warnings.

## Output

Report:

- configuration status
- number of stores found
- enabled stores
- configured sources
- errors
- warnings

Do not claim that advertisements, prices, discounts, or products are available.

Only report configuration state.
