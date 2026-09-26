# Ambiguities and explicit resolutions

These choices are part of the contract of this implementation. A different
choice can be valid if its accounting consequences are carried through. Nothing
here is represented as a universally correct bank policy.

| Question | Resolution and consequence | Alternative / why not used |
| --- | --- | --- |
| What does "replayed in this order" mean when E10 is booked Day 5 after E9 on Day 6? | Preserve array order. Close elapsed days when the highest observed booked day advances. E10 arrives after the original Day 5 close; final reconciliation includes it on value Day 5. | Sorting by booked day changes the explicit input order and hides late arrival. |
| Which date is transaction time? | Sequence is the authoritative knowledge cutoff. `booked_day` is the supplied business label; `value_day` is financial effect. E10 proves booked day cannot also be an arrival clock. | Inventing a new booked day for E10 loses supplied information. |
| Which Day 2 balance? | Require both value day and optional sequence cutoff. Original close: 250.00; after E7 before fees: -370.00; after Day 5 fees: -395.00; final: 225.00. | One mutable daily-balance cell cannot represent all four facts. |
| When are fees assessed? | At close, revisit all elapsed value days in increasing order. Fees apply to negative value-day closing ledger balance, not transient intraday negatives or hold-reduced available balance. | Immediate per-event assessment can charge a day that ends positive. |
| Does a fee affect later days? | Yes. It is an ordinary monetary debit in all later cumulative balances. This can cause another day's fee. | Excluding fees would contradict the all-entries balance rule. |
| Is the fee's value date the historical day or current processing day? | The day being assessed is the historical value day. Discovery/booked day remains the current close day. | Booking every catch-up fee with value Day 5 changes Days 2-4 and interest; the brief's phrase "day assessed" is ambiguous, so this convention is explicit. |
| Reversal and fee refunds? | Reverse E7 principal only, retaining earlier fee assessments. No refund command is implemented. A refund would be a separate compensating credit authorized under a product policy. | Automatic fee refund is plausible for bank error, but no cause or refund policy is supplied. Append-only does not settle this question. |
| Can a later credit retrospectively invalidate an earlier assessment? | No automatic cancellation of an assessed fee. Assessment records describe what was determined at a close cutoff. Final balance can be positive on a day with a retained fee. | Recompute-and-refund fees would need a distinct effective-fee policy and adjustment records. |
| Must a settlement have a prior authorization? | Treat SETTLEMENT as an already-binding clearing presentment. Post it and append an exception if the hold is absent/inactive. | If it meant a pre-clearing capture request, rejecting unknown IDs would be valid. The brief does not specify the network contract. |
| Does settlement re-check available balance? | No. Matching settlement releases the full hold and debits the actual amount. A larger capture may overdraw. | Applying authorization rules again could suppress an existing clearing liability. |
| Partial settlement / residual hold? | One settlement consumes the entire hold. The difference between 200 and 185 is released, never separately credited. | Multiple partial captures and incremental authorization need more identifiers and remaining-capture state. |
| Late settlement after cancellation/expiry/decline? | Post as unmatched, leave the original terminal auth state intact, and record an exception. A second settlement for that account/auth ID is rejected. | Multiple presentments per auth are intentionally unsupported; production needs a distinct clearing ID. |
| Scope and reuse of authorization IDs? | Account-scoped; reuse is rejected after any decision or settlement. Rejected authorizations have state DECLINED and hold zero. | Reusing IDs could attach a late clearing item to a new hold. |
| Does a backdate retroactively undo an approval? | No. A decision reflects the then-known ledger and active holds. Historical decision checkpoints remain queryable. | Re-running past approvals would change commitments already made externally. |
| What happens to Auth-B after E9? | It was declined at E8; later money does not reapprove it. A fresh request needs a fresh ID. | Implicit retry changes event semantics. |
| Hold expiry duration? | None invented. Explicit CANCEL and EXPIRE transitions release active holds. There is no scheduler; an active hold can outlive the window. | A generic arbitrary TTL could violate scheme/product rules. The separate failing test exposes this cut. |
| Interest base and fee order? | Use the after-fee ledger balance, positive only, excluding holds and uncapitalized accruals. | Available balance is not the specified interest base. |
| Restate interest or lock each original daily accrual? | Recompute elapsed days using current knowledge at every close. Append the difference to prior rounded daily accruals. | Locking past accruals ignores corrected value dates; overwriting would destroy the audit trail. |
| Does Day 6 interest earn interest on itself? | Calculate daily interest before the final capitalization. Exactly one capitalization per account, including a zero-valued audit credit if necessary. | Including the capitalization in its own base creates a circular calculation. |
| How to round? | Half-up, independently in currency minor units; daily rounded values are authoritative. Inputs with extra precision are rounded at ingestion, then must remain positive. | Half-even is defensible but unspecified. Summing unrounded accruals and rounding once can differ. |
| "Equal" BHD instalments? | Equal as closely as representable: stable remainder allocation to earlier parts. | Exact thirds cannot be expressed in thousandths; three rounded-up parts create money. |
| BHD overdraft tariff? | Not supplied. If a BHD close is negative, fail reconciliation before derived writes with `PolicyError`; no fee is invented. | AED 25 is not BHD 25, and no FX conversion policy exists. The supplied BHD path remains positive. |
| Opening balances? | Implicit fixed zero for both declared accounts. | Configurable opening balances or account creation events add no value to this fixed replay. |
| What is reversible? | Accepted CREDIT/DEBIT inputs, including all instalments of a credit. Same account and value day required; one full reversal only. | Settlement chargebacks, partial refunds and fee waivers need separate domain operations. |
| Retries and conflicting IDs? | Exact same Event returns its first immutable decision without appending. Reusing its ID with different fields appends a conflict error and moves no money. Rejected attempts also reserve IDs. | Silent overwrite loses identity; equivalent-but-differently-formatted amounts intentionally count as conflicting payloads. |
| Input errors? | Journal a rejected decision and continue. An unmatched settlement is a posted exception; insufficient authorization is a declined decision. | Treating every non-ACCEPTED code as a failed posting would misread E6. |
| Future value dates and window boundaries? | Days 1-6 only, no value day after the event's booked day. Reject monetary work after finalization. Exact retries still return the old result. | Future-dated holds and post-capitalization adjustments need a longer-lived engine. |
| Out-of-order hold requests? | Decisions use all currently known active holds and ledger entries through the request's booked day. The fixture's only late arrival is a credit. | A production ingest clock and scheme business calendar should replace this small-window convention. |
| Atomicity and concurrency? | One caller, one process. Validate domain rules before appending derived rows. No concurrency, rollback on process failure, or durability claim. | Transactional batches and per-account serialization belong in a durable service. |
| Is this double-entry accounting? | No: it is an account subledger. Each amount has account-owned currency; no FX. | A production general ledger needs balanced counter-entries and reconciliation. |
| Fee legality and local calendar? | The assignment's tariff is a fixture, not a claim of approved UAE product pricing. Days are integers, not dates or cut-off timestamps. | Compliance, disclosures, holidays, and timezone policies need product and legal review. |

## Temporal reconstruction

`balance(account, day, through)` selects monetary rows with both
`value_day <= day` and `sequence <= through`. An authorization view is at a
sequence cutoff, not inferred from value dates. A final-value-day balance and a
historical authorization decision are different projections; the report labels
them separately. Original closes are not rewritten when the final projection
changes. Zero interest is represented by absence/net zero of accrual deltas,
not by an interest-credit posting.
