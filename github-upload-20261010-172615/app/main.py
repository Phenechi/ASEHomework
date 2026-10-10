"""Local research workspace: search, PDFs, library, summaries and Q&A."""
from contextlib import asynccontextmanager
import hashlib
import json
import sqlite3

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from app import database, llm, papers

load_dotenv(database.ROOT / '.env')


@asynccontextmanager
async def lifespan(app):
    database.initialize()
    yield


app = FastAPI(title='AI Research Assistant', lifespan=lifespan)
app.mount('/static', StaticFiles(directory=database.ROOT / 'app' / 'static'), name='static')
FIELDS = 'id, title, authors, year, abstract, created_at, source_id, url, extraction_note, pdf_hash IS NOT NULL AS has_pdf'


class PaperInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    title: str = Field(min_length=1, max_length=500)
    authors: str = Field(default='', max_length=2000)
    year: int | None = Field(default=None, ge=1000, le=2100)
    abstract: str = Field(default='', max_length=20000)


class SearchSave(BaseModel):
    source_id: str = Field(pattern='^' + papers.ARXIV_ID + '$', max_length=80)


class Question(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(min_length=3, max_length=2000)


def get_paper(paper_id):
    with database.connect() as db:
        row = db.execute(f'SELECT {FIELDS}, pages_json FROM papers WHERE id=?', (paper_id,)).fetchone()
    if row is None:
        raise HTTPException(404, 'Paper not found.')
    result = dict(row)
    result['pages'] = json.loads(result.pop('pages_json'))
    return result


@app.get('/', include_in_schema=False)
def homepage():
    return FileResponse(database.ROOT / 'app' / 'static' / 'index.html')


@app.get('/api/health')
def health():
    with database.connect() as db:
        count = db.execute('SELECT COUNT(*) FROM papers').fetchone()[0]
    return {'status': 'ok', 'database': 'connected', 'paper_count': count,
            'llm_configured': llm.configured(), 'model': llm.model_name()}


@app.get('/api/search')
def search(q: str = Query(min_length=2, max_length=200)):
    return papers.search_arxiv(q)


@app.get('/api/papers')
def list_papers():
    with database.connect() as db:
        return [dict(row) for row in db.execute(f'SELECT {FIELDS} FROM papers ORDER BY id DESC')]


@app.post('/api/papers', status_code=201)
def save_paper(paper: PaperInput):
    with database.connect() as db:
        cursor = db.execute('INSERT INTO papers(title, authors, year, abstract) VALUES(?,?,?,?)',
                            (paper.title, paper.authors, paper.year, paper.abstract))
        paper_id = cursor.lastrowid
    return get_paper(paper_id)


@app.post('/api/papers/from-search')
def save_search(selection: SearchSave):
    with database.connect() as db:
        row = db.execute('SELECT id FROM papers WHERE source_id=?', (selection.source_id,)).fetchone()
    if row:
        return get_paper(row['id'])
    results = papers.arxiv_feed({'id_list': selection.source_id})
    if not results:
        raise HTTPException(404, 'This arXiv paper was not found.')
    item = results[0]
    with database.connect() as db:
        db.execute('''INSERT OR IGNORE INTO papers(title,authors,year,abstract,source_id,url)
                      VALUES(?,?,?,?,?,?)''', tuple(item[k] for k in ('title','authors','year','abstract','source_id','url')))
        paper_id = db.execute('SELECT id FROM papers WHERE source_id=?', (item['source_id'],)).fetchone()['id']
    return get_paper(paper_id)


def store_pdf(data, paper_id=None):
    digest = hashlib.sha256(data).hexdigest()
    with database.connect() as db:
        duplicate = db.execute('SELECT id FROM papers WHERE pdf_hash=?', (digest,)).fetchone()
    if duplicate:
        if paper_id is not None and paper_id != duplicate['id']:
            raise HTTPException(409, f'This PDF is already attached to library paper #{duplicate["id"]}. Open that paper instead.')
        return get_paper(duplicate['id'])
    extracted = papers.extract_pdf(data)
    source_id = None
    url = ''
    if paper_id is None and extracted['arxiv_id']:
        source_id = extracted['arxiv_id']
        url = f'https://arxiv.org/abs/{source_id}'
        with database.connect() as db:
            existing = db.execute('SELECT id FROM papers WHERE source_id=?', (source_id,)).fetchone()
        if existing:
            paper_id = existing['id']
        try:
            matches = papers.arxiv_feed({'id_list': source_id})
            if matches:
                extracted.update({key: matches[0][key] for key in ('title', 'authors', 'year', 'abstract')})
                extracted['extraction_note'] = 'Metadata matched using the arXiv identifier printed in the PDF. Year is the initial arXiv submission year. Review it against the paper. ' + extracted['extraction_note']
        except HTTPException:
            extracted['extraction_note'] += ' arXiv metadata lookup was unavailable; local estimates were retained.'
    try:
        with database.connect() as db:
            if paper_id is None:
                cursor = db.execute('INSERT INTO papers(title,authors,year,abstract,source_id,url) VALUES(?,?,?,?,?,?)',
                                    tuple(extracted[k] for k in ('title','authors','year','abstract')) + (source_id, url))
                paper_id = cursor.lastrowid
            cursor = db.execute('UPDATE papers SET pages_json=?, pdf_data=?, pdf_hash=?, extraction_note=? WHERE id=?',
                                (json.dumps(extracted['pages']), data, digest, extracted['extraction_note'], paper_id))
            if not cursor.rowcount:
                raise HTTPException(404, 'Paper not found.')
            db.execute('DELETE FROM analyses WHERE paper_id=?', (paper_id,))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409, 'This PDF was already saved. Refresh the library.') from exc
    return get_paper(paper_id)


