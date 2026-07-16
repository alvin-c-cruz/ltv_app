# Decumulator / Accumulator Period-Schedule Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `CreateSchedules` regenerate a Decumulator/Accumulator's bi-weekly period schedule so it matches the counterparty bank's termsheet exactly, instead of drifting.

**Architecture:** The bi-weekly/weekly period-end grid is anchored at `start_date` (`end_i = start_date + step·i − 1`), each end rolled forward independently to a business day (no cascade), with a fixed period count `N` sized to the tenor so the final period is written. The `monthly` branch is left exactly as-is. Correctness is proved by a standalone regression harness that regenerates three already-corrected contracts and asserts a zero-diff against their stored schedules.

**Tech Stack:** Python 3.13, Flask app factory (`ltv_app.create_app`), raw `sqlite3` (`get_db`), the `.venv` at `server/.venv`. No pytest suite exists in this copy — the "test" is a runnable harness script.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-16-decumulator-period-schedule-fix-design.md`.
- Only touch `ltv_app/blueprints/term_sheet/models.py` (class `CreateSchedules`) for the fix; do **not** change the `monthly` branch, `check_date`, `Counter`, or `is_holiday`.
- Bi-weekly convention (verified against contract #1449): fixed grid `end_i = start_date + (step·i − 1) days` (`step` = 14 for `bi-weekly`/`bi-monthly`, 7 for `weekly`), each end rolled **forward** to the next business day independently; `start_i` = previous rolled end + 1 business day; `N = round((maturity − start_date).days / step)`, minimum 1.
- Acceptance = **zero diff** (per-period `start_date`, `end_date`, `days`) for contracts **#1449, #1444, #1441** vs their stored `tbl_stock_contract_period` rows.
- Run everything with `server/.venv/Scripts/python.exe`, cwd `server/`.
- The DB in use is `server/instance/LTV Stocks.db` (a fresh copy of production, contains the corrected schedules). The harness never mutates it — it regenerates on a throwaway copy.

---

## File Structure

- **Create** `scripts/verify_period_schedule.py` — the regression harness (test). One responsibility: regenerate the three golden contracts on a DB copy and diff against their stored schedules.
- **Modify** `ltv_app/blueprints/term_sheet/models.py` — `CreateSchedules.__init__` period-generation loop and `__next_end_date` (remove the now-dead bi-weekly/weekly branch).

---

### Task 1: Regression harness (the failing test)

**Files:**
- Create: `scripts/verify_period_schedule.py`

**Interfaces:**
- Consumes: `ltv_app.create_app`, `ltv_app.blueprints.database.views.get_db`, `ltv_app.blueprints.term_sheet.models.CreateSchedules`.
- Produces: a script that exits 0 (all match) or 1 (any mismatch) and prints per-contract PASS/FAIL with the first differing period.

- [ ] **Step 1: Write the harness**

Create `scripts/verify_period_schedule.py`:

```python
"""Regression harness for the Decumulator/Accumulator period-schedule generator.

Regenerates each golden contract's schedule with CreateSchedules on a throwaway
copy of instance/LTV Stocks.db and diffs it, period-by-period, against the
contract's stored (bank-correct) tbl_stock_contract_period rows. Exit 0 iff all
match. Run: server/.venv/Scripts/python.exe scripts/verify_period_schedule.py
"""
import os, sys, shutil, tempfile
from types import SimpleNamespace

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
sys.path.insert(0, SERVER)

from ltv_app import create_app
from ltv_app.blueprints.database.views import get_db
from ltv_app.blueprints.term_sheet.models import CreateSchedules

GOLDEN = [1449, 1444, 1441]
SRC = os.path.join(SERVER, "instance", "LTV Stocks.db")


def _periods(db, ref):
    return [(str(r["start_date"])[:10], str(r["end_date"])[:10], r["days"])
            for r in db.execute(
                "SELECT start_date, end_date, days FROM tbl_stock_contract_period "
                "WHERE contract_ref=? ORDER BY start_date", (ref,)).fetchall()]


def _contract(db, ref):
    r = db.execute(
        "SELECT ref_num, trade_date, start_date, code_ref, tenor, frequency, gtd "
        "FROM tbl_stock_contract WHERE ref_num=?", (ref,)).fetchone()
    if r is None:
        return None
    return SimpleNamespace(
        ref_num=r["ref_num"], trade_date=str(r["trade_date"])[:10],
        start_date=str(r["start_date"])[:10], code_ref=r["code_ref"],
        tenor=r["tenor"], frequency=r["frequency"], gtd=str(r["gtd"]))


def _open(path):
    app = create_app()
    app.config["DATABASE"] = path
    ctx = app.app_context()
    ctx.push()
    return ctx, get_db()


