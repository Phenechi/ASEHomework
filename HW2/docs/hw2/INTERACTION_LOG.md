# HW2 interaction and decision log

## Kickoff - November 6, 2026

Actual user request:

> read the pdf first. we built the research app in part 1 and now in the second hw we are going to generate test and improvement using agents. build out a workflow plan and begin work on the project

Codex read all four PDF pages, including rendered pages, then inspected README,
the four backend modules, browser JavaScript and the existing 11 HW1 tests.
The homework calls for a coding agent; this session uses Codex directly. No
separate delegated agents or user feedback rounds have been invented.

Agent-generated initial working guidance (recorded here as agent guidance,
not a quotation of an additional user prompt):

> Preserve the HW1 suite as a baseline. Generate a distinct HW2 initial suite
> against the documented research workflows, covering normal use, validation,
> errors and persistence. Use isolated SQLite and local PDF fixtures, mock
> external services, assert content and side effects, and record coverage and
> execution evidence before adding improvement-round tests.

Implementation: `tests/hw2/test_initial.py`, standard-library unittest,
coverage.py 7.10.7, and `scripts/evaluate_tests.py`. Reused the pre-existing PDF
fixture rather than presenting it as newly generated. No production source or
original HW1 test was changed at kickoff.

Environment feedback:

- Installing coverage under restricted networking failed with DNS errors;
  approved installation into project `.venv` succeeded.
- Two sandboxed baseline attempts stalled. A diagnostic traceback located the
  stall in Windows asyncio's loopback socketpair creation during TestClient
  startup. Both stalled processes were stopped.
- Running the same 11 HW1 tests outside the sandbox passed in 0.456 seconds.
  The malformed-PDF fixture prints an expected `EOF marker not found` diagnostic.
  This is not a detected application bug or a completed improvement round.

See `INITIAL_EVALUATION.md` and `evidence/` for measured results and the initial
review. At kickoff, both improvement rounds remained future work.

Measured outcomes: baseline 11/11 passing, 79.47% line and 61.61% branch coverage;
initial suite 24/24 passing, 83.33% line and 69.64% branch coverage. Both cover
the same 414 Python statements and 112 branches. No application bug detected.
Saved raw results and hashes, reviewed assertions and recorded untested behavior.
Production-source hashes are identical between the two measured stages.

## Scope check and follow-up

The user requested a summary of completed and remaining work, then directed:

> finish the remaining task other than pdf and github

Codex completed local testing, evaluation and evidence preparation. No PDF
report, commit, push or GitHub work was performed in this follow-up.

## Improvement round 1: requirements context

See [recorded agent guidance](ROUND1_GUIDANCE.md), based on documented behavior
and the initial evaluation. Codex added 21 methods using real Atom/PDF fixtures,
mocked service responses, a fake clock and isolated SQLite. Earlier tests and
app source stayed fixed. The run passed 45/45: 94.93% lines, 90.18% branches,
93.92% combined. No bugs detected. `llm.py` remained at 80.00% combined; the
coverage table identified provider errors, invalid answers, stale-result handling
and metadata fallbacks as remaining gaps.

## Improvement round 2: execution feedback and test oracles

See [recorded agent guidance](ROUND2_GUIDANCE.md), which cites the actual round 1
coverage paths. Codex added 15 methods for provider exceptions, evidence and
history invariants, stale analysis, rollback, fallbacks and web asset delivery.
The pre-fix run reached full Python line/branch coverage but passed only 59/60.
The failing evidence test observed `(200, 1)` for HTTP status and stored analyses,
instead of `(502, 0)`. This was classified as an app bug based on the existing
requirement for evidence IDs per factual paragraph. No tests were weakened.

Codex archived and hash-verified the original `app/llm.py`, then moved the
missing-evidence check into the per-paragraph validation loop. The final run
passed 60/60 with 414/414 statements and 112/112 branches exercised. The 24-test
and 45-test suites reproduced their original coverage totals on the corrected
source, and standalone unittest discovery also passed all 60. `pip check` found
no broken requirements. All new tests and the bug fix were made by Codex; no
significant manual student interventions were recorded.

See [bug evidence](BUGS.md) and [the final comparison](FINAL_EVALUATION.md).
