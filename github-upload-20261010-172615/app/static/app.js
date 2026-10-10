const $ = (selector) => document.querySelector(selector);
let selectedId = null;
let health = null;
let selectionVersion = 0;
let aiBusy = false;
const message = $('#message');

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}
function notify(text, error = false) {
  message.textContent = text;
  message.className = error ? 'error' : 'success';
}
async function request(path, options) {
  let response;
  try { response = await fetch(path, options); }
  catch { throw new Error('Cannot reach the server. Check that it is running.'); }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Check the required fields and try again.');
  return data;
}
function jsonBody(value, method = 'POST') {
  return {method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(value)};
}
async function busy(button, work) {
  const original = button.textContent;
  button.disabled = true; button.textContent = 'Working…';
  try { await work(); }
  catch (error) { notify(error.message, true); }
  finally { button.disabled = false; button.textContent = original; }
}
function showPanel(name) {
  $('#discover').hidden = name !== 'search'; $('#library').hidden = name !== 'library';
  $('#nav-search').classList.toggle('active', name === 'search');
  $('#nav-library').classList.toggle('active', name === 'library');
}
function externalLink(url, label) {
  const link = element('a', label);
  if (/^https:\/\/arxiv\.org\//.test(url) || url.startsWith('/api/papers/')) link.href = url;
  link.target = '_blank'; link.rel = 'noopener noreferrer';
  return link;
}
function fields(form) {
  const data = new FormData(form);
  return {title: data.get('title'), authors: data.get('authors'), year: data.get('year') ? Number(data.get('year')) : null, abstract: data.get('abstract')};
}
async function refreshLibrary() {
  const [items, status] = await Promise.all([request('/api/papers'), request('/api/health')]);
  health = status;
  $('#health').textContent = `Database connected · ${status.llm_configured ? 'OpenAI key configured' : 'OpenAI key needed for AI'}`;
  $('#count').textContent = `${items.length} saved ${items.length === 1 ? 'paper' : 'papers'}`;
  $('#papers').replaceChildren();
  if (!items.length) $('#papers').append(element('p', 'No papers yet. Search or upload your first PDF.', 'muted'));
  for (const paper of items) {
    const card = element('article');
    const button = element('button', paper.title, 'paper-select');
    button.dataset.paperId = String(paper.id);
    button.setAttribute('aria-pressed', String(selectedId === paper.id));
    button.addEventListener('click', () => selectPaper(paper.id).catch(e => notify(e.message, true)));
    card.append(button, element('p', `${paper.authors || 'Unknown authors'} · ${paper.year ?? 'Unknown year'}`, 'muted'), element('span', paper.has_pdf ? 'PDF ready' : 'PDF needed for AI', 'badge'));
    $('#papers').append(card);
  }
  updateAiControls();
}
function updateAiControls() {
  const ready = Boolean(health?.llm_configured && $('#paper-detail').dataset.hasPdf === 'true');
  $('#summarize').disabled = !ready || aiBusy;
  $('#question-form button').disabled = !ready || aiBusy;
  $('#ai-status').textContent = !health?.llm_configured ? 'Set OPENAI_API_KEY in .env and restart the server to enable AI.' : !ready ? 'Attach or fetch the PDF to enable AI.' : `Ready · ${health.model} · Uses all extracted pages.`;
}
async function selectPaper(id) {
  const version = ++selectionVersion;
  const paper = await request(`/api/papers/${id}`);
  if (version !== selectionVersion) return;
  selectedId = id; showPanel('library');
  document.querySelectorAll('.paper-select').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.paperId === String(id))));
  $('#reader-empty').hidden = true; $('#paper-detail').hidden = false;
  $('#paper-detail').dataset.hasPdf = String(Boolean(paper.has_pdf));
  $('#paper-source').textContent = paper.source_id ? `ARXIV · ${paper.source_id}` : `LOCAL LIBRARY · #${paper.id}`;
  $('#paper-title').textContent = paper.title;
  $('#paper-meta').textContent = `${paper.authors || 'Authors not provided'} · ${paper.year ?? 'Year not provided'}`;
  $('#paper-abstract').textContent = paper.abstract || 'No abstract extracted. You can add one under metadata.';
  $('#paper-links').replaceChildren();
  if (paper.url) $('#paper-links').append(externalLink(paper.url, 'View on arXiv ↗'));
  if (paper.has_pdf) $('#paper-links').append(externalLink(`/api/papers/${id}/pdf`, 'Open PDF ↗'));
  if (paper.source_id && !paper.has_pdf) {
    const fetchButton = element('button', 'Fetch PDF from arXiv', 'secondary');
    fetchButton.addEventListener('click', () => busy(fetchButton, async () => {
      await request(`/api/papers/${id}/fetch-pdf`, {method:'POST'});
      await refreshLibrary(); if (selectedId === id) await selectPaper(id);
      notify('PDF downloaded and page text extracted.');
    }));
    $('#paper-links').append(fetchButton);
  }
  $('#content-status').textContent = paper.has_pdf ? `${paper.pages.length} PDF pages stored. Inspect the extracted text before relying on AI.` : 'Metadata only. Attach the matching PDF or fetch it from arXiv to enable summaries and Q&A.';
  $('#extraction-note').textContent = paper.extraction_note || 'Review these details against the paper.';
  for (const key of ['title', 'authors', 'year', 'abstract']) $(`#edit-${key}`).value = paper[key] ?? '';
  $('#attach-form').reset();
  $('#page-text').replaceChildren();
  for (const page of paper.pages) {
    const section = element('details'); section.id = `page-${page.page}`;
    section.append(element('summary', `PDF page ${page.page}`), element('pre', page.text || '(No text extracted from this page.)'));
    $('#page-text').append(section);
  }
  $('#analysis-history').replaceChildren();
  if (!paper.analyses.length) $('#analysis-history').append(element('p', 'Your generated summaries and answers will be saved here.', 'muted'));
  for (const analysis of paper.analyses) {
    const card = element('article', undefined, 'analysis');
    card.append(element('h4', analysis.kind === 'summary' ? 'Paper summary' : analysis.question), element('p', `${analysis.model} · ${analysis.created_at} UTC`, 'muted'));
    if (analysis.result.insufficient_evidence) card.append(element('p', 'The paper does not provide enough evidence for a complete answer.', 'notice'));
    card.append(element('p', analysis.result.answer, 'answer'));
    const evidence = element('details'); evidence.append(element('summary', 'Check supporting passages'));
    for (const item of analysis.result.evidence) {
      const passage = element('blockquote', item.quote);
      const button = element('button', `View PDF page ${item.page}`, 'secondary');
      button.addEventListener('click', () => {
        $('#text-details').open = true;
        const target = $(`#page-${item.page}`);
        if (target) { target.open = true; target.scrollIntoView({behavior:'smooth', block:'center'}); }
      });
      evidence.append(passage, button);
    }
    if (analysis.result.evidence.length) card.append(evidence);
    $('#analysis-history').append(card);
  }
  updateAiControls();
}
$('#nav-search').addEventListener('click', () => showPanel('search'));
$('#nav-library').addEventListener('click', () => showPanel('library'));
$('#refresh').addEventListener('click', () => busy($('#refresh'), async () => { await refreshLibrary(); if (selectedId) await selectPaper(selectedId); }));
$('#search-form').addEventListener('submit', event => {
  event.preventDefault();
  busy(event.submitter, async () => {
    $('#search-status').textContent = 'Searching arXiv…'; $('#results').replaceChildren();
    let results;
    try { results = await request(`/api/search?q=${encodeURIComponent($('#query').value.trim())}`); }
    catch (error) { $('#search-status').textContent = 'Search could not finish. Please try again.'; throw error; }
    $('#search-status').textContent = results.length ? `${results.length} results · Year is the first arXiv submission year.` : 'No results. Try fewer or different keywords.';
    for (const paper of results) {
      const card = element('article');
      card.append(element('h3', paper.title), element('p', `${paper.authors} · ${paper.year}`, 'muted'), element('p', paper.abstract));
      const actions = element('div', undefined, 'actions');
      const save = element('button', 'Save to library', 'secondary');
      save.addEventListener('click', () => busy(save, async () => {
        const stored = await request('/api/papers/from-search', jsonBody({source_id:paper.source_id}));
        await refreshLibrary(); await selectPaper(stored.id); notify('Paper saved. Fetch or attach its PDF to use AI.');
      }));
      actions.append(externalLink(paper.url, 'View paper ↗'), save); card.append(actions); $('#results').append(card);
    }
  });
});
for (const [formId, inputId, isAttachment] of [['#upload-form','#upload-file',false], ['#attach-form','#attach-file',true]]) {
  $(formId).addEventListener('submit', event => {
    event.preventDefault();
    const id = selectedId;
    busy(event.submitter, async () => {
      const file = $(inputId).files[0];
      if (!file || file.size > 20 * 1024 * 1024) throw new Error('Choose a PDF up to 20 MB.');
      const body = new FormData(); body.append('file', file);
      const paper = await request(isAttachment ? `/api/papers/${id}/upload` : '/api/papers/upload', {method:'POST', body});
      $(formId).reset(); await refreshLibrary();
      if (!isAttachment || selectedId === id) await selectPaper(paper.id);
      notify('PDF saved. Review the extracted metadata and page text.');
    });
  });
}
$('#paper-form').addEventListener('submit', event => {
  event.preventDefault(); busy(event.submitter, async () => {
    const paper = await request('/api/papers', jsonBody(fields(event.target)));
    event.target.reset(); await refreshLibrary(); await selectPaper(paper.id); notify('Paper saved.');
  });
});
$('#edit-form').addEventListener('submit', event => {
  event.preventDefault(); const id = selectedId;
  busy(event.submitter, async () => {
    await request(`/api/papers/${id}`, jsonBody(fields(event.target), 'PUT'));
    await refreshLibrary(); if (selectedId === id) await selectPaper(id); notify('Metadata updated.');
  });
});
async function analyze(question) {
  const id = selectedId;
  aiBusy = true; updateAiControls();
  $('#ai-progress').textContent = 'Reading the paper with OpenAI… This may take up to 90 seconds.';
  try {
    await request(`/api/papers/${id}/${question ? 'questions' : 'summary'}`, question ? jsonBody({question}) : {method:'POST'});
    if (selectedId === id) await selectPaper(id);
    notify('AI response saved with supporting passages.');
  } catch (error) { notify(error.message, true); }
  finally { aiBusy = false; $('#ai-progress').textContent = ''; updateAiControls(); }
}
$('#summarize').addEventListener('click', () => analyze());
$('#question-form').addEventListener('submit', event => { event.preventDefault(); analyze($('#question').value.trim()); });
refreshLibrary().catch(error => notify(error.message, true));
