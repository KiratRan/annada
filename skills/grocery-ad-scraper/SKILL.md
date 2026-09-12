---
name: grocery-ad-scraper
description: "Collect grocery store weekly ads/circulars and extract sale items into a normalized promotions format."
version: 1.0.0
---

# Grocery Ad Scraper Skill

## Purpose

Collect current grocery promotions, weekly ads, circulars, and sale information from configured nearby stores.

This skill supports household meal planning by identifying discounted ingredients and promotions that can influence recipe selection, meal plans, and grocery lists.

## Ownership and Boundaries

This skill owns:

- Retrieving configured grocery promotions
- Extracting promotion evidence
- Normalizing promotion records
- Recording source and verification metadata
- Writing promotion reports when explicitly requested

This skill does not own:

- Recipe selection
- Recipe creation
- Meal-plan creation
- Grocery-list generation
- Pantry inventory
- Store configuration changes

## Configuration

Store locations are defined by:

`$HOUSEHOLD_ROOT/grocery-data/stores.yaml`

This is the authoritative store configuration path.

Only stores with:

```yaml
enabled: true
```

should be processed.

The configuration may contain:

- Store name
- Location
- ZIP code
- Enabled status
- Available ad or circular sources

If the configuration file is missing or invalid, stop and report the problem. Do not invent store locations or process unconfigured stores.

## Workflow

Before collecting advertisements:

1. Read `$HOUSEHOLD_ROOT/ASSISTANT.md`.
2. Read `$HOUSEHOLD_ROOT/recipes/README.md` when recipe recommendations will be generated.
3. Read `$HOUSEHOLD_ROOT/grocery-data/stores.yaml`.
4. Process only enabled stores.
5. Retrieve available weekly ads, circulars, or promotion pages.
6. Extract sale information.
7. Normalize promotions into a consistent format.
8. Report unavailable sources or verification problems.

## Supported Sources

Initial supported source types:

- `weekly_ad`
- `circular`

Each source must include:

- Store name
- Source URL
- Retrieval date
- Verification status

## Promotion Extraction

Capture:

- Product name
- Brand (when available)
- Package size (when available)
- Sale price
- Regular price (when available)
- Discount amount (when available)
- Sale dates (when available)
- Store location

Do not invent:

- Prices
- Dates
- Discounts
- Product availability

If information cannot be verified, mark it as:

`Unknown`

## Output

When explicitly requested, generate:

### Canonical format

Machine-readable YAML:

`$HOUSEHOLD_ROOT/grocery-data/promotions/<name>.yaml`

The YAML file is the authoritative promotion source for downstream processing.

Schema:

```yaml
metadata:
  retrieval_date: YYYY-MM-DD
  source_type: weekly_ad
  store: <store name from stores.yaml>
  location: <store location from stores.yaml>
  source_url: https://example.com
  verification_status: verified
  sale_start: YYYY-MM-DD
  sale_end: YYYY-MM-DD

promotions:
  - item_name: chicken breast
    brand: optional
    package_size: 1 lb
    sale_price: "$1.99/lb"
    regular_price: unknown
    discount: unknown
    sale_start: YYYY-MM-DD
    sale_end: YYYY-MM-DD
    store: <store name>
    location: <store location>
    verification_status: verified
    notes: optional
```

Human format: 

Markdown report:
`$HOUSEHOLD_ROOT/grocery-data/promotions/<name>.md`

The Markdown report is generated for human review.

Do not use Markdown parsing for integrations when a YAML promotion file exists.

Use `unknown` rather than inventing null-like values.

## Promotion Normalization

- Preserve product identity separately from price, package size, and sale dates.
- Preserve brand and package size when available.
- Do not merge products solely because their names are similar.
- Do not merge different package sizes into one promotion.
- Preserve store and location separately from item identity.
- Preserve the original source URL and retrieval date.
- Do not place sale prices, discounts, or store names inside `item_name`.
- Normalize equivalent units only when the conversion is unambiguous.
- Do not infer a unit price when the source provides only a package price.
- Do not infer a package size from an image or banner.

For example

```
- item_name: <product name>
  brand: <brand if known>
  package_size: <size>
  sale_price: "<price>"
  regular_price: unknown
  discount: unknown
  store: <store name>
  verification_status: verified
```

## Verification Status

Allowed values:

- verified
- partially_verified
- unverified
- unavailable
- expired

Rules:

