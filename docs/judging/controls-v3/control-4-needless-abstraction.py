from abc import ABC, abstractmethod
from collections import defaultdict


class Money:
    def __init__(self, cents):
        self.cents = cents

    def minus(self, other):
        return Money(self.cents - other.cents)

    def plus(self, other):
        return Money(self.cents + other.cents)


class FeePolicy(ABC):
    @abstractmethod
    def fee(self, amount: Money) -> Money: ...


class CardFeePolicy(FeePolicy):
    def fee(self, amount):
        return Money((amount.cents * 29 + 500) // 1000 + 30)


class BankFeePolicy(FeePolicy):
    def fee(self, amount):
        return Money(25)


class CashFeePolicy(FeePolicy):
    def fee(self, amount):
        return Money(0)


class FeePolicyRegistry:
    def __init__(self):
        self._policies = {}

    def register(self, kind, policy):
        self._policies[kind] = policy
        return self

    def resolve(self, kind):
        try:
            return self._policies[kind]
        except KeyError:
            raise ValueError(f"unknown kind: {kind}") from None


REGISTRY = FeePolicyRegistry().register("card", CardFeePolicy()).register("bank", BankFeePolicy()).register("cash", CashFeePolicy())


class Record:
    def __init__(self, account, kind, amount):
        self.account, self.kind, self.amount = account, kind, amount


class RecordParser:
    def __init__(self, text):
        self._text = text

    def parse(self):
        return [self._parse_line(n, l) for n, l in enumerate(self._text.splitlines(), 1) if self._keep(l)]

    @staticmethod
    def _keep(line):
        return bool(line.strip()) and not line.strip().startswith("#")

    @staticmethod
    def _parse_line(number, line):
        fields = line.strip().split(",")
        if len(fields) != 4:
            raise ValueError(f"line {number}: expected 4 fields, got {len(fields)}")
        return Record(fields[1].strip(), fields[2].strip(), Money(int(fields[3])))


class BalanceAggregator:
    def __init__(self, registry):
        self._registry = registry
        self._totals = defaultdict(lambda: Money(0))

    def accept(self, record):
        fee = self._registry.resolve(record.kind).fee(record.amount)
        self._totals[record.account] = self._totals[record.account].plus(record.amount.minus(fee))
        return self

    def result(self):
        return {account: money.cents for account, money in self._totals.items()}


class Renderer:
    def render(self, totals):
        return [f"{account}  {self._money(cents)}" for account, cents in sorted(totals.items())]

    @staticmethod
    def _money(cents):
        dollars = f"{abs(cents) // 100}.{abs(cents) % 100:02d}"
        return f"({dollars})" if cents < 0 else dollars


def parse_records(text):
    return [(r.account, r.kind, r.amount.cents) for r in RecordParser(text).parse()]


def fee_cents(kind, amount_cents):
    return REGISTRY.resolve(kind).fee(Money(amount_cents)).cents


def balances(records):
    aggregator = BalanceAggregator(REGISTRY)
    for account, kind, amount in records:
        aggregator.accept(Record(account, kind, Money(amount)))
    return aggregator.result()


def render(totals):
    return Renderer().render(totals)
