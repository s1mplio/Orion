from threading import BoundedSemaphore, Thread
from typing import Optional

from app.services.job_manager import job_manager
from app.services.llm_service import (
    start_usage_tracking,
    stop_usage_tracking,
)
from app.services.pipeline import run_pipeline
from app.services.research_settings import (
    MAX_CONCURRENT_JOBS,
    MAX_QUESTION_CHARS,
)


class ResearchQuestionError(ValueError):
    """The research question was rejected before starting."""


class ResearchJobService:
    """
    Shared entry point for starting Research V2 jobs.

    This service can be used by:

        - FastAPI
        - Orion Companion
        - Voice commands
        - Future tools/interfaces

    All callers therefore use the same:

        JobManager
        Research V2 pipeline
        background execution
        progress tracking
        completion handling
        failure handling

    At most MAX_CONCURRENT_JOBS pipelines run at once;
    further jobs wait in the "queued" state.
    """

    def __init__(self):
        self._slots = BoundedSemaphore(
            MAX_CONCURRENT_JOBS
        )

    # =====================================================
    # START RESEARCH
    # =====================================================

    def start_research(
        self,
        question: str,
    ) -> Optional[str]:

        question = (question or "").strip()

        if not question:
            return None

        if len(question) > MAX_QUESTION_CHARS:
            raise ResearchQuestionError(
                f"Research question is too long "
                f"({len(question)} characters). "
                f"The limit is {MAX_QUESTION_CHARS}."
            )

        job_id = job_manager.create_job(
            question
        )

        thread = Thread(
            target=self._pipeline_worker,
            args=(
                job_id,
                question,
            ),
            daemon=True,
            name=f"orion-research-{job_id[:8]}",
        )

        thread.start()

        print("\n================================")
        print("ORION RESEARCH QUEUED")
        print("================================")
        print("Job ID:", job_id)
        print("Question:", question)
        print("================================\n")

        return job_id

    # =====================================================
    # BACKGROUND PIPELINE
    # =====================================================

    def _pipeline_worker(
        self,
        job_id: str,
        question: str,
    ):

        with self._slots:

            job_manager.start_job(job_id)

            start_usage_tracking()

            try:

                state = run_pipeline(
                    question,
                    job_id,
                    job_manager,
                )

                state.usage = stop_usage_tracking()

                job_manager.complete_job(
                    job_id,
                    state,
                )

                print("\n================================")
                print("ORION RESEARCH COMPLETED")
                print("================================")
                print("Job ID:", job_id)
                print("Question:", question)
                print("Model usage:", state.usage)
                print("================================\n")

            except Exception as exc:

                stop_usage_tracking()

                job_manager.fail_job(
                    job_id,
                    str(exc),
                )

                print("\n================================")
                print("ORION RESEARCH FAILED")
                print("================================")
                print("Job ID:", job_id)
                print("Question:", question)
                print("Error:", repr(exc))
                print("================================\n")

    # =====================================================
    # GET JOB
    # =====================================================

    def get_job(
        self,
        job_id: str,
    ):

        return job_manager.get_job(
            job_id
        )


research_job_service = ResearchJobService()
