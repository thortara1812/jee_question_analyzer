"""Bounded local SQLite history. Requests are never automatically replayed."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
from .schemas import Result

DEFAULT_PATH = Path(__file__).resolve().parents[2] / ".local" / "history.sqlite3"


def connect(path=DEFAULT_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, created TEXT DEFAULT CURRENT_TIMESTAMP, question TEXT, result TEXT)")
    return db


def save(question: str, result: Result, path=DEFAULT_PATH):
    with closing(connect(path)) as db, db:
        db.execute("INSERT INTO history(question,result) VALUES (?,?)", (question, result.model_dump_json()))
        db.execute("DELETE FROM history WHERE id NOT IN (SELECT id FROM history ORDER BY id DESC LIMIT 100)")


def recent(path=DEFAULT_PATH):
    with closing(connect(path)) as db:
        rows = db.execute("SELECT created,question,result FROM history ORDER BY id DESC LIMIT 20").fetchall()
    return [{"created": row[0], "question": row[1], "result": json.loads(row[2])} for row in rows]


def clear(path=DEFAULT_PATH):
    with closing(connect(path)) as db, db:
        db.execute("DELETE FROM history")
