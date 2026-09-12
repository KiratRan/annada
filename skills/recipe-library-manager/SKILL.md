# Recipe Library Manager Skill

## Purpose

Maintain the household Markdown recipe library.

Library:

```
$HOUSEHOLD_ROOT/recipes
```

Follow:

```
$HOUSEHOLD_ROOT/recipes/README.md
```

The recipe README defines the recipe format and metadata conventions.

This skill is responsible for creating normalized Markdown recipes, generating YAML frontmatter, and maintaining the generated recipe index.

---

# Responsibilities

- Import recipes.
- Normalize recipes.
- Create recipe files.
- Generate YAML frontmatter.
- Maintain recipe metadata.
- Check duplicates.
- Generate recipe index.
- Maintain Obsidian recipe presentation pages.

---

# Before Creating or Modifying Recipes

1. Read:

```
`$HOUSEHOLD_ROOT/ASSISTANT.md`
```

2. Read:

```
$HOUSEHOLD_ROOT/recipes/README.md
```

3. Inspect existing filenames.

4. Inspect existing recipe titles.

5. Check for duplicates.

6. Extract available:

- title
- category
- cuisine
- servings
- timing
- difficulty
- tags
- ingredients
- instructions
- notes
- source information
- verification status

---

# Frontmatter Management

Every new recipe must include YAML frontmatter.

Frontmatter is generated from verified recipe information.

Never:

- invent metadata
- estimate missing times
- invent dietary classifications
- claim source verification without evidence

Unknown values:

```
Unknown
```

---

# Recipe Creation Workflow

When creating a recipe:

1. Read source material.
2. Extract available recipe data.
3. Check duplicates.
4. Normalize recipe format.
5. Generate YAML frontmatter.
6. Create Markdown recipe file.
7. Update recipe index.
8. Verify files exist.
9. Report results.

---

# Recipe Index Management

The recipe index is:

```
$HOUSEHOLD_ROOT/recipes/index.yaml
```

The index is generated data.

The Markdown recipe files remain authoritative.

Never manually edit the index.

---

## Regenerate the index after:

- creating a recipe
- importing a recipe
- modifying recipe metadata
- changing recipe filenames
- removing a recipe with explicit approval

---

## Index generation rules

Generate the index from:

- recipe filenames
- YAML frontmatter
- normalized ingredient data when available

Include:

- recipe ID
- title
- filename
- category
- cuisine
- tags
- timing
- servings
- normalized ingredients

Do not include:

- full instructions
- full recipe text
- unsupported metadata

---

## Index validation

Before completing an operation:

Verify:

- every indexed recipe has a matching Markdown file
- every Markdown recipe has an index entry
- IDs match filenames
- metadata matches frontmatter

---

# File Safety

Never:

- overwrite recipes without approval
- delete recipes
- modify external application storage
- invent recipe information
- create recipes from incomplete sources

---

# File Naming

Use:

- lowercase
- hyphen-separated
- descriptive names

Example:

```
chicken-tikka-masala.md
```

---

# Source Handling

Preserve source attribution.

For website recipes record:

- original URL
- author if available
- verification method

Never:

- replace original URLs with archive URLs
- claim direct verification from archived sources

---

# Reporting

After creation or modification report:

- exact recipe path
- whether frontmatter was generated or updated
- whether index.yaml was updated
- unknown fields
- source information
- verification status
- assumptions made

---

# Obsidian Presentation Sync

Obsidian is a presentation layer, not an authoritative recipe store.

After creating or modifying a canonical recipe, the matching Obsidian recipe
presentation page must be regenerated to keep the presentation in sync with
the canonical source. Invoke:

```
obsidian-integration
```

to regenerate/update:

```
`$OBSIDIAN_VAULT/Recipes/<id>.md`
```

from the canonical recipe file (`$HOUSEHOLD_ROOT/recipes/<id>.md`).

Do not hand-edit the generated Obsidian recipe page. Regenerate it from the
canonical file.
