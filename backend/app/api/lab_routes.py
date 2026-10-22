import re
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.lab.lab_service import lab_service
from app.lab.lab_store import lab_store
from app.lab.notebook_agent import notebook_agent
from app.lab.notebook_export import build_notebook_docx
from app.services.job_manager import job_manager


router = APIRouter(
    prefix="/lab",
    tags=["Lab Copilot"],
)


# =========================================================
# REQUEST MODELS
# =========================================================

class CreateSessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    protocol: str = Field(default="", max_length=20000)
    research_job_id: Optional[str] = None


class NoteRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


# =========================================================
# HELPERS
# =========================================================

def _session_or_404(session_id: str) -> dict:
    session = lab_store.get_session(session_id)

    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Lab session not found.",
        )

    return session


def _active_session_or_409(session_id: str) -> dict:
    session = _session_or_404(session_id)

    if session["status"] != "active":
        raise HTTPException(
            status_code=409,
            detail="This session has ended.",
        )

    return session


# =========================================================
# SESSIONS
# =========================================================

@router.post("/sessions")
def create_session(request: CreateSessionRequest):
    title = request.title.strip()

    if not title:
        raise HTTPException(
            status_code=400,
            detail="Session title cannot be empty.",
        )

    research_job_id = (request.research_job_id or "").strip() or None

    if research_job_id:
        job = job_manager.get_job(research_job_id)

        if job is None or job["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail="Linked research report was not found.",
            )

    return lab_store.create_session(
        title=title,
        protocol=request.protocol.strip(),
        research_job_id=research_job_id,
    )


@router.get("/sessions")
def list_sessions():
    return {"sessions": lab_store.list_sessions()}


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    session = _session_or_404(session_id)
    session["entries"] = lab_store.list_entries(session_id)
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str):
    _session_or_404(session_id)
    lab_store.delete_session(session_id)
    return {"deleted": True}


# =========================================================
# RECORDING
# =========================================================

@router.post("/sessions/{session_id}/frames")
async def add_frame(
    session_id: str,
    image: UploadFile = File(...),
):
    _active_session_or_409(session_id)

    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(
            status_code=400,
            detail="Image is empty.",
        )

    try:
        # The vision model call blocks; keep it off the
        # event loop.
        return await run_in_threadpool(
            lab_service.process_frame,
            session_id,
            image_bytes,
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        print("Lab frame error:", repr(error))
        raise HTTPException(status_code=500, detail=str(error))


@router.post("/sessions/{session_id}/notes")
def add_note(session_id: str, request: NoteRequest):
    _active_session_or_409(session_id)

    text = request.text.strip()

    if not text:
        raise HTTPException(
            status_code=400,
            detail="Note cannot be empty.",
        )

    return lab_service.add_note(session_id, text)


@router.get("/sessions/{session_id}/entries/{entry_id}/image")
def entry_image(session_id: str, entry_id: int):
    _session_or_404(session_id)

    path = lab_store.image_path(session_id, entry_id)

    if not path.exists():
        raise HTTPException(status_code=404, detail="No image.")

    return FileResponse(path, media_type="image/jpeg")


# =========================================================
# NOTEBOOK
# =========================================================

@router.post("/sessions/{session_id}/notebook")
def generate_notebook(session_id: str):
    """End the session (if active) and write its notebook."""

    session = _session_or_404(session_id)

    lab_store.end_session(session_id)

    entries = lab_store.list_entries(session_id)

    try:
        notebook = notebook_agent.generate(session, entries)

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except Exception as error:
        print("Notebook error:", repr(error))
        raise HTTPException(status_code=500, detail=str(error))

    lab_store.save_notebook(session_id, notebook)

    return lab_store.get_session(session_id)


@router.get("/sessions/{session_id}/export/docx")
def export_notebook(session_id: str):
    session = _session_or_404(session_id)

    if not session.get("notebook"):
        raise HTTPException(
            status_code=409,
            detail="Generate the notebook first.",
        )

    content = build_notebook_docx(
        session,
        lab_store.list_entries(session_id),
    )

    slug = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        session["title"],
    ).strip("-")[:60] or "lab-notebook"

    return Response(
        content=content,
        media_type=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="{slug}-notebook.docx"'
            ),
        },
    )
