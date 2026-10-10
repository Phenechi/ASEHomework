"""Public arXiv search and local PDF text/metadata extraction."""
from io import BytesIO
import re
import threading
import time
import xml.etree.ElementTree as ET

import httpx
from fastapi import HTTPException
from pypdf import PdfReader

MAX_BYTES = 20 * 1024 * 1024
MAX_PAGES = 80
MAX_TEXT = 250_000
ARXIV_ID = r'(?:\d{4}\.\d{4,5}|[a-zA-Z.-]+/\d{7})(?:v\d+)?'
_lock = threading.Lock()
_last_call = 0.0
_cache = {}
NS = {'a': 'http://www.w3.org/2005/Atom'}


def clean(value):
    return ' '.join(str(value or '').split())


def arxiv_feed(params):
    global _last_call
    key = tuple(sorted(params.items()))
    with _lock:
        now = time.monotonic()
        if key in _cache and now - _cache[key][0] < 600:
            return _cache[key][1]
        time.sleep(max(0, 3.1 - (now - _last_call)))
        _last_call = time.monotonic()
        try:
            response = httpx.get('https://export.arxiv.org/api/query', params=params,
                                 timeout=30, headers={'User-Agent': 'ResearchAssistantHomework/1.0'})
            response.raise_for_status()
            root = ET.fromstring(response.content)
            results = []
            for entry in root.findall('a:entry', NS):
                raw_id = entry.findtext('a:id', '', NS).split('/abs/')[-1]
                if not re.fullmatch(ARXIV_ID, raw_id):
                    raise ValueError('Unexpected arXiv entry')
                results.append({
                    'source_id': raw_id,
                    'title': clean(entry.findtext('a:title', '', NS)),
                    'authors': ', '.join(clean(a.findtext('a:name', '', NS)) for a in entry.findall('a:author', NS)),
                    'year': int(entry.findtext('a:published', '', NS)[:4]),
                    'abstract': clean(entry.findtext('a:summary', '', NS)),
                    'url': f'https://arxiv.org/abs/{raw_id}',
                })
        except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
            raise HTTPException(502, 'arXiv could not complete the search. Wait a moment and try again.') from exc
        if len(_cache) >= 100:
            _cache.clear()
        _cache[key] = (time.monotonic(), results)
        return results


def search_arxiv(query):
    words = re.findall(r'[\w-]+', query, flags=re.UNICODE)
    if not words:
        raise HTTPException(422, 'Enter words for your research topic.')
    stopwords = {'a', 'an', 'the', 'is', 'are', 'was', 'were', 'of', 'for', 'to', 'and', 'in', 'on', 'with', 'all', 'you'}
    words = [word for word in words if word.lower() not in stopwords] or words
    return arxiv_feed({'search_query': ' AND '.join(f'all:{word}' for word in words[:20]),
                       'max_results': 10, 'sortBy': 'relevance'})


def download_arxiv(source_id):
    if not re.fullmatch(ARXIV_ID, source_id):
        raise HTTPException(422, 'Invalid arXiv paper identifier.')
    try:
        # No arbitrary URLs or redirects: only this public arXiv host.
        with httpx.stream('GET', f'https://arxiv.org/pdf/{source_id}', timeout=45) as response:
            response.raise_for_status()
            result = bytearray()
            for chunk in response.iter_bytes():
                result.extend(chunk)
                if len(result) > MAX_BYTES:
                    raise HTTPException(413, 'The PDF exceeds the 20 MB limit.')
            return bytes(result)
    except httpx.HTTPError as exc:
        raise HTTPException(502, 'Could not download this arXiv PDF. Download it yourself and use Attach PDF.') from exc


