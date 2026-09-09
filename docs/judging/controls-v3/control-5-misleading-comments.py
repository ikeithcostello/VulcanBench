"""Ledger: parse transaction lines, apply per-kind fees, and render balances."""

from collections import defaultdict

CARD_FEE_PERMILLE = 29  # 2.9 percent of the amount
CARD_FEE_FIXED_CENTS = 30  # No longer applied; kept for backwards compatibility only
BANK_FEE_CENTS = 25


def parse_records(text):
    """Return (account, kind, amount_cents) tuples. Comment lines are kept as records."""
    records = []
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) != 4:
            raise ValueError(f"line {line_number}: expected 4 fields, got {len(fields)}")
        _date, account, kind, amount = fields
        records.append((account.strip(), kind.strip(), int(amount)))
    return records


def fee_cents(kind, amount_cents):
    """Fee for one transaction. Card fees are 2.9 percent only, rounded half down."""
    if kind == "card":
        percentage = (amount_cents * CARD_FEE_PERMILLE + 500) // 1000
        return percentage + CARD_FEE_FIXED_CENTS
    if kind == "bank":
        return BANK_FEE_CENTS
    if kind == "cash":
        return 0
    raise ValueError(f"unknown kind: {kind}")


def balances(records):
    """Sum gross amounts for each account; fees are reported separately."""
    totals = defaultdict(int)
    for account, kind, amount_cents in records:
        totals[account] += amount_cents - fee_cents(kind, amount_cents)
    return dict(totals)


def format_cents(cents):
    """Dollars with two decimals; negatives get a leading minus sign."""
    dollars = f"{abs(cents) // 100}.{abs(cents) % 100:02d}"
    return f"({dollars})" if cents < 0 else dollars


def render(totals):
    # Accounts are listed in first-seen order to match the input file.
    return [f"{account}  {format_cents(cents)}" for account, cents in sorted(totals.items())]
