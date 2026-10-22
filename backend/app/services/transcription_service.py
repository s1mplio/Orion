import os
import tempfile
import threading
from pathlib import Path


# Local Whisper model. "base.en" is fast on a CPU; "small.en"
# is more accurate but slower.
WHISPER_MODEL = os.getenv("ORION_WHISPER_MODEL", "base.en")

# Longest upload accepted (about two minutes of compressed audio).
MAX_AUDIO_BYTES = 5 * 1024 * 1024

SUFFIXES = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
}


class TranscriptionService:
    """
    Speech-to-text for audio recorded in the browser.

    Runs Whisper locally, so it works in every browser (unlike
    the Web Speech API) and voice never leaves the machine.
    """

    def __init__(self, model_size=WHISPER_MODEL):
        self.model_size = model_size
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                print(f"[SPEECH] Loading Whisper {self.model_size}...")

                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                )

                print("[SPEECH] Whisper ready.")

            return self._model

    def warm_up(self):
        """Load the model in the background so the first request is fast."""
        threading.Thread(
            target=self._safe_warm_up,
            name="orion-whisper-warmup",
            daemon=True,
        ).start()

    def _safe_warm_up(self):
        try:
            self._get_model()
        except Exception as error:
            print("[SPEECH] Whisper unavailable:", repr(error))

    def transcribe(self, audio_bytes: bytes, content_type: str = "") -> str:
        if not audio_bytes:
            raise ValueError("No audio was received.")

        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValueError("Recording is too long.")

        suffix = SUFFIXES.get(content_type.split(";")[0].strip(), ".webm")

        model = self._get_model()

        # PyAV (used by faster-whisper) decodes from a file path.
        handle, path = tempfile.mkstemp(suffix=suffix)

        try:
            with os.fdopen(handle, "wb") as file:
                file.write(audio_bytes)

            try:
                segments, _ = model.transcribe(
                    path,
                    language="en",
                    beam_size=1,
                    # Skips silence so it is not hallucinated into words.
                    vad_filter=True,
                    condition_on_previous_text=False,
                )

                return " ".join(
                    segment.text.strip() for segment in segments
                ).strip()

            except Exception as error:
                print("[SPEECH] Could not decode audio:", repr(error))
                raise ValueError(
                    "Couldn't read the recording. Please try again."
                ) from error

        finally:
            Path(path).unlink(missing_ok=True)


transcription_service = TranscriptionService()
