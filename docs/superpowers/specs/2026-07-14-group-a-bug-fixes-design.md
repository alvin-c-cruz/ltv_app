# Group A bug fixes — design

Date: 2026-07-14
Status: Approved, pending implementation

## Context

`BUGS.md` (kept out of this public repo; lives in the wrapping `LTV-ai` workspace
only) tracks 9 known issues in `ltv_app`. They span independent subsystems with
very different risk profiles, so rather than one sprawling design they've been
split into sub-projects:

- **Group A** (this spec) — five small, independent, low-risk fixes.
- **Group B** — the period-schedule subsystem (validation + the Decu drift bug).
  Touches real client contract math; needs its own design, including how the
  regenerated schedules get validated against actual bank termsheets.
- **Group C** — the Workflow "Charges" stage skip. Blocked on a product decision
  (should term-sheet contracts have a Charges stage at all?) before any design
  makes sense.
- Bug #9 (edit-flow JS-population flakiness) — the originally reported repro
  path (View → Unlock → full-page edit) turned out to be correctly
  server-rendered on inspection and did not reproduce live. However, a
  *different* code path was found during this investigation — the quick-edit
  **modal** on the Trades Done page (`transactions/home.html:890-914`) does
  populate Spot/Strike/KO via a JS fetch to `/term-sheet/<ref>/data`, which is
  the mechanism the original bug report hypothesized. That path hasn't been
  tested. Flagged as a follow-up, not fixed here.

All five Group A fixes were reproduced and root-caused against a local instance
of `ltv_app` running against a fresh copy of the production database (pulled via
the PythonAnywhere API, kept local-only, never committed).

## Scope

Fix five independent, low-risk bugs:

1. Unlock 405 on locked term-sheet contracts
2. Fixings "Record" redirects to today instead of the recorded date
3. Bank Reference No. has no missing-value indicator
4. "Print Trades Done" button does nothing
5. Period Schedule's per-row "To Decu" column doesn't update live

Out of scope: Group B, Group C, the bug #9 follow-up, and PythonAnywhere
deployment (local verification only — deploying is a separate, explicit step).

## 1. Unlock 405

**Root cause:** `term_sheet.unlock` (`ltv_app/blueprints/term_sheet/views.py:347`)
is `methods=["POST"]`. Both call sites render it as a plain
`<a href="{{ url_for('term_sheet.unlock', ...) }}">Unlock</a>` — a GET. The
method mismatch is unconditional; the link can never succeed as currently wired.

**Fix:** Replace both links with a POST form, matching the app's existing
Delete-button pattern:

```html
<form method="post" action="{{ url_for('term_sheet.unlock', contract_ref=ts.id) }}"
      style="display:inline" onsubmit="return confirm('Unlock this contract?')">
  <button type="submit" class="btn btn-outline btn-sm">Unlock</button>
</form>
```

Call sites: `ltv_app/blueprints/transactions/pages/transactions/home.html:89-90`
(Accumulators table) and `:144-145` (Decumulators table). No route change needed.

## 2. Fixings redirect

**Root cause:** the `fixings.record/<date>` view redirects to
`url_for('fixings.index')` with no `date` param, so the index defaults to
today instead of the date just recorded.

**Fix:** `redirect(url_for('fixings.index', date=date))`.

## 3. Bank Reference No. indicator

**Root cause:** `bank_doc` is a plain, optional text input
(`term_sheet/pages/term_sheet/edit.html:169-170`) with no required marker and
no visibility into whether it's missing from list views.

**Decision:** visual indicator only, not a hard-required field — a real bank
reference sometimes isn't issued yet when a trade is first booked, and
blocking save would be worse than a silent gap.

**Fix:**
- Edit/Add form (`edit.html`, `add.html`): wrap the "Bank Reference No." label
  in a conditional class when `ts.bank_doc` is blank (Jinja `{% if not
  ts.bank_doc %}`), styled with a warm outline — CSS only, no JS.
