import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS owner (
 id INTEGER PRIMARY KEY CHECK (id = 1),
 username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS entries (
 id INTEGER PRIMARY KEY,
 title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 120),
 premiere TEXT,
 note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 10000),
 published INTEGER NOT NULL DEFAULT 0 CHECK(published IN (0,1)),
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS photos (
 id INTEGER PRIMARY KEY, entry_id INTEGER NOT NULL UNIQUE REFERENCES entries(id) ON DELETE CASCADE,
 filename TEXT NOT NULL UNIQUE, alt TEXT NOT NULL CHECK(length(alt) BETWEEN 1 AND 200),
 source_url TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS sessions (
 token_hash TEXT PRIMARY KEY, expires INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS login_attempts (
 address_hash TEXT PRIMARY KEY, count INTEGER NOT NULL, window_start INTEGER NOT NULL
);
"""


class Connection(sqlite3.Connection):
    close_on_exit = True

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            if self.close_on_exit:
                self.close()


def connect(path, close_on_exit=True):
    db = sqlite3.connect(path, timeout=10, factory=Connection)
    db.close_on_exit = close_on_exit
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.executescript(SCHEMA)
        columns = {row['name'] for row in db.execute('PRAGMA table_info(photos)')}
        if 'source_url' not in columns:
            db.execute("ALTER TABLE photos ADD COLUMN source_url TEXT NOT NULL DEFAULT ''")
