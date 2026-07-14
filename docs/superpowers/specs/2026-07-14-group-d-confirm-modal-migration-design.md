# Group D — app-wide confirm()/prompt() migration — design

Date: 2026-07-14
Status: Approved, pending implementation

## Context

During Group A (`docs/superpowers/specs/2026-07-14-group-a-bug-fixes-design.md`), fixing
the Unlock-405 bug required a decision about `ltv_app`'s many native `confirm()` dialogs:
they block Chrome browser automation entirely (a real testing-tool constraint), and more
importantly they're visually inconsistent with the rest of the app, which already has a
`.modal-overlay`/`.modal` styling system for everything else. The user decided, live during
that session, to build a small reusable confirmation-modal component
(`showConfirmModal`/`closeConfirmModal` in `ltv_app/static/js/main.js`, `#confirmModal`
markup in `ltv_app/templates/base.html`) and use it for the one Unlock call site Group A
touched — explicitly as the first instance of a component this project (Group D) would
later extend to every other `confirm()`/`prompt()` site in the app.

Group A's final whole-branch review flagged two follow-ups for this project to pick up:
the Confirm button is hardcoded to red (`btn-danger`) styling, and the Print-modal's
hardcoded report URL (`transactions/home.html`) is unrelated cleanup, not part of this
migration.

## Scope

Migrate every native `confirm()`/`prompt()` call site in `ltv_app` to the shared modal
component, extending the component's API only as far as the actual call sites require.

**Inventory** (surveyed 2026-07-14, current `main` at merge of Group A):

| # | File | Line(s) | Pattern |
|---|------|---------|---------|
| 1 | `ltv_app/static/js/main.js` + `ltv_app/templates/base.html` | 52-77 / 14-26 | Component itself — extend, no call-site change |
| 2 | `ltv_app/templates/macros.html` | 97, 104 | Shared Jinja macro (used by `stocks/form.html`, `stocks/home.html`) |
| 3 | `ltv_app/blueprints/fixings/pages/fixings/home.html` | 37, 97, 119 | `<a onclick="return confirm(...)">` |
| 4 | `ltv_app/blueprints/fixings/pages/fixings/transaction_macros.html` | 32 | `<a onclick="return confirm(...)">` |
| 5 | `ltv_app/blueprints/charges/pages/charges/home.html` | 84 | `<... onclick="return confirm(...)">` |
| 6 | `ltv_app/blueprints/workflow/pages/workflow/home.html` | 345, 378 | `<... onclick="return confirm(...)">` |
| 7 | `ltv_app/blueprints/lock/pages/lock/home.html` | 109, 169 | `<button onclick="return confirm(...)">` (109) + raw `if (confirm(...))` in a bulk-lock JS function (169) |
| 8 | `ltv_app/blueprints/bank_accounts/pages/bank_accounts/home.html` | 52 | `<... onclick="return confirm(...)">` |
| 9 | `ltv_app/blueprints/review/pages/review/home.html` | 37, 111, 170 | `<form onsubmit="return confirm(...)">` (×3, "Mark all reviewed") |
| 10 | `ltv_app/blueprints/upload/pages/upload/inspect.html` | 38, 47 | `<button onclick="return confirm(...)">` |
| 11 | `ltv_app/blueprints/users/pages/users/home.html` | 42 | `<a onclick="return confirm(...)">` |
| 12 | `ltv_app/blueprints/transactions/pages/transactions/home.html` | 99, 159, 205, 208, 216, 220, 265, 270 | `<a onclick="return confirm(...)">` (×8; the two Unlock-contract sites at 89-91/144-146 were already converted in Group A) |
| 13 | `ltv_app/blueprints/term_sheet/pages/term_sheet/edit.html` | 25, 28, 266, 345, 348 | `<button type="submit" form="external-id" onclick="return confirm(...)">` (Unlock/Lock ×2 pairs) + `<a onclick="return confirm(...)">` (Delete period) |
| 14 | `ltv_app/blueprints/term_sheet/pages/term_sheet/home.html` | 153, 179 | Raw `if (confirm(...)) { ... }` in JS (Set Inactive / Undo KO, context-menu-triggered) |
| 15 | `ltv_app/static/js/main.js` (`confirmation_message()`) + `ltv_app/blueprints/dividends/pages/dividends/home.html` | 47-49 / 46 | `prompt("Type YES to proceed.")`-based helper, sole caller is dividends Delete |

Out of scope: Group A's deferred Minor items (hardcoded print-report URL, redundant
`/trades/` Escape/backdrop listeners) — unrelated cleanup, not part of this migration.
No automated test suite exists in this repo; verification throughout is manual.

## 1. Component API extension

Current signature (`ltv_app/static/js/main.js:52`): `showConfirmModal(message, onConfirm)`.
Extend to a third, optional `options` parameter — fully backward-compatible, Group A's
existing Unlock call site needs no changes:

```js
function showConfirmModal(message, onConfirm, options) {
    options = options || {};
    var modal = document.getElementById('confirmModal');
    if (!modal) { if (onConfirm) onConfirm(); return; }

    document.getElementById('confirmModalMessage').textContent = message;

    var okBtn = document.getElementById('confirmModalOk');
    var newOkBtn = okBtn.cloneNode(true);
    okBtn.parentNode.replaceChild(newOkBtn, okBtn);
    okBtn = newOkBtn;

    okBtn.className = 'btn ' + (options.variant === 'primary' ? 'btn-primary' : 'btn-danger');

    var typedInput = document.getElementById('confirmModalTypedInput');
    if (options.requireTyped) {
        typedInput.style.display = 'block';
        typedInput.value = '';
        okBtn.disabled = true;
        typedInput.oninput = function () {
            okBtn.disabled = typedInput.value !== options.requireTyped;
        };
    } else {
        typedInput.style.display = 'none';
        typedInput.oninput = null;
        okBtn.disabled = false;
    }

    okBtn.addEventListener('click', function () {
        closeConfirmModal();
        onConfirm();
    });
    modal.classList.add('active');
}

function closeConfirmModal() {
    var modal = document.getElementById('confirmModal');
    if (modal) modal.classList.remove('active');
    var typedInput = document.getElementById('confirmModalTypedInput');
    if (typedInput) { typedInput.value = ''; typedInput.style.display = 'none'; }
}
```

