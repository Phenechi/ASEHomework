"""Round 2: coverage feedback, strong evidence oracles and failure side effects."""
import json
import os
import unittest
from unittest.mock import patch

import httpx
from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError

from app import database, llm, papers
from tests.hw2.support import IsolatedAPI, model_answer, text_pdf


class AIContracts(IsolatedAPI):
    def test_provider_errors_are_actionable_and_preserve_existing_history(self):
        paper = self.upload()
        response, _, _ = self.analyze_with(paper['id'], model_answer(('A supported result.', ['P1-B1'])))
        self.assertEqual(response.status_code, 200)
        previous = self.history(paper['id'])
        request = httpx.Request('POST', 'https://api.openai.com/v1/responses')
        def status(code):
            return httpx.Response(code, request=request)
        cases = [
            (AuthenticationError('bad key', response=status(401), body=None), 503, 'API key'),
            (RateLimitError('quota', response=status(429), body={'code': 'insufficient_quota'}), 503, 'billing'),
            (RateLimitError('rate', response=status(429), body={'code': 'rate_limit_exceeded'}), 503, 'rate or quota'),
            (APIConnectionError(request=request), 502, 'connection'),
            (APIStatusError('server error', response=status(500), body=None), 502, 'model access'),
            (ValueError('malformed JSON'), 502, 'unreadable'),
            (TypeError('invalid parsed value'), 502, 'unreadable'),
        ]
        for error, code, message in cases:
            with self.subTest(error=type(error).__name__, message=message):
                response, mocked, factory = self.analyze_with(paper['id'], error=error)
                self.assertEqual(response.status_code, code, response.text)
                self.assertIn(message, response.json()['detail'])
                self.assertEqual(self.history(paper['id']), previous)
                factory.assert_called_once_with(api_key='hw2-dummy', timeout=90, max_retries=0)
                mocked.responses.parse.assert_called_once()

    def test_incomplete_and_unparsed_answers_are_not_saved(self):
        paper = self.upload()
        for status, answer in [('incomplete', model_answer(('A result.', ['P1-B1']))), ('completed', None)]:
            with self.subTest(status=status):
                response, _, _ = self.analyze_with(paper['id'], answer, status=status)
                self.assertEqual(response.status_code, 502)
                self.assertIn('complete answer', response.json()['detail'])
                self.assertEqual(self.history(paper['id']), [])

    def test_empty_answer_and_empty_or_citation_only_paragraph_are_not_saved(self):
        paper = self.upload()
        for answer, message in [(model_answer(), 'no answer'),
                                (model_answer(('   ', ['P1-B1'])), 'empty paragraph'),
                                (model_answer(('[p. 999]', ['P1-B1'])), 'empty paragraph')]:
            with self.subTest(message=message):
                response, _, _ = self.analyze_with(paper['id'], answer)
                self.assertEqual(response.status_code, 502)
                self.assertIn(message, response.json()['detail'])
                self.assertEqual(self.history(paper['id']), [])

    def test_answer_without_any_support_is_rejected_and_not_saved(self):
        paper = self.upload()
        response, _, _ = self.analyze_with(paper['id'], model_answer(('An unsupported claim.', [])))
        self.assertEqual(response.status_code, 502)
        self.assertIn('supporting passages', response.json()['detail'])
        self.assertEqual(self.history(paper['id']), [])

    def test_each_substantive_paragraph_requires_evidence(self):
        paper = self.upload()
        answer = model_answer(('A supported statement.', ['P1-B1']),
                              ('The method achieved 99.9 percent on an invented dataset.', []))
        response, _, _ = self.analyze_with(paper['id'], answer)
        # One cited paragraph must not let another unsupported factual paragraph pass.
        self.assertEqual((response.status_code, len(self.history(paper['id']))), (502, 0), response.text)
        self.assertIn('supporting passages', response.json()['detail'])

    def test_multi_paragraph_citations_are_derived_sorted_and_deduplicated(self):
        paper = self.upload()
        answer = model_answer(('A combined result. [p. 999]', ['P2-B1', 'P1-B1', 'P2-B1']),
                              ('Another supported point. [pp. 900-901]', ['P1-B1']))
        response, _, _ = self.analyze_with(paper['id'], answer)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()['result']
        self.assertEqual(result['answer'], 'A combined result. [p. 1] [p. 2]\n\nAnother supported point. [p. 1]')
        self.assertEqual(result['evidence'], [{'page': 2, 'quote': paper['pages'][1]['text']},
                                              {'page': 1, 'quote': paper['pages'][0]['text']}])
        self.assertEqual(self.history(paper['id'])[0]['result'], result)

    def test_explicit_missing_information_can_have_no_evidence(self):
        paper = self.upload()
        answer = model_answer(('The paper does not state the funding source.', []), insufficient=True)
        response, _, _ = self.analyze_with(paper['id'], answer, question='Who funded the study?')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['result'], {'answer': 'The paper does not state the funding source.',
                                                     'evidence': [], 'insufficient_evidence': True})
        self.assertEqual(self.history(paper['id'])[0]['kind'], 'question')

    def test_trimmed_question_and_all_passages_reach_model_without_paid_retries(self):
        paper = self.upload()
        response, mocked, factory = self.analyze_with(paper['id'], model_answer(('Dataset Cedar.', ['P2-B1'])),
                                                      question='  Which dataset?  ')
        self.assertEqual(response.status_code, 200, response.text)
        call = mocked.responses.parse.call_args.kwargs
        task, sources = call['input'].split('\n\nEXTRACTED_PDF_PASSAGES_JSON:\n')
        self.assertEqual(task, 'Answer this question using only this paper: Which dataset?')
        self.assertEqual(json.loads(sources), llm.source_passages(paper['pages']))
        self.assertFalse(call['store'])
        self.assertIs(call['text_format'], llm.ModelAnswer)
        factory.assert_called_once_with(api_key='hw2-dummy', timeout=90, max_retries=0)
        self.assertEqual(self.history(paper['id'])[0]['question'], 'Which dataset?')


