# In-memory account ledger core

A Python standard-library implementation of the six-day assignment. No server,
database, persistence, or UI. The journal holds immutable input decisions,
postings, authorization transitions, fees, and interest corrections in memory.
The replay report is the executable specification of the chosen policies.

## Run

Use Python 3.10 or newer (verified here on Python 3.14). No packages are needed
for the ledger or tests.

```sh
python3 -m unittest discover -s tests -v
python3 replay.py
python3 known_failure.py
```

The first command should pass. The last command **must exit 1 with one failure**:
it demonstrates the missing automatic hold-expiry mechanism. It is deliberately
separate from regression discovery and is not skipped or marked expected-failure.
Read its inline explanation before changing it.

## Read the output

1. **Original close checkpoints** show ledger/available balances, holds,
   authorization states, fees newly assessed, and errors/exceptions per day.
   A sequence cutoff makes each historical view reproducible after later events.
2. **Restated value-day balances** include everything learned by the end of the
   replay. Old records and old authorization decisions are never rewritten.
3. **Daily interest audit** shows positive and negative accrual adjustments,
   their effective days, and the two final capitalization totals.

E10 is intentionally processed *after* E9, exactly as supplied. Its booked-day
label remains 5. It revises the Day 5 projection at Day 6 reconciliation, rather
than being sorted into the original Day 5 close. Every input attempt has a
sequence number separate from its booked and value days.

| Day | AED original close | AED final-as-known close | AED final daily interest | BHD final-as-known close |
| --- | ---: | ---: | ---: | ---: |
| 1 | 250.00 | 250.00 | 0.10 | 0.000 |
| 2 | 250.00 | 225.00 | 0.09 | 0.000 |
| 3 | 650.00 | 625.00 | 0.25 | 0.000 |
| 4 | 285.00 | 235.00 | 0.09 | 0.000 |
| 5 | -410.00 | 210.00 | 0.08 | 10.000 |
| 6 | 210.69 | 210.69 | 0.08 | 10.008 |

Day 6 closing includes the single interest credit; interest itself uses the
balance immediately before capitalization. AED interest totals 0.69. BHD earns
0.004 on each of Days 5 and 6, totaling 0.008. BHD's original Day 5 close is zero.

## Policies that materially affect the answer

- An unmatched settlement posts as a clearing debit with an
  `UNMATCHED_SETTLEMENT` exception. Auth-Z is never fabricated as an approved hold.
- Reconciliation assesses AED 25.00 on value Days 2, 4, and 5, booked on Day 5.
  Fees affect subsequent value-day balances. No second assessment for the same
  account/day is permitted.
- Reversal cancels only E7's principal. The three fee assessments remain;
  the brief supplies no fee-refund policy. Append-only alone does **not** prohibit
  a compensating refund; retaining fees is a separate policy choice.
- Auth-A is approved when received, then settled for 185.00 and its whole
  200.00 hold released. Auth-B is declined and is not retried after E9.
- Instalments are 3.334, 3.333, 3.333 BHD. They differ by at most one minor unit
  and sum exactly to the input amount.

These are defended, not hidden, in [AMBIGUITIES.md](AMBIGUITIES.md) and
[REJECTED.md](REJECTED.md). Some refusals are conditional on domain assumptions;
the brief does not uniquely determine every policy.

## Repository guide

| File | Purpose |
| --- | --- |
| `ledger.py` | Integer money, immutable records, transitions, value-day close |
| `replay.py` | Supplied stream in exact order and readable per-day report |
| `tests/test_ledger.py` | Regression, boundary, retry, and conservation checks |
| `known_failure.py` | Real, annotated failing test against an intentional cut |
| `NUMBERS.md` | Constants, rounding derivations, and numerical reconciliation |
| `AMBIGUITIES.md` | Resolutions and alternatives, including operational limits |
| `REJECTED.md` | All eight criteria assessed and approaches abandoned |
| `ARCHITECTURE.md` | Source for the concise architecture document |
| `output/pdf/architecture-trade-offs.pdf` | Submission PDF |
| `output/replay.txt` | Captured reference output from the supplied stream |
| `WORKLOG.md` | Actual UTC work entries and verification results |
| `DESIGN.md` | Initial design checkpoint, retained in commit history |

## Rebuild the PDF (optional)

PDF tooling is separate from the dependency-free ledger:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-pdf.txt
.venv/bin/python scripts/build_pdf.py
```

The PDF is already committed. Do not squash the development commits when
submitting. AI assistance was used; the implementation and policy decisions
should be reviewed and understood before the no-AI live defense.
