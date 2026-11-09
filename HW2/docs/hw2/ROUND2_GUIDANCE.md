# Round 2 guidance - execution feedback and assertion review

Observed round 1 result: 45 tests passed. coverage.py reports 21 missing lines
and 9 partially covered branches across app; combined coverage is 93.92%.
Uncovered lines include llm.py 90-101, 104, 108, 125, 129;
main.py 59, 144, 215; papers.py 143-144. Partial paths also include repeated
evidence IDs, metadata fallback without title candidates, and exhausted authors.

Agent-generated working guidance, based on that actual feedback:

> Exercise the untested provider-error and invalid-answer paths through the API,
> asserting actionable errors and no new persisted analysis. Use real SDK
> exception instances and fixture outputs; do not call the provider. Strengthen
> the one-paragraph summary assertion with multiple paragraphs, repeated IDs,
> sorted physical-page citations, copied text and removal of model-written page
> numbers. Probe whether an unsupported factual paragraph can slip through when
> a different paragraph has evidence: instructions already require supporting
> IDs for each factual paragraph. Also test changed/deleted papers during
> analysis, transaction rollback, page/static serving and metadata fallbacks.
> Classify failures before correcting anything. Preserve the complete pre-fix
> result if a real application defect is found; never relax the regression test.

This is a second guidance strategy: execution/coverage feedback and stronger
oracles, following round 1's explicit requirements context. No extra user prompt
or separate agent conversation is being claimed.
