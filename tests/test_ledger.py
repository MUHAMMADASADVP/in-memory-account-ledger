from dataclasses import FrozenInstanceError, replace
import random
import unittest

from ledger import Event, Ledger, PolicyError, amount, daily_interest, money, split
from replay import EVENTS, replay


def credit(id="credit", units="100.00", day=1):
    return Event(id, day, "CREDIT", "ACC-001", "AED", day, units)


class MoneyTests(unittest.TestCase):
    def test_currency_rounding_and_reject_float(self):
        self.assertEqual(amount("1.005", "AED"), 101)
        self.assertEqual(amount("1.0005", "BHD"), 1001)
        self.assertEqual(amount("1.0049", "AED"), 100)
        self.assertEqual(money(-1, "BHD"), "-0.001")
        for invalid in (1.2, "NaN", "Infinity", "-1", "1e2", "1_000", " 1"):
            with self.assertRaises(ValueError):
                amount(invalid, "AED")

    def test_instalments_conserve_every_unit(self):
        self.assertEqual(split(10000, 3), (3334, 3333, 3333))
        for total in range(101):
            for count in range(1, 10):
                parts = split(total, count)
                self.assertEqual(sum(parts), total)
                self.assertLessEqual(max(parts) - min(parts), 1)

    def test_daily_interest_rounding_boundary(self):
        self.assertEqual(daily_interest(1250), 1)  # 0.5 minor units, half-up.
        self.assertEqual(daily_interest(1249), 0)
        self.assertEqual(daily_interest(-100000), 0)
        self.assertEqual(daily_interest(0), 0)