def main():
    failures = 0
    for ref in GOLDEN:
        ctx0, db0 = _open(SRC)
        ts = _contract(db0, ref)
        expected = _periods(db0, ref) if ts else []
        ctx0.pop()
        if not ts or not expected:
            print(f"  #{ref}: SKIP (contract or stored schedule not found)")
            failures += 1
            continue

        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        shutil.copy(SRC, tmp)
        try:
            ctx, db = _open(tmp)
            db.execute("DELETE FROM tbl_stock_contract_period WHERE contract_ref=?", (ref,))
            db.commit()
            CreateSchedules(ts, db)
            actual = _periods(db, ref)
            ctx.pop()
        finally:
            os.unlink(tmp)

        if actual == expected:
            print(f"  #{ref} {ts.frequency}: PASS ({len(expected)} periods)")
        else:
            failures += 1
            print(f"  #{ref} {ts.frequency}: FAIL  expected {len(expected)} periods, got {len(actual)}")
            for i in range(max(len(expected), len(actual))):
                e = expected[i] if i < len(expected) else None
                a = actual[i] if i < len(actual) else None
                if e != a:
                    print(f"      P{i+1}: expected {e}  got {a}")
                    break

    print("RESULT:", "ALL PASS" if failures == 0 else f"{failures} contract(s) FAIL")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the harness against the current (buggy) code**

Run: `.venv/Scripts/python.exe scripts/verify_period_schedule.py`
Expected: **FAIL** — at least #1444 and #1441 report a mismatch at their tail (the current generator drops the final period and/or drifts). Example line: `#1444 bi-monthly: FAIL  expected 26 periods, got 25`. This proves the harness detects the bug.

> If a golden contract instead reports SKIP or an unexpected shape, stop and confirm that contract's stored schedule is actually the corrected one (cross-check the bank termsheet PDF) before treating a later PASS/FAIL as meaningful — a stale golden invalidates the test for that contract.

- [ ] **Step 3: Commit the harness**

```bash
git add scripts/verify_period_schedule.py
git commit -m "test(term_sheet): add period-schedule regression harness (currently failing)"
```

---

### Task 2: Fix the bi-weekly / weekly generator

**Files:**
- Modify: `ltv_app/blueprints/term_sheet/models.py` — `CreateSchedules.__init__` (the period-generation loop) and `__next_end_date` (drop the dead bi-weekly/weekly branch).

**Interfaces:**
- Consumes: existing `self.check_date`, `self.__next_start_date`, `Counter`, `FixingSchedule` (all unchanged).
- Produces: `CreateSchedules(term_sheet, db)` writes the correct, contiguous, full-length schedule for `monthly`, `bi-weekly`, `bi-monthly`, and `weekly`.

- [ ] **Step 1: Replace the period-generation loop in `__init__`**

In `ltv_app/blueprints/term_sheet/models.py`, replace the current tail of `CreateSchedules.__init__` — the block that starts at `start_date = self.start_date` / `end_date = self.trade_date` and runs the `while end_date < self.end_date:` loop — with:

```python
        contract_ref = term_sheet.ref_num  # keep the existing binding above; shown for context

        if self.frequency == "monthly":
            # UNCHANGED behaviour: month-anchored while-loop. Saves each period
            # including the final one (the old `or self.frequency == "monthly"`
            # guard was always true here).
            start_date = self.start_date
            end_date = self.trade_date
            i = 0
            while end_date < self.end_date:
                i += 1
                end_date = self.__next_end_date(end_date, i)
                end_date_on_record = self.check_date(end_date)
                days = Counter(self.db, start_date, end_date, self.code_ref).count
                FixingSchedule(
                    db=self.db, contract_ref=contract_ref, start_date=start_date,
                    end_date=end_date, days=days,
                    gtd="Yes" if i <= self.gtd else "No",
                ).save()
                start_date = self.__next_start_date(end_date_on_record)
        else:
            # bi-weekly / bi-monthly / weekly: fixed grid anchored at start_date,
            # each end rolled forward independently (no cascade), N periods to
            # span the tenor including the final period.
            step = 7 if self.frequency == "weekly" else 14
            anchor = datetime.strptime(str(self.start_date)[:10], "%Y-%m-%d")
            maturity = datetime.strptime(str(self.end_date)[:10], "%Y-%m-%d")
            num_periods = max(1, round((maturity - anchor).days / step))
            start_date = self.start_date
            for i in range(1, num_periods + 1):
                grid_end = str((anchor + timedelta(days=step * i - 1)).date())
                end_date = self.check_date(grid_end)
                days = Counter(self.db, start_date, end_date, self.code_ref).count
                FixingSchedule(
                    db=self.db, contract_ref=contract_ref, start_date=start_date,
                    end_date=end_date, days=days,
                    gtd="Yes" if i <= self.gtd else "No",
                ).save()
                start_date = self.__next_start_date(end_date)
```

