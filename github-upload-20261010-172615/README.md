# AI Research Assistant

A local research workspace built incrementally with Codex: browser HTML/CSS/JavaScript, Python/FastAPI, SQLite, arXiv search, pypdf processing, and the OpenAI Responses API.

## Features

- Search arXiv by research topic. Results show title, authors, initial submission year, abstract, and a source link.
- Save and browse papers in a persistent local library. Repeated saves of the same arXiv version reuse the existing record.
- Upload a PDF as a new paper or attach it to a saved result. Fetch an arXiv PDF directly from the library.
- Extract title, authors, year, abstract, and text by physical PDF page. Review and correct metadata; inspect every extracted page and open the stored PDF.
- Generate a summary from all extracted pages and ask questions about the selected paper. Answers contain page references and supporting quotations. Missing information should be acknowledged.
- Keep generated summaries, questions, answers, and original PDFs in SQLite across restarts. Replacing a PDF clears old analyses to avoid stale answers.

## Windows setup and run

Requires Python 3.13 (used for development), pip, internet for external services, and an OpenAI API key with access to the configured model for AI features. Node is not required to run the app.

Open PowerShell in the project directory:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` **only if `.env` does not already exist**. Enter your API key locally in `.env`:

```dotenv
OPENAI_API_KEY=your-own-key-goes-here
OPENAI_MODEL=gpt-4.1-mini
```

Never paste a real key into source code, chat, a screenshot, or a commit. `.env` is ignored by Git. The backend loads it at startup; restart after changing configuration. Existing environment variables take precedence over `.env`. The browser sees only a configured/not-configured flag, never the key. A configured flag does not prove the key has valid access or quota.

Start the server:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Visit **http://127.0.0.1:8000**. Keep the terminal open. Ctrl+C stops the app; repeat the command to restart. No virtual environment activation is necessary. `start.ps1` is an optional shortcut if your existing PowerShell script policy allows it.

If port 8000 is occupied, stop the earlier server or use `--port 8001` and browse to that port. Codex's sandbox may require execution approval for Python or network access on Windows; do not change Windows security settings as a workaround.

## Try the complete workflow

1. In **Discover**, search `transformer`. Review the real arXiv results and save one.
2. In **My library**, select it and click **Fetch PDF from arXiv**. If the download fails, use the source link to get the PDF and attach it manually.
3. Open **Inspect extracted pages** and verify that the paper's body, methods, and results are present. **Open PDF** shows the original.
4. Click **Generate summary**. Review the result and expand **Check supporting passages**. Page buttons open the corresponding extracted text.
5. Ask `What datasets are used and how does the method compare with its baselines?` Compare the answer with the PDF. Ask a question the paper does not answer and check that the response acknowledges missing information.
6. In **Discover**, upload a different research PDF. Review the automatically estimated title/authors/year/abstract, correct them if needed, and save metadata.
7. Refresh, then stop/restart the app. The papers, PDFs, and saved AI responses should remain.

AI actions send the selected paper's extracted text and question to OpenAI and may incur API charges. PDF upload/extraction and metadata editing happen locally; search queries go to arXiv. We request `store=False` for OpenAI responses. This option is not a promise of zero provider-side retention; consult the provider's data policy.

## How it works

| Component | Responsibility |
|---|---|
| `app/static/` | Browser interface, search results, upload forms, selected-paper reader, AI history |
| `app/main.py` | HTTP routes, validation, orchestration, history storage |
| `app/database.py` | SQLite connections, schema creation, additive migration of milestone 1 data |
| `app/papers.py` | arXiv requests, bounded PDF downloads, text and metadata extraction |
| `app/llm.py` | OpenAI requests, grounding instructions, structured paragraphs, source-ID checks, page citations |
| `data/research.db` | Local papers, PDF bytes, page text, and AI history; excluded from Git |
| `tests/test_workflows.py` | Focused integration checks using a temporary database and mocked AI |

The backend serves the frontend and API from one address. SQLite requires no separate database installation. Metadata saves use parameterized SQL, and the frontend displays external text without interpreting it as HTML.

The LLM receives **all extracted pages**, not just metadata or retrieved snippets. This is a simple approach suitable for bounded research papers. A 250,000-character cap prevents oversized inputs rather than silently truncating the paper. The default model supports a large context and structured output; choosing a different model can require adjusting limits and verifying feature support.

The full text is divided into numbered passages without omitting characters. The model returns paragraphs and supporting passage IDs. The backend rejects nonexistent IDs, copies the exact source text itself, and derives physical PDF page references from those passages. A substantive answer with no supporting passages is rejected. These checks establish that the evidence exists; they do not prove that every claim or interpretation is supported. Inspect the paper when evaluating an answer. Questions are independent requests, not a conversational memory chain.

## Limits and error handling

- This is a local, single-user coursework app. Keep it bound to 127.0.0.1; it has no login or production hosting setup.
- PDF limits: 20 MB, 80 pages, 250,000 extracted characters. Encrypted, broken, and textless PDFs produce readable errors. OCR and image/table interpretation are not implemented. Partially unreadable pages are disclosed in the extraction note.
- Metadata extraction uses PDF properties, title font sizes, and opening-page heuristics. If an arXiv identifier is printed in an uploaded PDF, its identifier is sent to arXiv to retrieve matching metadata. If that lookup fails, local estimates are retained. Titles, affiliation blocks, dates, and multi-column abstracts can still require manual correction. Year may be absent; PDF creation time is not treated as publication time.
- arXiv covers selected research fields, not all scholarly literature. Its displayed year is the first arXiv submission year. Common filler words are removed from topic searches; remaining keywords are combined with AND. Ten results are returned.
- arXiv requests are serialized at least 3.1 seconds apart and cached for ten minutes. Network failures and upstream errors prompt a retry. PDF download URLs are restricted to validated arXiv identifiers.
- Missing/invalid OpenAI keys, quota/rate limits, connection errors, and invalid AI evidence show actionable messages. There are no automatic paid retries.
- Duplicate PDFs are detected by content hash. If already attached to another record, the app tells you which library entry holds the PDF. Manual metadata-only entries may still duplicate each other.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Tests cover extraction, duplicates, invalid/scanned/oversized PDFs, missing full text/key, search-save deduplication, metadata edits, full-text AI input, evidence rejection, insufficient-evidence responses, migration, and history persistence. They use dummy keys and mocked OpenAI responses, not live paid requests. See the development log for actual live verification and any limitations.

Useful URLs: http://127.0.0.1:8000/api/health and http://127.0.0.1:8000/docs.

## Credentials and GitHub

The local Git repository is initialized on `main`. No commits or remote publication have been performed. `.gitignore` excludes `.env`, environments, uploads, database files, and logs. Review changes before committing; ignore rules cannot detect secrets hardcoded into tracked files.

On the original machine, Git was initially absent from PATH, so Codex used its bundled executable. Git for Windows can provide normal terminal commands. Because the sandbox initialized `.git`, an ownership warning may occur outside the sandbox. For this known repository, a command-scoped `-c safe.directory='C:/Users/Matthew/Desktop/ASE HW1'` option allows that invocation without changing global trust settings.

## Submission

The assignment says October 10 at 11:59 PM without a year/timezone; confirm timing in Brightspace. App: 60%; reflection: 40%.

- GitHub repository: complete source, README, dependency/configuration files. Verify setup from a fresh copy before submission.
- Demo: search, save, upload a PDF, generate a summary, ask a question. Use `docs/DEMO_CHECKLIST.md`.
- Reflection: use the actual events in `docs/DEVELOPMENT_LOG.md`, add your own observations, and capture conversation screenshots showing prompts, problems, proposed code/output, and your corrections. Do not fabricate personal experiences.

The assignment discusses deployment but its explicit submission list does not require a public URL. Confirm with the instructor before treating public hosting as required.

## Official references

- [arXiv API manual](https://info.arxiv.org/help/api/user-manual.html)
- [OpenAI text generation](https://developers.openai.com/api/docs/guides/text)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-4.1 mini model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini)
