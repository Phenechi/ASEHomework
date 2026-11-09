"""Shared fixtures for improvement rounds; no live services or user data."""
from contextlib import ExitStack
from io import BytesIO
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app import database, llm
from app.main import app
from tests.test_workflows import pdf_fixture


def text_pdf(texts, metadata=None):
    writer = PdfWriter()
    if metadata:
        writer.add_metadata(metadata)
    for text in texts:
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): font})})
        stream = DecodedStreamObject()
        lines = [line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)') for line in text.split('\n')]
        commands = ' '.join(f'({line}) Tj T*' for line in lines)
        stream.set_data(('BT /F1 12 Tf 30 760 Td 16 TL ' + commands + ' ET').encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def model_answer(*paragraphs, insufficient=False):
    return llm.ModelAnswer(paragraphs=[llm.GroundedParagraph(text=text, evidence_ids=ids)
                                     for text, ids in paragraphs], insufficient_evidence=insufficient)


def mock_model(answer=None, error=None, status='completed'):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.parse.return_value = SimpleNamespace(output_parsed=answer, status=status)
    client.responses.parse.side_effect = error
    return client


class IsolatedAPI(unittest.TestCase):
    def setUp(self):
        stack = self.enterContext(ExitStack())
        folder = stack.enter_context(tempfile.TemporaryDirectory())
        stack.enter_context(patch.object(database, 'DATABASE', Path(folder) / 'test.db'))
        stack.enter_context(patch.dict(os.environ, {'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'hw2-test-model'}))
        stack.enter_context(patch('app.papers.httpx.get', side_effect=AssertionError('Unexpected arXiv request')))
        stack.enter_context(patch('app.papers.httpx.stream', side_effect=AssertionError('Unexpected download')))
        stack.enter_context(patch('app.llm.OpenAI', side_effect=AssertionError('Unexpected paid request')))
        self.client = stack.enter_context(TestClient(app))

    def save(self, **values):
        response = self.client.post('/api/papers', json={'title': 'Research paper', **values})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def upload(self, content=None):
        response = self.client.post('/api/papers/upload', files={'file': ('paper.pdf', content or pdf_fixture())})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def analyze_with(self, paper_id, answer=None, error=None, question=None, status='completed'):
        mocked = mock_model(answer, error, status)
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'hw2-dummy'}), patch('app.llm.OpenAI', return_value=mocked) as factory:
            path = f'/api/papers/{paper_id}/' + ('questions' if question is not None else 'summary')
            response = self.client.post(path, json={'question': question} if question is not None else None)
        return response, mocked, factory

    def history(self, paper_id):
        return self.client.get(f'/api/papers/{paper_id}').json()['analyses']
