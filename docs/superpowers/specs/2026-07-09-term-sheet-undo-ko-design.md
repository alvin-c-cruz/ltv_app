# Term Sheet: undo a KO from the context menu

**Date:** 2026-07-09
**Status:** Approved, pending implementation

## Problem

On `/term-sheet/<bank_id>`, right-clicking a contract row opens a context menu whose
only item is **Set Inactive**. There is no way to undo a knock-out. If a contract is
marked `KO` by mistake, the only recoveries today are the edit form's status dropdown
or a direct database edit. Setting a contract inactive is one-way from the menu, and
reverting a KO is not offered at all.

## Background: how KO is actually stored

`tbl_stock_contract.status` is a single free-text column and the only source of truth
for KO/active/inactive. There is no `ko` boolean, no `active` flag, no `ko_date`.
In the live database it takes exactly three values:

| status     | rows |
|------------|-----:|
| `inactive` | 1317 |
| `active`   |   72 |
| `KO`       |    6 |

Two facts that shape this design:

- **Nothing sets `status='KO'` automatically.** The `localhost/modules/fixings*.py`
  modules compute a *derived* KO from prices for reporting, but never write it back to
  `tbl_stock_contract`. KO is only ever set by hand through the edit form. A reverted
  status will therefore not be clobbered by a later recalculation.
- **All 6 current KO contracts have `locked=1`.** Any lock guard we copy from
  `set_inactive` means that, today, only a superuser can revert any KO in the database.
  This is intended, not incidental.

`tbl_stock_contract.ko_rate` is a pricing input (the KO barrier percentage), not a
status flag. It is not touched by this feature.

## Scope

A new context-menu item that reverts `status='KO'` to `status='active'`.

The item appears **only** on rows whose status is `KO`. The existing **Set Inactive**
item is offered on both `KO` rows and `DONE` rows (a `DONE` row is one whose periods
are all complete; it is still `status='active'` underneath). Showing the new item on a
`DONE` row would offer a no-op, so it is hidden there.

Out of scope: reviving `inactive` contracts. The home page filters `inactive` rows out
of the listing entirely, so the context menu cannot reach them. Doing so would require
a "show inactive" toggle or a separate view — a larger change, deliberately deferred.

## Permission model

Identical to `set_inactive`, so the two menu items behave consistently:

- `@login_required`.
- A `locked` contract returns **403** unless `current_user.role == 'superuser'`.

Consequence, stated plainly because it is surprising: since every KO contract in the
live database is locked, only a superuser can currently use this feature at all.

## Backend

New route in `applications/ltv_app/blueprints/term_sheet/views.py`, immediately below
`set_inactive`:

```python
@bp.route("/<contract_ref>/set-active", methods=["POST"])
@login_required
def set_active(contract_ref):
    db = get_db()
    row = db.execute(
        "SELECT status, locked FROM tbl_stock_contract WHERE ref_num=?", (contract_ref,)
    ).fetchone()
    if not row:
        return jsonify({"success": False, "message": "Contract not found"}), 404
    if row["locked"] and current_user.role != "superuser":
        return jsonify({"success": False, "message": "Contract is locked and cannot be modified"}), 403
    if row["status"] != "KO":
        return jsonify({"success": False, "message": "Only contracts with KO status can be set back to active"}), 400
    db.execute("UPDATE tbl_stock_contract SET status='active' WHERE ref_num=?", (contract_ref,))
    db.commit()
    return jsonify({"success": True, "message": "Contract status updated to active"})
```

Guard order — existence, then lock/permission, then precondition, then write — mirrors
`set_inactive`. Checking the lock before the status means a non-superuser who POSTs at
a locked contract gets 403 without learning that contract's status.

The `status != 'KO'` check is the server-side twin of the menu's visibility rule: the
menu hides the item on `DONE` rows, and this makes a hand-crafted POST against one fail.

### Why a dedicated route rather than a generalized `set_status`

A single `set-status` endpoint taking `{"status": ...}` in the body was considered and
rejected. Each target status carries a different precondition (`inactive` requires
KO-or-DONE; `active` requires KO), so a shared handler would be a branch on the
requested status — it would remove the duplicated guard clauses, which are the part
worth reading at the point of use, while widening the write surface on a production
financial column to a caller-supplied value.

## Frontend

`applications/ltv_app/blueprints/term_sheet/pages/term_sheet/home.html`.

The row `<tr class="clickable-row">` already carries `data-contract-ref` and
`data-status`. Add one attribute:

```html
data-set-active-url="{{ url_for('term_sheet.set_active', contract_ref=accu.ref_num) }}"
```

Add a second `<li>` to the context menu, labelled **"Set Active (undo KO)"** — the
parenthetical says why you would reach for it.

In the existing `contextmenu` handler, toggle the new item from the row's status before
showing the menu, leaving **Set Inactive** visible in both cases:

```javascript
setActiveOption.style.display = (status === 'KO') ? 'block' : 'none';
```

The click handler follows the existing item exactly: `confirm()`, `POST` with
`Content-Type: application/json` and an empty body, `location.reload()` on
`data.success`, otherwise `alert(data.message)`.

The new item reads its URL from `data-set-active-url`. The existing **Set Inactive**
item keeps its current `{{ url_for('term_sheet.home', bank_id='') }}/../${ref}/set-inactive`
relative-path construction; converting it is a change to working code and is
deliberately left out of this diff.

## Data effects

One column write, `status = 'active'`, on one row of `tbl_stock_contract`. Nothing is
written to `tbl_stock_contract_period`. `locked` and `reviewed` are untouched, so a
locked contract remains locked after the revert.

## Testing

New file `tests/functional/test_term_sheet_set_active.py`, using the isolated temp
SQLite fixtures from `tests/functional/conftest.py`, seeded with a KO contract:

1. Superuser reverts a KO contract — 200, and `status` is `'active'` when read back
   through `db_conn`.
2. Non-superuser POSTs at a locked KO contract — 403, **and `status` is still `'KO'`**.
3. Contract with `status='active'` (a DONE row) — 400, status unchanged.
4. Unknown `ref_num` — 404.

The status-unchanged assertions in cases 2 and 3 carry the weight: a route that returns
the right code but writes anyway would pass without them.

`set_inactive` has no test coverage today. Adding it is out of scope here.

## Verification

Drive the menu with Playwright against a seeded test contract. The 6 real KO contracts
are production financial records and are not to be flipped as part of verification,
even though the action is reversible.
