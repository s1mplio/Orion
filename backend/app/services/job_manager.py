import uuid
from threading import Lock
from datetime import datetime


class JobManager:

    def __init__(self):
        self.jobs = {}
        self.lock = Lock()

    def create_job(self, question: str):

        job_id = str(uuid.uuid4())

        with self.lock:

            self.jobs[job_id] = {
            "status": "running",
            "progress": 0,
            "current_step": "Starting...",
            "logs": [],
            "state": None,
            "question": question,
            "error": None
        }

        return job_id


    def add_log(self, job_id, message):

        with self.lock:

            if job_id not in self.jobs:
                return

            timestamp = datetime.now().strftime("%H:%M:%S")

            self.jobs[job_id]["logs"].append({
                "time": timestamp,
                "message": message
            })

    def update_progress(self, job_id, step, progress):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["current_step"] = step
            self.jobs[job_id]["progress"] = progress

        
        self.add_log(job_id, step)

    def complete_job(self, job_id, state):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["status"] = "completed"
            self.jobs[job_id]["progress"] = 100
            self.jobs[job_id]["current_step"] = "Completed"
            self.jobs[job_id]["state"] = state

        self.add_log(job_id, "Research completed successfully.")

    def fail_job(self, job_id, error):

        with self.lock:

            if job_id not in self.jobs:
                return

            self.jobs[job_id]["status"] = "failed"
            self.jobs[job_id]["error"] = str(error)

        self.add_log(job_id, f"Pipeline failed: {error}")

    def get_job(self, job_id):

        with self.lock:
            return self.jobs.get(job_id)


job_manager = JobManager()