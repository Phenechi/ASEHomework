"""Initial HW2 generation: public API contracts and documented research workflows.

Keep this stage stable; put subsequent improvements in separate modules.
External services are mocked. Every API test uses a fresh temporary SQLite DB.
"""
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import database, llm, papers
from app.main import app
from tests.test_workflows import pdf_fixture


class InitialAPI(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        folder = stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(patch.object(database, 'DATABASE', Path(folder) / 'test.db'))
        stack.enter_context(patch.dict(os.environ, {'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'hw2-test-model'}))
        # Unexpected external calls fail immediately; individual tests override these.
        stack.enter_context(patch('app.papers.httpx.get', side_effect=AssertionError('Unexpected arXiv request')))
        stack.enter_context(patch('app.papers.httpx.stream', side_effect=AssertionError('Unexpected PDF download')))
        stack.enter_context(patch('app.llm.OpenAI', side_effect=AssertionError('Unexpected OpenAI request')))
        self.client = stack.enter_context(TestClient(app))

    def save(self, **values):
        response = self.client.post('/api/papers', json={'title': 'A research paper', **values})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def upload(self):
        response = self.client.post('/api/papers/upload', files={'file': ('paper.pdf', pdf_fixture(), 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_empty_library_and_health(self):
        self.assertEqual(self.client.get('/api/papers').json(), [])
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'database': 'connected', 'paper_count': 0,
                                          'llm_configured': False, 'model': 'hw2-test-model'})

    def test_create_list_and_detail_preserve_literal_metadata(self):
        first = self.save(title='  A study  ', authors="O'Connor", abstract='<script>example</script>', year=2026)
        second = self.save(title='Second')
        self.assertEqual(first['title'], 'A study')
        listing = self.client.get('/api/papers').json()
        self.assertEqual([p['id'] for p in listing], [second['id'], first['id']])
        detail = self.client.get(f'/api/papers/{first["id"]}').json()
        self.assertEqual(detail['authors'], "O'Connor")
        self.assertEqual(detail['abstract'], '<script>example</script>')
        self.assertEqual(detail['year'], 2026)
        self.assertEqual(detail['pages'], [])
        self.assertEqual(detail['analyses'], [])
        self.assertEqual(self.client.get('/api/health').json()['paper_count'], 2)

    def test_invalid_metadata_does_not_create_records(self):
        cases = [{'title': '   '}, {'title': 'x' * 501}, {'title': 'x', 'year': 999},
                 {'title': 'x', 'year': 2101}, {'title': 'x', 'unknown': True}]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/papers', json=body).status_code, 422)
        self.assertEqual(self.client.get('/api/papers').json(), [])

    def test_missing_paper_routes_return_readable_404(self):
        for method, path, kwargs in [
            ('get', '/api/papers/999', {}), ('get', '/api/papers/999/pdf', {}),
            ('put', '/api/papers/999', {'json': {'title': 'Edit'}}),
            ('post', '/api/papers/999/summary', {}),
            ('post', '/api/papers/999/questions', {'json': {'question': 'Which dataset?'}}),
            ('post', '/api/papers/999/fetch-pdf', {})]:
            with self.subTest(path=path, method=method):
                response = getattr(self.client, method)(path, **kwargs)
                self.assertEqual(response.status_code, 404)
                self.assertIsInstance(response.json()['detail'], str)

    def test_search_normalizes_topic_and_returns_metadata(self):
        item = {'source_id': '2601.12345v1', 'title': 'Study', 'authors': 'A. Author',
                'year': 2026, 'abstract': 'Findings', 'url': 'https://arxiv.org/abs/2601.12345v1'}
        with patch('app.papers.arxiv_feed', return_value=[item]) as feed:
            response = self.client.get('/api/search', params={'q': 'the graph learning for research'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [item])
        feed.assert_called_once_with({'search_query': 'all:graph AND all:learning AND all:research',
                                      'max_results': 10, 'sortBy': 'relevance'})

    def test_invalid_search_and_upstream_failure_are_readable(self):
        for query in ('x', '!!!', ' ' * 4, 'x' * 201):
            with self.subTest(query=query):
                self.assertEqual(self.client.get('/api/search', params={'q': query}).status_code, 422)
        with patch('app.papers.arxiv_feed', side_effect=HTTPException(502, 'arXiv unavailable')):
            response = self.client.get('/api/search', params={'q': 'graph'})
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['detail'], 'arXiv unavailable')

    def test_save_missing_search_result_leaves_library_empty(self):
        with patch('app.papers.arxiv_feed', return_value=[]):
            response = self.client.post('/api/papers/from-search', json={'source_id': '2601.12345'})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get('/api/papers').json(), [])

    def test_edit_metadata_preserves_pdf_pages_and_bytes(self):
        paper = self.upload()
        replacement = {'title': 'Corrected', 'authors': 'Correct author', 'year': 2025, 'abstract': 'Correct abstract'}
        response = self.client.put(f'/api/papers/{paper["id"]}', json=replacement)
        self.assertEqual(response.status_code, 200)
        for key, value in replacement.items():
            self.assertEqual(response.json()[key], value)
        self.assertEqual(response.json()['pages'], paper['pages'])
        pdf = self.client.get(f'/api/papers/{paper["id"]}/pdf')
        self.assertEqual(pdf.content, pdf_fixture())
        self.assertEqual(pdf.headers['content-type'], 'application/pdf')

    def test_duplicate_attachment_conflict_preserves_both_records(self):
        original = self.upload()
        target = self.save(title='Other record')
        response = self.client.post(f'/api/papers/{target["id"]}/upload', files={'file': ('same.pdf', pdf_fixture())})
        self.assertEqual(response.status_code, 409)
        self.assertIn(f'#{original["id"]}', response.json()['detail'])
        self.assertEqual(self.client.get(f'/api/papers/{target["id"]}').json()['pages'], [])
        self.assertEqual(self.client.get(f'/api/papers/{original["id"]}/pdf').content, pdf_fixture())

    def test_fetch_requires_source_and_reuses_attached_pdf(self):
        manual = self.save()
        self.assertEqual(self.client.post(f'/api/papers/{manual["id"]}/fetch-pdf').status_code, 409)
        uploaded = self.upload()
        with patch('app.papers.download_arxiv') as download:
            response = self.client.post(f'/api/papers/{uploaded["id"]}/fetch-pdf')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['pages'], uploaded['pages'])
        download.assert_not_called()

    def test_question_validation_never_saves_history(self):
        paper = self.upload()
        for question in ('', '  ', 'ab', 'x' * 2001):
            with self.subTest(question=question[:20]):
                response = self.client.post(f'/api/papers/{paper["id"]}/questions', json={'question': question})
                self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get(f'/api/papers/{paper["id"]}').json()['analyses'], [])

    def test_summary_copies_evidence_and_persists_analysis_kind(self):
        paper = self.upload()
        model = llm.ModelAnswer(paragraphs=[llm.GroundedParagraph(text='Dataset Cedar has 100 examples.', evidence_ids=['P2-B1'])], insufficient_evidence=False)
        client = MagicMock()
        client.__enter__.return_value = client
        client.responses.parse.return_value = SimpleNamespace(output_parsed=model, status='completed')
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'hw2-dummy'}), patch('app.llm.OpenAI', return_value=client):
            response = self.client.post(f'/api/papers/{paper["id"]}/summary')
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()['result']
        self.assertEqual(result['answer'], 'Dataset Cedar has 100 examples. [p. 2]')
        self.assertEqual(result['evidence'], [{'page': 2, 'quote': paper['pages'][1]['text']}])
        history = self.client.get(f'/api/papers/{paper["id"]}').json()['analyses']
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['kind'], 'summary')
        self.assertEqual(history[0]['question'], '')
        self.assertEqual(history[0]['result'], result)
        self.assertEqual(history[0]['model'], 'hw2-test-model')
        self.assertFalse(client.responses.parse.call_args.kwargs['store'])


class InitialPassages(unittest.TestCase):
    def test_passages_preserve_all_characters_and_physical_page_numbers(self):
        text = 'alpha\n' * 301 + 'omega'
        passages = llm.source_passages([{'page': 4, 'text': text}, {'page': 5, 'text': ''}, {'page': 6, 'text': 'last'}])
        self.assertEqual(''.join(p['text'] for p in passages if p['page'] == 4), text)
        self.assertEqual([p['id'] for p in passages], ['P4-B1', 'P4-B2', 'P4-B3', 'P6-B1'])
        self.assertTrue(all(len(p['text']) <= 900 for p in passages))