- Per-account Term Sheet list (`term_sheet/pages/term_sheet/home.html:59,99`)
  and Trades Done list (`transactions/pages/transactions/home.html`): where
  `bank_doc` renders as a table cell, show a small amber "missing" badge
  instead of a blank cell when empty.

## 4. Print Trades Done modal

**Root cause (corrected during plan-writing — see below):** the button is not
actually inert. `transactions/pages/transactions/home.html:39-41` already has
`onclick="window.open(this.href,'printTrades',...); return false;"`. Live
testing during the reproduction session showed zero effect (no navigation, no
new tab) — consistent with the `window.open()` call being silently blocked by
a popup blocker, which is exactly what "the button doesn't do anything" looks
like from a user's perspective (no error, nothing visible happens). The
original BUGS.md entry's premise ("no handler wired") was an incorrect
inference from the symptom; the actual defect is reliance on a blockable
`window.open()` popup rather than an in-page UI element. The target report
(`/trades/print_with_gain_loss/<date>`) itself works correctly when navigated
to directly — only the popup delivery mechanism is unreliable.

**Decision:** show the report in a modal (not a new tab or same-tab nav), reusing
the app's existing `modal-overlay` pattern already used for `+Spot`/`+Contract`/etc.

**Fix:** add a `printModal` block to `transactions/pages/transactions/home.html`
containing a large `<iframe>`. Replace the button's `window.open(...)` handler
with `onclick="openTxnModal('printModal')"`, and on open, set the iframe `src`
to `/trades/print_with_gain_loss/{current_trade_date}` (the Portrait/Landscape
toggle and all existing report behavior work unmodified inside the iframe).
This also structurally fixes the popup-blocker exposure, since nothing calls
`window.open()` anymore. No backend route changes.

## 5. Per-row "To Decu" live update

**Root cause:** the table footer (Received/Remaining/Total) is already wired to
a live JS listener (`updateToDecuTotals()`,
`term_sheet/pages/term_sheet/edit.html:460-488`) and updates correctly — this
part of the original bug report is already fixed. What's still stale is the
**per-row** "To Decu" `<td>` (`edit.html:246-255`), which is static
server-rendered Jinja text with no `id`/JS hook.

**Fix:** convert that `<td>` to a `readonly` `<input class="row-todecu">`
(styled like the readonly footer cells), server-rendered with its current value
as now. Extend `updateToDecuTotals()` to also write `days * multiplier` into
the row's own input alongside the footer, using the same `.period-days` /
`daily_shares` / `leveraged` input listeners already in place.

## Verification

No test suite exists in this copy (`tests/` removed per repo history, `pytest`
unused). Verification is manual, via the local `ltv_app` instance (run against
a local-only copy of the production DB) driven through Chrome browser
automation:

1. **Unlock:** click Unlock on a locked Accu row and a locked Decu row on
   Trades Done → confirm both land on the edit page instead of a 405.
2. **Fixings:** record fixings for a date with none yet → confirm the redirect
   lands back on that date, not today.
3. **Bank Reference:** save a contract with it blank → confirm the
   label/badge appears on the form, the per-account Term Sheet list, and the
   Trades Done list; fill it in → confirm the indicator clears.
4. **Print modal:** click "Print Trades Done" → confirm the modal opens with
   the report rendered inside, the Portrait/Landscape toggle still works
   inside the iframe, and closing it returns to Trades Done with filter state
   intact.
5. **Live totals:** edit a period's Days value → confirm that row's To Decu
   cell updates immediately, matching the already-live footer.

## Files touched

- `ltv_app/blueprints/transactions/pages/transactions/home.html` — Unlock
  forms (×2), Print modal + button, Bank Reference indicator
- `ltv_app/blueprints/fixings/views.py` — redirect target
- `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html` — Bank Reference
  label, To Decu row input + JS
- `ltv_app/blueprints/term_sheet/pages/term_sheet/add.html`,
  `home.html` — Bank Reference indicator

## Deployment

Local only. Pushing to the PythonAnywhere `larrylilia` deployment is a
separate, explicit step outside this plan.
