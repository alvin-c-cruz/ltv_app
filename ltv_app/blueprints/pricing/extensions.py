BANKS = {
    "CB": "Citibank",
    "BOS": "Bank of Singapore",
    "DB": "Deutsche Bank",
    "SHK": "Sun Hung Kai",
    "MS": "Morgan Stanley",
    "NSG": "Nomura"
}

HEADER = {
    "BOS": [
        {
          "CP": "",
          "Daycount": "",
          "Guaranteed": "gtd",
          "KO Barrier": "ko",
          "Normal/Leveraged": "leverage",
          "Product": "product",
          "RFQ ID": "",
          "Set Freq": "frequency",
          "Strike": "strike",
          "Tenor": "tenor",
          "Underlying": "code"
        }
    ],
    "SHK": [
        {
          "GUARANTEED PERIODS": "gtd",
          "Issuer": "",
          "KO (%)": "ko",
          "KO+1 SETTLEMENT CYCLE": "",
          "NORMAL / LEVERAGED": "leverage",
          "PRODUCT": "product",
          "Remark": "",
          "SETTLEMENT FREQUENCY": "frequency",
          "Strike": "strike",
          "TENOR (M)": "tenor",
          "Tradable Size": "",
          "UNDERLYING (BLOOMBERG)": "code"
        }
    ]
}

ACCUMULATORS = (
    "Accum",
)

DECUMULATORS = (
    "Decum",
)

LEVERAGE_SINGLE = (
)

LEVERAGE_DOUBLE = (
    "Leveraged",
)

GTD_NO = (
    "0m",
)

GTD_1 = (
    "1m",
)

def transform_email(textarea_data, bank_code, form):
    list_data = transform_raw_email(textarea_data, bank_code, form)
    analyzed_data = analyze_data(list_data)

    return analyzed_data


def transform_raw_email(textarea_data, bank_code, form):
    #  Transform email message into a list of dictionary entries
    list_data = []
    for i, row in enumerate(textarea_data.split("\n")):
        if i == 0:
            email_headers = list([i.strip() for i in row.replace("\r", "").split("\t")])
            sorted_header = list([i.strip() for i in row.replace("\r", "").split("\t")]).sort()

            # headers = pricing_columns.get(bank_code)
            headers = [list(header.keys()) for header in HEADER[bank_code]]
            if headers:
                for i, header in enumerate(headers):
                    if sorted_header == header.sort():
                        use_header = HEADER[bank_code][i]
                        break
                else:
                    form["not_in_record"] = email_headers if email_headers[0] != "" else []
                    break
            else:
                form["not_in_record"] = email_headers if email_headers[0] != "" else []
                use_header = []
        else:
            row_data = row.replace("\r", "").split("\t")
            dict_row = {}
            for key, value in zip(email_headers, row_data):
                if value and use_header:
                    use_key = use_header[key]
                    if use_key:
                        dict_row[use_key] = value

            if dict_row:
                dict_row["bank_code"] = bank_code
                list_data.append(dict_row)

    return list_data


def analyze_data(list_data):
    def decision(key, _dict, *args):
        for choices, value in args:
            if _dict[key] in choices:
                _dict[key] = value
                break
        else:
            _dict[key] += " not in record"

    for row in list_data:
        decision("product", row, (ACCUMULATORS, "ACCU"), (DECUMULATORS, "DECU"))
        decision("leverage", row, (LEVERAGE_DOUBLE, "Yes"), (LEVERAGE_SINGLE, "No"))
        decision("gtd", row, (GTD_NO, "No"), (GTD_1, "1m"))

    analyzed_data = list_data

    return analyzed_data
