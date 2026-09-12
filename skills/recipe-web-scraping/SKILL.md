---
name: recipe-web-scraping
version: 1
description: Use when scraping with crawl4ai or Wayback fails.
---

# Recipe Web Scraping (crawl4ai)

Use crawl4ai to scrape recipe pages when the Wayback Machine fails, or as a primary scraper. It drives a headless Chromium browser, so it works on sites that block plain HTTP fetches.

## Invocation

crawl4ai runs in an externally provisioned virtual environment, never the system python. The environment is provided at runtime via two environment variables:

- `CRAWL4AI_VENV` — absolute path to the venv interpreter (e.g. `.venv/bin/python`).
- `CRAWL4AI_PROJECT` — working directory for crawl4ai project/scripts (optional; needed only where the skill must operate inside a crawl project dir).

Browser binaries are staged externally (e.g. `~/.cache/ms-playwright/`); `CRAWL4AI_PROJECT` may contain a `test_crawl*.py` scratch area. None of these paths belong to this repository — they are machine-specific and must come from the environment.

Example:
```bash
"$CRAWL4AI_VENV" "$CRAWL4AI_PROJECT/my_script.py"   # or cd into $CRAWL4AI_PROJECT first
```

## Basic async crawl

```python
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig

async def main():
    config = CrawlerRunConfig(verbose=False)
    async with AsyncWebCrawler(verbose=False) as crawler:
        result = await crawler.arun(URL, config=config)
        md = result.markdown or result.markdown_v2 or ""
        print("success:", result.success, "status:", result.status_code)
        print(md)

asyncio.run(main())
```

`result.markdown_v2` is the fallback if `result.markdown` is empty.

## Pitfalls

- DEPENDENCY: `websockets` was missing from the venv and broke the `AsyncWebCrawler`/`websockets` import. Install it into the venv with `"$CRAWL4AI_VENV" -m pip install websockets` (from `$CRAWL4AI_PROJECT`). Check `pip list | grep -i websocket` first if a crawl errors on import.
- A bare `import crawl4ai` succeeding does NOT mean a crawl works; the Playwright browser must be staged (external). If errors mention browser launch, from `$CRAWL4AI_PROJECT` run the venv's setup/dependency executables, which live in the same bin dir as `$CRAWL4AI_VENV`:
  `"$(dirname "$CRAWL4AI_VENV")/crawl4ai-setup"` or `"$(dirname "$CRAWL4AI_VENV")/crawl4ai-download-models"`.
- The first run of AsyncWebCrawler spins up the browser and downloads models; allow a timeout of at least 60-120s.
- Use `timeout 120` on the terminal call; the browser init + scrape can take a moment.
- system python (python3) does NOT import crawl4ai. Always use the venv interpreter.

## Site-specific notes

### Serious Eats (seriouseats.com)

Cloudflare/Akamai 403s curl and plain web_extract. Bypass options, best first:
1. **crawl4ai** (Verification this session: got 200 + 36KB markdown for a recipe where curl→403 and Wayback had NO valid snapshot). Uses the venv interpreter above; the full ingredient/instruction lists render cleanly as `## Ingredients` / `## Directions`. Groups appear as `* **For the X:**` bullets; strip leading `*` and resolve `[text](url)` link markdown.
2. **Wayback Machine** via web_extract `https://web.archive.org/web/20210507175654/https://www.seriouseats.com/<slug>` (pick a real timestamp from CDX). Older (2021) slugs have clean 200 captures; recent 2025 Kristina Cimini/Rick A. Martínez (Kenji) recipes are often 402/redirect-only and unusable.

Slug pattern: `https://www.seriouseats.com/<dish-slug>-<numeric-id>` (NOT `/recipe/`). Never fetch the numeric-id slug with a bogus year — wayback `2023/` wildcard resolves, but `2024/`/`2025/` may land on archive.org's home.

### BudgetBytes (budgetbytes.com)

WordPress site. The raw markdown starts with a LOT of nav/menu junk (Recipe links, Sign up, etc.). The real recipe is further down. Slice from the first `## Ingredients` marker:

```python
idx = md.find("## Ingredients")
recipe = md[idx:]
```

Ingredients render as `* ▢ <qty> <ingredient> ($cost)` bullets — strip the `▢` and the trailing `($...)` cost annotation before normalizing into the recipe library. Instructions render as `### Instructions` followed by numbered `*` bullets. Nutrition data is at the end under `### Nutrition Information`.

The recipe body (intro, tips) sits BEFORE `## Ingredients`, so searching for 'keywords' finds the article copy first — use the exact `## Ingredients` heading to land on the ingredient list.
