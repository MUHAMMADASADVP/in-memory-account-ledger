# Numbers and their justification

All stored monetary amounts are integers in their account's minor units. No
cross-currency arithmetic or binary floating-point money exists in the core.

## Contract and arithmetic constants

| Constant | Value / representation | Why this value, rather than half |
| --- | --- | --- |
| Account opening balance | 0 for both accounts | Fixed by the brief; half of zero is still zero. |
| Window | Inclusive Days 1 through 6 | Fixed by the brief. Three days would omit settlements, correction, and capitalization. |
| AED precision | 2 decimal places; scale 100 | Fixed by the brief. A scale of 50 is not a decimal currency precision and cannot express every fils. |
| BHD precision | 3 decimal places; scale 1,000 | Fixed by the brief. A scale of 500 cannot represent every 0.001 unit. |
| Decimal radix | 10 | Decimal strings and the required currency precisions. Radix 5 changes the representation. |
| AED daily overdraft fee | 2,500 minor units = 25.00 | Fixed by the brief. 12.50 undercharges it. |
| BHD overdraft fee | `None` (missing policy) | A deliberate absence, not zero and not a converted AED tariff. Cannot halve an unspecified value. |
| Interest rate | 4 / 10,000 = 0.0004 = 0.04% | Fixed by the brief. Halving the numerator underaccrues; halving the denominator doubles the rate. Using 1/2,500 would be equivalent, but the basis-point form is easier to defend. |
| Interest tie rule | Increment quotient when `2 * remainder >= denominator` | Half-up compares with half a minor unit without floating point. A multiplier of 1 would implement the wrong threshold. |
| Input tie digit | First discarded decimal digit >= 5 | Half-up in radix 10. A threshold of 2.5 is not rounding to the nearest minor unit. |
| Maximum assessment frequency | 1 per account/value-day | Fixed by the brief. A half-assessment has no event meaning. |
| Final capitalization count | 1 per account | Fixed by the brief; includes a zero credit if all accruals are zero. A fractional posting count is meaningless. |
| Hold approval threshold | Remaining available >= 0 | Fixed by the brief. Equality is allowed. Holds do not create ledger debits. |
| Hold release | All remaining held units on the single settlement or explicit termination | An explicit single-capture policy. Releasing half would strand funds after completion. |
| Instalment count | 3 | Fixed for E10 by the brief. A fractional count is invalid. |
| Remainder distribution | First `remainder` parts receive 1 extra minor unit | Deterministic conservation with a maximum part difference of 1. Half a minor unit cannot be stored. |
| Sequence / day origin | 1; zero sequence means no knowledge yet | Audit rows are one-indexed; the zero cutoff is the empty ledger. This is a convention, not a monetary parameter. |
| Loop increments | 1 day / row / part | Discrete identifiers and iteration; fractions have no meaning. |

## Supplied inputs (not tuned constants)

| Input | Amount stored | Value day | Booked-day label |
| --- | ---: | ---: | ---: |
| E1 credit | +120,000 AED minor units | 1 | 1 |
| E2 debit | -95,000 AED minor units | 1 | 1 |
| E3 hold | 20,000 AED minor units, no posting | 2 | 2 |
| E4 credit | +40,000 AED minor units | 3 | 3 |
| E5 settlement | -18,500 AED minor units; releases 20,000 hold | 4 | 4 |
| E6 settlement | -18,000 AED minor units | 4 | 4 |
| E7 debit | -62,000 AED minor units | 2 | 5 |
| E8 requested hold | 9,000 AED minor units; declined | 5 | 5 |
| E9 reversal | +62,000 AED minor units, derived from E7 | 2 | 6 |
| E10 instalment credit | +10,000 BHD minor units, split into 3,334 / 3,333 / 3,333 | 5 | 5 |

Halving any supplied amount changes the exercise, rather than simplifying the
design. Event/account/auth identifiers are opaque labels, not numeric settings.

## Reconciliation from input to final balances

AED principal net is `1200 - 950 + 400 - 185 - 180 - 620 + 620 = 285`.
Three assessed fees subtract 75, leaving 210 before capitalization. Daily
accruals are computed from these final-as-known, pre-capitalization balances:

| Value day | AED interest base | Unrounded AED interest | Rounded AED accrual | BHD interest base | Rounded BHD accrual |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 250.00 | 0.100 | 0.10 | 0.000 | 0.000 |
| 2 | 225.00 | 0.090 | 0.09 | 0.000 | 0.000 |
| 3 | 625.00 | 0.250 | 0.25 | 0.000 | 0.000 |
| 4 | 235.00 | 0.094 | 0.09 | 0.000 | 0.000 |
| 5 | 210.00 | 0.084 | 0.08 | 10.000 | 0.004 |
| 6 | 210.00 | 0.084 | 0.08 | 10.000 | 0.004 |
| **Total** | | **0.702** | **0.69** | | **0.008** |

Rounding the unrounded AED total once would give 0.70, **not** 0.69. The contract
requires the sum of daily rounded accruals; capitalization is therefore exactly
0.69. The 0.012 between raw and daily-rounded sums is ordinary disclosed daily
rounding, not an unmatched remainder discarded at capitalization.

Final credits give AED **210.69** and BHD **10.008**. At E8, before the Day 5 fee
pass, the known ledger balance is already -335.00, so a further 90.00 hold is
declined. Interest on Day 3 at the Day 5 cutoff uses +5.00: `5 * .0004 = .002`,
rounded to AED 0.00. Its later corrected accrual is 0.25.

## Test and presentation constants

- Test seed **20260926** records the working date and makes randomized checks
  reproducible. Half would be another arbitrary seed, not better coverage.
- **100** randomized posting/reversal pairs are a cheap smoke sample, not a
  statistical guarantee. **1..100,000** minor units span both small and larger
  amounts; half that range/trial count weakens variety without useful savings.
- Exhaustive small allocation checks use totals **0..100** and counts **1..9**
  (**909** combinations), covering zero and non-divisible cases. Half would
  remove cases for negligible runtime benefit. No production limits are implied.
- Boundary fixtures use **1** minor unit and the **1,249/1,250** interest bases
  immediately below/at the half-unit tie; halving them would stop testing that
  boundary. Credits/holds such as **100/100**, **100/101**, and **100/90** isolate
  exact-zero approval, insufficient funds, and abandoned holds. Their absolute
  size is illustrative; the inequality/tie is what matters.
- Python **3.10+** is the syntax floor for union type annotations; **3.14** is the
  available test interpreter. These are version identifiers, not tunable sizes.
- PDF uses **3 A4 pages**, **48-point** margins, **10-point** body text with
  **14-point** leading, **9-point** list text with **13-point** leading, and
  **22/14/11-point** title/section/subsection headings. These are readability and
  pagination choices; halving makes the document cramped or hard to read. The
  renderer uses **1.5x** scale for inspection, not a ledger calculation.
- No arbitrary amount ceiling, backdating horizon within the six-day window,
  cache size, network timeout, or automatic expiry TTL is a ledger constant.
  Production resource/validation bounds remain an explicit cut.