class ReplayTests(unittest.TestCase):
    def test_exact_stream_and_final_values(self):
        ledger, closes = replay()
        self.assertEqual([r.event.id for r in ledger.journal if r.kind == "EVENT"], [e.id for e in EVENTS])
        self.assertEqual([ledger.balance("ACC-001", d, closes[d]) for d in range(1, 7)],
                         [25000, 25000, 65000, 28500, -41000, 21069])
        self.assertEqual([ledger.balance("ACC-001", d) for d in range(1, 7)],
                         [25000, 22500, 62500, 23500, 21000, 21069])
        self.assertEqual(ledger.balance("ACC-002", 5, closes[5]), 0)
        self.assertEqual(ledger.balance("ACC-002", 5), 10000)
        self.assertEqual(ledger.balance("ACC-002", 6), 10008)

    def test_backdate_and_cascading_fees(self):
        ledger = Ledger()
        for event in EVENTS[:7]:
            ledger.process(event)
        self.assertEqual(ledger.balance("ACC-001", 2), -37000)
        ledger.close(5)
        self.assertEqual([(r.value_day, r.booked_day, r.units) for r in ledger.journal if r.kind == "FEE"],
                         [(2, 5, -2500), (4, 5, -2500), (5, 5, -2500)])
        self.assertEqual(ledger.balance("ACC-001", 3), 500)  # Day 3 avoids a fee.
        ledger.close(5)
        self.assertEqual(len([r for r in ledger.journal if r.kind == "FEE"]), 3)

    def test_interest_conservation_and_revisions(self):
        ledger, _ = replay()
        self.assertEqual([ledger.accrual("ACC-001", d) for d in range(1, 7)], [10, 9, 25, 9, 8, 8])
        self.assertTrue(any(r.kind == "ACCRUAL_DELTA" and r.units < 0 for r in ledger.journal))
        for account in ledger.accounts:
            caps = [r for r in ledger.journal if r.kind == "CAPITALIZATION" and r.account == account.id]
            self.assertEqual(len(caps), 1)
            self.assertEqual(caps[0].units, sum(ledger.accrual(account.id, d) for d in range(1, 7)))

    def test_reversal_preserves_records_and_fees(self):
        ledger = Ledger()
        for event in EVENTS[:8]:
            ledger.process(event)
        ledger.close(5)
        before = ledger.journal
        ledger.process(EVENTS[8])
        self.assertEqual(ledger.journal[:len(before)], before)
        self.assertEqual(ledger.balance("ACC-001", 5), 21000)
        self.assertEqual(ledger.auth_states("ACC-001")["Auth-B"].state, "DECLINED")
        self.assertEqual(ledger.process(replace(EVENTS[8], id="again")).code, "ALREADY_REVERSED")

    def test_original_authorization_survives_restatement(self):
        ledger, closes = replay()
        self.assertEqual(ledger.available("ACC-001", 2, closes[2]), 5000)
        self.assertEqual(ledger.auth_states("ACC-001", closes[2])["Auth-A"].state, "ACTIVE")
        self.assertEqual(ledger.auth_states("ACC-001")["Auth-A"].state, "SETTLED")
        self.assertEqual(ledger.held("ACC-001"), 0)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.ledger.process(credit())

    def auth(self, id="hold", name="A", units="100.00"):
        return Event(id, 1, "AUTHORIZATION", "ACC-001", "AED", 1, units, auth=name)

    def test_hold_boundary_multiple_holds_and_decline(self):
        self.assertEqual(self.ledger.process(self.auth()).code, "ACCEPTED")
        self.assertEqual(self.ledger.balance("ACC-001", 1), 10000)
        self.assertEqual(self.ledger.available("ACC-001", 1), 0)
        self.assertEqual(self.ledger.process(self.auth("second", "B", "0.01")).code, "INSUFFICIENT_AVAILABLE")
        self.assertEqual(self.ledger.held("ACC-001"), 10000)

    def test_settlement_releases_whole_hold_and_can_overdraw(self):
        self.ledger.process(self.auth())
        result = self.ledger.process(Event("settle", 1, "SETTLEMENT", "ACC-001", "AED", 1, "110.00", auth="A"))
        self.assertEqual(result.code, "ACCEPTED")
        self.assertEqual(self.ledger.held("ACC-001"), 0)
        self.assertEqual(self.ledger.balance("ACC-001", 1), -1000)
        self.assertEqual(self.ledger.process(replace(result.event, id="settle2")).code, "AUTH_ALREADY_SETTLED")

    def test_unmatched_presentment_posts_and_is_audited(self):
        event = Event("settle", 1, "SETTLEMENT", "ACC-001", "AED", 1, "40", auth="Z")
        self.assertEqual(self.ledger.process(event).code, "UNMATCHED_SETTLEMENT")
        self.assertEqual(self.ledger.balance("ACC-001", 1), 6000)
        self.assertTrue(any(r.kind == "EXCEPTION" and r.auth == "Z" for r in self.ledger.journal))
        self.assertEqual(self.ledger.process(replace(event, id="again")).code, "AUTH_ALREADY_SETTLED")

    def test_cancel_expire_and_late_presentment(self):
        for kind, state in (("CANCEL", "CANCELLED"), ("EXPIRE", "EXPIRED")):
            with self.subTest(kind=kind):
                ledger = Ledger()
                ledger.process(credit())
                ledger.process(self.auth())
                event = Event("end", 2, kind, "ACC-001", "AED", 2, auth="A")
                self.assertEqual(ledger.process(event).code, "ACCEPTED")
                self.assertEqual(ledger.auth_states("ACC-001")["A"].state, state)
                self.assertEqual(ledger.held("ACC-001"), 0)
                self.assertEqual(ledger.process(replace(event, id="end2")).code, "AUTH_NOT_ACTIVE")
                late = Event("late", 3, "SETTLEMENT", "ACC-001", "AED", 3, "10", auth="A")
                self.assertEqual(ledger.process(late).code, "UNMATCHED_SETTLEMENT")
                self.assertEqual(ledger.balance("ACC-001", 3), 9000)

    def test_exact_retry_and_conflicting_id(self):
        before = self.ledger.journal
        result = self.ledger.process(credit())
        self.assertEqual(result, before[0])
        self.assertEqual(before, self.ledger.journal)
        self.assertEqual(self.ledger.process(credit(units="200")).code, "DUPLICATE_CONFLICT")
        self.assertEqual(self.ledger.balance("ACC-001", 1), 10000)

    def test_invalid_events_never_move_money(self):
        cases = [(replace(credit(), id="bad", currency="BHD"), "CURRENCY_MISMATCH"),
                 (replace(credit(), id="bad", amount="NaN"), "INVALID_AMOUNT"),
                 (replace(credit(), id="bad", value_day=2), "FUTURE_VALUE_DATE"),
                 (replace(credit(), id="bad", amount="0.001"), "NONPOSITIVE_AMOUNT"),
                 (replace(credit(), id="bad", account="X"), "UNKNOWN_ACCOUNT"),
                 (replace(credit(), id="bad", booked_day=7), "INVALID_DAY")]
        for event, code in cases:
            with self.subTest(code=code):
                ledger = Ledger()
                self.assertEqual(ledger.process(event).code, code)
                self.assertEqual(ledger.balance("ACC-001", 6), 0)
                ledger.close(1)  # Invalid booked dates must not poison the close clock.

    def test_reversal_validation_and_instalment_reversal(self):
        ledger = Ledger()
        ledger.process(EVENTS[-1])
        event = Event("reverse", 6, "REVERSAL", "ACC-002", "BHD", 5, reference="E10")
        self.assertEqual(ledger.process(replace(event, id="bad-day", value_day=4)).code, "REVERSAL_VALUE_DATE_MISMATCH")
        self.assertEqual(ledger.process(event).code, "ACCEPTED")
        self.assertEqual(ledger.balance("ACC-002", 6), 0)
        self.assertEqual(ledger.process(replace(event, id="unknown", reference="missing")).code, "NOT_REVERSIBLE")

    def test_negative_bhd_has_no_invented_fx_policy(self):
        ledger = Ledger()
        ledger.process(Event("debit", 1, "DEBIT", "ACC-002", "BHD", 1, "1"))
        before = ledger.journal
        with self.assertRaisesRegex(PolicyError, "missing BHD"):
            ledger.close(1)
        self.assertEqual(ledger.journal, before)

    def test_finalization_and_immutable_records(self):
        ledger, closes = replay()
        before = ledger.journal
        self.assertEqual(ledger.close(6), closes[6])
        self.assertEqual(ledger.journal, before)
        with self.assertRaises(FrozenInstanceError):
            ledger.journal[0].units = 999
        self.assertEqual(ledger.process(credit(id="late")).code, "WINDOW_FINALIZED")
        self.assertEqual(ledger.balance("ACC-001", 6), 21069)

    def test_seeded_credit_debit_reversal_conservation(self):
        rng = random.Random(20260926)
        expected = 10000
        for i in range(100):
            units = rng.randint(1, 100000)
            kind = rng.choice(("CREDIT", "DEBIT"))
            event = replace(credit(id=f"random-{i}", units=money(units, "AED")), kind=kind)
            self.ledger.process(event)
            expected += units if kind == "CREDIT" else -units
            self.assertEqual(self.ledger.balance("ACC-001", 1), expected)
            self.ledger.process(Event(f"reverse-{i}", 1, "REVERSAL", "ACC-001", "AED", 1, reference=event.id))
            expected -= units if kind == "CREDIT" else -units
            self.assertEqual(self.ledger.balance("ACC-001", 1), expected)


if __name__ == "__main__":
    unittest.main()
