# Development log

Record actual events, not invented reflection. Add your own reactions and screenshots as you work.

## 2026-09-30 - Milestone 1

### Request and assignment review

- User requested an incremental build starting from an empty Windows folder, with environment setup and a minimal running app first.
- Read all four pages of `hw1 (1).pdf`. Requirements include external search, a persistent library, PDF metadata extraction, and LLM summaries/Q&A based on paper content. Submission includes source/setup instructions, a demo, and reflection with screenshots.
- PDF extraction emitted malformed-object-offset warnings but returned text for all four pages. No PDF edits were made.

### Environment and choices

- Folder was empty. Python launcher reported Microsoft Store Python 3.13. Node 20.11.0 and npm 10.2.4 were available. Git was absent from PATH; a Codex-bundled Git executable was available.
- Selected plain HTML/CSS/JavaScript, FastAPI, and SQLite for this milestone. Serving everything from FastAPI keeps setup to one process and avoids a frontend build step. Stack can evolve later.
- Created project-local `.venv`; installed FastAPI 0.142.2 and Uvicorn 0.54.0, recorded as direct pinned dependencies. SQLite ships with Python.
- Added a manual paper form to verify the full browser/API/database path before external search and LLM integration. The UI explicitly labels the unfinished features.

### Failures and corrections

- Creating the virtual environment failed with access denied to Microsoft Store Python in the sandbox. The agent then attempted pip before confirming the environment existed, causing a second avoidable failure. Correction: rerun environment creation with execution approval, verify success, then install dependencies.
- The sandbox also blocked the virtual environment Python during pip installation. Retrying with approved execution succeeded.
- A Node syntax check failed with EPERM while resolving the user directory. The approved retry completed successfully.
- Git initialization worked in the sandbox, but branch rename could not write `.git/HEAD.lock`. An approved retry encountered Git's ownership check because `.git` belonged to the sandbox account. Correction: use a command-scoped trust exception for this exact project to set HEAD to main; no global trust setting was changed.

### Implementation and verification

- Added a responsive browser form, empty library state, save confirmation, error feedback, FastAPI API, SQLite initialization, setup instructions, and ignore rules for credentials/local artifacts.
- Started Uvicorn at 127.0.0.1:8000; startup and SQLite initialization succeeded.
- Used the browser to create `Milestone 1 verification paper` with explicitly fictional sample content. API returned 201 and health reported one saved paper.
- Sending a whitespace-only title returned HTTP 422 as expected.
- JavaScript syntax check passed after the sandbox retry.
- Verified `.env`, `.venv/Scripts/python.exe`, and `data/research.db` are ignored by Git.
- Stopped the server and started a new process to check disk persistence. Reloaded the browser: it displayed the same sample paper and a connected database. Saved `docs/milestone-1.png` as evidence of the working app; this screenshot does not replace the required conversation screenshots.
- No credentials were needed, entered, committed, or pushed. No GitHub repository has been published.

### Reflection prompts for the student

- Did the small first milestone make the architecture easier to understand?
- What did you notice about the agent's failed dependent pip command and its recovery?
- How useful were permission/error messages compared with a working browser demonstration?
- Capture relevant conversation screenshots yourself, including any follow-up directions you give. These notes do not substitute for your personal reflection.

## 2026-09-30 - Search, PDF processing, and AI workflows

### User direction and decisions

- User asked to build the remaining features and selected OpenAI API. Created a local, ignored `.env` and a tracked blank `.env.example`. The user configured the key locally; the app's health flag confirmed presence without exposing the key.
- Kept the original one-server stack. Added arXiv keyword search, duplicate-aware saves, direct arXiv PDF retrieval, local PDF upload, metadata correction, a page-text inspector, summaries, Q&A, and persistent response history.
- Consulted official arXiv and OpenAI documentation. Selected configurable `gpt-4.1-mini` with the Responses API and Pydantic structured outputs.
- Stored PDF bytes and page text in SQLite. Additive schema changes preserve existing milestone 1 data. Replacing a PDF invalidates prior analyses.
- Chose all extracted pages as LLM context for bounded papers (20 MB, 80 pages, 250,000 characters), rather than pretending an abstract is full content. No silent content truncation. No OCR or image interpretation.
- AI prompts instruct the model to use only the paper, cite physical PDF pages, and acknowledge missing evidence. The backend verifies quoted text and page existence, but that does not prove every scientific inference is correct. PDF/user text is treated as untrusted content in the prompt.

### Actual failures and corrections