Notes for the implementer:
- `datetime`, `date`, and `timedelta` are already imported at the top of `models.py` (used by `check_date`/`Counter`/the old branch) — do not add imports.
- Keep every line above `start_date = self.start_date` in `__init__` (the `self.trade_date`, `self.tenor`, `self.gtd` setup and the `self.gtd *=` frequency scaling) exactly as-is.
- `contract_ref` is already assigned near the top of `__init__`; the line in the snippet is only for context — do not duplicate it.

- [ ] **Step 2: Remove the now-dead bi-weekly/weekly branch from `__next_end_date`**

In `CreateSchedules.__next_end_date`, delete the two `elif` branches for `("bi-weekly", "bi-monthly")` and `("weekly")` and their trailing `return self.check_date(end_date)` so the method keeps only the `monthly` branch (still called by the monthly loop). The method becomes monthly-only:

```python
    def __next_end_date(self, previous_end_date, i):
        # monthly only — bi-weekly/weekly is generated inline in __init__ from a
        # fixed start_date grid.
        trade_year = int(self.trade_date[:4])
        trade_month = int(self.trade_date[5:7])
        total = (trade_month - 1) + i
        end_year = trade_year + total // 12
        end_month = total % 12 + 1
        end_date = None
        day = self.end_day
        while end_date is None:
            try:
                end_date = str(date(end_year, end_month, day))
            except ValueError:
                day -= 1
        return self.check_date(end_date)
```

(This is the existing monthly logic verbatim, with the `if self.frequency == "monthly":` guard and the dead branches removed — `__next_end_date` is now only ever called from the monthly path.)

- [ ] **Step 3: Run the harness**

Run: `.venv/Scripts/python.exe scripts/verify_period_schedule.py`
Expected: **PASS** — `#1449 ... PASS`, `#1444 ... PASS`, `#1441 ... PASS`, `RESULT: ALL PASS`, exit 0.

- [ ] **Step 4: Sanity-check monthly is unchanged**

Pick any `monthly`-frequency contract ref that has a stored schedule (find one with:
`.venv/Scripts/python.exe -c "import sqlite3;d=sqlite3.connect(r'instance/LTV Stocks.db');print([r[0] for r in d.execute(\"SELECT ref_num FROM tbl_stock_contract WHERE frequency='monthly' AND ref_num IN (SELECT contract_ref FROM tbl_stock_contract_period) LIMIT 5\")])"`),
add it to `GOLDEN` in the harness temporarily, re-run, confirm it PASSes, then revert the harness edit. (Monthly must still reproduce exactly.)

- [ ] **Step 5: Commit**

```bash
git add ltv_app/blueprints/term_sheet/models.py
git commit -m "fix(term_sheet): reproduce the bank's bi-weekly period schedule exactly

Anchor bi-weekly/weekly period-ends on a fixed start_date grid rolled forward
independently (no cascade) and generate a fixed N periods so the final period
is written. Monthly path unchanged. Verified zero-diff against contracts
1449/1444/1441 via scripts/verify_period_schedule.py."
```

---

## Self-Review

**Spec coverage:** ① cascading-drift root cause → fixed by the grid-anchored `end_i` in Task 2 Step 1. ② dropped-final-period root cause → fixed by the `for i in range(1, N+1)` loop. ③ "same convention for all counterparties" / "reproduce exactly" → the zero-diff harness (Task 1) over the three DBPe goldens. ④ monthly untouched → explicit `if self.frequency == "monthly"` branch keeps the old code; Task 2 Step 4 verifies. ⑤ forward-looking/on-demand only, no touching existing locked data → the fix only runs when generation is invoked; the harness uses a throwaway copy.

**Placeholder scan:** none — all steps carry runnable code/commands and expected output.

**Type consistency:** `_periods` tuples `(start_date, end_date, days)` match between expected and actual; `CreateSchedules(term_sheet, db)` signature matches the app's call site (`views.py`); `FixingSchedule(db=, contract_ref=, start_date=, end_date=, days=, gtd=)` matches the existing constructor used elsewhere in `__init__`.

**Risk carried forward:** if #1449's stored schedule was corrected in a browser session but never persisted to the DB now in `instance/`, its golden is stale — Task 1 Step 2's note tells the implementer to confirm against the termsheet before trusting the result. #1444/#1441 were re-verified and re-locked (BUGS.md), so they are the reliable goldens.
