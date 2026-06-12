# Spec Enhancer Skill — Design

**Date:** 2026-06-12  
**Status:** Approved  

## Overview

A project-local skill (`spec-enhancer`) that automatically improves every brainstorming spec before the user reviews it. It runs four systematic passes on the draft spec file, overwrites it in-place, and prints a change summary.

## Pipeline Position

```
brainstorm → draft spec → spec self-review → spec-enhancer → user reviews → writing-plans
```

Triggered automatically after brainstorming self-reviews the spec. A CLAUDE.md instruction enforces this: *"After brainstorming writes and self-reviews a spec, always invoke `spec-enhancer` on the spec file before asking the user to review it."*

Also triggerable manually when the user says "enhance the spec", "improve the spec", "ground this spec".

## Input / Output

- **Input:** Path to the draft spec file (e.g. `docs/superpowers/specs/2026-06-12-foo-design.md`)
- **Output:** Same file, overwritten with improvements. Terminal summary of changes per pass.

## The Four Passes

### Pass 1 — Vagueness Resolution

Scan the spec for weak language: "TBD", "TODO", "should", "might", "etc.", "as needed", "if applicable", "some", "various", "potentially". For each hit:
- If the codebase or spec context makes the right answer obvious, make an explicit decision.
- Otherwise, ask one targeted question, wait for the answer, then continue. Resolve all vague items before moving to Pass 2.

No placeholder or ambiguous phrase survives this pass.

### Pass 2 — Edge Case Generation + Permission Checks

For each feature or requirement in the spec, generate explicit handling for:
- Invalid or missing inputs
- DB operation failures
- Records that don't exist or have already been modified
- Quantity/date boundary conditions

**Permission sub-pass (mandatory for every route):**
- Which user levels (1=admin, 2=audit, 3=accountant, 4=bookkeeper, 5=viewer) may access this feature?
- Which decorator applies: `@login_required` or `@superuser_required`?
- Are there read vs. write distinctions by level?
- What happens when a lower-privileged user attempts the action?

Every route in the spec must have an explicit access policy. No route is left unspecified.

### Pass 3 — Codebase Grounding

Read the spec to identify what's being built, then use Glob/Grep to locate:
- Affected blueprint directory and `views.py`
- Relevant model classes and their file paths
- Related Jinja2 templates
- DB tables involved (`tbl_*`)
- Any extension files in `extensions/`

Replace all generic references ("the transaction model", "the edit form") with exact paths and names (e.g. `ltv_app/blueprints/transactions/models.py:Transaction`, `ltv_app/blueprints/transactions/pages/transactions/edit.html`).

### Pass 4 — Convention Compliance

Read `CLAUDE.md` and check the spec against established project rules. Flag and correct any violation:

| Rule | Check |
|------|-------|
| No `confirm()`/`alert()`/`prompt()` | Any confirmation flow must use the custom modal |
| Blueprint pattern | New routes follow `views.py` + `models.py` + `pages/` structure |
| DB connection | All DB access uses `get_db()`, never direct `sqlite3.connect()` |
| Schema changes | Spec must note that `localhost/` must be analyzed first |
| Index/home page | Any changes to home page require explicit user approval |
| Report generation | Excel reports use templates from `instance/excel_templates/` |
| Timezone | Uses `ph_now()` / `ph_today()` from `ltv_app/tz.py` |

## Terminal Output Format

```
Spec enhanced: docs/superpowers/specs/2026-06-12-foo-design.md

Pass 1 — Vagueness:     4 items resolved
Pass 2 — Edge cases:   11 added (3 permission policies, 8 error states)
Pass 3 — Grounding:     6 references replaced with exact paths
Pass 4 — Conventions:   2 violations corrected

Review the spec, then proceed to writing-plans.
```

## Skill Location

`.claude/skills/spec-enhancer/SKILL.md` — project-local skill, not added to any plugin.

## CLAUDE.md Addition

Under the Development Commands section:

> After brainstorming writes and self-reviews a spec, always invoke `spec-enhancer` on the spec file before asking the user to review it.
