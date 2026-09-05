import threading
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.services.pipeline import run_pipeline
from app.services.job_manager import job_manager


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="Orion Research API",
    version="2.0",
    description=(
        "Backend API for Orion Research V2."
    ),
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class ResearchRequest(BaseModel):
    question: str


# =========================================================
# HEALTH
# =========================================================

@app.get("/")
def root():
    return {
        "service": "Orion Research API",
        "version": "2.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "status": "ok"
    }


# =========================================================
# START RESEARCH
# =========================================================

@app.post("/research")
def start_research(
    request: ResearchRequest
):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Research question cannot be empty.",
        )

    # -----------------------------------------------------
    # Create job
    # -----------------------------------------------------

    job_id = job_manager.create_job(
        question
    )

    job_manager.add_log(
        job_id,
        "Research job created.",
    )

    # -----------------------------------------------------
    # Run pipeline in background thread
    # -----------------------------------------------------

    thread = threading.Thread(
        target=_run_research_job,
        args=(
            job_id,
            question,
        ),
        daemon=True,
        name=f"ResearchJob-{job_id[:8]}",
    )

    thread.start()

    return {
        "job_id": job_id,
        "status": "running",
        "question": question,
    }


# =========================================================
# BACKGROUND PIPELINE
# =========================================================

def _run_research_job(
    job_id: str,
    question: str,
):
    try:

        job_manager.add_log(
            job_id,
            "Research V2 pipeline started.",
        )

        state = run_pipeline(
            question=question,
            job_id=job_id,
            job_manager=job_manager,
        )

        job_manager.complete_job(
            job_id,
            state,
        )

    except Exception as exc:

        print(
            "\n[RESEARCH API] PIPELINE ERROR:"
        )

        print(
            repr(exc)
        )

        job_manager.fail_job(
            job_id,
            exc,
        )


# =========================================================
# JOB STATUS
# =========================================================

@app.get(
    "/research/{job_id}/status"
)
def research_status(
    job_id: str
):
    job = job_manager.get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Research job not found.",
        )

    return {
        "job_id": job_id,
        "question": job.get(
            "question",
            "",
        ),
        "status": job.get(
            "status",
            "unknown",
        ),
        "progress": job.get(
            "progress",
            0,
        ),
        "current_step": job.get(
            "current_step",
            "",
        ),
        "logs": job.get(
            "logs",
            [],
        ),
        "error": job.get(
            "error",
        ),
    }


# =========================================================
# FINAL RESULT
# =========================================================

@app.get(
    "/research/{job_id}/result"
)
def research_result(
    job_id: str
):
    job = job_manager.get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Research job not found.",
        )

    status = job.get(
        "status"
    )

    if status == "failed":
        raise HTTPException(
            status_code=500,
            detail=job.get(
                "error",
                "Research pipeline failed.",
            ),
        )

    if status != "completed":
        return {
            "job_id": job_id,
            "status": status,
            "progress": job.get(
                "progress",
                0,
            ),
            "current_step": job.get(
                "current_step",
                "",
            ),
            "ready": False,
        }

    state = job.get(
        "state"
    )

    if state is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Research completed but "
                "no ResearchState was stored."
            ),
        )

    return {
        "job_id": job_id,
        "status": "completed",
        "ready": True,
        "result": _serialize_research_state(
            state
        ),
    }


# =========================================================
# SERIALIZATION
# =========================================================

def _serialize_research_state(
    state
):
    """
    Convert ResearchState into JSON-safe data for
    the Next.js frontend.

    This intentionally exposes the important Research V2
    stages while keeping the Python model objects inside
    the backend.
    """

    return {
        "question": getattr(
            state,
            "question",
            "",
        ),

        "sub_questions": list(
            getattr(
                state,
                "sub_questions",
                [],
            )
            or []
        ),

        "papers": [
            _serialize_paper(
                paper
            )
            for paper in (
                getattr(
                    state,
                    "papers",
                    [],
                )
                or []
            )
        ],

        "evidence": [
            _serialize_evidence(
                evidence
            )
            for evidence in (
                getattr(
                    state,
                    "evidence",
                    [],
                )
                or []
            )
        ],

        "critic": _serialize_object(
            getattr(
                state,
                "critic_results",
                None,
            )
        ),

        "synthesis": _serialize_object(
            getattr(
                state,
                "synthesis",
                None,
            )
        ),

        "hypothesis": _serialize_object(
            getattr(
                state,
                "hypothesis",
                None,
            )
        ),

        "hypothesis_review": _serialize_object(
            getattr(
                state,
                "hypothesis_review",
                None,
            )
        ),

        "experiment": _serialize_object(
            getattr(
                state,
                "experiments",
                None,
            )
        ),

        "final_report": _make_json_safe(
            getattr(
                state,
                "final_report",
                None,
            )
        ),
    }


def _serialize_paper(
    paper
):
    return {
        "title": getattr(
            paper,
            "title",
            "",
        ),

        "authors": getattr(
            paper,
            "authors",
            [],
        ),

        "year": getattr(
            paper,
            "year",
            None,
        ),

        "url": getattr(
            paper,
            "url",
            None,
        ),

        "doi": getattr(
            paper,
            "doi",
            None,
        ),

        "citation_count": getattr(
            paper,
            "citation_count",
            0,
        ),

        "landing_page_url": getattr(
            paper,
            "landing_page_url",
            None,
        ),

        "pdf_url": getattr(
            paper,
            "pdf_url",
            None,
        ),

        "is_open_access": getattr(
            paper,
            "is_open_access",
            False,
        ),

        "open_access_status": getattr(
            paper,
            "open_access_status",
            None,
        ),

        "source_name": getattr(
            paper,
            "source_name",
            None,
        ),

        "full_text_available": getattr(
            paper,
            "full_text_available",
            False,
        ),
    }


def _serialize_evidence(
    evidence
):
    if hasattr(
        evidence,
        "to_dict",
    ):
        try:
            return _make_json_safe(
                evidence.to_dict()
            )

        except Exception:
            pass

    return {
        "paper_title": getattr(
            evidence,
            "paper_title",
            "",
        ),

        "findings": getattr(
            evidence,
            "findings",
            [],
        ),

        "methods": getattr(
            evidence,
            "methods",
            "",
        ),

        "limitations": getattr(
            evidence,
            "limitations",
            "",
        ),

        "relevance": getattr(
            evidence,
            "relevance",
            "",
        ),

        "query": getattr(
            evidence,
            "query",
            None,
        ),

        "source_type": getattr(
            evidence,
            "source_type",
            "unknown",
        ),

        "cited_chunk_ids": getattr(
            evidence,
            "cited_chunk_ids",
            [],
        ),

        "retrieved_chunks": getattr(
            evidence,
            "retrieved_chunks",
            [],
        ),
    }


def _serialize_object(
    obj
):
    if obj is None:
        return None

    if isinstance(
        obj,
        dict,
    ):
        return _make_json_safe(
            obj
        )

    if hasattr(
        obj,
        "__dict__",
    ):
        return _make_json_safe(
            vars(obj)
        )

    return _make_json_safe(
        obj
    )


def _make_json_safe(
    value: Any
):
    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key): _make_json_safe(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _make_json_safe(
                item
            )
            for item in value
        ]

    if hasattr(
        value,
        "__dict__",
    ):
        return _make_json_safe(
            vars(value)
        )

    return str(
        value
    )


# =========================================================
# DEVELOPMENT ENTRY POINT
# =========================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "app.api_main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )