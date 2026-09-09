# This module is the ledger module. It handles the ledger.


def parse_records(text):
    # First we make an empty list to hold the records.
    records = []
    # Now we go through every line.
    line_number = 0
    for raw in text.splitlines():
        line_number = line_number + 1
        line = raw.strip()
        # Skip the line if it is blank.
        if line == "":
            continue
        # Skip the line if it is a comment.
        if line.startswith("#"):
            continue
        fields = line.split(",")
        # Check the number of fields.
        if len(fields) != 4:
            raise ValueError(f"line {line_number}: expected 4 fields, got {len(fields)}")
        account = fields[1].strip()
        kind = fields[2].strip()
        amount = int(fields[3])
        # Validate the kind here so bad kinds are caught early.
        if kind == "card":
            pass
        elif kind == "bank":
            pass
        elif kind == "cash":
            pass
        else:
            raise ValueError(f"unknown kind: {kind}")
        records.append((account, kind, amount))
    return records


def balances(records):
    # Start with an empty dictionary of totals.
    totals = {}
    for record in records:
        account = record[0]
        kind = record[1]
        amount = record[2]
        # Work out the fee for a card.
        if kind == "card":
            fee = (amount * 29 + 500) // 1000
            fee = fee + 30
            net = amount - fee
        # Work out the fee for a bank transfer.
        elif kind == "bank":
            fee = 25
            net = amount - fee
        # Work out the fee for cash.
        elif kind == "cash":
            fee = 0
            net = amount - fee
        else:
            raise ValueError(f"unknown kind: {kind}")
        # Add the net amount to the account.
        if account in totals:
            totals[account] = totals[account] + net
        else:
            totals[account] = net
    return totals


def total_fees(records):
    # Sum all the fees. Uses the same rules as balances.
    fees = 0
    for record in records:
        kind = record[1]
        amount = record[2]
        if kind == "card":
            fees = fees + (amount * 29 + 500) // 1000 + 30
        elif kind == "bank":
            fees = fees + 25
        elif kind == "cash":
            fees = fees + 0
        else:
            raise ValueError(f"unknown kind: {kind}")
    return fees


def render(totals):
    # Build the output lines.
    lines = []
    accounts = list(totals.keys())
    accounts.sort()
    for account in accounts:
        cents = totals[account]
        # Format negative numbers with parentheses.
        if cents < 0:
            cents = -cents
            dollars = str(cents // 100) + "." + str(cents % 100).zfill(2)
            lines.append(account + "  (" + dollars + ")")
        else:
            dollars = str(cents // 100) + "." + str(cents % 100).zfill(2)
            lines.append(account + "  " + dollars)
    return lines
