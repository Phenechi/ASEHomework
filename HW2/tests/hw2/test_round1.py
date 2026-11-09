"""Round 1: requirements-focused service contracts, PDF bounds, persistence."""
from io import BytesIO
import unittest
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from pypdf import PdfReader, PdfWriter

from app import database, papers
from app.main import store_pdf
from tests.hw2.support import IsolatedAPI, model_answer, text_pdf
from tests.test_workflows import pdf_fixture


ATOM = b'''<feed xmlns="http://www.w3.org/2005/Atom"><entry>
<id>https://arxiv.org/abs/2601.12345v2</id><title>  Graph\n learning </title>
<author><name>Alice  Example</name></author><author><name>Bob Example</name></author>
<published>2024-02-01T00:00:00Z</published><updated>2026-02-01T00:00:00Z</updated>
<summary> A reproducible\n experiment. </summary></entry></feed>'''


class Clock:
    def __init__(self):
        self.now = 100.0
        self.waits = []

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.waits.append(duration)
        self.now += duration


class ArxivContracts(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.enterContext(patch.object(papers, '_cache', {}))
        self.enterContext(patch.object(papers, '_last_call', 0.0))
        self.enterContext(patch('app.papers.time.monotonic', self.clock.monotonic))
        self.enterContext(patch('app.papers.time.sleep', self.clock.sleep))
        response = httpx.Response(200, content=ATOM, request=httpx.Request('GET', 'https://export.arxiv.org/api/query'))
        self.get = self.enterContext(patch('app.papers.httpx.get', return_value=response))

    def test_atom_metadata_uses_initial_year_and_cleans_whitespace(self):
        result = papers.arxiv_feed({'search_query': 'all:graph'})
        self.assertEqual(result, [{'source_id': '2601.12345v2', 'title': 'Graph learning',
                                  'authors': 'Alice Example, Bob Example', 'year': 2024,
                                  'abstract': 'A reproducible experiment.', 'url': 'https://arxiv.org/abs/2601.12345v2'}])
        self.assertEqual(self.get.call_args.args, ('https://export.arxiv.org/api/query',))
        self.assertEqual(self.get.call_args.kwargs['params'], {'search_query': 'all:graph'})

    def test_cache_reuses_reordered_params_and_expires_at_ten_minutes(self):
        expected = papers.arxiv_feed({'search_query': 'x', 'max_results': 10})
        self.clock.now = 699.999
        self.assertEqual(papers.arxiv_feed({'max_results': 10, 'search_query': 'x'}), expected)
        self.get.assert_called_once()
        self.clock.now = 700.0
        self.assertEqual(papers.arxiv_feed({'search_query': 'x', 'max_results': 10}), expected)
        self.assertEqual(self.get.call_count, 2)

    def test_distinct_queries_are_spaced_without_real_waiting(self):
        papers.arxiv_feed({'search_query': 'one'})
        self.clock.now = 101.0
        papers.arxiv_feed({'search_query': 'two'})
        self.assertAlmostEqual(self.clock.waits[-1], 2.1)
        self.assertAlmostEqual(self.clock.now, 103.1)
        self.assertEqual(self.get.call_count, 2)

    def test_malformed_feed_is_readable_and_not_cached(self):
        for content in (b'<feed', ATOM.replace(b'2601.12345v2', b'not-an-id'),
                        ATOM.replace(b'2024-02-01', b'bad-year--')):
            with self.subTest(content=content):
                self.get.return_value = httpx.Response(200, content=content, request=httpx.Request('GET', 'https://arxiv.org'))
                before = self.get.call_count
                for _ in range(2):
                    with self.assertRaises(HTTPException) as caught:
                        papers.arxiv_feed({'search_query': 'malformed'})
                    self.assertEqual(caught.exception.status_code, 502)
                    self.assertIn('try again', caught.exception.detail)
                self.assertEqual(self.get.call_count - before, 2)
                self.assertEqual(papers._cache, {})

    def test_http_failure_is_translated_and_empty_feed_is_valid(self):
        self.get.side_effect = httpx.ConnectError('offline')
        with self.assertRaises(HTTPException) as caught:
            papers.arxiv_feed({'search_query': 'offline'})
        self.assertEqual(caught.exception.status_code, 502)
        self.assertEqual(papers._cache, {})
        self.get.side_effect = None
        self.get.return_value = httpx.Response(200, content=b'<feed xmlns="http://www.w3.org/2005/Atom"/>', request=httpx.Request('GET', 'https://arxiv.org'))
        self.assertEqual(papers.arxiv_feed({'search_query': 'empty'}), [])

    def test_full_cache_remains_bounded_and_new_result_is_available(self):
        papers._cache.update({(('search_query', str(i)),): (100.0, []) for i in range(100)})
        expected = papers.arxiv_feed({'search_query': 'new'})
        self.assertLessEqual(len(papers._cache), 100)
        self.assertEqual(papers.arxiv_feed({'search_query': 'new'}), expected)
        self.get.assert_called_once()


class DownloadContracts(unittest.TestCase):
    def stream(self, chunks, error=None):
        context = MagicMock()
        response = context.__enter__.return_value
        response.iter_bytes.return_value = iter(chunks)
        response.raise_for_status.side_effect = error
        return context

    def test_valid_modern_and_legacy_ids_use_fixed_host_and_complete_bytes(self):
        for source_id in ('2601.12345v2', 'hep-th/9901001v1'):
            with self.subTest(source_id=source_id):
                context = self.stream([b'%PDF-', b'example'])
                with patch('app.papers.httpx.stream', return_value=context) as stream:
                    self.assertEqual(papers.download_arxiv(source_id), b'%PDF-example')
                stream.assert_called_once_with('GET', f'https://arxiv.org/pdf/{source_id}', timeout=45)
                context.__exit__.assert_called_once()

    def test_invalid_ids_never_open_a_download(self):
        with patch('app.papers.httpx.stream') as stream:
            for source_id in ('https://localhost/x', '../secret', '2601.12345\n', '', '2601.123456'):
                with self.subTest(source_id=source_id), self.assertRaises(HTTPException) as caught:
                    papers.download_arxiv(source_id)
                self.assertEqual(caught.exception.status_code, 422)
            stream.assert_not_called()

    def test_chunk_limit_accepts_exact_boundary_and_stops_on_overflow(self):
        with patch.object(papers, 'MAX_BYTES', 8):
            with patch('app.papers.httpx.stream', return_value=self.stream([b'1234', b'5678'])):
                self.assertEqual(papers.download_arxiv('2601.12345'), b'12345678')
            iterator = iter([b'1234', b'56789', b'must not read'])
            context = self.stream([])
            context.__enter__.return_value.iter_bytes.return_value = iterator
            with patch('app.papers.httpx.stream', return_value=context), self.assertRaises(HTTPException) as caught:
                papers.download_arxiv('2601.12345')
            self.assertEqual(caught.exception.status_code, 413)
            self.assertEqual(next(iterator), b'must not read')
            context.__exit__.assert_called_once()

    def test_upstream_http_and_connection_errors_become_actionable_502(self):
        request = httpx.Request('GET', 'https://arxiv.org/pdf/2601.12345')
        errors = [httpx.ConnectError('offline'), httpx.HTTPStatusError('unavailable', request=request, response=httpx.Response(503, request=request))]
        for error in errors:
            with self.subTest(error=type(error).__name__), patch('app.papers.httpx.stream', return_value=self.stream([], error)), self.assertRaises(HTTPException) as caught:
                papers.download_arxiv('2601.12345')
            self.assertEqual(caught.exception.status_code, 502)
            self.assertIn('Attach PDF', caught.exception.detail)


class PDFLimits(unittest.TestCase):
    def test_direct_extraction_enforces_byte_limit_before_parser(self):
        with patch.object(papers, 'MAX_BYTES', 5), patch('app.papers.PdfReader') as reader:
            with self.assertRaises(HTTPException) as caught:
                papers.extract_pdf(b'%PDF-too-long')
        self.assertEqual(caught.exception.status_code, 413)
        reader.assert_not_called()

    def test_encrypted_pdf_rejected(self):
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('private')
        out = BytesIO()
        writer.write(out)
        with self.assertRaises(HTTPException) as caught:
            papers.extract_pdf(out.getvalue())
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn('Password-protected', caught.exception.detail)

    def test_zero_and_81_page_documents_rejected(self):
        for count in (0, 81):
            with self.subTest(count=count):
                writer = PdfWriter()
                for _ in range(count):
                    writer.add_blank_page(width=100, height=100)
                out = BytesIO()
                writer.write(out)
                with self.assertRaises(HTTPException) as caught:
                    papers.extract_pdf(out.getvalue())
                self.assertEqual(caught.exception.status_code, 422)
                self.assertIn('1 to 80', caught.exception.detail)

    def test_80_pages_accepted_with_blank_pages_disclosed(self):
        writer = PdfWriter(clone_from=BytesIO(pdf_fixture()))
        for _ in range(78):
            writer.add_blank_page(width=100, height=100)
        out = BytesIO()
        writer.write(out)
        result = papers.extract_pdf(out.getvalue())
        self.assertEqual(len(result['pages']), 80)
        self.assertEqual(result['pages'][-1], {'page': 80, 'text': ''})
        self.assertIn('3, 4, 5', result['extraction_note'])
        self.assertIn('80', result['extraction_note'])

    def test_text_limit_accepts_exact_boundary_and_rejects_one_over(self):
        for count in (250000, 250001):
            with self.subTest(count=count):
                data = text_pdf(['x' * count], {'/Title': 'Boundary test', '/Author': 'Example'})
                if count == 250000:
                    result = papers.extract_pdf(data)
                    self.assertEqual(result['pages'][0]['text'], 'x' * count)
                else:
                    with self.assertRaises(HTTPException) as caught:
                        papers.extract_pdf(data)
                    self.assertEqual(caught.exception.status_code, 422)
                    self.assertIn('never silently truncated', caught.exception.detail)

    def test_minimum_usable_text_and_creation_time_not_publication_year(self):
        data = text_pdf(['x' * 149], {'/Title': 'A short paper', '/Author': 'Example'})
        with self.assertRaises(HTTPException) as caught:
            papers.extract_pdf(data)
        self.assertEqual(caught.exception.status_code, 422)
        result = papers.extract_pdf(text_pdf(['x' * 150], {'/Title': 'A short paper', '/Author': 'Example', '/CreationDate': 'D:20240101000000'}))
        self.assertEqual(len(result['pages'][0]['text']), 150)
        self.assertIsNone(result['year'])


class LibraryAssociations(IsolatedAPI):
    def test_fetch_stores_download_on_selected_search_record(self):
        item = {'title': 'Search title', 'authors': 'Author', 'year': 2024, 'abstract': 'Original', 'source_id': '2601.12345v1', 'url': 'https://arxiv.org/abs/2601.12345v1'}
        with patch('app.papers.arxiv_feed', return_value=[item]):
            saved = self.client.post('/api/papers/from-search', json={'source_id': item['source_id']}).json()
        with patch('app.papers.download_arxiv', return_value=pdf_fixture()) as download:
            response = self.client.post(f'/api/papers/{saved["id"]}/fetch-pdf')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['id'], saved['id'])
        self.assertEqual(response.json()['title'], 'Search title')
        self.assertTrue(response.json()['has_pdf'])
        self.assertEqual(len(response.json()['pages']), 2)
        download.assert_called_once_with(item['source_id'])
        self.assertEqual(len(self.client.get('/api/papers').json()), 1)

    def test_unavailable_enrichment_keeps_locally_extracted_metadata(self):
        data = pdf_fixture(typography=True)
        with patch('app.papers.arxiv_feed', side_effect=HTTPException(502, 'offline')):
            saved = self.upload(data)
        self.assertEqual(saved['title'], 'A Test Research Paper')
        self.assertEqual(saved['source_id'], '2601.12345v1')
        self.assertIn('local estimates were retained', saved['extraction_note'])
        self.assertEqual(self.client.get(f'/api/papers/{saved["id"]}/pdf').content, data)

    def test_upload_matches_existing_source_without_duplicating_record(self):
        item = {'title': 'Curated title', 'authors': 'Author', 'year': 2024, 'abstract': 'Curated', 'source_id': '2601.12345v1', 'url': 'https://arxiv.org/abs/2601.12345v1'}
        with patch('app.papers.arxiv_feed', return_value=[item]):
            saved = self.client.post('/api/papers/from-search', json={'source_id': item['source_id']}).json()
        with patch('app.papers.arxiv_feed', return_value=[]):
            uploaded = self.upload(pdf_fixture(typography=True))
        self.assertEqual(uploaded['id'], saved['id'])
        self.assertEqual(uploaded['title'], 'Curated title')
        self.assertTrue(uploaded['has_pdf'])
        self.assertEqual(len(self.client.get('/api/papers').json()), 1)

    def test_reuploading_identical_pdf_preserves_existing_history(self):
        paper = self.upload()
        response, _, _ = self.analyze_with(paper['id'], model_answer(('A result.', ['P1-B1'])))
        self.assertEqual(response.status_code, 200, response.text)
        history = self.history(paper['id'])
        self.assertEqual(self.upload()['id'], paper['id'])
        self.assertEqual(self.history(paper['id']), history)

    def test_store_pdf_missing_target_rolls_back(self):
        with self.assertRaises(HTTPException) as caught:
            store_pdf(pdf_fixture(), paper_id=999)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertEqual(self.client.get('/api/papers').json(), [])
