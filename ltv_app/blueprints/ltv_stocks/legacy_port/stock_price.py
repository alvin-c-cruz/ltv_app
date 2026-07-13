from datetime import date


def get_stock_price(db, code_ref, d):
    """Closing price for (code_ref, date), or None. Ports get_stock_price."""
    ds = d.isoformat() if isinstance(d, date) else str(d)[:10]
    row = db.execute(
        "SELECT closing_price FROM tbl_stock_price WHERE code_ref = ? AND trade_date = ?",
        (code_ref, ds)
    ).fetchone()
    return row[0] if row else None
