import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from app.services.job_manager import job_manager
from app.services.report_export import build_docx
from app.services.research_job_service import (
    ResearchQuestionError,
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

    try:
        job_id = (
            research_job_service
            .start_research(
                question
            )
        )
    except ResearchQuestionError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
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
        "status": "queued",
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

def _completed_result(job_id: str) -> dict:
    job = job_manager.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    if job["status"] == "failed":
        raise HTTPException(
            status_code=500,
            detail=job.get("error")
            or "Research pipeline failed.",
        )

    if job["status"] != "completed":
        return None

    result = job.get("result")

    if result is None:
        raise HTTPException(
            status_code=500,
            detail="Research completed but its result is missing.",
        )

    return result


@router.get(
    "/research/{job_id}/result"
)
def get_result(
    job_id: str,
):

    result = _completed_result(job_id)

    if result is None:
        return {
            "job_id": job_id,
            "status": "running",
            "ready": False,
            "message": "Pipeline still running.",
        }

    return {
        "job_id": job_id,
        "status": "completed",
        "ready": True,
        "result": result,
    }


# =========================================================
# REPORT HISTORY
# =========================================================

@router.get("/research")
def list_research():

    return {
        "jobs": job_manager.list_jobs(),
    }


@router.delete("/research/{job_id}")
def delete_research(
    job_id: str,
):

    job = job_manager.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found",
        )

    if job["status"] in ("running", "queued"):
        raise HTTPException(
            status_code=409,
            detail="Research is still running.",
        )

    job_manager.delete_job(job_id)

    return {"deleted": True}


# =========================================================
# EXPORT
# =========================================================

@router.get("/research/{job_id}/export/docx")
def export_docx(
    job_id: str,
):

    result = _completed_result(job_id)

    if result is None:
        raise HTTPException(
            status_code=409,
            detail="Research is still running.",
        )

    content = build_docx(result)

    slug = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        result.get("question") or "orion-review",
    ).strip("-")[:60] or "orion-review"

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{slug}.docx"'
            ),
        },
    )
