from fastapi import APIRouter
from pydantic import BaseModel
from threading import Thread

from app.services.pipeline import run_pipeline
from app.services.job_manager import job_manager

router = APIRouter()


class ResearchRequest(BaseModel):
    question: str


def pipeline_worker(job_id: str, question: str):

    try:

        state = run_pipeline(
            question,
            job_id,
            job_manager
        )

        job_manager.complete_job(job_id, state)

    except Exception as e:

        job_manager.fail_job(job_id, str(e))

@router.post("/research")
def research(request: ResearchRequest):

    job_id = job_manager.create_job(request.question)

    thread = Thread(
        target=pipeline_worker,
        args=(job_id, request.question)
    )

    thread.start()

    return {
        "job_id": job_id
    }

@router.get("/research/{job_id}/status")
def get_status(job_id: str):

    job = job_manager.get_job(job_id)

    if job is None:
        return {"error": "Job not found"}

    question = job["question"]

    if job["state"] is not None:
        question = job["state"].question

    return {
        "status": job["status"],
        "progress": job["progress"],
        "current_step": job["current_step"],
        "logs": job["logs"],
        "question": question
    }
@router.get("/research/{job_id}/result")
def get_result(job_id: str):

    job = job_manager.get_job(job_id)

    if job is None:
        return {
            "error": "Job not found"
        }

    if job["status"] != "completed":
        return {
            "message": "Pipeline still running."
        }

    state = job["state"]

    papers = []

    for paper in state.papers:

        papers.append({
            "title": paper.title,
            "authors": paper.authors,
            "year": paper.year,
            "url": paper.url,
            "citation_count": paper.citation_count
        })

    report = {
        "title": state.final_report.title,
        "executive_summary": state.final_report.executive_summary,
        "background": state.final_report.background,
        "evidence_summary": state.final_report.evidence_summary,
        "hypothesis": state.final_report.hypothesis,
        "experiment_plan": state.final_report.experiment_plan,
        "conclusion": state.final_report.conclusion,
        "future_work": state.final_report.future_work
    }   
    print("\n==============================")
    print("GET RESULT")
    print("Requested Job:", job_id)
    print("State Question:", state.question)
    print("State Object ID:", id(state))


    return {
        "question": state.question,
        "papers_found": len(state.papers),
        "papers": papers,
        "hypothesis": state.hypothesis.hypothesis if state.hypothesis else None,
        "report": report
    }