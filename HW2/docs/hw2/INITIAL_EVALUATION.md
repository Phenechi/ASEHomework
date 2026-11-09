# Initial HW2 evaluation

This is the historical evaluation recorded before improvements. See
[the final evaluation](FINAL_EVALUATION.md) for both completed rounds and the
initial-to-final comparison.

## Executed measurements

| Measure | HW1 baseline | HW2 initial suite |
|---|---:|---:|
| unittest test methods executed | 11 | 24 (11 retained + 13 new) |
| Failures / errors / skipped | 0 / 0 / 0 | 0 / 0 / 0 |
| Test execution time, from unittest output | 0.521 s | 1.035 s |
| Python lines | 329 / 414 (79.47%) | 345 / 414 (83.33%) |
| Python branches | 69 / 112 (61.61%) | 78 / 112 (69.64%) |
| coverage.py combined line/branch metric | 75.67% | 80.42% |
| Naturally discovered application bugs | None detected | None detected |

These are baseline-to-initial results, **not** the assignment's required
initial-to-final comparison. Parameterized subtests are included within the
test-method counts. Timings are single-run observations, not performance claims.

Evidence:

- `evidence/baseline/01-execution.txt` and `evidence/initial/01-execution.txt`: full test identifiers and outcomes.
- Each stage's `test-results.json`: counts and failure/error/skip details.
- Each stage's `coverage.json` and `02-execution.txt`: line/branch data and missing paths.
- Each stage's `manifest.json`: Python version, exact commands and SHA-256 hashes.
- Local interactive coverage: each stage's `html/index.html` (ignored by Git).

The application hashes match between these two stages. No application fixes
were made during initial generation. `pip check` reported no broken requirements.
The later round 2 fix is recorded separately in [the bug record](BUGS.md).

## Correctness review

The README is the behavioral source for search, persistent metadata and PDFs,
duplicate handling, grounding, and history. Source inspection helps locate the
interface; it does not justify changing requirements to fit the implementation.

The 13 new methods exercise health/empty state; metadata creation and ordering;
invalid metadata; missing-record routes; search normalization; invalid queries
and a mocked upstream failure; absent search result; metadata edits preserving
PDF data; duplicate attachments; fetch prerequisites/reuse; question validation;
grounded summary persistence; and lossless passage splitting.

Strong assertions check exact literal metadata, ID ordering, unchanged library
state after invalid writes, identical PDF bytes/pages after metadata edits,
duplicate conflict ownership, exact copied evidence and derived page citation,
history kind/model/result, and reconstruction of all input characters. Temporary
SQLite files exercise real persistence code; locally generated PDFs exercise the
real parser. The summary and search expectations come from controlled fixture
data. Mocked responses do not establish that a live model understands a paper.

No incorrect tests were identified in this review. Some concerns remain:

- Several validation subtests assert HTTP 422 without examining the individual
  Pydantic error details. The library/history side-effect assertions provide
  additional value; asserting entire framework error payloads would be brittle.
- Search failure testing injects an HTTPException at `arxiv_feed`; it verifies
  route propagation, not actual XML/network exception translation.
- The summary fixture covers one paragraph and one evidence passage. It leaves
  multiple-paragraph evidence handling and insufficient-evidence semantics open.
- Several missing-record cases share status/message-type assertions. They cover
  distinct routes but provide less depth than content and side-effect tests.
- Existing HW1 and new HW2 tests overlap on PDF output and metadata. Retained
  coverage is intentional: new checks add byte preservation and conflict behavior.
- Literal `<script>` text round-tripping through JSON is **not** a browser XSS test.

## Coverage gaps and next guidance

| Module | Initial combined coverage | Main missing behavior |
|---|---:|---|
| `app/database.py` | 100.00% | Covered execution does not prove every migration/storage invariant. |
| `app/main.py` | 93.07% | Homepage, unavailable metadata enrichment, race/constraint handling, successful fetch, changed-PDF analysis guard. |
| `app/llm.py` | 80.00% | Authentication/quota/network/provider/parse failures, incomplete or empty answers, missing supporting passages. |
| `app/papers.py` | 63.13% | Atom parsing/cache/throttle, actual streamed-download behavior, encryption/page/text bounds and metadata fallbacks. |

Coverage includes every Python file under `app`, including zero-statement
`__init__.py`. It excludes browser JavaScript/CSS/HTML, third-party library
internals, and the test code. A 100% module figure does not prove correctness.

Round 1 should use explicit requirements to test arXiv service contracts and PDF
limits with realistic fixtures/fake clocks. Round 2 should consume its coverage
report and failures, add provider-error and evidence-boundary tests, strengthen
weak assertions and preserve any confirmed bug reproduction before fixes.
These were the planned strategies at the time of initial evaluation. Both are
documented in the final evaluation.

## Fault detection and limitations

No application bugs were detected by this initial suite. No mutation experiment
was run, so its sensitivity to deliberately injected faults was not measured.
The suite detects invalid evidence and stale-history behavior through the
retained HW1 regressions, but these previously implemented protections must not
be presented as newly discovered HW2 bugs.

An unrestricted preliminary run and both measured stages confirm the old suite
runs. Earlier sandbox stalls occurred in Windows event-loop socketpair startup,
before assertions. They are environment failures, not application faults.
There were no failing newly generated tests to correct in this initial run.

The evaluation runner blocks unmocked arXiv and OpenAI entry points and empties
the API-key environment variable before importing the app. No live paid model
requests or production database changes were made. New tests were produced by
Codex without manual student corrections during this kickoff.
