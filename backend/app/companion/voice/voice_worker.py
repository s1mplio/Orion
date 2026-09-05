import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from app.companion.voice.voice_service import (
    VoiceService,
)


# =========================================================
# VOICE JOB
# =========================================================

@dataclass
class VoiceJob:

    text: str

    memory_id: Optional[int] = None

    generation: Optional[int] = None

    source: str = "proactive"


# =========================================================
# VOICE RESULT
# =========================================================

@dataclass
class VoiceResult:

    text: str

    success: bool

    memory_id: Optional[int]

    generation: Optional[int]

    source: str

    error: Optional[str] = None


# =========================================================
# VOICE WORKER
# =========================================================

class VoiceWorker:
    """
    Asynchronous speech worker.

    Important:

        Vision does not wait for speech.

        Proactive message generation does not wait
        for speech.

        Audio playback happens independently.
    """

    def __init__(
        self,
        on_result: Optional[
            Callable[[VoiceResult], None]
        ] = None,
        voice_service: Optional[
            VoiceService
        ] = None,
    ):

        self.on_result = on_result

        self.voice_service = (
            voice_service
            if voice_service is not None
            else VoiceService()
        )

        # Only one pending speech message.
        #
        # Orion should not accumulate a long queue of
        # outdated comments.

        self.job_queue = queue.Queue(
            maxsize=1
        )

        self.thread: Optional[
            threading.Thread
        ] = None

        self.running = False

        self.processing = False

        self.state_lock = (
            threading.Lock()
        )

    # =====================================================
    # START
    # =====================================================

    def start(
        self,
    ):

        if self.running:
            return

        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="OrionVoiceWorker",
        )

        self.thread.start()

        print(
            "Voice Worker started."
        )

    # =====================================================
    # STOP
    # =====================================================

    def stop(
        self,
    ):

        if not self.running:
            return

        print(
            "Stopping Voice Worker..."
        )

        self.running = False

        try:

            self.job_queue.put_nowait(
                None
            )

        except queue.Full:

            pass

        if self.thread is not None:

            self.thread.join(
                timeout=3.0
            )

        self.thread = None

        print(
            "Voice Worker stopped."
        )

    # =====================================================
    # STATE
    # =====================================================

    def is_processing(
        self,
    ) -> bool:

        with self.state_lock:

            return self.processing

    # =====================================================
    # SUBMIT
    # =====================================================

    def submit(
        self,
        job: VoiceJob,
    ) -> bool:

        if not self.running:

            print(
                "VOICE_WORKER_NOT_RUNNING"
            )

            return False

        if not job.text:

            return False

        # ---------------------------------------------
        # NEWEST PENDING MESSAGE WINS
        # ---------------------------------------------

        try:

            while True:

                self.job_queue.get_nowait()

                self.job_queue.task_done()

        except queue.Empty:

            pass

        try:

            self.job_queue.put_nowait(
                job
            )

        except queue.Full:

            return False

        print(
            "Voice job submitted."
        )

        return True

    # =====================================================
    # LOOP
    # =====================================================

    def _run(
        self,
    ):

        while self.running:

            try:

                job = (
                    self.job_queue.get(
                        timeout=0.5
                    )
                )

            except queue.Empty:

                continue

            if job is None:

                self.job_queue.task_done()

                continue

            with self.state_lock:

                self.processing = True

            try:

                self._process_job(
                    job
                )

            except Exception as exc:

                print(
                    "VOICE_WORKER_ERROR:",
                    repr(exc),
                )

                self._deliver_result(
                    VoiceResult(
                        text=job.text,
                        success=False,
                        memory_id=job.memory_id,
                        generation=job.generation,
                        source=job.source,
                        error=repr(exc),
                    )
                )

            finally:

                with self.state_lock:

                    self.processing = False

                self.job_queue.task_done()

    # =====================================================
    # PROCESS
    # =====================================================

    def _process_job(
        self,
        job: VoiceJob,
    ):

        success = (
            self.voice_service.speak(
                job.text
            )
        )

        result = VoiceResult(
            text=job.text,
            success=success,
            memory_id=job.memory_id,
            generation=job.generation,
            source=job.source,
        )

        self._deliver_result(
            result
        )

    # =====================================================
    # RESULT
    # =====================================================

    def _deliver_result(
        self,
        result: VoiceResult,
    ):

        if self.on_result is None:
            return

        try:

            self.on_result(
                result
            )

        except Exception as exc:

            print(
                "VOICE_CALLBACK_ERROR:",
                repr(exc),
            )