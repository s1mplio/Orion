from threading import Thread
from typing import Optional

from app.services.pipeline import run_pipeline
from app.services.job_manager import job_manager


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
    """

    # =====================================================
    # START RESEARCH
    # =====================================================

    def start_research(
        self,
        question: str,
    ) -> Optional[str]:

        if not question:
            return None

        question = question.strip()

        if not question:
            return None

        # -------------------------------------------------
        # Create shared research job
        # -------------------------------------------------

        job_id = (
            job_manager.create_job(
                question
            )
        )

        # -------------------------------------------------
        # Run Research V2 asynchronously
        # -------------------------------------------------

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

        print(
            "\n================================"
        )

        print(
            "ORION RESEARCH STARTED"
        )

        print(
            "================================"
        )

        print(
            "Job ID:",
            job_id,
        )

        print(
            "Question:",
            question,
        )

        print(
            "================================\n"
        )

        return job_id

    # =====================================================
    # BACKGROUND PIPELINE
    # =====================================================

    def _pipeline_worker(
        self,
        job_id: str,
        question: str,
    ):

        try:

            state = run_pipeline(
                question,
                job_id,
                job_manager,
            )

            job_manager.complete_job(
                job_id,
                state,
            )

            print(
                "\n================================"
            )

            print(
                "ORION RESEARCH COMPLETED"
            )

            print(
                "================================"
            )

            print(
                "Job ID:",
                job_id,
            )

            print(
                "Question:",
                question,
            )

            print(
                "================================\n"
            )

        except Exception as exc:

            job_manager.fail_job(
                job_id,
                str(exc),
            )

            print(
                "\n================================"
            )

            print(
                "ORION RESEARCH FAILED"
            )

            print(
                "================================"
            )

            print(
                "Job ID:",
                job_id,
            )

            print(
                "Question:",
                question,
            )

            print(
                "Error:",
                repr(exc),
            )

            print(
                "================================\n"
            )

    # =====================================================
    # GET JOB
    # =====================================================

    def get_job(
        self,
        job_id: str,
    ):

        return (
            job_manager.get_job(
                job_id
            )
        )


research_job_service = (
    ResearchJobService()
)