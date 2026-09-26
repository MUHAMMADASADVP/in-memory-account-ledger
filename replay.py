"""Run the exact input order and print historical closes plus restated balances."""

from ledger import Event, Ledger, WINDOW, money


EVENTS = (
    Event("E1", 1, "CREDIT", "ACC-001", "AED", 1, "1200.00"),
    Event("E2", 1, "DEBIT", "ACC-001", "AED", 1, "950.00"),
    Event("E3", 2, "AUTHORIZATION", "ACC-001", "AED", 2, "200.00", auth="Auth-A"),
    Event("E4", 3, "CREDIT", "ACC-001", "AED", 3, "400.00"),
    Event("E5", 4, "SETTLEMENT", "ACC-001", "AED", 4, "185.00", auth="Auth-A"),
    Event("E6", 4, "SETTLEMENT", "ACC-001", "AED", 4, "180.00", auth="Auth-Z"),
    Event("E7", 5, "DEBIT", "ACC-001", "AED", 2, "620.00"),
    Event("E8", 5, "AUTHORIZATION", "ACC-001", "AED", 5, "90.00", auth="Auth-B"),
    Event("E9", 6, "REVERSAL", "ACC-001", "AED", 2, reference="E7"),
    Event("E10", 5, "CREDIT", "ACC-002", "BHD", 5, "10.000", instalments=3),
)


def replay():
    ledger = Ledger()
    closes = {}
    next_close = 1
    for event in EVENTS:
        while next_close < event.booked_day:
            closes[next_close] = ledger.close(next_close)
            next_close += 1
        ledger.process(event)
    while next_close <= WINDOW:
        closes[next_close] = ledger.close(next_close)
        next_close += 1
    return ledger, closes


def report(ledger, closes):
    print("ORIGINAL CLOSE CHECKPOINTS (input order; E10 arrives after the Day 5 close)")
    previous = 0
    for day, cutoff in closes.items():
        print(f"\nDay {day} | journal through sequence {cutoff}")
        for account in ledger.accounts:
            fmt = lambda units: money(units, account.currency)
            print(f"  {account.id} {account.currency}: closing={fmt(ledger.balance(account.id, day, cutoff))}"
                  f" held={fmt(ledger.held(account.id, cutoff))}"
                  f" available={fmt(ledger.available(account.id, day, cutoff))}"
                  f" daily_interest={fmt(ledger.accrual(account.id, day, cutoff))}")
            states = ledger.auth_states(account.id, cutoff)
            print("    authorizations: " + (", ".join(f"{k}={v.state}" for k, v in states.items()) or "none"))
            fees = [r for r in ledger.journal[previous:cutoff] if r.kind == "FEE" and r.account == account.id]
            print("    fees assessed this close: " + (", ".join(
                f"{fmt(-r.units)} (value Day {r.value_day}, booked Day {r.booked_day})" for r in fees) or "none"))
        problems = [r for r in ledger.journal[previous:cutoff]
                    if r.kind in {"EVENT", "ERROR"} and r.code != "ACCEPTED"]
        print("  errors/exceptions: " + (", ".join(f"{r.reference}: {r.code}" for r in problems) or "none"))
        previous = cutoff

    print("\nRESTATED VALUE-DAY BALANCES, AS KNOWN AFTER ALL EVENTS")
    print("Day | ACC-001 AED close | fee on value day | interest | ACC-002 BHD close | interest")
    for day in range(1, WINDOW + 1):
        fee = -sum(r.units for r in ledger.journal if r.kind == "FEE" and r.account == "ACC-001" and r.value_day == day)
        print(f"{day:3} | {money(ledger.balance('ACC-001', day), 'AED'):>17}"
              f" | {money(fee, 'AED'):>16} | {money(ledger.accrual('ACC-001', day), 'AED'):>8}"
              f" | {money(ledger.balance('ACC-002', day), 'BHD'):>17}"
              f" | {money(ledger.accrual('ACC-002', day), 'BHD'):>8}")
    print("Day 6 closing includes capitalization; Day 6 interest uses the pre-capitalization balance.")
    print("Historical authorization decisions stay at their original sequence; they are not restated.")
    print("\nDAILY INTEREST AUDIT (append-only deltas)")
    for r in ledger.journal:
        if r.kind == "ACCRUAL_DELTA":
            currency = next(a.currency for a in ledger.accounts if a.id == r.account)
            print(f"  seq={r.seq} {r.account} booked Day {r.booked_day}, value Day {r.value_day}: {money(r.units, currency)}")
    for account in ledger.accounts:
        capital = sum(r.units for r in ledger.journal if r.kind == "CAPITALIZATION" and r.account == account.id)
        print(f"  {account.id} capitalized: {account.currency} {money(capital, account.currency)}")
    parts = [money(r.units, "BHD") for r in ledger.journal if r.kind == "POSTING" and r.reference == "E10"]
    print("E10 instalments: BHD " + " + ".join(parts) + " = 10.000")


if __name__ == "__main__":
    report(*replay())
