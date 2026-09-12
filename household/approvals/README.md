# Household Approval Records

This directory contains approval records for household workflow transitions.

Location:

$HOUSEHOLD_ROOT/approvals


The household-wide instructions are:

$HOUSEHOLD_ROOT/ASSISTANT.md


---

# Purpose

Approval records capture human decisions before workflow mutations.

They provide an audit boundary between:

suggested

and

approved


Approval records are not:

- recipes
- recommendations
- meal plans
- grocery lists
- inventory records


---

# Ownership

Approval records are maintained by:

household-workflow


Individual skills remain responsible for their own artifacts.


---

# Approval Use Cases

Current approval points:


Recipe recommendation approval:

recommendation

|

v

approved selection

|

v

meal planning



Meal plan approval:

draft meal plan

|

v

approved meal plan

|

v

grocery generation



Obsidian publication:

approved artifact

|

v

presentation approval

|

v

Obsidian presentation

(presentation-layer operation; no external synchronization)



---

# Directory Structure

approvals/

README.md

YYYY-MM/

approval-YYYY-MM-DDTHH-MM-SS.yaml


---

# Approval Schema

Example:


version: 1


approval:

  id: approval-2026-09-07T10-30-00


  created_at: 2026-09-07T10:30:00


  status: approved


  action:

    type: meal-plan-selection



source:


  artifact:

    type: recommendation


    path: $HOUSEHOLD_ROOT/recommendations/week-YYYY-MM-DD.yaml



selection:


  recipes:

    - chicken-tikka-masala

    - vegetable-lasagna



---

# Status Values


pending

approved

rejected

cancelled


---

# Action Types


Allowed values:


meal-plan-selection

meal-plan-approval


---

# Approval Rules


Approval must identify:


- who or what requested the action
- what artifact was reviewed
- what decision was made
- when the decision occurred


---

# Recommendation Approval


Example:


source:


  artifact:

    type: recommendation


selection:


  recipes:

    - recipe-id



The approved recipe IDs become input for:

household-meal-planner



---

# Meal Plan Approval


A draft meal plan must not trigger grocery generation until approved.


Example:


source:


  artifact:

    type: meal-plan


    path: $HOUSEHOLD_ROOT/plans/week.yaml


status:

  approved



---

# Canonical Artifact Approval

Approvals govern modifications to canonical household artifacts.

Approval applies to:

- recipe recommendations
- meal-plan selection and approval
- grocery-list generation
- pantry inventory modifications

Pantry modifications require the:

modify_pantry_inventory

approval.

No action may modify canonical household artifacts without the
corresponding approval.

## Obsidian Publication Approval

Obsidian publication is a presentation-layer operation.

It renders canonical data into the visual vault and does not change the
canonical data itself.

There is no external shopping or inventory synchronization approval.

Approval does not by itself:

- mark items purchased
- modify recipes
- modify pantry inventory


---

# Validation Rules


Before using an approval record:


Verify:


- referenced artifact exists
- status is valid
- action type is valid
- timestamps exist


Do not:


- approve missing artifacts
- infer approval
- reuse expired approvals


---

# Relationship To Other Systems


Recommendations:


recommendations/*.yaml

        |

        v

approval record

        |

        v

meal planner



Meal plans:


plans/*.yaml

        |

        v

approval record

        |

        v

grocery-list-generator



Grocery lists:


grocery-lists/*.yaml

        |

        v

approval record

        |

        v

household consumer (grocery list)

(shopping execution; no external synchronization)



---

# Design Principle


Approval records document decisions.

They do not own the data being approved.
