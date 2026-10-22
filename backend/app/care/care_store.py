import json
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock


# backend/data is gitignored.
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

DEFAULT_SETTINGS = {
    "person_name": "",
    # Minutes after the scheduled time before a dose is missed.
    "grace_minutes": "60",
    # Minutes between repeated spoken reminders.
    "repeat_minutes": "10",
    # Local time the daily summary is sent to family.
    "summary_time": "21:00",
}


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


class CareStore:
    """
    SQLite storage for the care companion: medications and
    their doses, tracked objects and where they were seen,
    family contacts, settings and a daily event log.

    Photos live under data/care/photos/ and are deleted after
    the retention period; text records are kept.
    """

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir / "orion_care.db"
        self.photo_dir = self.data_dir / "care" / "photos"

        self.photo_dir.mkdir(parents=True, exist_ok=True)

        # Serializes read-modify-write sequences (dose state
        # changes) between API requests and the scheduler.
        self.lock = RLock()

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
                CREATE TABLE IF NOT EXISTS medications (
                    med_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    dose TEXT NOT NULL DEFAULT '',
                    instructions TEXT NOT NULL DEFAULT '',
                    times TEXT NOT NULL,
                    days TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS doses (
                    dose_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    med_id INTEGER NOT NULL,
                    scheduled_for TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confirmed_at TEXT,
                    method TEXT,
                    late INTEGER NOT NULL DEFAULT 0,
                    photo TEXT,
                    alerted INTEGER NOT NULL DEFAULT 0,
                    UNIQUE (med_id, scheduled_for)
                );

                CREATE TABLE IF NOT EXISTS tracked_objects (
                    object_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sightings (
                    sighting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    object_id INTEGER NOT NULL,
                    seen_at TEXT NOT NULL,
                    location TEXT NOT NULL,
                    photo TEXT
                );

                CREATE INDEX IF NOT EXISTS sightings_object
                ON sightings (object_id, sighting_id);

                CREATE TABLE IF NOT EXISTS contacts (
                    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    telegram_chat_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS summaries (
                    day TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    sent_at TEXT
                );
                """
            )

    # =====================================================
    # SETTINGS
    # =====================================================

    def get_settings(self):
        settings = dict(DEFAULT_SETTINGS)

        with self._connect() as db:
            for row in db.execute("SELECT key, value FROM settings"):
                settings[row["key"]] = row["value"]

        return settings

    def update_settings(self, values):
        with self._connect() as db:
            for key, value in values.items():
                if key in DEFAULT_SETTINGS and value is not None:
                    db.execute(
                        """
                        INSERT INTO settings (key, value) VALUES (?, ?)
                        ON CONFLICT(key) DO UPDATE SET value = excluded.value
                        """,
                        (key, str(value)),
                    )

        return self.get_settings()

    def setting_int(self, key):
        try:
            return int(self.get_settings()[key])
        except (KeyError, ValueError):
            return int(DEFAULT_SETTINGS[key])

    # =====================================================
    # MEDICATIONS
    # =====================================================

    @staticmethod
    def _med_row(row):
        med = dict(row)
        med["times"] = json.loads(med["times"])
        med["days"] = json.loads(med["days"])
        med["active"] = bool(med["active"])
        return med

    def add_medication(self, name, dose, instructions, times, days):
        with self._connect() as db:
            cursor = db.execute(
                """
                INSERT INTO medications (
                    name, dose, instructions, times, days, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    dose,
                    instructions,
                    json.dumps(sorted(times)),
                    json.dumps(sorted(days)),
                    now_iso(),
                ),
            )

        return self.get_medication(cursor.lastrowid)

    def update_medication(self, med_id, name, dose, instructions, times, days):
        with self.lock, self._connect() as db:
            db.execute(
                """
                UPDATE medications
                SET name = ?, dose = ?, instructions = ?,
                    times = ?, days = ?
                WHERE med_id = ?
                """,
                (
                    name,
                    dose,
                    instructions,
                    json.dumps(sorted(times)),
                    json.dumps(sorted(days)),
                    med_id,
                ),
            )

            # Future doses follow the new schedule; past and
            # confirmed doses stay as recorded.
            db.execute(
                """
                DELETE FROM doses
                WHERE med_id = ? AND status = 'pending'
                  AND scheduled_for > ?
                """,
                (med_id, now_iso()),
            )

        return self.get_medication(med_id)

    def deactivate_medication(self, med_id):
        with self.lock, self._connect() as db:
            db.execute(
                "UPDATE medications SET active = 0 WHERE med_id = ?",
                (med_id,),
            )

            db.execute(
                """
                DELETE FROM doses
                WHERE med_id = ? AND status = 'pending'
                """,
                (med_id,),
            )

    def get_medication(self, med_id):
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM medications WHERE med_id = ?",
                (med_id,),
            ).fetchone()

        return self._med_row(row) if row else None

    def list_medications(self, active_only=True):
        query = "SELECT * FROM medications"

        if active_only:
            query += " WHERE active = 1"

        with self._connect() as db:
            rows = db.execute(query + " ORDER BY name").fetchall()

        return [self._med_row(row) for row in rows]

    # =====================================================
    # DOSES
    # =====================================================

    def create_dose(self, med_id, scheduled_for):
        """Insert a pending dose unless it already exists."""
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO doses (med_id, scheduled_for, status)
                VALUES (?, ?, 'pending')
                """,
                (med_id, scheduled_for),
            )

    def get_dose(self, dose_id):
        with self._connect() as db:
            row = db.execute(
                """
                SELECT d.*, m.name, m.dose AS amount, m.instructions
                FROM doses d JOIN medications m ON m.med_id = d.med_id
                WHERE d.dose_id = ?
                """,
                (dose_id,),
            ).fetchone()

        return dict(row) if row else None

    def doses_between(self, start, end):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT d.*, m.name, m.dose AS amount, m.instructions
                FROM doses d JOIN medications m ON m.med_id = d.med_id
                WHERE d.scheduled_for >= ? AND d.scheduled_for < ?
                ORDER BY d.scheduled_for, m.name
                """,
                (start, end),
            ).fetchall()

        return [dict(row) for row in rows]

    def doses_for_day(self, day):
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)
        return self.doses_between(
            start.isoformat(timespec="seconds"),
            end.isoformat(timespec="seconds"),
        )

    def mark_taken(self, dose_id, method, late, photo):
        with self._connect() as db:
            db.execute(
                """
                UPDATE doses
                SET status = 'taken', confirmed_at = ?, method = ?,
                    late = ?, photo = ?
                WHERE dose_id = ?
                """,
                (now_iso(), method, 1 if late else 0, photo, dose_id),
            )

    def mark_missed(self, dose_id):
        with self._connect() as db:
            db.execute(
                "UPDATE doses SET status = 'missed' WHERE dose_id = ?",
                (dose_id,),
            )

    def mark_alerted(self, dose_id):
        with self._connect() as db:
            db.execute(
                "UPDATE doses SET alerted = 1 WHERE dose_id = ?",
                (dose_id,),
            )

    def overdue_pending(self, cutoff):
        """Pending doses scheduled before the cutoff."""
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT d.*, m.name, m.dose AS amount, m.instructions
                FROM doses d JOIN medications m ON m.med_id = d.med_id
                WHERE d.status = 'pending' AND d.scheduled_for < ?
                """,
                (cutoff,),
            ).fetchall()

        return [dict(row) for row in rows]

    # =====================================================
    # TRACKED OBJECTS
    # =====================================================

    def add_object(self, name):
        with self._connect() as db:
            db.execute(
                """
                INSERT OR IGNORE INTO tracked_objects (name, created_at)
                VALUES (?, ?)
                """,
                (name, now_iso()),
            )

        return self.list_objects()

    def delete_object(self, object_id):
        with self._connect() as db:
            db.execute(
                "DELETE FROM sightings WHERE object_id = ?",
                (object_id,),
            )
            db.execute(
                "DELETE FROM tracked_objects WHERE object_id = ?",
                (object_id,),
            )

    def list_objects(self):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT o.object_id, o.name,
                       s.seen_at AS last_seen_at,
                       s.location AS last_location,
                       s.photo AS last_photo
                FROM tracked_objects o
                LEFT JOIN sightings s ON s.sighting_id = (
                    SELECT MAX(sighting_id) FROM sightings
                    WHERE object_id = o.object_id
                )
                ORDER BY o.name
                """
            ).fetchall()

        return [dict(row) for row in rows]

    def add_sighting(self, object_id, location, photo):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO sightings (object_id, seen_at, location, photo)
                VALUES (?, ?, ?, ?)
                """,
                (object_id, now_iso(), location, photo),
            )

    # =====================================================
    # CONTACTS
    # =====================================================

    def add_contact(self, name, chat_id):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO contacts (name, telegram_chat_id, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(telegram_chat_id) DO UPDATE SET name = excluded.name
                """,
                (name, str(chat_id), now_iso()),
            )

        return self.list_contacts()

    def delete_contact(self, contact_id):
        with self._connect() as db:
            db.execute(
                "DELETE FROM contacts WHERE contact_id = ?",
                (contact_id,),
            )

    def list_contacts(self):
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM contacts ORDER BY name"
            ).fetchall()

        return [dict(row) for row in rows]

    # =====================================================
    # EVENTS + SUMMARIES
    # =====================================================

    def log_event(self, kind, text):
        with self._connect() as db:
            db.execute(
                "INSERT INTO events (at, kind, text) VALUES (?, ?, ?)",
                (now_iso(), kind, text),
            )

    def events_for_day(self, day):
        start = datetime.combine(day, datetime.min.time())
        end = start + timedelta(days=1)

        with self._connect() as db:
            rows = db.execute(
                """
                SELECT * FROM events WHERE at >= ? AND at < ?
                ORDER BY event_id
                """,
                (
                    start.isoformat(timespec="seconds"),
                    end.isoformat(timespec="seconds"),
                ),
            ).fetchall()

        return [dict(row) for row in rows]

    def get_summary(self, day):
        with self._connect() as db:
            row = db.execute(
                "SELECT * FROM summaries WHERE day = ?",
                (day.isoformat(),),
            ).fetchone()

        return dict(row) if row else None

    def save_summary(self, day, text, sent):
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO summaries (day, text, sent_at) VALUES (?, ?, ?)
                ON CONFLICT(day) DO UPDATE SET
                    text = excluded.text,
                    sent_at = COALESCE(excluded.sent_at, summaries.sent_at)
                """,
                (day.isoformat(), text, now_iso() if sent else None),
            )

    # =====================================================
    # PHOTOS
    # =====================================================

    def save_photo(self, prefix, image_bytes):
        """Store a JPEG and return its file name."""
        name = (
            f"{prefix}-{datetime.now():%Y%m%d%H%M%S}-"
            f"{uuid.uuid4().hex[:8]}.jpg"
        )
        (self.photo_dir / name).write_bytes(image_bytes)
        return name

    def photo_path(self, name):
        """Resolve a stored photo name, refusing path tricks."""
        if not name or "/" in name or "\\" in name or ".." in name:
            return None

        path = self.photo_dir / name
        return path if path.is_file() else None

    def delete_photos_older_than(self, days):
        cutoff = datetime.now() - timedelta(days=days)
        removed = 0

        for path in self.photo_dir.glob("*.jpg"):
            if datetime.fromtimestamp(path.stat().st_mtime) < cutoff:
                path.unlink(missing_ok=True)
                removed += 1

        if removed:
            # Text records stay; only their photo links go.
            existing = {path.name for path in self.photo_dir.glob("*.jpg")}

            with self._connect() as db:
                for table, key in (("sightings", "sighting_id"), ("doses", "dose_id")):
                    for row in db.execute(
                        f"SELECT {key}, photo FROM {table} WHERE photo IS NOT NULL"
                    ).fetchall():
                        if row["photo"] not in existing:
                            db.execute(
                                f"UPDATE {table} SET photo = NULL WHERE {key} = ?",
                                (row[key],),
                            )

        return removed


care_store = CareStore()