`base.html:14-26` gains one new element (a text input, hidden by default) between the
message `<p>` and the button row:

```html
<input type="text" id="confirmModalTypedInput" style="display:none;width:100%;
       margin:0 0 16px;padding:8px 10px;" placeholder="Type to confirm" autocomplete="off">
```

`variant`: `'danger'` (default, matches current red styling — Delete/Unlock-class actions)
or `'primary'` (neutral gold `btn-primary` — Lock/Mark-reviewed/Record-class actions).
`requireTyped`: omit for the plain modal; set to an exact string (e.g. `'YES'`) to require
that text before Confirm enables — replaces `confirmation_message()`'s `prompt()` flow.

## 2. Migration mechanics by markup shape

**`<a onclick="return confirm(msg)">` (plain navigation, e.g. Delete/Unlock links):**
```html
<!-- before -->
<a href="{{ url_for(...) }}" onclick="return confirm('Delete this transaction?')">Delete</a>
<!-- after -->
<button type="button" onclick="showConfirmModal('Delete this transaction?', function(){
    window.location.href = '{{ url_for(...) }}';
})">Delete</button>
```
Several of these are GET links performing a mutation (the same "GET where POST belongs"
smell Group A's Task 1 fixed for Unlock) — where the target route is GET-only and mutating,
leave the route as-is for this migration (route-method correctness is a separate concern
from dialog styling); only convert the confirmation mechanism itself unless a task
discovers the same 405-class bug Group A found, in which case flag it rather than silently
fixing scope beyond this migration.

**`<button type="submit" form="external-id" onclick="return confirm(msg)">` (term_sheet edit's Unlock/Lock):**
```html
<!-- before -->
<button type="submit" form="form-unlock" onclick="return confirm('Unlock this contract?')">Unlock</button>
<!-- after -->
<button type="button" onclick="showConfirmModal('Unlock this contract?', function(){
    document.getElementById('form-unlock').requestSubmit();
})">Unlock</button>
```

**`<form onsubmit="return confirm(msg)">` (review's "Mark all reviewed" forms):**
```html
<!-- before -->
<form onsubmit="return confirm('Mark all {{ total }} transaction(s) as reviewed?')">
<!-- after -->
<form id="review-all-form" onsubmit="return false">
  ...
  <button type="submit" onclick="showConfirmModal('Mark all {{ total }} transaction(s) as reviewed?', function(){
      document.getElementById('review-all-form').submit();
  })">...</button>
```
(each of the 3 forms gets its own unique id, e.g. `review-all-form`, `review-all-short-form`,
`review-all-contracts-form`, matching the existing distinct messages)

**Raw `if (confirm(msg)) { ...body... }` in `<script>` (lock bulk-action, term_sheet context menu):**
```js
// before
if (confirm('Lock ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?')) {
    ...body...
}
// after
showConfirmModal('Lock ' + count + ' selected transaction' + (count > 1 ? 's' : '') + '?', function () {
    ...body...
});
```
The existing conditional body moves into the callback verbatim — no logic changes.

**`templates/macros.html`'s two macros:** rewrite their emitted HTML to the
button+`showConfirmModal` shape; `stocks/form.html` and `stocks/home.html` (the only two
callers) need no changes themselves.

**`confirmation_message()` / dividends delete:** remove the `prompt()`-based helper from
`main.js`; convert the one call site to
`showConfirmModal('Delete this dividend?', function(){ window.location.href = '...'; }, {requireTyped: 'YES'})`.

## 3. Task breakdown

Sequenced foundation-first, then roughly by file size/risk:

1. Extend `showConfirmModal` (variant + `requireTyped`) — no call-site changes yet, this is what every later task depends on
2. `templates/macros.html` (2 sites → fixes `stocks/*` with zero template changes there)
3. `fixings/home.html` (3) + `fixings/transaction_macros.html` (1)
4. `charges/home.html` (1) + `workflow/home.html` (2)
5. `lock/home.html` (2 — including the bulk-lock JS block)
6. `bank_accounts/home.html` (1)
7. `review/home.html` (3 — the onsubmit-form pattern, 3 near-identical forms)
8. `upload/inspect.html` (2)
9. `users/home.html` (1)
10. `transactions/home.html` (8 remaining sites — Delete contract ×2, Unlock/Delete transaction ×4, Delete transaction ×2)
11. `term_sheet/edit.html` (5 — two Unlock/Lock pairs, Delete period) + `term_sheet/home.html` (2 — Set Inactive, Undo KO)
12. `dividends/home.html` (1 — the `requireTyped` case, last since it exercises the newest part of the API; also removes `confirmation_message()` from `main.js`)

Each task: implement per its file(s), verify manually against the locally running app
(login, trigger the action, confirm the modal appears with correct message/variant,
Confirm executes the original action, Cancel/Escape/backdrop-click all correctly abort),
commit, task-scoped review — same process Group A used.

## Verification

No automated test suite exists in this repo. Verification is manual, per task, against a
locally running `ltv_app` instance driven via Chrome browser automation — same approach as
Group A.

## Deployment

Local only. Pushing to the PythonAnywhere `larrylilia` deployment is a separate, explicit
step outside this plan.
