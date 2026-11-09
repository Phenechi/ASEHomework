# HW2 final test evaluation

Both agent-guided improvement rounds and local verification are complete. The
PDF report and GitHub work were excluded by the user. The suite is in `tests/`:
11 original HW1 methods, 13 initial HW2 methods, 21 round 1 methods, and 15 round 2
methods. Counts are unittest methods; subtests are included within those methods.

## Initial-to-final comparison

| Stage | Passed / run | Python lines | Python branches | Naturally discovered faults |
|---|---:|---:|---:|---|
| HW2 initial, original app | 24 / 24 | 345 / 414 (83.33%) | 78 / 112 (69.64%) | None detected |
| Round 1, original app | 45 / 45 | 393 / 414 (94.93%) | 101 / 112 (90.18%) | None detected |
| Round 2, before bug fix | 59 / 60 | 414 / 414 (100%) | 112 / 112 (100%) | HW2-01 reproduced |
| Final, after bug fix | 60 / 60 | 414 / 414 (100%) | 112 / 112 (100%) | HW2-01 regression passes |

All runs had zero errors and skips. The final coverage run took 2.163 s of
unittest time; standalone discovery independently ran all 60 in 1.737 s. These
single-run timings are reproducibility details, not performance measurements.

The final suite adds **69 exercised Python statements and 34 branches** over the
initial suite: +16.67 percentage points of line coverage and +30.36 points of
branch coverage. Both use coverage.py 7.10.7 with branch mode and the same source
scope. Combined line/branch coverage increased from 80.42% to 100%. Coverage is
limited to Python under `app/`; the HTML/JS/CSS serving test does not execute
JavaScript in a browser.

The bug fix changed only `app/llm.py`. For a controlled comparison, the frozen
initial and round 1 suites were rerun on the **same corrected app source** as
the final suite. Both reproduced their original coverage totals (24/24 at
83.33% lines / 69.64% branches; 45/45 at 94.93% lines / 90.18% branches). App
hashes match across the controlled runs, and test hashes confirm the earlier
tests were preserved. The coverage gains came from the extra tests, rather than
the change in source. See `evidence/comparison.json` for exact denominators and
source-match flags.

## Round 1: explicit requirements context

See [working guidance](ROUND1_GUIDANCE.md) and [execution](evidence/round1/01-execution.txt).
Replacing high-level service stubs with controlled HTTP responses exercised real
Atom parsing, normalization, cache expiry, minimum request spacing, download URL
validation and streaming. The fake clock tested boundaries without real sleeps.
Real generated PDFs covered encryption, page count and text caps, as well as
partial blank pages. Library tests checked the selected record's identity, PDF
bytes, history and record count. No production change was made in this round.

Coverage rose from 83.33% to 94.93% of lines and from 69.64% to 90.18% of
branches. `papers.py` rose from 63.13% to 97.21% combined coverage; `llm.py`
remained at 80.00%. The requirements context was effective for service and PDF
contracts, but did not exercise provider failures or multi-paragraph grounding.
The cache-capacity test depends on an implementation resource limit rather than
a documented user-facing behavior. It deliberately avoids prescribing eviction
order.

## Round 2: execution feedback and stronger assertions

See [working guidance](ROUND2_GUIDANCE.md) and the [pre-fix run](evidence/round2-before-fix/01-execution.txt).
The remaining lines and partial branches directed tests toward provider errors,
invalid model outputs, repeated evidence IDs, metadata fallback and stale
analysis handling. Instead of checking only status codes, the new tests check
actionable error text, existing history preservation, exact quotes and page
citations, and absence of orphaned records. The controlled SQLite trigger and
database changes during analysis exercise real rollback/stale-result logic
without scheduler-dependent races. The static asset test checks the served app
shell and files, with no claim of browser interaction coverage.

Coverage feedback identified execution gaps. The stronger paragraph-level oracle
found a fault even with every line and branch exercised. The test expected
rejection and no write; the app accepted and saved an unsupported factual
paragraph beside a cited one. [HW2-01](BUGS.md) documents the requirement,
reproduction, exact failing result, archived original source and targeted fix.
There were no test-construction failures in the recorded improvement runs.

## Final correctness and fault-detection review

| Area | What the final assertions establish | What they do not establish |
|---|---|---|
| Search and fetch | Expected Atom metadata and year, cache timings, validated fixed-host requests, stream boundaries, user-facing failures | Live arXiv availability or compatibility with every possible feed |
| PDF and library | Real extraction, documented bounds, blank-page disclosure, duplicate ownership, bytes/metadata preservation, SQLite rollback and history | Accuracy on arbitrary document layouts, OCR, or behavior under real concurrent load |
| AI | Valid IDs, exact quotations, derived citations, no fabricated page numbers, no unsupported paragraphs in substantive responses, no saves after failures | Semantic support of every claim, honesty of the model's insufficient-evidence flag, live provider quality |
| Web delivery | Homepage and essential static assets are served | Browser event behavior, layout or XSS protection |

Subtests group similar cases such as malformed feeds, upload boundaries and
provider exceptions without counting each variant as a separate method. Some
contract tests share setup and routes, but each new check adds a distinct oracle
or failure case. The app uses temporary SQLite and local PDF fixtures; no paid
OpenAI calls or user data are needed. Error checks use short meaningful message
fragments rather than pinning complete framework-generated payloads.

Initial and round 1 tests did not detect HW2-01 on the original source; round 2
did, and the unchanged test passes after the fix. The synthetic constraint test
is controlled error-path testing, not a naturally discovered fault. No mutation
score or comprehensive fault-detection claim is made. Most notably, the pre-fix
run had 100% line and branch coverage **and still failed**, which distinguishes
execution coverage from correct output and persistence behavior.

## Evidence and reproduction

- [Testing instructions](TESTING.md): dependencies, stage commands and the
  original-source reproduction procedure.
- [Interaction log](INTERACTION_LOG.md): actual user instructions, representative
  agent guidance, run feedback and app correction.
- [Initial evaluation](INITIAL_EVALUATION.md) and [reflection notes](REFLECTION_NOTES.md).
- `evidence/{initial,round1,round2-before-fix,final}/`: verbatim test/coverage
  output, structured outcomes, coverage JSON, source hashes and local coverage HTML.
- `evidence/{initial-on-final-source,round1-on-final-source}/`: controlled replays.
- [Standalone discovery log](evidence/verification/unittest-discovery.txt) and
  [machine-readable comparison](evidence/comparison.json).
