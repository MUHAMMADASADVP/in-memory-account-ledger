# Initial design checkpoint

The input order is authoritative, even though E10 says booked Day 5 after E9
says booked Day 6. Sequence, booked day, and value day are separate dimensions.
At the first advance to a new booked day, close intervening days. Accept late
events before finalization, and restate earlier value-day projections without
changing records or past authorization decisions. Preserve original close
checkpoints and show a second, final-as-known view.

Use integer minor units (AED hundredths, BHD thousandths), half-up rounding,
and a stable largest-remainder allocation for instalments. All monetary rows
belong to exactly one account/currency. No binary floating point.

At close, scan value days chronologically, including earlier assessed fees in
later balances. Assess at most once per account/value-day, append a fee record,
and retain it after principal reversal; refund policy is deliberately separate.
The fee's value day is the historical day being assessed, while its booked day
is the current processing day. Interest follows fees and is corrected through
append-only daily deltas. Capitalize the sum of effective rounded accruals once,
after calculating Day 6 interest; no interest on that capitalization itself.

Authorization decisions use the currently known balance and active holds.
Settlement is a financial presentment, not another authorization request:
consume a matching hold in full, and post unmatched presentments with an audit
exception. This is an explicit domain assumption, not a rule derived from the
brief. Support explicit cancellation and expiry, with no invented automatic TTL.

The supplied BHD path never goes negative. No BHD fee or FX rate is specified:
a negative BHD close must fail with a missing-policy error, not silently convert
the AED tariff or waive fees.

Intended commits: design; core and tests; replay and edge-case validation;
submission documentation and PDF. Retain actual commits, including fixes.
