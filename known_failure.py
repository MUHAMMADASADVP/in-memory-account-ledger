"""Deliberately failing design challenge, separate from the regression suite."""

import unittest

from ledger import Event, Ledger


class AuthorizationExpiryGap(unittest.TestCase):
    def test_an_abandoned_hold_should_eventually_release_without_a_message(self):
        ledger = Ledger()
        ledger.process(Event("credit", 1, "CREDIT", "ACC-001", "AED", 1, "100"))
        ledger.process(Event("hold", 1, "AUTHORIZATION", "ACC-001", "AED", 1, "90", auth="abandoned"))
        ledger.close(6)
        # Deliberately false for this design: there is no expiry scheduler or TTL.
        # A lost merchant cancellation leaves 90.00 unavailable indefinitely.
        # Day 6 is this test's proposed release boundary, NOT a brief requirement.
        # The core supports EXPIRE, but nothing generates it. Fixing production
        # requires a scheme-specific deadline and a reliable expiry-event source.
        # Do not weaken this assertion or label it expectedFailure to turn it green.
        self.assertEqual(ledger.held("ACC-001"), 0,
                         "design gap: abandoned authorization remains held without an explicit EXPIRE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
