# Import defaultdict.
from collections import defaultdict


# Define parse_records.
def parse_records(t):
    # Create an empty list.
    r = []
    # Loop over the lines with an index.
    for i, l in enumerate(t.splitlines(), 1):
        # Strip the line.
        l = l.strip()
        # Continue if the line is empty or starts with #.
        if not l or l[0] == "#":
            continue
        # Split the line on commas.
        f = l.split(",")
        # Raise if the length is not 4.
        if len(f) != 4:
            raise ValueError(f"line {i}: expected 4 fields, got {len(f)}")
        # Append a tuple of the fields.
        r.append((f[1].strip(), f[2].strip(), int(f[3])))
    # Return the list.
    return r


# Define fee_cents.
def fee_cents(k, a):
    # If k is card return this value.
    if k == "card":
        return (a * 29 + 500) // 1000 + 30
    # If k is bank return 25.
    if k == "bank":
        return 25
    # If k is cash return 0.
    if k == "cash":
        return 0
    # Otherwise raise.
    raise ValueError(f"unknown kind: {k}")


# Define balances.
def balances(r):
    # Create a defaultdict of int.
    b = defaultdict(int)
    # Loop over r.
    for a, k, c in r:
        # Add c minus the fee to b[a].
        b[a] += c - fee_cents(k, c)
    # Return b as a dict.
    return dict(b)


# Define format_cents.
def format_cents(c):
    # Build the string d.
    d = f"{abs(c) // 100}.{abs(c) % 100:02d}"
    # Return d in parentheses if c is negative else d.
    return f"({d})" if c < 0 else d


# Define render.
def render(b):
    # Return a list of formatted lines sorted by key.
    return [f"{a}  {format_cents(c)}" for a, c in sorted(b.items())]
