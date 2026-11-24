import sqlite3
from contextlib import contextmanager
from pathlib import Path
from app import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, source BLOB NOT NULL, book BLOB NOT NULL,
  result TEXT NOT NULL, created TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reviews (
  run_id TEXT NOT NULL REFERENCES runs(id), version INTEGER NOT NULL,
  decision TEXT NOT NULL, note TEXT NOT NULL, changed TEXT NOT NULL,
  PRIMARY KEY(run_id,version)
);
CREATE TABLE IF NOT EXISTS settle_receipts (
  id TEXT PRIMARY KEY, stall TEXT NOT NULL, total_portions INTEGER NOT NULL,
  closed_at TEXT
);
CREATE TABLE IF NOT EXISTS settle_claims (
  receipt_id TEXT NOT NULL REFERENCES settle_receipts(id),
  claim_no INTEGER NOT NULL, stall TEXT NOT NULL, portions INTEGER NOT NULL,
  status TEXT NOT NULL, changed TEXT NOT NULL,
  PRIMARY KEY(receipt_id,claim_no)
);
CREATE INDEX IF NOT EXISTS idx_settle_claims ON settle_claims(receipt_id,status);
"""


@contextmanager
def connection():
    path = Path(settings.DB)
    path.parent.mkdir(parents=True,exist_ok=True)
    db = sqlite3.connect(path,timeout=10)
    db.row_factory = sqlite3.Row
    try:
        db.execute('PRAGMA foreign_keys = ON')
        db.executescript(SCHEMA)
        with db:
            yield db
    finally:
        db.close()
