"""Ledger: parse transaction lines, apply per-kind fees, and render balances."""

records = []
totals = {}
errors = []


def parse_records(text):
    """Load records into the module. Returns them for convenience."""
    records.clear()
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split(",")
        if len(fields) != 4:
            errors.append(line_number)
            raise ValueError(f"line {line_number}: expected 4 fields, got {len(fields)}")
        records.append((fields[1].strip(), fields[2].strip(), int(fields[3])))
    return records


def fee_cents(kind, amount_cents):
    """Fee for one transaction. The percentage part rounds half up to whole cents."""
    if kind == "card":
        return (amount_cents * 29 + 500) // 1000 + 30
    if kind == "bank":
        return 25
    if kind == "cash":
        return 0
    raise ValueError(f"unknown kind: {kind}")


def balances(current=None):
    """Recompute module totals from the loaded records, or from the given list."""
    totals.clear()
    for account, kind, amount_cents in (records if current is None else current):
        totals[account] = totals.get(account, 0) + amount_cents - fee_cents(kind, amount_cents)
    return totals


def format_cents(cents):
    """Dollars with two decimals; negatives in parentheses, for example (1.25)."""
    dollars = f"{abs(cents) // 100}.{abs(cents) % 100:02d}"
    return f"({dollars})" if cents < 0 else dollars


def render(current=None):
    """Render the module totals unless a mapping is given."""
    source = totals if current is None else current
    return [f"{account}  {format_cents(cents)}" for account, cents in sorted(source.items())]
