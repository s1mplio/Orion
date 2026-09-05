import threading
from typing import Optional

import pyttsx3


class VoiceService:
    """
    Converts Orion's final text response into speech.

    V1:
        Uses the operating system's local TTS engine.

    Later:
        This implementation can be replaced with a
        neural/cloud TTS provider without changing
        VoiceWorker or the rest of Orion.
    """

    def __init__(
        self,
        rate: int = 175,
        volume: float = 1.0,
        voice_name: Optional[str] = None,
    ):
        self.rate = rate
        self.volume = volume
        self.voice_name = voice_name

        self._lock = threading.Lock()

    # =====================================================
    # SPEAK
    # =====================================================

    def speak(
        self,
        text: str,
    ) -> bool:

        if not text:
            return False

        text = str(text).strip()

        if not text:
            return False

        try:

            # Create the engine inside the worker thread.
            #
            # This is safer than creating it in the main
            # thread and later using it from another thread.

            with self._lock:

                engine = pyttsx3.init()

                engine.setProperty(
                    "rate",
                    self.rate,
                )

                engine.setProperty(
                    "volume",
                    self.volume,
                )

                self._select_voice(
                    engine
                )

                print(
                    "\n================================"
                )

                print(
                    "ORION SPEAKING"
                )

                print(
                    "================================"
                )

                print(text)

                print(
                    "================================"
                )

                engine.say(text)

                engine.runAndWait()

                engine.stop()

            return True

        except Exception as exc:

            print(
                "\nVOICE_SERVICE_ERROR:",
                repr(exc),
            )

            return False

    # =====================================================
    # VOICE SELECTION
    # =====================================================

    def _select_voice(
        self,
        engine,
    ):

        if not self.voice_name:
            return

        try:

            voices = (
                engine.getProperty(
                    "voices"
                )
                or []
            )

        except Exception:

            return

        target = (
            self.voice_name
            .strip()
            .lower()
        )

        for voice in voices:

            name = str(
                getattr(
                    voice,
                    "name",
                    "",
                )
            ).lower()

            if target in name:

                engine.setProperty(
                    "voice",
                    voice.id,
                )

                print(
                    "ORION VOICE:",
                    getattr(
                        voice,
                        "name",
                        voice.id,
                    ),
                )

                return