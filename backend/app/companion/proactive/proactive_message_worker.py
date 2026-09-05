import queue
import threading
from dataclasses import dataclass
from typing import Callable, List, Optional

from app.companion.proactive.proactive_message_service import (
    ProactiveMessageService,
)


# =========================================================
# JOB
# =========================================================

@dataclass
class ProactiveMessageJob:
    """
    One approved proactive message-generation request.

    The policy has ALREADY decided that Orion may speak.
    This worker only generates the natural-language message.
    """

    message_hint: str

    current_activity: Optional[str] = None

    current_salient_event: Optional[str] = None

    active_interactions: Optional[List[str]] = None

    recent_actions: Optional[List[str]] = None

    memory_id: Optional[int] = None

    generation: Optional[int] = None

    reason: Optional[str] = None

    priority: int = 0


# =========================================================
# RESULT
# =========================================================

@dataclass
class ProactiveMessageResult:
    """
    Result returned after proactive message generation.
    """

    message: Optional[str]

    memory_id: Optional[int]

    generation: Optional[int]

    reason: Optional[str]

    priority: int

    message_hint: str

    error: Optional[str] = None


# =========================================================
# WORKER
# =========================================================

class ProactiveMessageWorker:
    """
    Runs proactive natural-language generation outside
    the vision/VLM callback thread.

    Architecture:

        VisionLoop
            ↓
        ProactivePolicy
            ↓
        submit(job)
            ↓
        ProactiveMessageWorker thread
            ↓
        ProactiveMessageService
            ↓
        LLMService.generate()
            ↓
        callback(result)

    This prevents a slow conversational LLM request from
    blocking Orion's visual processing.

    Queue size = 1 because proactive messages are highly
    time-sensitive. Old pending messages should not pile up.
    """

    def __init__(
        self,
        on_result: Callable[
            [ProactiveMessageResult],
            None,
        ],
        message_service: Optional[
            ProactiveMessageService
        ] = None,
    ):

        self.on_result = on_result

        self.message_service = (
            message_service
            if message_service is not None
            else ProactiveMessageService()
        )

        # -------------------------------------------------
        # NEWEST RELEVANT JOB ONLY
        # -------------------------------------------------

        self.job_queue = queue.Queue(
            maxsize=1
        )

        # -------------------------------------------------
        # THREAD STATE
        # -------------------------------------------------

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
            name="OrionProactiveMessageWorker",
        )

        self.thread.start()

        print(
            "Proactive Message Worker started."
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
            "Stopping Proactive Message Worker..."
        )

        self.running = False

        # -------------------------------------------------
        # WAKE WORKER
        # -------------------------------------------------

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
            "Proactive Message Worker stopped."
        )

    # =====================================================
    # PROCESSING STATE
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
        job: ProactiveMessageJob,
    ) -> bool:
        """
        Submit a proactive message-generation job.

        Important:
        We never build an unlimited backlog.

        If a pending job already exists, it is removed and
        replaced with the newest approved proactive event.

        If the worker is currently generating a message,
        the current generation is allowed to finish.
        """

        if not self.running:

            print(
                "PROACTIVE_MESSAGE_WORKER_NOT_RUNNING"
            )

            return False

        # -------------------------------------------------
        # REMOVE OLD PENDING JOB
        # -------------------------------------------------

        try:

            while True:

                self.job_queue.get_nowait()

                self.job_queue.task_done()

        except queue.Empty:

            pass

        # -------------------------------------------------
        # ADD NEWEST JOB
        # -------------------------------------------------

        try:

            self.job_queue.put_nowait(
                job
            )

        except queue.Full:

            return False

        print(
            "Proactive message job submitted."
        )

        print(
            "Reason:",
            job.reason,
        )

        print(
            "Priority:",
            job.priority,
        )

        print(
            "Generation:",
            job.generation,
        )

        return True

    # =====================================================
    # WORKER LOOP
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

            # Sentinel used during shutdown.

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
                    "PROACTIVE_MESSAGE_WORKER_ERROR:",
                    repr(exc),
                )

                result = (
                    ProactiveMessageResult(
                        message=None,

                        memory_id=(
                            job.memory_id
                        ),

                        generation=(
                            job.generation
                        ),

                        reason=(
                            job.reason
                        ),

                        priority=(
                            job.priority
                        ),

                        message_hint=(
                            job.message_hint
                        ),

                        error=repr(
                            exc
                        ),
                    )
                )

                self._deliver_result(
                    result
                )

            finally:

                with self.state_lock:

                    self.processing = False

                self.job_queue.task_done()

    # =====================================================
    # PROCESS JOB
    # =====================================================

    def _process_job(
        self,
        job: ProactiveMessageJob,
    ):

        print(
            "\n================================"
        )

        print(
            "PROACTIVE MESSAGE PROCESSING"
        )

        print(
            "================================"
        )

        print(
            "Reason:",
            job.reason,
        )

        print(
            "Priority:",
            job.priority,
        )

        print(
            "Hint:",
            job.message_hint,
        )

        print(
            "================================"
        )

        # -------------------------------------------------
        # EXACTLY ONE PROACTIVE LLM CALL
        # -------------------------------------------------

        message = (
            self.message_service.generate(
                message_hint=(
                    job.message_hint
                ),

                current_activity=(
                    job.current_activity
                ),

                current_salient_event=(
                    job.current_salient_event
                ),

                active_interactions=(
                    job.active_interactions
                    or []
                ),

                recent_actions=(
                    job.recent_actions
                    or []
                ),
            )
        )

        result = (
            ProactiveMessageResult(
                message=message,

                memory_id=(
                    job.memory_id
                ),

                generation=(
                    job.generation
                ),

                reason=(
                    job.reason
                ),

                priority=(
                    job.priority
                ),

                message_hint=(
                    job.message_hint
                ),

                error=None,
            )
        )

        self._deliver_result(
            result
        )

    # =====================================================
    # CALLBACK
    # =====================================================

    def _deliver_result(
        self,
        result: ProactiveMessageResult,
    ):

        try:

            self.on_result(
                result
            )

        except Exception as exc:

            print(
                "PROACTIVE_MESSAGE_CALLBACK_ERROR:",
                repr(exc),
            )