- `verified` means the item, price, and applicable date information were directly confirmed.
- `partially_verified` means some fields were confirmed but others remain unknown.
- `unverified` means the source was found but the promotion could not be adequately confirmed.
- `unavailable` means the expected source could not be accessed.
- `expired` means the promotion's validity period has ended.

Never represent an unverified promotion as verified. This is especially important for OCR-derived flyer state.

## Meal Planning Integration

When used with meal planning:

- Consider existing recipes in `$HOUSEHOLD_ROOT/recipes`.
- Do not create recipes unless explicitly requested.
- Clearly distinguish:
  - Existing recipes
  - New suggestions
  - Sale-based recommendations

## Source-Specific Procedures

- Treat OCR output as provisional until checked against the flyer image.
- Preserve the flyer page number when available.
- Preserve the original PDF or source reference when available.
- Do not report a product-level price from a banner that does not show a product-level price.
- If OCR produces conflicting values, mark the field as `Unknown` and report the conflict.
- If sale dates differ across pages, preserve the page-specific dates rather than inventing one global date.

### Grocery store flyer (working method)
This is the general method used when a store's weekly ad is served as a download-hosted PDF or image flipbook rather than a plain web page. It was verified against a specific store's flyer and may require adjustment if a given store's website, redirect behavior, PDF structure, or OCR output changes.

A store whose ad is not a plain web page typically serves two targets from its store-location page: a download-hosted PDF and an image flipbook. Neither yields usable text via `web_extract`.

Store-specific source URLs, flyer links, and any per-store quirks belong in the household's store configuration, NOT in this skill.

Working procedure:
1. Start from the store's store-location/page in the household's store configuration and find the `Weekly Flyer` link.
2. curl/download that link — it may redirect to a download-host viewer page whose content embeds a file id.
3. Download the actual PDF directly, e.g. `curl -sL "<direct_download_url>" -o flyer.pdf`. This returns a real PDF.
4. The PDF is often ~half text-layer, half image-only pages. Extract text with pymupdf (`import pymupdf`): `doc[i].get_text()`. Pages returning empty text are image-only ads (produce/meat banners, manufacturer coupon pages) — render them `page.get_pixmap(dpi=200).save('p.png')` and OCR with `rapidocr_onnxruntime` (bundles its own model; `pip install rapidocr-onnxruntime`).
5. OCR reading order: sort results by bounding-box y-coordinate (`box[0][1]`); noisy text-boxes/leader lines/footers can be dropped.
6. Cross-check the deal dates printed on the flyer pages and report them.
7. Deal text pages tend to list non-produce items. The image-only pages often just carry branded banner ads, not item-level prices — don't fabricate a price from a banner.

Pitfalls: `vision_analyze` may be unavailable (auth) — use local rapidocr or tesseract instead. Tesseract-OCR can be installed on the host (`which tesseract`); pymupdf can still render pages to PNG for tesseract input: `page.get_pixmap(dpi=200).save('p.png')`. For faster OCR without python deps, `tesseract page2.png stdout` works directly. If tesseract is missing (e.g. fresh env), fall back to `rapidocr-onnxruntime` via a throwaway venv: `python3 -m venv v && v/bin/pip install pymupdf rapidocr-onnxruntime`.

## Source Verification

If a webpage cannot be directly accessed:

- State that it could not be verified.
- Identify the fallback source if one was used.
- Include the retrieval date.
- Do not claim current accuracy.

Example:

```
Could not be verified:
The store page was unavailable. Information was obtained from an archived source dated YYYY-MM-DD.
```

## Freshness

- Always record the retrieval date.
- Record sale start and end dates whenever available.
- Do not present expired promotions as current.
- If sale dates are missing, label the promotion date range as `Unknown`.
- Downstream recommendation skills must consider both retrieval date and sale validity dates.
- A promotion without verified dates must not be treated as a currently active sale without qualification.

## Persistence

- By default, return a report preview without writing files.
- Write promotion artifacts only when explicitly requested.
- When saving, generate the canonical YAML and Markdown report together.
- Do not overwrite an existing promotion artifact without explicit authorization.
- If the target filename already exists, ask whether to replace it or create a new version.

## File Safety

This skill must not:

- Modify recipes automatically.
- Modify meal plans automatically.
- Modify grocery lists automatically.
- Modify store configuration automatically.
- Access application databases.
- Store credentials, tokens, or secrets.

The skill may create output reports only when explicitly requested.
