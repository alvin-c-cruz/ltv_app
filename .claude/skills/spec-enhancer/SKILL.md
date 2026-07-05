---
name: spec-enhancer
description: Automatically improves brainstorming specs through four passes: vagueness resolution, edge case generation with permission checks, codebase grounding, and convention compliance. Invoke immediately after brainstorming writes and self-reviews a spec, before asking the user to review it. Also triggers when the user says "enhance the spec", "improve the spec", "ground this spec", or "run spec-enhancer".
---

# Spec Enhancer

Improve a draft spec through four systematic passes, then overwrite the file with the enhanced version.

## Input

The path to the draft spec file. If not provided, ask for it before proceeding.

## The Four Passes

Run all four passes and collect all improvements before writing anything. Overwrite the spec file once at the end.

### Pass 1 — Vagueness Resolution

Read the entire spec. Scan for weak language: "TBD", "TODO", "should", "might", "etc.", "as needed", "if applicable", "some", "various", "potentially", "where appropriate", "when necessary".

For each hit:
- If the codebase or surrounding spec context makes the right answer obvious, decide explicitly.
- Otherwise, ask one targeted question and wait for the answer before continuing.

Resolve ALL vague items before moving to Pass 2. No placeholder or ambiguous phrase survives this pass.

### Pass 2 — Edge Case Generation + Permission Checks

For each feature or requirement in the spec, add explicit handling for:
- Invalid or missing inputs (empty strings, None, out-of-range values)
- DB operation failures (IntegrityError, OperationalError)
- Records that don't exist or have already been modified or deleted
- Quantity/date boundary conditions (zero quantity, future dates, date range inversions)

**Permission sub-pass — mandatory for every route described in the spec:**

Check that each route explicitly states:
- Which user levels may access it: 1=admin, 2=audit, 3=accountant, 4=bookkeeper, 5=viewer
- Which decorator applies: `@login_required` or `@superuser_required`
- Read vs. write distinctions by level, if applicable
- What HTTP response a lower-privileged user receives (403, redirect, or hidden UI element)

Every route must have an explicit access policy. If any route is missing one, add it.

### Pass 3 — Codebase Grounding

Use Glob and Grep to locate the actual files involved:
- Affected blueprint directory and its `views.py`
- Relevant model classes with exact file paths (use `ltv_app/blueprints/<name>/models.py`)
- Related Jinja2 templates under `pages/`
- DB tables touched (`tbl_*`)
- Extension files under `extensions/` if relevant

Replace all generic references with exact paths and names. Examples:
- "the transaction model" → `ltv_app/blueprints/transactions/models.py:Transaction`
- "the edit form" → `ltv_app/blueprints/transactions/pages/transactions/edit.html`
- "the transactions table" → `tbl_transaction`

If a referenced file does not exist, flag it explicitly in the spec (do not silently drop the reference).

### Pass 4 — Convention Compliance

Read `CLAUDE.md`. Check the spec against these rules and correct any violation:

| Rule | Required behaviour |
|------|--------------------|
| Confirmation dialogs | Must use custom modal — never `confirm()`, `alert()`, or `prompt()` |
| Blueprint structure | New routes follow `views.py` + `models.py` + `pages/` pattern |
| DB connection | All DB access via `get_db()` — never `sqlite3.connect()` directly |
| Schema changes | Spec must state that `localhost/` must be analyzed before any schema change |
| Index/home page changes | Must note that explicit user approval is required before implementation |
| Excel reports | Use templates from `instance/excel_templates/` via `load_workbook()` |
| Timezone | Use `ph_now()` / `ph_today()` from `ltv_app/tz.py` — never `datetime.now()` |

For each violation: correct it in the spec and note it in the Pass 4 count.

## Output

1. Overwrite the spec file with all improvements applied.
2. Print this summary to the terminal (fill in actual counts):

```
Spec enhanced: <spec-file-path>

Pass 1 — Vagueness:     N items resolved
Pass 2 — Edge cases:    N added (N permission policies, N error states)
Pass 3 — Grounding:     N references replaced with exact paths
Pass 4 — Conventions:   N violations corrected

Review the spec, then proceed to writing-plans.
```
