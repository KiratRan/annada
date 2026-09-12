# Grocery Advertisement Data

This directory contains imported grocery advertisements and extracted promotions.

Location:

$HOUSEHOLD_ROOT/grocery-data/ads


The household-wide instructions are:

$HOUSEHOLD_ROOT/ASSISTANT.md


The grocery data rules are:

$HOUSEHOLD_ROOT/grocery-data/README.md


---

# Purpose

Advertisement data contains external grocery information used for meal planning.

It provides:

- available promotions
- sale information
- source-backed pricing information

Advertisement data is not:

- a recipe source
- pantry inventory
- a meal plan
- a grocery list
- a purchase record


---

# Ownership

Advertisement data is maintained by:

grocery-ad-scraper


The scraper is responsible for:

- retrieving advertisements
- extracting promotions
- preserving source information
- recording retrieval status


The scraper must not:

- create recipes
- create meal plans
- modify pantry inventory
- mark items purchased


---

# Directory Structure

ads/

README.md

raw/

processed/


---

# Raw Data

Raw advertisement data preserves the original imported source.

Examples:

- downloaded advertisements
- scraped pages
- extracted source documents


Raw data should not be modified after import.

---

# Processed Data

Processed data contains normalized promotion records.

Processed records are generated from raw sources.

They should preserve:

- original store
- original source URL
- retrieval timestamp
- effective dates
- extracted deals


---

# Advertisement Record Schema

Each advertisement record should include:

version

metadata

deals


Example:

version: 1


metadata:

  store: Example Market

  source:

    url: https://example.com/weekly-ad

    retrieved_at: 2026-09-07T10:30:00


  effective_dates:

    start: 2026-09-07

    end: 2026-09-13


  status: retrieved


deals:

  - item:

      name: chicken breast


    promotion:

      type: sale

      price: "$1.99/lb"


---

# Metadata

Required fields:


metadata:

  store:

  source:

  effective_dates:

  status:


---

# Store Rules

The store must exist in:


$HOUSEHOLD_ROOT/grocery-data/stores.yaml


Do not:

- invent stores
- add stores automatically
- assume nearby stores exist


---

# Source Rules

Every advertisement must preserve:


source:

  url:

  retrieved_at:


The source URL must identify where the information was obtained.


Do not:

- replace source URLs with archive URLs
- claim direct verification without evidence
- infer prices from unrelated store pages


---

# Effective Dates

Promotions should include their active period when available.


Example:


effective_dates:

  start: 2026-09-07

  end: 2026-09-13


If unavailable:


effective_dates:

  status: unknown


Do not infer missing dates.


---

# Retrieval Status

Allowed values:


retrieved

partial

unavailable


Meaning:


retrieved:

The advertisement was successfully obtained and verified.


partial:

Some information was obtained but the source was incomplete.


unavailable:

The source could not be retrieved or verified.


---

# Deal Records

Deals represent extracted source information.

Example:


deals:

  - item:

      name: chicken breast


    promotion:

      type: sale

      price: "$1.99/lb"


Do not include:

- meal recommendations
- recipe selections
- shopping decisions


Those belong to other skills.


---

# Price Rules

Prices are advisory and time-sensitive.


Never:

- assume a price is current
- claim a discount without a source
- modify recipes because of prices
- infer prices from store location


---

# Relationship To Other Systems


Grocery advertisements:


grocery-data

      |

      v

recipe-recommendation-agent

      |

      v

household-meal-planner

      |

      v

plans/*.yaml


Advertisement data does not directly create:

- recipes
- meal plans
- grocery lists


---

# Validation Rules

Before accepting advertisement data:


Verify:

- store exists in stores.yaml
- source URL exists
- retrieval date exists
- effective dates are recorded when available
- status accurately reflects retrieval quality


Never present unavailable data as verified.
