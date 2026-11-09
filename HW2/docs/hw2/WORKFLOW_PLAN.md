# HW2 workflow and evidence plan

Assignment read: all four pages of the user's `hw2.pdf`. Due November 8, 2026,
11:59 PM (assignment gives no timezone). Weight: 10% of course grade.
This document plans the work; unchecked items are not claims of completion.

Current status: stages 0-3 and the local reproducibility checks are complete.
See [the final evaluation](FINAL_EVALUATION.md) for both rounds and the 60-test
suite. PDF report and GitHub work remain outside the user's current request.

## Experiment design

Use Codex as the coding agent and Python unittest with coverage.py. The app is
FastAPI/SQLite with a plain JavaScript frontend. Keep the original 11 HW1 tests
in `tests/test_workflows.py` as a separately measured baseline. The HW2 initial
suite consists of those tests plus `tests/hw2/test_initial.py`. Do not label the
old suite as newly generated work. Keep production code fixed during the first
comparison; document any later bug fixes separately from test improvements.

Use the README's intended behavior as the oracle, then inspect source to locate
test seams. A test passing is not evidence that its expected behavior is correct.
Each round must assess coverage, correctness, and fault detection independently.

## Milestones

| Stage | Work and agent guidance strategy | Required evidence / exit condition |
|---|---|---|
| 0. Preserve HW1 baseline | Inventory routes/modules, run old tests with temporary DB and mocked services; identify repository state. | 11-test baseline results; line and branch coverage; source/test hashes. |
| 1. Initial generation | Codex inspects app and documented requirements, generates normal/error/edge-case tests. | Frozen initial module, run results, coverage JSON/HTML, correctness review and uncovered paths. |
| 2. Improvement round 1 | Requirements-focused guidance: explicitly review extraction limits, search parsing/cache, download bounds, AI error translation, and persistence invariants. | Separate `test_round1.py`, actual guidance and feedback log, rerun results, correctness review. |
| 3. Improvement round 2 | Feedback-focused guidance: provide round 1 missing lines/branches and failures; strengthen assertions and add regressions for confirmed faults. | Separate `test_round2.py`, actual guidance and feedback log, final measurements and before/after comparison. |
| 4. Report and reproducibility | Prepare six-section report using actual evidence; verify installation/run instructions. | Rendered/visually checked PDF; no invented personal reflection or agent interactions. |
| 5. Submission | Review changes and publish final suite to the HW1 GitHub repository. | Verified remote URL and final suite location; student submits PDF. |

## Stage 1 scope

- API integration: temporary SQLite DB, paper validation/list/detail/edit,
  missing records, search/save outcomes, upload/duplicate conflicts, PDF bytes,
  metadata preservation, AI summary/history, question validation.
- Unit behavior: topic normalization and passage splitting without lost text.
- Retained HW1 tests: PDF extraction, migration, full-text AI request, invalid
  evidence rejection, duplicate save, replacement invalidation and restart history.
- Network and paid model calls are mocked. The evaluation runner rejects
  unexpected outgoing arXiv and OpenAI calls. Real DB contents are never used.
- Coverage denominator: **all Python modules under `app/`**. This does not measure
  browser JavaScript or semantic quality of live model answers.

## Requirements / risk matrix for the improvement rounds

| Requirement | Initial evidence | Targeted follow-up |
|---|---|---|
| Topic search and arXiv metadata | API delegation, normalized keywords, mocked errors | Actual Atom parsing, malformed XML/IDs/year, cache expiration and rate spacing with fake clock |
| Library persistence / deduplication | CRUD, literal text, original restart/migration tests | Transaction rollback, source-to-PDF association, metadata/history invariants |
| Bounded PDF extraction | Real generated PDF; original invalid/blank/oversize tests | Encryption, page/text caps, partial blank pages, failed enrichment fallback |
| Bounded arXiv download | Reuse/no-source route tests | Chunk overflow, HTTP error translation, validated URLs |
| Grounded summaries / Q&A | Exact copied source, derived page, persisted history | Multiple paragraphs, empty/missing evidence, invalid response, provider failures, stale analysis race |
| Browser workflow | No browser automation yet | Consider a small isolated UI smoke suite; report coverage scope explicitly |

## Test correctness and fault triage

For each test, map assertions to a documented requirement. Check status and
response values, plus persistence/side effects on writes and failures. Prefer real
SQLite and generated local PDFs; mock external service boundaries. Use fake clocks
for cache tests and never sleep to test throttling.

For each failure record: test identifier, expected requirement, observed behavior,
minimal reproduction, and classification (application bug, invalid test, environment
problem). Never change expected behavior simply to make the suite pass. Preserve
failing evidence before a correction. Deliberately injected faults, if used later,
must be clearly distinguished from naturally discovered bugs.

## Evidence and interaction recording

`scripts/evaluate_tests.py` saves verbose output, structured outcomes, line/branch
coverage JSON, local HTML, exact commands, and hashes. Use a **new directory for
every run**; the runner refuses to overwrite results. Keep initial tests stable
while adding round modules. Extend the runner's stage selection when each round is
actually implemented. Do not predeclare a completed improvement round.

Record actual user prompts verbatim and agent-generated working guidance as such
in `INTERACTION_LOG.md`. Include coverage feedback, changed tests, detected bugs,
and significant manual interventions. The student should retain conversation
screenshots if useful and supply their own reflection before submission.

## Local commands (PowerShell, project root)

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/evaluate_tests.py --stage initial --output tmp/hw2-initial-repeat
.\.venv\Scripts\python.exe scripts/evaluate_tests.py --stage final --output tmp/hw2-final-repeat
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Use [the testing instructions](TESTING.md) for all stage commands and the
pre-fix reproduction. For repeated measurements, use a fresh output name.
Open the generated `html/index.html` for missing paths. `.coverage` data and HTML
are local artifacts; execution text/JSON/manifests are kept as report evidence.
On this Windows machine, sandboxed TestClient startup stalls in asyncio's
loopback socketpair creation. The same tests pass outside the sandbox. Record
this as an environment issue, not an application failure; no app workaround is
needed. Normal local PowerShell execution does not use the Codex sandbox.

## Report structure and remaining submission work

1. Test Generation Approach: agent, actual prompt, test types and scope.
2. Initial Test Evaluation: results, coverage, correctness review, bugs or explicit none found.
3. Iterative Test Improvement: at least two rounds; exact extra context and execution feedback.
4. Final Evaluation: same metrics and denominator, comparison table, effective/ineffective changes.
5. Reflection: student's observations on understanding, strengths, limitations and feedback.
6. GitHub Repository: real URL, suite location, dependency/run/coverage instructions.

At kickoff, `.git` has no commits and no remote. The source is untracked. The HW1
README also states publication is unfinished. Obtain the actual HW1 remote before
publishing. The document's submission instructions are task requirements to plan
for, not an independent request to publish or submit during this kickoff.
