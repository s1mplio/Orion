from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any

from app.services.job_manager import job_manager
from app.services.research_job_service import (
    research_job_service,
)


router = APIRouter()


# =========================================================
# REQUEST MODEL
# =========================================================

class ResearchRequest(BaseModel):
    question: str


# =========================================================
# START RESEARCH
# =========================================================

@router.post("/research")
def research(
    request: ResearchRequest,
):

    question = request.question.strip()

    if not question:

        raise HTTPException(
            status_code=400,
            detail=(
                "Research question cannot be empty."
            ),
        )

    job_id = (
        research_job_service
        .start_research(
            question
        )
    )

    if not job_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "Research question cannot be empty."
            ),
        )

    return {
        "job_id": job_id,
        "status": "running",
        "question": question,
    }


# =========================================================
# JOB STATUS
# =========================================================

@router.get(
    "/research/{job_id}/status"
)
def get_status(
    job_id: str,
):

    job = (
        job_manager.get_job(
            job_id
        )
    )

    if job is None:

        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    question = job.get(
        "question",
        "",
    )

    if job.get("state") is not None:

        question = getattr(
            job["state"],
            "question",
            question,
        )

    return {
        "job_id": job_id,

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

        "question": question,

        "error": job.get(
            "error"
        ),
    }


# =========================================================
# FINAL RESULT
# =========================================================

@router.get(
    "/research/{job_id}/result"
)
def get_result(
    job_id: str,
):

    job = (
        job_manager.get_job(
            job_id
        )
    )

    if job is None:

        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    if job["status"] == "failed":

        raise HTTPException(
            status_code=500,
            detail=job.get(
                "error",
                "Research pipeline failed.",
            ),
        )

    if job["status"] != "completed":

        return {
            "job_id": job_id,
            "status": job["status"],
            "ready": False,
            "message": (
                "Pipeline still running."
            ),
        }

    state = job.get(
        "state"
    )

    if state is None:

        raise HTTPException(
            status_code=500,
            detail=(
                "Research completed but "
                "state is missing."
            ),
        )

    # =====================================================
    # SERIALIZE COMPLETE RESEARCH V2 STATE
    # =====================================================

    result = {
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
            serialize_paper(
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
            serialize_evidence(
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

        "critic": serialize_object(
            getattr(
                state,
                "critic_results",
                None,
            )
        ),

        "synthesis": serialize_object(
            getattr(
                state,
                "synthesis",
                None,
            )
        ),

        "hypothesis": serialize_object(
            getattr(
                state,
                "hypothesis",
                None,
            )
        ),

        "hypothesis_review": (
            serialize_object(
                getattr(
                    state,
                    "hypothesis_review",
                    None,
                )
            )
        ),

        "experiment": serialize_object(
            getattr(
                state,
                "experiments",
                None,
            )
        ),

        "final_report": make_json_safe(
            getattr(
                state,
                "final_report",
                None,
            )
        ),
    }

    print(
        "\n=============================="
    )

    print(
        "GET RESULT"
    )

    print(
        "Requested Job:",
        job_id,
    )

    print(
        "State Question:",
        result["question"],
    )

    print(
        "State Object ID:",
        id(state),
    )

    print(
        "Papers:",
        len(result["papers"]),
    )

    print(
        "Evidence:",
        len(result["evidence"]),
    )

    print(
        "Final Report Present:",
        (
            result["final_report"]
            is not None
        ),
    )

    return {
        "job_id": job_id,
        "status": "completed",
        "ready": True,
        "result": result,
    }


# =========================================================
# PAPER SERIALIZER
# =========================================================

def serialize_paper(
    paper,
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


# =========================================================
# EVIDENCE SERIALIZER
# =========================================================

def serialize_evidence(
    evidence,
):

    if hasattr(
        evidence,
        "to_dict",
    ):

        try:

            return make_json_safe(
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


# =========================================================
# GENERIC OBJECT SERIALIZER
# =========================================================

def serialize_object(
    obj,
):

    if obj is None:

        return None

    if isinstance(
        obj,
        dict,
    ):

        return make_json_safe(
            obj
        )

    if hasattr(
        obj,
        "__dict__",
    ):

        return make_json_safe(
            vars(obj)
        )

    return make_json_safe(
        obj
    )


# =========================================================
# JSON SAFE CONVERTER
# =========================================================

def make_json_safe(
    value: Any,
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
            str(key): make_json_safe(
                item
            )
            for key, item
            in value.items()
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
            make_json_safe(
                item
            )
            for item in value
        ]

    if hasattr(
        value,
        "__dict__",
    ):

        return make_json_safe(
            vars(value)
        )

    return str(
        value
    )