import datetime
import json
from math import ceil

from .stock_price import Stock_Price


class forecast:
  def __init__(self, db = None, code = None):
    self.db = db                      # sqlite3 connection object
    self.code = code
    self.code_ref, self.ccy_id = db.execute(
          """
          SELECT c.ref_num, cur.ccy_id 
          FROM tbl_code as c
          INNER JOIN tbl_currency as cur ON c.ccy_ref = cur.ref_num
          WHERE code = ?
          """, 
          (code,)
          ).fetchone()   

    self.data = {} # Main variable

    self.generate()

  def __getitem__(self, bank_id):
    if bank_id in self.data:
      return self.data[bank_id]
    else:
      return []

  def generate(self):
    wd = Working_Day(self.db, self.ccy_id)
    stock_price = Stock_Price(self.db, self.code)
    fixings = self.db.execute(
      """
        SELECT 
          b.bank_id,
          c.transaction_type,
          c.daily_shares,
          c.leveraged,
          c.spot,
          c.strike_rate,
          c.ko_rate,
          d.start_date,
          d.end_date,
          d.gtd,
          d.contract_ref,
          c.frequency
        FROM tbl_stock_contract_period as d
        INNER JOIN tbl_stock_contract as c ON d.contract_ref = c.ref_num
        INNER JOIN tbl_bank_account as b ON c.bank_ref = b.ref_num
        WHERE c.code_ref = ? AND d.received = "" AND c.status = "active"
        ORDER BY b.priority, d.end_date, c.transaction_type
        ;
      """, (self.code_ref, )
      ).fetchall()

    fixing_period = {}

    for fixing in fixings:
      bank_id, transaction_type, single, leveraged, spot, strike_rate, ko_rate, start_date, end_date, gtd, contract_ref, frequency = fixing

      double = single * 2 if leveraged == 'Yes' else single
      strike = round(spot * strike_rate / 100, 4)
      ko = round(spot * ko_rate / 100, 4)

      # print(bank_id, transaction_type, strike, ko)

      fixing_date = str(wd.Next(end_date))[:10]

      shares_aqdq = Count_Shares(
                                db = self.db,
                                ccy_id = self.ccy_id,
                                start_date = start_date,
                                end_date = end_date, 
                                transaction_type = transaction_type, 
                                spot=spot,
                                strike = strike,
                                ko = ko, 
                                single = single, 
                                double = double, 
                                gtd = gtd,
                                stock_price = stock_price
      )

      # Determine fixing period number
      if contract_ref not in fixing_period: fixing_period[contract_ref] = 0.0

      if frequency == 'weekly':
        fixing_increment = 0.25
      elif frequency in ('bi-weekly', 'bi-monthly'):
        fixing_increment = 0.5
      else:
        fixing_increment = 1.0

      fixing_period[contract_ref] += fixing_increment

      # Create a dictionary of fixing
      _dict = {
        'fixing_date': fixing_date,
        'transaction_type':transaction_type, 
        'strike': strike,
        'ko': ko,
        'single': single,
        'double': double,
        'start_date': start_date,
        'end_date': end_date,
        'gtd': gtd,
        'days_done': shares_aqdq.days_done,
        'days_double': shares_aqdq.days_double,
        'days_indicative': shares_aqdq.days_indicative,
        'contract_ref': contract_ref,
        'frequency': frequency,
        'fixing_num':ceil(fixing_period[contract_ref])
      }

      # Add fixing to data variable
      if bank_id not in self.data: self.data[bank_id] = []
      self.data[bank_id].append(_dict)

      print(f"Analyzed {bank_id}: ({transaction_type}), ",
            f"{str(fixing_date)[:10]}, ", 
            f"SK {strike}, ",
            f"KO {ko}, ", 
            f"days_done {shares_aqdq.days_done}",
            f"days_double {shares_aqdq.days_double}",
            f"days_indi {shares_aqdq.days_indicative}",
            f"Total Days {shares_aqdq.days_done + shares_aqdq.days_indicative}"
            )


class Working_Day:
  def __init__(self, db = None, ccy_id = None):
    self.holidays = [x[0] for x in db.execute(
      """
      SELECT h.holi_date
      FROM tbl_holiday as h
      INNER JOIN tbl_currency as c ON h.ccy_ref = c.ref_num
      WHERE c.ccy_id = ?
      ;
      """,
      (ccy_id, )
      ).fetchall()
    ]

  def Next(self, initial_date):
    if type(initial_date) == str:
        initial_date = datetime.datetime(int(initial_date[:4]),int(initial_date[5:7]),int(initial_date[-2:]))

    nextDay = initial_date + datetime.timedelta(days=1)

    loop = True
    while loop: 
      if nextDay.isoweekday() == 6 or nextDay.isoweekday() == 7 or str(nextDay)[:10] in self.holidays:
        nextDay = nextDay + datetime.timedelta(days=1)
      else:
        loop = False

    return nextDay


class Count_Shares:
  def __init__(self, 
                db = None,
                ccy_id = None,
                start_date = None, 
                end_date = None, 
                transaction_type = None, 
                spot=None,
                strike = None, 
                ko = None, 
                single = None, 
                double = None, 
                gtd = None, 
                stock_price = None  # <Class 'Stock_Price'> 
                ):
    self.db = db
    self.ccy_id = ccy_id
    
    # Variables for external use
    self.days_done = 0
    self.days_double = 0
    self.days_indicative = 0

    fixing_days = self.f_fixing(start_date, end_date, ccy_id)

    for fixing_day in fixing_days:
      _date = str(fixing_day)[:10]
      stock_price.add(_date)
      closing_price=stock_price[_date]
      if closing_price is not None:
        sdk = SDK(spot=spot, strike=strike, ko=ko, closing_price=closing_price).get()
      else:
        sdk = None

      if sdk == 2:
        self.days_done += 1
        if single != double: self.days_double += 1  # Count only if notional is double
      elif sdk == 1:
        self.days_done += 1
      else:
        self.days_indicative += 1

  def f_fixing(self, start_date, end_date, ccy_id):
      wd = Working_Day(self.db, self.ccy_id)
      start_date = self.f_date(start_date)
      end_date = self.f_date(end_date)

      list_date = []

      for single_date in self.daterange(start_date, end_date):
          if single_date.isoweekday() in (6, 7):
              pass
          elif str(single_date)[:10] in wd.holidays:
              pass
          else:
              list_date.append(single_date)
      
      return list_date

  def daterange(self, start_date, end_date):
      end_date = end_date + datetime.timedelta(1)
      for n in range(int ((end_date - start_date).days)):
          yield start_date + datetime.timedelta(n)

  def f_date(self, _date):  # Convert a string date into datetime
      _year = int(_date[:4])
      _month = int(_date[5:7])
      _day = int(_date[-2:])
      return datetime.datetime(_year,_month,_day)


class SDK:
  def __init__(self, spot=None, strike=None, ko= None, closing_price=None):
    if spot > strike:                 # Accumulator
      if ko <= closing_price:
        self._sdk = 0                 # KO Event
      elif strike >= closing_price:   
        self._sdk = 2                 # Double
      else:
        self._sdk = 1                 # Single

    else:                             # Decumulator
      if ko >= closing_price:
        self._sdk = 0                 # KO Event
      elif strike <= closing_price:   
        self._sdk = 2                 # Double
      else:
        self._sdk = 1                 # Single

  def get(self):
    return self._sdk