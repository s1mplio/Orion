from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.services.transcription_service import transcription_service


router = APIRouter(
    prefix="/speech",
    tags=["Speech"],
)


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    audio_bytes = await audio.read()

    try:
        text = await run_in_threadpool(
            transcription_service.transcribe,
            audio_bytes,
            audio.content_type or "",
        )

    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Speech recognition is not installed (pip install faster-whisper).",
        )

    except Exception as error:
        print("Transcription error:", repr(error))
        raise HTTPException(
            status_code=500,
            detail="Could not understand the recording.",
        )

    return {"text": text}
