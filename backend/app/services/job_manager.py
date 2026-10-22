import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from threading import Lock

from app.services.research_serializer import serialize_state


# backend/data/orion_research.db (backend/data is gitignored)
DEFAULT_DB_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "orion_research.db"
)


class JobManager:
    """
    Tracks research jobs.

    Live jobs are kept in memory for fast status polling,
    and every change is written to SQLite so completed
    reports survive backend restarts.
    """

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.jobs = {}
        self.lock = Lock()

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    # =====================================================
    # DATABASE
    # =====================================================

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=30)

    def _init_db(self):
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS research_jobs (
                    job_id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress INTEGER NOT NULL,
                    current_step TEXT,
                    logs TEXT NOT NULL,
                    error TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            # A job that was running when the backend stopped
            # can never finish: its worker thread is gone.
            db.execute(
                """
                UPDATE research_jobs
                SET status = 'failed',
                    error = 'Interrupted because the backend restarted.',
                    updated_at = ?
                WHERE status IN ('running', 'queued')
                """,
                (datetime.now().isoformat(),),
            )

    def _save(self, job_id):
        job = self.jobs[job_id]

        result = job.get("result")

        with self._connect() as db:
            db.execute(
                """
                INSERT INTO research_jobs (
                    job_id, question, status, progress,
                    current_step, logs, error, result,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    status = excluded.status,
                    progress = excluded.progress,
                    current_step = excluded.current_step,
                    logs = excluded.logs,
                    error = excluded.error,
                    result = excluded.result,
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    job["question"],
                    job["status"],
                    job["progress"],
                    job["current_step"],
                    json.dumps(job["logs"], ensure_ascii=False),
                    job["error"],
                    json.dumps(result, ensure_ascii=False)
                    if result is not None
                    else None,
                    job["created_at"],
                    datetime.now().isoformat(),
                ),
            )

    def _load(self, job_id):
        with self._connect() as db:
            row = db.execute(
                """
                SELECT question, status, progress, current_step,
                       logs, error, result, created_at
                FROM research_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        (
            question, status, progress, current_step,
            logs, error, result, created_at,
        ) = row

        return {
            "status": status,
            "progress": progress,
            "current_step": current_step,
            "logs": json.loads(logs),
            "state": None,
            "result": json.loads(result) if result else None,
            "question": question,
            "error": error,
            "created_at": created_at,
        }

    # =====================================================
    # JOB LIFECYCLE
    # =====================================================

    def create_job(self, question: str):

        job_id = str(uuid.uuid4())

        with self.lock:

            self.jobs[job_id] = {
                "status": "queued",
                "progress": 0,
                "current_step": "Waiting for a free research slot...",
                "logs": [],
                "state": None,
                "result": None,
                "question": question,
                "error": None,
                "created_at": datetime.now().isoformat(),
            }

            self._save(job_id)

        return job_id

    def start_job(self, job_id):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["status"] = "running"
            self.jobs[job_id]["current_step"] = "Starting..."

        self.add_log(job_id, "Research started.")

    def add_log(self, job_id, message):

        with self.lock:

            if job_id not in self.jobs:
                return

            timestamp = datetime.now().strftime("%H:%M:%S")

            self.jobs[job_id]["logs"].append({
                "time": timestamp,
                "message": message
            })

            self._save(job_id)

    def update_progress(self, job_id, step, progress):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["current_step"] = step
            self.jobs[job_id]["progress"] = progress

        self.add_log(job_id, step)

    def complete_job(self, job_id, state):

        # Serialize outside the lock; it can take a moment.
        result = serialize_state(state)

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["progress"] = 100
            self.jobs[job_id]["current_step"] = "Completed"
            self.jobs[job_id]["state"] = state
            self.jobs[job_id]["result"] = result

        self.add_log(job_id, "Research completed successfully.")

    def fail_job(self, job_id, error):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(error)

        self.add_log(job_id, f"Pipeline failed: {error}")

    # =====================================================
    # QUERIES
    # =====================================================

    def get_job(self, job_id):

        with self.lock:
            job = self.jobs.get(job_id)

            if job is not None:
                # Snapshot so callers never iterate a log list
                # that the pipeline thread is appending to.
                snapshot = dict(job)
                snapshot["logs"] = list(job["logs"])
                return snapshot

        return self._load(job_id)

    def list_jobs(self, limit=100):
        with self._connect() as db:
            rows = db.execute(
                """
                SELECT job_id, question, status, progress,
                       error, created_at, updated_at
                FROM research_jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "job_id": job_id,
                "question": question,
                "status": status,
                "progress": progress,
                "error": error,
                "created_at": created_at,
                "updated_at": updated_at,
            }
            for (
                job_id, question, status, progress,
                error, created_at, updated_at,
            ) in rows
        ]

    def delete_job(self, job_id):
        with self.lock:
            job = self.jobs.get(job_id)

            if job is not None and job["status"] in ("running", "queued"):
                return False

            self.jobs.pop(job_id, None)

            with self._connect() as db:
                cursor = db.execute(
                    "DELETE FROM research_jobs WHERE job_id = ?",
                    (job_id,),
                )

            return cursor.rowcount > 0


job_manager = JobManager()
