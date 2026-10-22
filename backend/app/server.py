from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before importing modules that read settings
# from the environment (Telegram token, research limits, ...).
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.companion_routes import router as companion_router
from app.api.lab_routes import router as lab_router
from app.api.care_routes import router as care_router
from app.api.speech_routes import router as speech_router
from app.care.care_service import care_service
from app.services.transcription_service import transcription_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Medication reminders, missed-dose alerts and the
    # daily summary run in the background.
    care_service.start_scheduler()
    # Load Whisper now so the first voice question is fast.
    transcription_service.warm_up()
    yield
    care_service.stop_scheduler()


app = FastAPI(
    title="Orion API",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    # Any LAN address, so the frontend keeps working when the
    # machine's local IP changes.
    allow_origin_regex=r"http://192\.168\.\d{1,3}\.\d{1,3}:3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)
app.include_router(companion_router)
app.include_router(lab_router)
app.include_router(care_router)
app.include_router(speech_router)
