import json
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock


# backend/data is gitignored.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class LabStore:
    """
    SQLite storage for lab sessions and their log entries.

    Entry snapshots are saved as JPEG files under
    data/lab_sessions/<session_id>/<entry_id>.jpg.
    """

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "orion_lab.db"
        self.image_dir = self.data_dir / "lab_sessions"

        self.image_dir.mkdir(parents=True, exist_ok=True)

        # Serializes read-modify-write sequences such as
        # merging a frame into the previous entry.
        self.lock = Lock()

        self._init_db()

    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self):
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS lab_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    protocol TEXT NOT NULL DEFAULT '',
                    research_job_id TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    ended_at TEXT,
                    notebook TEXT
                );

                CREATE TABLE IF NOT EXISTS lab_entries (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT NOT NULL,
                    activity TEXT NOT NULL,
                    details TEXT NOT NULL,
                    has_image INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS lab_entries_session
                ON lab_entries (session_id, entry_id);
                """
            )

    @staticmethod
    def _now():
        return datetime.now().isoformat(timespec="seconds")

    @staticmethod
    def _session_row(row):
        if row is None:
            return None

        session = dict(row)
        session["notebook"] = (
            json.loads(session["notebook"])
            if session["notebook"]
            else None
        )
        return session

    @staticmethod
    def _entry_row(row):
        entry = dict(row)
        entry["details"] = json.loads(entry["details"])
        entry["has_image"] = bool(entry["has_image"])
        return entry

    # =====================================================
    # SESSIONS
    # =====================================================

    def create_session(self, title, protocol="", research_job_id=None):
        session_id = str(uuid.uuid4())

        with self._connect() as db:
            db.execute(
                """
                INSERT INTO lab_sessions (
                    session_id, title, protocol, research_job_id,
                    status, created_at
                )
                VALUES (?, ?, ?, ?, 'active', ?)
                """,
                (
                    session_id,
                    title,
                    protocol or "",
                    research_job_id or None,
                    self._now(),
                ),
            )

        return self.get_session(session_id)

    def get_session(self, session_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM lab_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()

        return self._session_row(row)

    def list_sessions(self, limit=100):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT s.session_id, s.title, s.status, s.created_at,
                       s.ended_at, s.research_job_id,
                       COUNT(e.entry_id) AS entry_count
                FROM lab_sessions s
                LEFT JOIN lab_entries e ON e.session_id = s.session_id
                GROUP BY s.session_id
                ORDER BY s.created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [dict(row) for row in rows]

    def end_session(self, session_id):
        with self._connect() as db:
            db.execute(
                """
                UPDATE lab_sessions
                SET status = 'ended',
                    ended_at = COALESCE(ended_at, ?)
                WHERE session_id = ?
                """,
                (self._now(), session_id),
            )

    def save_notebook(self, session_id, notebook):
        with self._connect() as db:
            db.execute(
                "UPDATE lab_sessions SET notebook = ? WHERE session_id = ?",
                (json.dumps(notebook, ensure_ascii=False), session_id),
            )

    def delete_session(self, session_id):
        with self._connect() as db:
            db.execute(
                "DELETE FROM lab_entries WHERE session_id = ?",
                (session_id,),
            )
            cursor = db.execute(
                "DELETE FROM lab_sessions WHERE session_id = ?",
                (session_id,),
            )

        shutil.rmtree(
            self.session_image_dir(session_id),
            ignore_errors=True,
        )

        return cursor.rowcount > 0

    # =====================================================
    # ENTRIES
    # =====================================================

    def add_entry(self, session_id, kind, activity, details, image_bytes=None):
        now = self._now()

        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO lab_entries (
                    session_id, kind, started_at, ended_at,
                    activity, details, has_image
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    kind,
                    now,
                    now,
                    activity,
                    json.dumps(details, ensure_ascii=False),
                    1 if image_bytes else 0,
                ),
            )
            entry_id = cursor.lastrowid

        if image_bytes:
            path = self.image_path(session_id, entry_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(image_bytes)

        return self.get_entry(session_id, entry_id)

    def extend_entry(self, session_id, entry_id, details):
        with self._connect() as db:
            db.execute(
                """
                UPDATE lab_entries
                SET ended_at = ?, details = ?
                WHERE session_id = ? AND entry_id = ?
                """,
                (
                    self._now(),
                    json.dumps(details, ensure_ascii=False),
                    session_id,
                    entry_id,
                ),
            )

        return self.get_entry(session_id, entry_id)

    def get_entry(self, session_id, entry_id):
        with self._connect() as db:
            row = db.execute(
                """
                SELECT * FROM lab_entries
                WHERE session_id = ? AND entry_id = ?
                """,
                (session_id, entry_id),
            ).fetchone()

        return self._entry_row(row) if row else None

    def list_entries(self, session_id):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM lab_entries
                WHERE session_id = ?
                ORDER BY entry_id
                """,
                (session_id,),
            ).fetchall()

        return [self._entry_row(row) for row in rows]

    def last_observation(self, session_id):
        with self._connect() as db:
            row = db.execute(
                """
                SELECT * FROM lab_entries
                WHERE session_id = ? AND kind = 'observation'
                ORDER BY entry_id DESC
                LIMIT 1
                """,
                (session_id,),
            ).fetchone()

        return self._entry_row(row) if row else None

    # =====================================================
    # IMAGES
    # =====================================================

    def session_image_dir(self, session_id):
        return self.image_dir / session_id

    def image_path(self, session_id, entry_id):
        return self.session_image_dir(session_id) / f"{int(entry_id)}.jpg"


lab_store = LabStore()
