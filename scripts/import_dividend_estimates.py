"""Import dividend declarations from dividends_analysis/json/ into tbl_cash_dividends
as status='Estimate' rows.

Dry-run by default (reports what it would do, writes nothing). Pass --apply to
actually insert new rows and correct the already_in_tbl_cash_dividends flag in the
source JSON files for declarations now fully represented in the DB.

Never trusts the JSON's own already_in_tbl_cash_dividends flag for skip decisions --
it's proven stale and file-level-only (see BUGS.md, 2026-07-23 dividend-declaration
-import entry: 0371_2022-09-28.json looked fully covered by file-level count but was
only 3/6 banks actually in the DB). Always checks tbl_cash_dividends directly by
(bank_ref, stock_ref, ex_date), per bank entitlement, not per file.

Run: server/.venv/Scripts/python.exe scripts/import_dividend_estimates.py [--apply]
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER = os.path.dirname(HERE)
WORKSPACE = os.path.dirname(SERVER)
JSON_DIR = os.path.join(WORKSPACE, "dividends_analysis", "json")


def resolve_bank(db, bank_id):
    """entitlement[].bank_id -> tbl_bank_account.ref_num, or None if unresolvable.

    Older JSON files store the actual ref_num as an int; newer files store the
    short bank_id code as a str and need a lookup.
    """
    if isinstance(bank_id, int):
        row = db.execute("SELECT ref_num FROM tbl_bank_account WHERE ref_num=?", (bank_id,)).fetchone()
    else:
        row = db.execute("SELECT ref_num FROM tbl_bank_account WHERE bank_id=?", (bank_id,)).fetchone()
    return row["ref_num"] if row else None


def resolve_stock(db, stock_code):
    row = db.execute("SELECT ref_num FROM tbl_code WHERE code=?", (stock_code,)).fetchone()
    return row["ref_num"] if row else None


def resolve_currency(db, ccy_id):
    row = db.execute("SELECT ref_num FROM tbl_currency WHERE ccy_id=?", (ccy_id,)).fetchone()
    return row["ref_num"] if row else None


def existing_row(db, bank_ref, stock_ref, ex_date):
    row = db.execute(
        "SELECT ref_num FROM tbl_cash_dividends WHERE bank_id=? AND stock_id=? AND ex_date=?",
        (bank_ref, stock_ref, ex_date),
    ).fetchone()
    return row["ref_num"] if row else None


def plan_file(db, path):
    """Return (label, per_bank_results, fully_covered) for one JSON file.

    per_bank_results: list of dicts with keys bank_id, bank_name, status
    ('new' | 'already' | 'skipped'), detail (reason if skipped, else None),
    and insert_kwargs (only present when status == 'new').

    fully_covered is True when every entitlement row resolved to either 'already'
    or 'new' (i.e. after --apply, the whole declaration will be in the DB) -- False
    if anything was skipped.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    stock_code = data["stock_code"]
    ex_date = data["ex_date"]
    label = f"{stock_code} {ex_date} ({data.get('stock_name', '')})"

    stock_ref = resolve_stock(db, stock_code)
    ccy_ref = resolve_currency(db, data["currency"])

    results = []
    for ent in data.get("entitlement", []):
        bank_id = ent["bank_id"]
        bank_name = ent.get("bank_name", str(bank_id))

        if stock_ref is None:
            results.append({"bank_id": bank_id, "bank_name": bank_name, "status": "skipped",
                             "detail": f"unresolvable stock_code {stock_code!r}"})
            continue
        if ccy_ref is None:
            results.append({"bank_id": bank_id, "bank_name": bank_name, "status": "skipped",
                             "detail": f"unresolvable currency {data['currency']!r}"})
            continue

        bank_ref = resolve_bank(db, bank_id)
        if bank_ref is None:
            results.append({"bank_id": bank_id, "bank_name": bank_name, "status": "skipped",
                             "detail": f"unresolvable bank_id {bank_id!r}"})
            continue

        if existing_row(db, bank_ref, stock_ref, ex_date) is not None:
            results.append({"bank_id": bank_id, "bank_name": bank_name, "status": "already", "detail": None})
            continue

        results.append({
            "bank_id": bank_id, "bank_name": bank_name, "status": "new", "detail": None,
            "insert_kwargs": dict(
                bank_id=bank_ref, stock_id=stock_ref, ccy_id=ccy_ref,
                declaration_date=data.get("declaration_date"),
                ex_date=ex_date,
                record_date=data.get("record_date"),
                pay_out=data.get("pay_date"),
                nominal=float(ent["entitled_qty"]),
                dividends_per_share=float(data["dividends_per_share"]),
                tax=0.0, charges=0.0, status="Estimate",
            ),
        })

    fully_covered = bool(results) and all(r["status"] != "skipped" for r in results)
    return label, results, fully_covered


def build_plan(db):
    files = sorted(glob.glob(os.path.join(JSON_DIR, "*.json")))
    return {path: plan_file(db, path) for path in files}


def print_report(plan):
    total_checked = total_new = total_already = total_skipped = 0
    flag_candidates = []

    for path, (label, results, fully_covered) in plan.items():
        if not results:
            continue
        all_already = all(r["status"] == "already" for r in results)
        tag = "  [ALL ALREADY IN DB, flag stale -- will be corrected on --apply]" if (fully_covered and all_already) else ""
        print(f"{os.path.basename(path)}: {label} -- {len(results)} bank(s){tag}")
        for r in results:
            total_checked += 1
            if r["status"] == "new":
                total_new += 1
                qty = r["insert_kwargs"]["nominal"]
                rate = r["insert_kwargs"]["dividends_per_share"]
                print(f"  {r['bank_name']}: {qty:,.0f} shares x {rate} -- [NEW]")
            elif r["status"] == "already":
                total_already += 1
                print(f"  {r['bank_name']}: -- [ALREADY IN DB]")
            else:
                total_skipped += 1
                print(f"  {r['bank_name']}: SKIPPED -- {r['detail']}")
        if fully_covered:
            flag_candidates.append(path)

    print()
    print(f"Totals: {total_checked} entitlement rows checked across {len(plan)} files")
    print(f"  New Estimate rows to insert: {total_new}")
    print(f"  Files whose flag will be corrected to true: {len(flag_candidates)}")
    print(f"  Skipped (unresolvable lookup): {total_skipped}")
    return flag_candidates


def apply_plan(db, plan, flag_candidates):
    from ltv_app.blueprints.dividends.models import CashDividends

    inserted = 0
    for path, (label, results, fully_covered) in plan.items():
        for r in results:
            if r["status"] == "new":
                # Model.save() commits internally per row -- matches the pattern
                # used everywhere else this model is written (dividends.add()).
                CashDividends(db=db, **r["insert_kwargs"]).save()
                inserted += 1

    for path in flag_candidates:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["already_in_tbl_cash_dividends"] = True
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually write; default is dry-run")
    args = parser.parse_args()

    sys.path.insert(0, SERVER)
    from ltv_app import create_app
    from ltv_app.blueprints.database.views import get_db

    app = create_app()
    ctx = app.app_context()
    ctx.push()
    db = get_db()

    plan = build_plan(db)
    flag_candidates = print_report(plan)

    if args.apply:
        inserted = apply_plan(db, plan, flag_candidates)
        print()
        print(f"Applied: inserted {inserted} Estimate row(s), corrected {len(flag_candidates)} JSON flag(s).")
    else:
        print()
        print("Dry run -- nothing written. Re-run with --apply to write.")


if __name__ == "__main__":
    main()
