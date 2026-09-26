# Criteria reviewed and refused

The numbered rows below cover **all eight** supplied acceptance criteria.
Criteria 2, 4, 6, 7, and 8 are refused under the documented contract. Of those,
4 and the monetary restoration portion of 6 require domain assumptions; they
are not mathematical contradictions established by append-only storage alone.

| # | Criterion (abridged) | Decision and reasoning |
| --- | --- | --- |
| 1 | Day 2 at end of Day 5, before fees, is -370.00 AED. | **Accept.** 1,200 - 950 - 620 = -370. E3 is a hold, not a debit. E4-E6 have later value days. After the Day 2 fee the balance is -395, a different query. |
| 2 | E7 causes exactly one fee, on Day 2. | **Refuse.** A backdated debit affects subsequent daily cumulative balances. At Day 5 reconciliation, Day 2 is negative, Day 3 remains +5 after that fee, and Days 4 and 5 are negative. Three fees total AED 75.00. See the waterfall below. |
| 3 | Day 4 settlement of Auth-A must be accepted. | **Accept.** The active hold exists and was approved with available funds. Settlement posts 185 and releases the entire 200 hold. Later knowledge does not rescind an already-made approval. |
| 4 | Every unknown-authorization settlement must be rejected. | **Refuse under the clearing-presentment interpretation.** Absence of a local hold does not prove absence of a clearing obligation; offline/late presentments or a missing upstream message are possible. E6 posts -180 with an exception. If SETTLEMENT instead means an uncommitted capture request, this criterion is defensible; the brief leaves that unspecified. |
| 5 | An approved Auth-B hold affects available, not ledger balance. | **Accept as a conditional.** Holds are separate from postings. In this stream Auth-B is declined; the tests separately exercise an approved hold at the exact zero-available boundary. |
| 6 | After E9 all balances and fees return to pre-E7 values. | **Refuse as an unconditional promise.** E9 reverses principal, not fees. Retained AED 75 leaves principal-plus-fee balance 210 versus 285 before E7. Auth-B's historical decline remains. A fee-refund policy could restore monetary amounts with compensating entries, but no such policy is supplied, and journal/decision history would still differ. |
| 7 | Each BHD instalment is 3.334. | **Refuse.** Three such credits sum to 10.002, creating 0.002. Allocate 3.334, 3.333, 3.333; sum 10.000 and maximum part difference 0.001. |
| 8 | Discard any difference between daily rounded interest and capitalization. | **Refuse.** Capitalization is defined as the sum of effective rounded daily accruals, making reconciliation exact by construction. A discrepancy is an invariant failure, not permission to discard money. |

## Fee waterfall at Day 5, before E9

| Value day | Principal-only close | Earlier fees carried in | Balance before this day's fee | New fee | Balance after fee |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 250.00 | 0.00 | 250.00 | 0.00 | 250.00 |
| 2 | -370.00 | 0.00 | -370.00 | 25.00 | -395.00 |
| 3 | 30.00 | -25.00 | 5.00 | 0.00 | 5.00 |
| 4 | -335.00 | -25.00 | -360.00 | 25.00 | -385.00 |
| 5 | -335.00 | -50.00 | -385.00 | 25.00 | -410.00 |

This is not three fees on Day 5: these are three distinct historical value-day
assessments discovered/booked on Day 5. Re-running reconciliation cannot assess
any of those account/day keys twice.

## Approaches abandoned during this build

- **Decimal as the stored representation.** Initially considered and described
  in the first progress update. Replaced before the core commit by integer minor
  units; integer rational interest has no ambient decimal-context precision.
  String conversion still rounds explicitly to the currency's precision.
- **A single final historical table.** During replay construction, added
  original close checkpoints as well: one table would conceal that E10 arrived
  after Day 5 closed and would blur what was known at authorization time.
- **Automatic hold release at the window boundary.** Considered while building
  the required failing test, but no contractual expiry is supplied. Kept an
  explicit EXPIRE transition and an honestly failing scheduler-gap test instead
  of inventing a six-day TTL just to pass it.
- **Using Poppler for PDF review.** The executable was absent. Used PyMuPDF to
  rasterize the PDF and pypdf to validate page count/text instead; review remains
  visual, not just text extraction.

These are actual design/build changes, not fabricated claims of prototypes or
benchmarks. Rejected criteria are specification disagreements; the separate
`known_failure.py` is a test of a real limitation in this implementation.
