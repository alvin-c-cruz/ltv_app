from .. term_sheet import StockContract


def _short_date(date_str):
    """Match localhost/modules/dates.py::short_date's exact output format --
    confirmed via a throwaway script (deleted) against sample dates:
    short_date('2026-08-15') -> '15-Aug-2026', short_date('2026-08-05') ->
    '5-Aug-2026' (day is NOT zero-padded), short_date('2026-01-31') ->
    '31-Jan-2026'. Reproduced by hand rather than via strftime, since
    strftime's %d would wrongly zero-pad single-digit days.
    """
    months = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
    }
    year = date_str[:4]
    month = int(date_str[5:7])
    day = int(date_str[-2:])
    return f"{day}-{months[month]}-{year}"


def get_next_month(observation_month):
    year = int(observation_month[:4])
    month = int(observation_month[-2:])
    if month != 12:
        month += 1
    else:
        year += 1
        month = 1
    return f"{year}-{str(month).zfill(2)}"


def _stock_name_with_gtd(ts):
    """Matches legacy localhost/modules/term_sheet.py::summary_ts's stock_name
    construction exactly (gtd == 'Yes' -> 'GTD 1m', gtd == 'No' -> 'NO GTD',
    else -> 'GTD {gtd.upper()}' -- e.g. real DB values '1m'/'2m'/'3m'/'4m'
    become 'GTD 1M'/'GTD 2M'/etc.)."""
    if ts.gtd == "Yes":
        return f"{ts.stock_name} GTD 1m"
    elif ts.gtd == "No":
        return f"{ts.stock_name} NO GTD"
    else:
        return f"{ts.stock_name} GTD {ts.gtd.upper()}"


def _contract_to_dict(ts):
    single = ts.daily_shares
    if ts.leveraged == "Yes":
        double_str = "{0:,.0f}".format(single * 2)
        single_str = "{0:,.0f}".format(single)
        shares = f"{single_str} / {double_str}"
    else:
        shares = "{0:,.0f}".format(single)

    last_period = len(ts.schedules)
    end_date = ts.schedules[-1].end_date if ts.schedules else ts.end_date

    if ts.frequency == "monthly":
        total = last_period
    elif ts.frequency == "weekly":
        total = last_period / 4
    else:
        total = last_period / 2

    received = 0
    for period in ts.schedules:
        if period.received in (None, ""):
            break
        if ts.frequency == "monthly":
            received += 1
        elif ts.frequency == "weekly":
            received += 0.25
        else:
            received += 0.5

    return {
        "contract_ref": ts.ref_num,
        "reference": ts.reference,
        "code": ts.code,
        "stock_name": _stock_name_with_gtd(ts),
        "shares": shares,
        "spot": "{0:,.4f}".format(ts.spot),
        "strike": "{0:,.4f}".format(ts.strike_value),
        "ko": "{0:,.4f}".format(ts.ko_value),
        "strike_value": ts.strike_value,
        "ko_value": ts.ko_value,
        "start_date": _short_date(ts.start_date),
        "end_date": _short_date(end_date),
        "total": total,
        "received": received,
        "remaining": total - received,
        "days_received": ts.received_days,
        "days_max": ts.total_days,
        "this_month": 0,
        "next_month": 0,
        "_ts": ts,
    }


def gather_margin_data(db, ccy, observation_month):
    """Port of legacy cash_margin() -> get_term_sheets() -> group_accounts()
    -> get_two_fixings() (localhost/modules/cash_margin.py), rebuilt on top of
    StockContract instead of the legacy summary_ts/term_sheet classes.

    Drops the legacy bank_group layer ("All") -- see Task 6 brief / plan doc:
    that layer was already a dead no-op in the legacy code (every lookup
    always indexed dict_margin["All"][bank_ref]), so this is a simplification,
    not a fidelity break. Returns {bank_id: {"ACCU": {reference: ts_dict},
    "DECU": {...}}}.
    """
    next_observation_month = get_next_month(observation_month)

    sql = """
        SELECT tbl_stock_contract.ref_num
        FROM tbl_stock_contract
        INNER JOIN tbl_bank_account ON tbl_bank_account.ref_num = tbl_stock_contract.bank_ref
        INNER JOIN tbl_code ON tbl_code.ref_num = tbl_stock_contract.code_ref
        INNER JOIN tbl_currency ON tbl_currency.ref_num = tbl_code.ccy_ref
        WHERE tbl_stock_contract.status = "active"
            AND tbl_currency.ccy_id = ?
        ORDER BY tbl_bank_account.priority
    """
    contract_refs = [row['ref_num'] for row in db.execute(sql, (ccy,)).fetchall()]

    dict_margin = {}
    for contract_ref in contract_refs:
        ts = StockContract(db=db)
        ts.get(ref_num=contract_ref)
        ts.__post_init__()
        ts.get_schedules()

        bank_id = ts.bank_id
        product = ts.transaction_type  # "ACCU" or "DECU"

        if bank_id not in dict_margin:
            dict_margin[bank_id] = {"ACCU": {}, "DECU": {}}

        ts_dict = _contract_to_dict(ts)

        this_month = 0
        next_month = 0
        for period in ts.schedules:
            if period.received in (None, ""):
                fixing_date = period.end_date
                if fixing_date[:7] == observation_month:
                    this_month += period.days
                if fixing_date[:7] == next_observation_month:
                    next_month += period.days
        ts_dict["this_month"] = this_month
        ts_dict["next_month"] = next_month

        dict_margin[bank_id][product][ts_dict["reference"]] = ts_dict

    return dict_margin


def build_cash_margin_file(db, ccy, observation_month, instance_path):
    raise NotImplementedError
