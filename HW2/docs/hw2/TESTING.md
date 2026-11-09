# Run the HW2 tests and reproduce coverage

Use Python 3.13 from PowerShell in the project root. The pinned development
requirements include the app dependencies and coverage.py. The tests run
without an arXiv connection, OpenAI credentials, Node, or a running web server.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Expect 60 passing tests. The intentionally broken PDF fixture may emit `EOF
marker not found`. Temporary SQLite files are used for all API tests. The
documented discovery command and `pip check` both passed in the project venv.

## Coverage

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_tests.py --stage final --output tmp/hw2-final-repeat
```

Choose a **new** output directory for each run. The evaluator records verbose
execution, structured outcomes, coverage JSON, a coverage table, local HTML
and source/test hashes. It overrides the OpenAI key and blocks unexpected
external service calls. Open the output's `html/index.html` to inspect coverage.
The app scope is Python under `app/`; browser JavaScript is not instrumented.

To compare earlier suites with the final suite on the current app source:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_tests.py --stage initial --output tmp/hw2-initial-same-source
.\.venv\Scripts\python.exe scripts/evaluate_tests.py --stage round1 --output tmp/hw2-round1-same-source
```

`baseline` selects only the original HW1 suite. `initial` selects HW1 plus
`test_initial.py`. `round1` adds `test_round1.py`, and `round2`/`final` both add
`test_round2.py`. Stages select tests; the application revision is determined by
the files in the project being run. The archived historical stages and the
same-source replays are in `evidence/`.

## Reproduce the pre-fix result in a separate copy

1. Make a separate local copy containing `app`, `tests`, `scripts`, `.coveragerc`,
   `requirements.txt` and `requirements-dev.txt`. No user data or `.env` is needed.
2. Replace **only in that copy** `app/llm.py` with the contents of
   `evidence/round2-before-fix/llm.py.original.txt`.
3. From that copy, create the venv and install the requirements as above. Run
   `scripts/evaluate_tests.py --stage round2 --output tmp/hw2-pre-fix-replay`.
   Expect an intentional nonzero exit from one regression failure: HTTP 200 and
   a saved analysis where HTTP 502 and no write were expected.

The current app has the fix. Full failure details and the original source hash
are in [the bug record](BUGS.md). On the development Windows host, Codex's
restricted sandbox stalled during asyncio's loopback socket setup; the standard
commands ran successfully outside that sandbox.
