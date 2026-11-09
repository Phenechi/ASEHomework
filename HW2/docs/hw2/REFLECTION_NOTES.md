# Evidence for the student's reflection

These are observations from the recorded work, not a claim about the student's
personal experience. Use them as examples when writing the reflection.

- **Where the agent understood the app well:** The initial suite identified core
  user workflows and verified state as well as responses: metadata edits kept
  PDF bytes, duplicate uploads retained identity, and summary history carried
  exact evidence. It reused a known fixture and isolated SQLite instead of
  depending on a live account.
- **Where the initial suite fell short:** It mocked `arxiv_feed` itself, so a
  passing search test did not exercise Atom parsing, throttling, or error
  translation. A single cited paragraph also missed the failure when one
  paragraph was supported and another was not.
- **What explicit requirements added:** The 80-page and 250,000-character
  boundaries gave independent expected results. Real PDF fixtures tested both
  sides of the limits. A fake clock verified expiry and spacing without waiting.
- **What execution feedback added:** Missing paths led to provider-error and
  rollback tests. Comparing the intended paragraph contract with the behavior of
  a mixed answer found HW2-01. Checking both HTTP status and saved history showed
  that the fault affected persistent user data, not just response formatting.
- **What coverage cannot tell us:** The pre-fix run executed every measured
  Python line and branch but still exposed a real bug. The final 100% result
  says nothing about browser interactions, live service behavior, or whether a
  cited passage semantically proves a model's claim.

See the [interaction log](INTERACTION_LOG.md) for actual instructions and the
[final evaluation](FINAL_EVALUATION.md) for the measured comparison. No student
test edits were made in the recorded rounds; Codex wrote the fixtures, tests,
and small app correction.