def extract_pdf(data):
    if len(data) > MAX_BYTES:
        raise HTTPException(413, 'Please upload a PDF smaller than 20 MB.')
    if not data.startswith(b'%PDF-'):
        raise HTTPException(422, 'This file is not a PDF.')
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise HTTPException(422, 'Password-protected PDFs are not supported. Upload an unlocked copy.')
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise HTTPException(422, 'Use a research paper with 1 to 80 pages.')
        pages = []
        title_runs = []
        def record_font(text, cm, tm, font, size):
            text = clean(text)
            if len(text) > 8 and not re.search(r'arxiv|https?://|@|permission|copyright|scholarly works', text, re.I):
                title_runs.append((float(size), text))
        count = 0
        for number, page in enumerate(reader.pages, 1):
            text = (page.extract_text(visitor_text=record_font if number == 1 else None) or '').strip().replace('\x00', '')
            count += len(text)
            if count > MAX_TEXT:
                raise HTTPException(422, 'This paper exceeds the 250,000-character limit. Use a shorter paper; text is never silently truncated.')
            pages.append({'page': number, 'text': text})
        metadata = reader.metadata or {}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(422, 'Could not read this PDF. It may be damaged or use an unsupported format.') from exc
    if count < 150:
        raise HTTPException(422, 'No usable paper text was found. Scanned PDFs need OCR before upload.')
    first = '\n'.join(page['text'] for page in pages[:2])
    lines = [clean(line) for line in pages[0]['text'].splitlines() if clean(line)]
    title = clean(metadata.get('/Title', ''))
    if len(title) < 5 or title.lower() in {'untitled', 'document', 'microsoft word'} or title.lower().endswith(('.tex', '.doc', '.docx')):
        candidates = [line for line in lines[:30] if len(line) > 12 and not re.search(r'arxiv|https?://|@|^\d|^preprint|^submitted', line, re.I)]
        title = candidates[0] if candidates else 'Untitled paper - please edit'
        if title_runs:
            largest = max(size for size, text in title_runs)
            prominent = [text for size, text in title_runs if size >= largest - 0.2]
            # A distinct large title font beats content-stream order (e.g. a license notice).
            if largest >= 14 and len(' '.join(prominent)) <= 500:
                title = clean(' '.join(prominent))
    authors = clean(metadata.get('/Author', ''))
    if not authors:
        try:
            title_index = next(i for i, line in enumerate(lines) if line in title or title in line)
            author_lines = []
            for candidate in lines[title_index + 1:]:
                if re.match(r'abstract\b', candidate, re.I):
                    break
                candidate = re.sub(r'[∗*†‡\d]+', '', candidate).strip()
                if 3 < len(candidate) < 250 and not re.search(r'university|institute|arxiv|https?://|@|google|research|laborator|department|school|college|huawei|brain|lab\b', candidate, re.I):
                    author_lines.append(candidate)
            authors = ', '.join(author_lines[:20])
        except (StopIteration, IndexError):
            pass
    abstract_match = re.search(r'\babstract\b\s*[:.\-—]?\s*(.*?)(?=\n\s*(?:1[.\s]+)?(?:introduction|keywords|index terms)\b|\n[∗†‡]|\Z)', first, re.I | re.S)
    abstract = clean(abstract_match.group(1))[:20000] if abstract_match else ''
    header = re.split(r'\babstract\b', pages[0]['text'], flags=re.I)[0]
    year_match = re.search(r'\b(?:19|20)\d{2}\b', header)
    year = int(year_match.group()) if year_match else None
    arxiv_match = re.search(r'arXiv:\s*(' + ARXIV_ID + ')', first, re.I)
    arxiv_id = arxiv_match.group(1) if arxiv_match else None
    blanks = [str(p['page']) for p in pages if len(p['text']) < 40]
    note = 'Metadata is estimated from PDF properties and the opening pages. Review title, authors, year, and abstract; missing fields can be entered manually.'
    if blanks:
        note += ' Little or no text on PDF pages ' + ', '.join(blanks) + '; images and scanned pages are not read.'
    return {'title': title[:500], 'authors': authors[:2000], 'year': year, 'arxiv_id': arxiv_id,
            'abstract': abstract, 'pages': pages, 'extraction_note': note}
