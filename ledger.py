"""Single-writer, six-day ledger. Integer amounts are account minor units."""

from dataclasses import dataclass
import re


PRECISION = {"AED": 2, "BHD": 3}
WINDOW = 6
RATE_NUMERATOR, RATE_DENOMINATOR = 4, 10_000
MONETARY = frozenset({"POSTING", "FEE", "CAPITALIZATION"})


def amount(text: str, currency: str) -> int:
    """Parse a nonnegative decimal, rounding half-up at the currency boundary."""
    if not isinstance(text, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", text):
        raise ValueError("amount must be a nonnegative plain decimal string")
    places = PRECISION[currency]
    whole, _, fraction = text.partition(".")
    units = int(whole) * 10**places + int((fraction + "0" * places)[:places])
    return units + int(len(fraction) > places and fraction[places] >= "5")


def money(units: int, currency: str) -> str:
    places = PRECISION[currency]
    whole, fraction = divmod(abs(units), 10**places)
    return f"{'-' if units < 0 else ''}{whole}.{fraction:0{places}d}"


def split(units: int, count: int) -> tuple[int, ...]:
    """Assign remainder units to earliest instalments; exact conservation."""
    if type(units) is not int or units < 0 or type(count) is not int or count < 1:
        raise ValueError("nonnegative integer units and positive integer count required")
    quotient, remainder = divmod(units, count)
    return tuple(quotient + int(i < remainder) for i in range(count))


def daily_interest(units: int) -> int:
    quotient, remainder = divmod(max(units, 0) * RATE_NUMERATOR, RATE_DENOMINATOR)
    return quotient + int(2 * remainder >= RATE_DENOMINATOR)


@dataclass(frozen=True)
class Account:
    id: str
    currency: str
    overdraft_fee: int | None


@dataclass(frozen=True)
class Event:
    id: str
    booked_day: int
    kind: str
    account: str
    currency: str
    value_day: int
    amount: str = "0"
    auth: str = ""
    reference: str = ""
    instalments: int = 1


@dataclass(frozen=True)
class Record:
    seq: int
    kind: str
    account: str
    booked_day: int
    value_day: int
    units: int = 0
    reference: str = ""
    auth: str = ""
    state: str = ""
    code: str = ""
    event: Event | None = None


class PolicyError(ValueError):
    pass


class Ledger:
    def __init__(self):
        self._accounts = (
            Account("ACC-001", "AED", 2500),
            Account("ACC-002", "BHD", None),
        )
        self._journal: list[Record] = []

    @property
    def accounts(self) -> tuple[Account, ...]:
        return self._accounts

    @property
    def journal(self) -> tuple[Record, ...]:
        return tuple(self._journal)

    @property
    def finalized(self) -> bool:
        return any(r.kind == "FINALIZED" for r in self._journal)

    def _append(self, kind, account="", booked_day=0, value_day=0, **fields):
        row = Record(len(self._journal) + 1, kind, account, booked_day, value_day, **fields)
        self._journal.append(row)
        return row

    def _rows(self, through: int | None = None):
        if through is not None and (type(through) is not int or not 0 <= through <= len(self._journal)):
            raise ValueError("invalid sequence cutoff")
        return self._journal if through is None else self._journal[:through]

    def balance(self, account: str, day: int, through: int | None = None, *, capitalized=True) -> int:
        return sum(r.units for r in self._rows(through)
                   if r.account == account and r.value_day <= day and r.kind in MONETARY
                   and (capitalized or r.kind != "CAPITALIZATION"))

    def auth_states(self, account: str, through: int | None = None) -> dict[str, Record]:
        states = {}
        for row in self._rows(through):
            if row.kind == "AUTH_STATE" and row.account == account:
                states[row.auth] = row
        return states

    def held(self, account: str, through: int | None = None) -> int:
        return sum(r.units for r in self.auth_states(account, through).values() if r.state == "ACTIVE")

    def available(self, account: str, day: int, through: int | None = None) -> int:
        return self.balance(account, day, through) - self.held(account, through)

    def accrual(self, account: str, day: int, through: int | None = None) -> int:
        return sum(r.units for r in self._rows(through)
                   if r.kind == "ACCRUAL_DELTA" and r.account == account and r.value_day == day)

    def process(self, event: Event) -> Record:
        """Validate before mutation; exact retries return the original decision."""
        original = next((r for r in self._journal if r.kind == "EVENT"
                         and r.event.id == event.id), None)
        if original is not None:
            if original.event == event:
                return original
            return self._append("ERROR", event.account, event.booked_day, event.value_day,
                                reference=event.id, code="DUPLICATE_CONFLICT", event=event)

        def reject(code):
            return self._append("EVENT", event.account, event.booked_day, event.value_day,
                                reference=event.id, code=code, event=event)

        if self.finalized:
            return reject("WINDOW_FINALIZED")
        account = next((a for a in self.accounts if a.id == event.account), None)
        if account is None:
            return reject("UNKNOWN_ACCOUNT")
        if event.currency != account.currency:
            return reject("CURRENCY_MISMATCH")
        if not event.id or not isinstance(event.id, str):
            return reject("INVALID_ID")
        if any(type(d) is not int or not 1 <= d <= WINDOW for d in (event.booked_day, event.value_day)):
            return reject("INVALID_DAY")
        if event.value_day > event.booked_day:
            return reject("FUTURE_VALUE_DATE")
        if type(event.instalments) is not int or event.instalments < 1:
            return reject("INVALID_INSTALMENTS")
        if event.instalments != 1 and event.kind != "CREDIT":
            return reject("INVALID_INSTALMENTS")
        supported = {"CREDIT", "DEBIT", "AUTHORIZATION", "SETTLEMENT", "REVERSAL", "CANCEL", "EXPIRE"}
        if event.kind not in supported:
            return reject("UNKNOWN_KIND")
        if event.kind in {"AUTHORIZATION", "SETTLEMENT", "CANCEL", "EXPIRE"} and not event.auth:
            return reject("MISSING_AUTH_ID")
        states = self.auth_states(event.account)
        auth = states.get(event.auth)
        units = 0
        if event.kind in {"CREDIT", "DEBIT", "AUTHORIZATION", "SETTLEMENT"}:
            try:
                units = amount(event.amount, event.currency)
            except ValueError:
                return reject("INVALID_AMOUNT")
            if units <= 0:
                return reject("NONPOSITIVE_AMOUNT")
        else:
            if event.amount != "0":
                return reject("UNEXPECTED_AMOUNT")

        code = "ACCEPTED"
        if event.kind == "AUTHORIZATION":
            if auth is not None or any(r.kind == "POSTING" and r.account == event.account
                                       and r.auth == event.auth for r in self._journal):
                return reject("AUTH_ID_REUSED")
            if self.available(event.account, event.booked_day) < units:
                code = "INSUFFICIENT_AVAILABLE"
        if event.kind == "SETTLEMENT":
            if auth is None or auth.state != "ACTIVE":
                code = "UNMATCHED_SETTLEMENT"
            # A previously settled ID is a duplicate capture, not a fresh force post.
            if auth is not None and auth.state == "SETTLED":
                return reject("AUTH_ALREADY_SETTLED")
            if any(r.kind == "POSTING" and r.account == event.account and r.auth == event.auth
                   for r in self._journal):
                return reject("AUTH_ALREADY_SETTLED")
        if event.kind in {"CANCEL", "EXPIRE"} and (auth is None or auth.state != "ACTIVE"):
            return reject("AUTH_NOT_ACTIVE")
        if event.kind == "REVERSAL":
            target = next((r for r in self._journal if r.kind == "EVENT" and r.event.id == event.reference), None)
            if target is None or target.code != "ACCEPTED" or target.event.kind not in {"CREDIT", "DEBIT"}:
                return reject("NOT_REVERSIBLE")
            if target.account != event.account:
                return reject("REVERSAL_ACCOUNT_MISMATCH")
            if target.value_day != event.value_day:
                return reject("REVERSAL_VALUE_DATE_MISMATCH")
            if any(r.kind == "EVENT" and r.code == "ACCEPTED" and r.event.kind == "REVERSAL"
                   and r.event.reference == event.reference for r in self._journal):
                return reject("ALREADY_REVERSED")
            units = -sum(r.units for r in self._journal if r.kind == "POSTING" and r.reference == event.reference)

        decision = self._append("EVENT", event.account, event.booked_day, event.value_day,
                                reference=event.id, code=code, event=event)

        def append(kind, **fields):
            return self._append(kind, event.account, event.booked_day, event.value_day,
                                reference=event.id, **fields)

        if event.kind == "AUTHORIZATION":
            append("AUTH_STATE", auth=event.auth, units=units,
                   state="ACTIVE" if code == "ACCEPTED" else "DECLINED")
        elif event.kind in {"CANCEL", "EXPIRE"}:
            append("AUTH_STATE", auth=event.auth, state="CANCELLED" if event.kind == "CANCEL" else "EXPIRED")
        else:
            if event.kind == "SETTLEMENT":
                if auth is not None and auth.state == "ACTIVE":
                    append("AUTH_STATE", auth=event.auth, state="SETTLED")
                if code == "UNMATCHED_SETTLEMENT":
                    append("EXCEPTION", auth=event.auth, code=code)
            if event.kind in {"DEBIT", "SETTLEMENT"}:
                units = -units
            for part in split(units, event.instalments) if event.kind == "CREDIT" else (units,):
                append("POSTING", units=part, auth=event.auth if event.kind == "SETTLEMENT" else "")
        return decision

    def close(self, day: int) -> int:
        """Reconcile all elapsed value days. Return immutable sequence checkpoint."""
        if type(day) is not int or not 1 <= day <= WINDOW:
            raise ValueError("day outside window")
        if self.finalized:
            if day == WINDOW:
                return next(r.seq for r in self._journal if r.kind == "FINALIZED")
            raise PolicyError("window is finalized")
        last_close = max((r.value_day for r in self._journal if r.kind == "CLOSE"), default=0)
        if day < last_close:
            raise PolicyError("close clock cannot move backwards")
        if any(r.kind == "EVENT" and r.code in {"ACCEPTED", "UNMATCHED_SETTLEMENT", "INSUFFICIENT_AVAILABLE"}
               and r.booked_day > day for r in self._journal):
            raise PolicyError("cannot close before an observed booked day")
        # Preflight the only missing tariff before appending any derived rows.
        for account in self.accounts:
            if account.overdraft_fee is None and any(self.balance(account.id, d) < 0 for d in range(1, day + 1)):
                raise PolicyError(f"missing {account.currency} overdraft tariff")
        assessed = {(r.account, r.value_day) for r in self._journal if r.kind == "FEE"}
        for d in range(1, day + 1):
            for account in self.accounts:
                if self.balance(account.id, d) < 0 and (account.id, d) not in assessed:
                    self._append("FEE", account.id, day, d, units=-account.overdraft_fee,
                                 code="OVERDRAFT")
                    assessed.add((account.id, d))
        for d in range(1, day + 1):
            for account in self.accounts:
                revised = daily_interest(self.balance(account.id, d, capitalized=False))
                delta = revised - self.accrual(account.id, d)
                if delta:
                    self._append("ACCRUAL_DELTA", account.id, day, d, units=delta)
        if day == WINDOW:
            for account in self.accounts:
                total = sum(self.accrual(account.id, d) for d in range(1, WINDOW + 1))
                self._append("CAPITALIZATION", account.id, day, day, units=total)
        checkpoint = self._append("CLOSE", booked_day=day, value_day=day)
        if day == WINDOW:
            checkpoint = self._append("FINALIZED", booked_day=day, value_day=day)
        return checkpoint.seq
