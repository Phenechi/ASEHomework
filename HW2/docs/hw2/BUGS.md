# Confirmed bug and regression evidence

## HW2-01: one cited paragraph allowed another unsupported factual paragraph

Discovered in improvement round 2 by
`tests.hw2.test_round2.AIContracts.test_each_substantive_paragraph_requires_evidence`.

Expected behavior: the model's grounding instructions require evidence IDs for
each factual paragraph. An ordinary substantive response (`insufficient_evidence`
false) must not persist a paragraph without any supporting passage IDs. Existing
explicit missing-information responses remain allowed without evidence.

Reproduction: upload the local two-page fixture; mock a completed model response
with two paragraphs. Give the first `P1-B1` and give the second, "The method
achieved 99.9 percent on an invented dataset.", no IDs. Post to the summary API.
No live model request is required to reproduce the application validation defect.

Observed before fix: HTTP 200 and one saved analysis. The unsupported second
paragraph appeared without a page citation. Expected: HTTP 502 and zero analyses.
The failing assertion records both the HTTP result and the persistence effect.

Cause: `app/llm.py` checked whether the whole answer had any evidence after
processing all paragraphs. Evidence attached to one paragraph satisfied that
global check for every other paragraph.

Fix: apply the missing-evidence check inside the paragraph loop, using the
current paragraph's IDs. Keep invalid-ID checks, exact source copying, derived
page citations, and explicit insufficient-evidence acknowledgments intact.
The regression expectation was not relaxed. No requirements were changed.

Evidence: `evidence/round2-before-fix/01-execution.txt`, `test-results.json` and
`manifest.json`. The entire original `app/llm.py` is preserved as
`evidence/round2-before-fix/llm.py.original.txt`; its hash was checked against the
run's manifest before the fix. The pre-fix suite ran 60 tests, with 59 passing
and this one failure, despite reaching 100% Python line and branch coverage.
This directly demonstrates why coverage alone is not a correctness measure.

To reproduce the pre-fix fault, make a separate local copy of the project,
replace that copy's `app/llm.py` with the archived original, then run the round2
stage into a fresh evidence directory. The current working app should retain
the fix. The initial and round1 suites pass on the original source and did not
detect this fault; the new round2 regression does.

The synthetic SQLite trigger in another round2 test is controlled fault injection
for an error-handling path, not a second naturally discovered bug. No broad
mutation score is claimed. Passage-ID validation establishes that supporting
text exists; it still cannot prove that a model's interpretation is correct, or
that an insufficient-evidence flag is semantically honest.