class PersistenceFeedback(IsolatedAPI):
    def test_pdf_changed_during_analysis_rejects_stale_result(self):
        paper = self.upload()
        replacement = [{'page': 1, 'text': 'Replacement contents'}]
        def replace(pages, question):
            with database.connect() as db:
                db.execute('UPDATE papers SET pages_json=? WHERE id=?', (json.dumps(replacement), paper['id']))
            return {'answer': 'Stale result', 'evidence': [], 'insufficient_evidence': True}
        with patch('app.llm.analyze', side_effect=replace):
            response = self.client.post(f'/api/papers/{paper["id"]}/summary')
        self.assertEqual(response.status_code, 409)
        self.assertIn('PDF changed', response.json()['detail'])
        self.assertEqual(self.history(paper['id']), [])
        self.assertEqual(self.client.get(f'/api/papers/{paper["id"]}').json()['pages'], replacement)

    def test_deleted_paper_during_analysis_does_not_leave_orphan_history(self):
        paper = self.upload()
        def delete(pages, question):
            with database.connect() as db:
                db.execute('DELETE FROM papers WHERE id=?', (paper['id'],))
            return {'answer': 'Stale result', 'evidence': [], 'insufficient_evidence': True}
        with patch('app.llm.analyze', side_effect=delete):
            response = self.client.post(f'/api/papers/{paper["id"]}/summary')
        self.assertEqual(response.status_code, 409)
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)

    def test_sql_constraint_failure_rolls_back_new_paper_and_returns_conflict(self):
        # A synthetic DB trigger exercises the real sqlite3.IntegrityError branch.
        # It is fault injection, not a claimed naturally discovered application bug.
        with database.connect() as db:
            db.execute("CREATE TRIGGER simulate_race BEFORE UPDATE OF pdf_hash ON papers BEGIN SELECT RAISE(ABORT, 'simulated competing save'); END")
        response = self.client.post('/api/papers/upload', files={'file': ('x.pdf', text_pdf(['A paper title\n' + 'body ' * 50]))})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertIn('Refresh the library', response.json()['detail'])
        self.assertEqual(self.client.get('/api/papers').json(), [])
        with database.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM analyses').fetchone()[0], 0)

    def test_homepage_and_assets_are_served(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response.headers['content-type'])
        for control in ('search-form', 'upload-form', 'question-form'):
            self.assertIn(f'id="{control}"', response.text)
        for path, marker in [('/static/app.js', 'refreshLibrary'), ('/static/styles.css', 'body')]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn(marker, response.text)


class MetadataAndConfiguration(unittest.TestCase):
    def test_missing_title_candidates_and_authors_remain_reviewable(self):
        result = papers.extract_pdf(text_pdf(['https://example.org ' * 20], {'/Title': 'document'}))
        self.assertEqual(result['title'], 'Untitled paper - please edit')
        self.assertEqual(result['authors'], '')
        self.assertEqual(result['abstract'], '')
        self.assertIn('missing fields can be entered manually', result['extraction_note'])

    def test_local_title_and_author_fallback_without_abstract(self):
        result = papers.extract_pdf(text_pdf(['Interesting research title\nAlice Example\n' + 'x' * 300]))
        self.assertEqual(result['title'], 'Interesting research title')
        self.assertEqual(result['authors'], 'Alice Example')
        self.assertIsNone(result['year'])
        self.assertEqual(result['abstract'], '')

    def test_key_placeholders_whitespace_and_model_fallback(self):
        for key, expected in [('', False), ('   ', False), ('your-key-here', False),
                              ('YOUR_API_KEY', False), ('  hw2-dummy  ', True)]:
            with self.subTest(key=key), patch.dict(os.environ, {'OPENAI_API_KEY': key}):
                self.assertEqual(llm.configured(), expected)
        for model, expected in [('', 'gpt-4.1-mini'), ('   ', 'gpt-4.1-mini'), (' custom-model ', 'custom-model')]:
            with self.subTest(model=model), patch.dict(os.environ, {'OPENAI_MODEL': model}):
                self.assertEqual(llm.model_name(), expected)
