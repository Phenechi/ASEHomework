"""SQLite storage and additive migrations for the original database."""
from contextlib import contextmanager
import os
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parent.parent
DATABASE = Path(os.environ.get('RESEARCH_DATABASE', str(ROOT / 'data' / 'research.db')))


@contextmanager
def connect():
    connection = sqlite3.connect(DATABASE, timeout=20)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize():
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
            authors TEXT NOT NULL DEFAULT '', year INTEGER,
            abstract TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
        columns = {row['name'] for row in db.execute('PRAGMA table_info(papers)')}
        additions = {
            'source_id': 'TEXT', 'url': "TEXT NOT NULL DEFAULT ''",
            'pages_json': "TEXT NOT NULL DEFAULT '[]'", 'pdf_data': 'BLOB',
            'pdf_hash': 'TEXT', 'extraction_note': "TEXT NOT NULL DEFAULT ''",
        }
        for name, declaration in additions.items():
            if name not in columns:
                db.execute(f'ALTER TABLE papers ADD COLUMN {name} {declaration}')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS paper_source ON papers(source_id)')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS paper_pdf_hash ON papers(pdf_hash)')
        db.execute('''CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER NOT NULL REFERENCES papers(id),
            kind TEXT NOT NULL, question TEXT NOT NULL, result_json TEXT NOT NULL,
            model TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )''')
