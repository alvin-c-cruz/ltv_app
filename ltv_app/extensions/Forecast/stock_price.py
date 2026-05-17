class Stock_Price:
  def __init__(self, db = None, code = None):
    self.db = db                      # sqlite3 connection object
    self.code_ref = db.execute(
          "SELECT ref_num FROM tbl_code WHERE code = ?", 
          (code,)
          ).fetchone()[0]            
    self.prices = {}                  # a dictionary of stock prices

  def add(self, trade_date):
    if trade_date not in self.prices:
      closing_price = self.db.execute("""
            SELECT closing_price
            FROM tbl_stock_price
            WHERE trade_date = ? AND code_ref = ?
      """, (trade_date, self.code_ref)).fetchone()

      if closing_price:
        self.prices[trade_date] = closing_price[0]
      else:
        self.prices[trade_date] = None

  def get_price(self, trade_date):
    result = self.db.execute("""
            SELECT closing_price
            FROM tbl_stock_price
            WHERE trade_date = ? AND code_ref = ?
      """, (trade_date, self.code_ref)).fetchone()

    return result[0] if result is not None else None

  def __getitem__(self, trade_date):
    return self.prices[trade_date] if trade_date in self.prices else None

  def __len__(self):
    return len(self.prices)
