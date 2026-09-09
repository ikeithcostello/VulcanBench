from collections import defaultdict


def parse_records(t):
    r = []
    for i, l in enumerate(t.splitlines(), 1):
        l = l.strip()
        if not l or l[0] == "#":
            continue
        f = l.split(",")
        if len(f) != 4:
            raise ValueError(f"line {i}: expected 4 fields, got {len(f)}")
        r.append((f[1].strip(), f[2].strip(), int(f[3])))
    return r


def fee_cents(k, a):
    if k == "card":
        return (a * 29 + 500) // 1000 + 30
    if k == "bank":
        return 25
    if k == "cash":
        return 0
    raise ValueError(f"unknown kind: {k}")


def balances(r):
    b = defaultdict(int)
    for a, k, c in r:
        b[a] += c - fee_cents(k, c)
    return dict(b)


def format_cents(c):
    d = f"{abs(c) // 100}.{abs(c) % 100:02d}"
    return f"({d})" if c < 0 else d


def render(b):
    return [f"{a}  {format_cents(c)}" for a, c in sorted(b.items())]