- Sandbox networking blocked the initial public arXiv probe. Approved execution succeeded with HTTP 200.
- The first large patch attempted both deletion and addition of the same file in one operation and was rejected without applying changes. Split new-module additions from replacing the entry point.
- A focused test passed its assertions but failed Windows cleanup because its setup SQLite connection remained open. Explicitly closed that connection; all subsequent runs passed.
- The old browser tab timed out. Used the documented browser recovery path to open a fresh tab in the same browser.
- A full-sentence search returned no results when common filler words were ANDed with research terms. Removed common filler words from the search query and retained the AND behavior for meaningful keywords.
- Real PDF upload initially misidentified a permission notice as the title and its next line as the author list in `Attention Is All You Need`. The year heuristic also picked a dataset year. Fixed title detection using font size, collected author lines while excluding affiliations, restricted the local date search to the header, and added arXiv identifier matching for metadata. Corrected the already-created test record through the metadata API. Verified the full upload route again in a temporary database: correct title, eight authors, 2017, abstract, and 15 pages.
- Printing mathematical characters from the PDF hit Windows cp1252 encoding. Reran that inspection with UTF-8 output.
- Real OpenAI summary and question requests both returned HTTP 429. Displayed a rate/quota message instead of fake responses; no AI output was saved. Added specific handling for `insufficient_quota` when the provider supplies that code. User was asked to check API billing, credits, and project limits. Live AI success remains unverified pending account access.

### Verified results

- Live arXiv search for `transformer` returned ten results in the browser. Saved `PyramidTNT: Improved Transformer-in-Transformer Baselines with Pyramid Architecture` through the UI.
- Fetched its PDF through the UI; stored six pages and 24,945 extracted characters. AI controls became available only after the full text was present.
- Uploaded the public `Attention Is All You Need` PDF through the browser; used its actual metadata failure to improve extraction as described above.
- Ten automated checks pass: metadata/page extraction and duplicate upload; invalid/blank/oversized PDFs; full-text/key requirements; search saves and metadata edits; all-page AI input with persistent history; rejection of invented quotations; honest insufficient-evidence output; preservation of old database records; typography/arXiv metadata enrichment; invalidation of stale history after PDF replacement.
- AI success-path tests use controlled mock responses and a temporary database. They are not proof of successful live OpenAI output, nor is test data presented as a real model answer.
- JavaScript syntax and pip dependency compatibility checks pass. No credentials were displayed, committed, or published. `.env`, local database, and downloaded test PDF remain ignored by Git.
- Updated the README and created a demo checklist. The demo video, GitHub publication, and personal reflection remain submission tasks.

### Reflection evidence to capture

- The permission-notice metadata error, the diagnosis based on font/text order, and the corrected extraction are a concrete example of agent-generated code needing real-world verification.
- The OpenAI HTTP 429 shows the difference between writing integration code and verifying service/account access.
- Compare small controlled tests with the public PDF that exposed a layout assumption. Add your own observations and screenshots of the conversation; do not present these notes as your personal reaction.

### Funded-account verification and grounding correction

- User reported adding funds and asked to continue. The next real request passed the earlier quota barrier but failed our exact-quotation check.
- Inspected a real response using only public-paper data. The model had normalized line-break hyphens, corrected a typo, and combined/paraphrased passages with ellipses while presenting them as quotations. Rejecting those responses was appropriate; asking for exact model-generated quotes was too brittle for this PDF.
- First switched to numbered passage IDs. A further live response exposed brittle model-written page citation formatting. Final design uses structured paragraphs with passage IDs; the backend copies source passages and derives page citations itself. It rejects unknown IDs and substantive responses without evidence. All extracted characters still go into the request.
- Live summary of PyramidTNT succeeded with `gpt-4.1-mini` and was saved. Live browser Q&A about datasets and baselines succeeded and was saved. Checked representative figures against extracted Tables 4 and 5: RetinaNet AP 42.0 versus Swin-T 41.5; Mask R-CNN 3x bounding-box AP 47.1 and mask AP 42.2. Claims still require human review; source IDs are not a semantic proof.
- A question about the exact dollar training cost returned an insufficient-evidence flag with no paragraphs. Initially that was shown as an incomplete-response error. Added a readable fallback only for an explicit model insufficient-evidence result: `The paper does not provide enough evidence to answer this question.` The live retry succeeded and was saved.
- Restarted the server after saving the summary and first answer. Both remained in SQLite; the third saved response acknowledges missing evidence. The previous quota blocker is resolved.
- Final regression suite has 11 checks, including the empty insufficient-evidence case. Screenshot and final verification are recorded in the final update below.
- Final checks: all 11 tests pass; pip reports no broken requirements; JavaScript syntax passes. The running database has the six-page PyramidTNT PDF and three genuine saved AI responses (summary, factual Q&A, and insufficient-evidence Q&A). Saved a browser screenshot in `docs/research-assistant-working.png`.
- The browser retained cached frontend assets during final polish. Versioned the static asset URLs so the updated layout and empty-evidence display load reliably.
