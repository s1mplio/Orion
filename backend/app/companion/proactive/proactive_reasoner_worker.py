import queue
import threading
from dataclasses import dataclass
from typing import Callable, Optional, Any

from app.companion.proactive.proactive_reasoner import (
    ProactiveReasoner,
    ProactiveReasoningResult,
)


# =========================================================
# JOB
# =========================================================

@dataclass
class ProactiveReasoningJob:
    policy_decision: Any
    memory_id: Optional[int]
    generation: Optional[int]


# =========================================================
# WORKER RESULT
# =========================================================

@dataclass
class ProactiveReasoningWorkerResult:
    reasoning: Optional[
        ProactiveReasoningResult
    ]

    memory_id: Optional[int]
    generation: Optional[int]

    error: Optional[str] = None


# =========================================================
# WORKER
# =========================================================

class ProactiveReasonerWorker:

    def __init__(
        self,
        reasoner: ProactiveReasoner,
        on_result: Optional[
            Callable[
                [ProactiveReasoningWorkerResult],
                None,
            ]
        ] = None,
    ):

        self.reasoner = reasoner
        self.on_result = on_result

        # Newest pending candidate wins.
        self.queue = queue.Queue(
            maxsize=1
        )

        self.running = False
        self.processing = False

        self.state_lock = (
            threading.Lock()
        )

        self.thread: Optional[
            threading.Thread
        ] = None

    # =====================================================
    # START
    # =====================================================

    def start(
        self,
    ):

        with self.state_lock:

            if self.running:
                return

            self.running = True

        self.thread = threading.Thread(
            target=self._run,
            name=(
                "OrionProactiveReasonerWorker"
            ),
            daemon=True,
        )

        self.thread.start()

        print(
            "Proactive Reasoner Worker started."
        )

    # =====================================================
    # STOP
    # =====================================================

    def stop(
        self,
    ):

        with self.state_lock:

            if not self.running:
                return

            self.running = False

        # Wake worker if it is waiting.
        try:

            self.queue.put_nowait(
                None
            )

        except queue.Full:

            # If queue already contains a job,
            # the timeout loop will still notice
            # running=False.
            pass

        if (
            self.thread is not None
            and
            self.thread.is_alive()
        ):

            self.thread.join(
                timeout=2.0
            )

        print(
            "Proactive Reasoner Worker stopped."
        )

    # =====================================================
    # PROCESSING
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
        job: ProactiveReasoningJob,
    ) -> bool:

        if job is None:
            return False

        with self.state_lock:

            if not self.running:
                return False

        # ---------------------------------------------
        # NEWEST PENDING CANDIDATE WINS
        # ---------------------------------------------

        if self.queue.full():

            try:

                self.queue.get_nowait()

            except queue.Empty:

                pass

        try:

            self.queue.put_nowait(
                job
            )

            return True

        except queue.Full:

            return False

    # =====================================================
    # THREAD LOOP
    # =====================================================

    def _run(
        self,
    ):

        while True:

            try:

                job = self.queue.get(
                    timeout=0.25
                )

            except queue.Empty:

                with self.state_lock:

                    if not self.running:
                        break

                continue

            if job is None:

                with self.state_lock:

                    if not self.running:
                        break

                continue

            with self.state_lock:

                self.processing = True

            try:

                result = (
                    self._process_job(
                        job
                    )
                )

                self._deliver_result(
                    result
                )

            finally:

                with self.state_lock:

                    self.processing = False

    # =====================================================
    # PROCESS
    # =====================================================

    def _process_job(
        self,
        job: ProactiveReasoningJob,
    ) -> ProactiveReasoningWorkerResult:

        try:

            reasoning = (
                self.reasoner
                .evaluate_candidate(
                    job.policy_decision
                )
            )

            return (
                ProactiveReasoningWorkerResult(
                    reasoning=reasoning,
                    memory_id=(
                        job.memory_id
                    ),
                    generation=(
                        job.generation
                    ),
                )
            )

        except Exception as exc:

            return (
                ProactiveReasoningWorkerResult(
                    reasoning=None,
                    memory_id=(
                        job.memory_id
                    ),
                    generation=(
                        job.generation
                    ),
                    error=repr(exc),
                )
            )

    # =====================================================
    # CALLBACK
    # =====================================================

    def _deliver_result(
        self,
        result: ProactiveReasoningWorkerResult,
    ):

        if self.on_result is None:
            return

        try:

            self.on_result(
                result
            )

        except Exception as exc:

            print(
                "PROACTIVE_REASONER_CALLBACK_ERROR:",
                repr(exc),
            )