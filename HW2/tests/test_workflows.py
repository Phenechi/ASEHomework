"""Focused regression checks; no real API key or network calls are used."""
from io import BytesIO
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import database, llm, papers
from app.main import app


def pdf_fixture(typography=False):
    writer = PdfWriter()
    if not typography:
        writer.add_metadata({'/Title': 'A Test Research Paper', '/Author': 'Jane Example'})
    for text in [
        'A Test Research Paper|Jane Example|2026|Abstract|We investigate a small research system with a baseline comparison and a reproducible experiment.|1 Introduction|Our system retrieves evidence from local papers for scientific questions.',
        '2 Experiments|We evaluated on Dataset Cedar with 100 examples.|The proposed method scored 85 percent while the baseline scored 70 percent.|3 Limitations|The evaluation uses a single small dataset and does not measure generalization.'
    ]:
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'), NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        commands = ' '.join(f'({line}) Tj T*' for line in text.split('|'))
        if typography and text.startswith('A Test Research Paper'):
            commands = '(Provided proper attribution grants permission.) Tj T* /F1 18 Tf (A Test Research Paper) Tj T* /F1 12 Tf ' + ' '.join(f'({line}) Tj T*' for line in text.split('|')[1:]) + ' (arXiv:2601.12345v1) Tj T*'
        stream.set_data(('BT /F1 12 Tf 30 760 Td 16 TL ' + commands + ' ET').encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO(); writer.write(output)
    return output.getvalue()


class Workflows(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(database, 'DATABASE', Path(self.tmp.name) / 'library.db')
        self.db_patch.start()
        self.key_patch = patch.dict(os.environ, {'OPENAI_API_KEY': ''})
        self.key_patch.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.key_patch.stop(); self.db_patch.stop(); self.tmp.cleanup()

    def upload(self):
        response = self.client.post('/api/papers/upload', files={'file': ('paper.pdf', pdf_fixture(), 'application/pdf')})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_metadata_pages_and_duplicate_upload(self):
        paper = self.upload()
        self.assertEqual(paper['title'], 'A Test Research Paper')
        self.assertEqual(paper['authors'], 'Jane Example')
        self.assertEqual(paper['year'], 2026)
        self.assertIn('investigate', paper['abstract'])
        self.assertEqual(len(paper['pages']), 2)
        self.assertIn('Dataset Cedar', paper['pages'][1]['text'])
        self.assertEqual(self.upload()['id'], paper['id'])
        self.assertTrue(self.client.get(f'/api/papers/{paper["id"]}/pdf').content.startswith(b'%PDF'))

    def test_reject_invalid_blank_and_oversize_pdf(self):
        for content in (b'not a PDF', b'%PDF-broken'):
            self.assertEqual(self.client.post('/api/papers/upload', files={'file': ('x.pdf', content)}).status_code, 422)
        writer = PdfWriter(); writer.add_blank_page(width=100, height=100)
        out = BytesIO(); writer.write(out)
        self.assertEqual(self.client.post('/api/papers/upload', files={'file': ('scan.pdf', out.getvalue())}).status_code, 422)
        with patch.object(papers, 'MAX_BYTES', 10):
            self.assertEqual(self.client.post('/api/papers/upload', files={'file': ('big.pdf', b'x' * 11)}).status_code, 413)

    def test_title_typography_and_arxiv_metadata_enrichment(self):
        content = pdf_fixture(typography=True)
        extracted = papers.extract_pdf(content)
        self.assertEqual(extracted['title'], 'A Test Research Paper')
        self.assertEqual(extracted['arxiv_id'], '2601.12345v1')
        metadata = {'title': 'Verified title', 'authors': 'All Authors', 'year': 2026, 'abstract': 'Verified abstract'}
        with patch('app.papers.arxiv_feed', return_value=[metadata]):
            response = self.client.post('/api/papers/upload', files={'file': ('x.pdf', content)})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['title'], 'Verified title')
        self.assertEqual(response.json()['source_id'], '2601.12345v1')

    def test_replacing_pdf_clears_stale_ai_history(self):
        paper = self.upload()
        with database.connect() as db:
            db.execute('INSERT INTO analyses(paper_id,kind,question,result_json,model) VALUES(?,?,?,?,?)', (paper['id'],'summary','', '{}','test'))
        with patch('app.papers.arxiv_feed', return_value=[]):
            response = self.client.post(f'/api/papers/{paper["id"]}/upload', files={'file':('new.pdf',pdf_fixture(typography=True))})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f'/api/papers/{paper["id"]}').json()['analyses'], [])

    def test_metadata_only_cannot_use_ai_and_key_is_required(self):
        paper = self.client.post('/api/papers', json={'title':'Metadata only'}).json()
        self.assertEqual(self.client.post(f'/api/papers/{paper["id"]}/summary').status_code, 409)
        uploaded = self.upload()
        self.assertEqual(self.client.post(f'/api/papers/{uploaded["id"]}/summary').status_code, 503)
        self.assertNotIn('OPENAI_API_KEY', self.client.get('/api/health').text)

    def test_search_save_deduplicates_and_metadata_edit(self):
        item = {'title':'Search paper','authors':'A. Author','year':2020,'abstract':'Abstract', 'source_id':'2001.12345v1','url':'https://arxiv.org/abs/2001.12345v1'}
        with patch('app.papers.arxiv_feed', return_value=[item]):
            first = self.client.post('/api/papers/from-search', json={'source_id':item['source_id']}).json()
            second = self.client.post('/api/papers/from-search', json={'source_id':item['source_id']}).json()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(self.client.put(f'/api/papers/{first["id"]}', json={'title':'Corrected title'}).status_code, 200)
        self.assertEqual(self.client.get('/api/papers').json()[0]['title'], 'Corrected title')
        self.assertEqual(self.client.post('/api/papers/from-search', json={'source_id':'https://localhost'}).status_code, 422)

    def mock_llm(self, answer):
        client = MagicMock()
        client.__enter__.return_value = client
        client.responses.parse.return_value = SimpleNamespace(output_parsed=answer, status='completed')
        return client

    def test_ai_full_text_evidence_and_persistent_history(self):
        paper = self.upload()
        answer = llm.ModelAnswer(paragraphs=[llm.GroundedParagraph(text='Dataset Cedar was used.', evidence_ids=['P2-B1'])], insufficient_evidence=False)
        mocked = self.mock_llm(answer)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-placeholder'}), patch('app.llm.OpenAI', return_value=mocked):
            response = self.client.post(f'/api/papers/{paper["id"]}/questions', json={'question':'What dataset was used?'})
        self.assertEqual(response.status_code, 200, response.text)
        prompt = mocked.responses.parse.call_args.kwargs['input']
        self.assertIn('Dataset Cedar', prompt)
        self.assertIn('single small dataset', prompt)
        self.assertFalse(mocked.responses.parse.call_args.kwargs['store'])
        with TestClient(app) as restarted:
            detail = restarted.get(f'/api/papers/{paper["id"]}').json()
        self.assertEqual(len(detail['analyses']), 1)
        self.assertEqual(detail['analyses'][0]['result']['evidence'][0]['page'], 2)
        self.assertIn(detail['analyses'][0]['result']['evidence'][0]['quote'], paper['pages'][1]['text'])

    def test_fake_evidence_reference_is_rejected_and_not_saved(self):
        paper = self.upload()
        answer = llm.ModelAnswer(paragraphs=[llm.GroundedParagraph(text='An invented result.', evidence_ids=['P2-B999'])], insufficient_evidence=False)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-placeholder'}), patch('app.llm.OpenAI', return_value=self.mock_llm(answer)):
            self.assertEqual(self.client.post(f'/api/papers/{paper["id"]}/summary').status_code, 502)
        self.assertEqual(self.client.get(f'/api/papers/{paper["id"]}').json()['analyses'], [])

    def test_missing_evidence_can_be_acknowledged(self):
        paper = self.upload()
        answer = llm.ModelAnswer(paragraphs=[llm.GroundedParagraph(text='The paper does not report that detail.', evidence_ids=[])], insufficient_evidence=True)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-placeholder'}), patch('app.llm.OpenAI', return_value=self.mock_llm(answer)):
            response = self.client.post(f'/api/papers/{paper["id"]}/questions', json={'question':'Who funded it?'})
        self.assertTrue(response.json()['result']['insufficient_evidence'])

    def test_empty_insufficient_evidence_is_readable(self):
        paper = self.upload()
        answer = llm.ModelAnswer(paragraphs=[], insufficient_evidence=True)
        with patch.dict(os.environ, {'OPENAI_API_KEY':'test-placeholder'}), patch('app.llm.OpenAI', return_value=self.mock_llm(answer)):
            response = self.client.post(f'/api/papers/{paper["id"]}/questions', json={'question':'What did training cost in dollars?'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('does not provide enough evidence', response.json()['result']['answer'])

    def test_original_database_migration_preserves_papers(self):
        old = Path(self.tmp.name) / 'old.db'
        with sqlite3.connect(old) as db:
            db.execute("CREATE TABLE papers(id INTEGER PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,abstract TEXT,created_at TEXT)")
            db.execute("INSERT INTO papers VALUES(1,'Existing record','Author',2020,'Abstract','2026-09-30')")
        db.close()
        with patch.object(database, 'DATABASE', old):
            database.initialize(); database.initialize()
            self.assertEqual(self.client.get('/api/papers/1').json()['title'], 'Existing record')


if __name__ == '__main__':
    unittest.main()