async def read_upload(file):
    try:
        data = await file.read(papers.MAX_BYTES + 1)
    finally:
        await file.close()
    if len(data) > papers.MAX_BYTES:
        raise HTTPException(413, 'Please upload a PDF smaller than 20 MB.')
    return data


@app.post('/api/papers/upload')
async def upload(file: UploadFile = File(...)):
    return await run_in_threadpool(store_pdf, await read_upload(file))


@app.get('/api/papers/{paper_id}')
def detail(paper_id: int):
    result = get_paper(paper_id)
    with database.connect() as db:
        rows = db.execute('SELECT * FROM analyses WHERE paper_id=? ORDER BY id DESC', (paper_id,)).fetchall()
    result['analyses'] = [{**dict(row), 'result': json.loads(row['result_json'])} for row in rows]
    for analysis in result['analyses']:
        analysis.pop('result_json')
    return result


@app.put('/api/papers/{paper_id}')
def edit_metadata(paper_id: int, paper: PaperInput):
    get_paper(paper_id)
    with database.connect() as db:
        db.execute('UPDATE papers SET title=?,authors=?,year=?,abstract=? WHERE id=?',
                   (paper.title, paper.authors, paper.year, paper.abstract, paper_id))
    return get_paper(paper_id)


@app.post('/api/papers/{paper_id}/upload')
async def attach_pdf(paper_id: int, file: UploadFile = File(...)):
    get_paper(paper_id)
    return await run_in_threadpool(store_pdf, await read_upload(file), paper_id)


@app.post('/api/papers/{paper_id}/fetch-pdf')
def fetch_pdf(paper_id: int):
    paper = get_paper(paper_id)
    if paper['has_pdf']:
        return paper
    if not paper['source_id']:
        raise HTTPException(409, 'Upload a PDF for this manually added paper.')
    return store_pdf(papers.download_arxiv(paper['source_id']), paper_id)


@app.get('/api/papers/{paper_id}/pdf')
def view_pdf(paper_id: int):
    with database.connect() as db:
        row = db.execute('SELECT pdf_data FROM papers WHERE id=?', (paper_id,)).fetchone()
    if not row or not row['pdf_data']:
        raise HTTPException(404, 'No PDF is attached to this paper.')
    return Response(row['pdf_data'], media_type='application/pdf',
                    headers={'Content-Disposition': f'inline; filename="paper-{paper_id}.pdf"'})


def run_analysis(paper_id, question=None):
    paper = get_paper(paper_id)
    result = llm.analyze(paper['pages'], question)
    with database.connect() as db:
        current = db.execute('SELECT pages_json FROM papers WHERE id=?', (paper_id,)).fetchone()
        if not current or json.loads(current['pages_json']) != paper['pages']:
            raise HTTPException(409, 'The PDF changed during analysis. Please try again.')
        cursor = db.execute('INSERT INTO analyses(paper_id,kind,question,result_json,model) VALUES(?,?,?,?,?)',
                            (paper_id, 'question' if question else 'summary', question or '', json.dumps(result), llm.model_name()))
        analysis_id = cursor.lastrowid
    return {'id': analysis_id, 'result': result, 'model': llm.model_name()}


@app.post('/api/papers/{paper_id}/summary')
def summarize(paper_id: int):
    return run_analysis(paper_id)


@app.post('/api/papers/{paper_id}/questions')
def ask(paper_id: int, body: Question):
    return run_analysis(paper_id, body.question)
