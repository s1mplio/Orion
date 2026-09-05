import time
from typing import Optional

from app.companion.chat_service import CompanionChatService

from app.companion.routing.intent_router import (
    IntentRouter,
)

from app.services.research_job_service import (
    research_job_service,
)

from app.companion.voice.speech_input_service import (
    SpeechInputService,
)

from app.companion.voice.voice_worker import (
    VoiceJob,
    VoiceResult,
    VoiceWorker,
)


class ConversationLoop:
    """
    Orion Unified Conversational Loop.

    User input can now be routed to different Orion
    capabilities.

    Current V1 routes:

        CHAT
            ↓
        CompanionChatService

        RESEARCH
            ↓
        ResearchJobService
            ↓
        Research V2 background pipeline

    Both typed and voice input pass through the same
    routing layer.

    IMPORTANT:

    Research runs asynchronously.

    Orion remains responsive while Research V2 runs.
    """

    def __init__(
        self,
        speech_model_size: str = "small.en",
        sample_rate: int = 16000,
        record_seconds: float = 4.0,
        input_device: Optional[int] = None,
    ):

        # =================================================
        # COMPANION CHAT
        # =================================================

        self.chat_service = (
            CompanionChatService()
        )

        # =================================================
        # CAPABILITY ROUTER
        # =================================================

        self.intent_router = (
            IntentRouter()
        )

        # =================================================
        # RESEARCH
        # =================================================

        self.research_service = (
            research_job_service
        )

        # Keep track of research started from this
        # conversation.
        #
        # Later this will allow Orion to notify the user
        # when research finishes.

        self.active_research_jobs = {}

        # =================================================
        # SPEECH INPUT CONFIGURATION
        # =================================================

        self.speech_model_size = (
            speech_model_size
        )

        self.sample_rate = (
            sample_rate
        )

        self.record_seconds = (
            record_seconds
        )

        self.input_device = (
            input_device
        )

        self.speech_input: Optional[
            SpeechInputService
        ] = None

        # =================================================
        # VOICE OUTPUT
        # =================================================

        self.voice_worker = VoiceWorker(
            on_result=(
                self._on_voice_result
            ),
        )

        self.running = False

    # =====================================================
    # START
    # =====================================================

    def start(
        self,
    ):

        if self.running:
            return

        self.running = True

        self.voice_worker.start()

        print(
            "\n================================"
        )

        print(
            "ORION CONVERSATION LOOP"
        )

        print(
            "================================"
        )

        print(
            "ENTER  -> speak"
        )

        print(
            "t      -> type message"
        )

        print(
            "q      -> quit"
        )

        print(
            "================================"
        )

        print(
            "Capabilities:"
        )

        print(
            "- Companion conversation"
        )

        print(
            "- Contextual visual memory"
        )

        print(
            "- Research V2"
        )

        print(
            "================================"
        )

    # =====================================================
    # STOP
    # =====================================================

    def stop(
        self,
    ):

        if not self.running:
            return

        self.running = False

        self.voice_worker.stop()

        print(
            "Conversation loop stopped."
        )

    # =====================================================
    # RUN
    # =====================================================

    def run(
        self,
    ):

        self.start()

        try:

            while self.running:

                self._wait_for_voice_idle()

                try:

                    command = input(
                        "\n"
                        "[ENTER=speak | "
                        "t=type | "
                        "q=quit] > "
                    )

                except (
                    KeyboardInterrupt,
                    EOFError,
                ):

                    print()
                    break

                raw_command = (
                    command.strip()
                )

                command_lower = (
                    raw_command.lower()
                )

                # =========================================
                # QUIT
                # =========================================

                if command_lower in {
                    "q",
                    "quit",
                    "exit",
                }:

                    break

                # =========================================
                # TEXT MODE
                # =========================================

                if command_lower in {
                    "t",
                    "text",
                }:

                    self._handle_typed_input()

                    continue

                # =========================================
                # VOICE MODE
                # =========================================

                if raw_command == "":

                    self._handle_voice_input()

                    continue

                # =========================================
                # DIRECT TEXT
                # =========================================

                self.handle_text(
                    raw_command
                )

        finally:

            self.stop()

    # =====================================================
    # TYPED INPUT
    # =====================================================

    def _handle_typed_input(
        self,
    ):

        try:

            text = input(
                "You: "
            )

        except (
            KeyboardInterrupt,
            EOFError,
        ):

            print()

            return

        text = text.strip()

        if not text:
            return

        self.handle_text(
            text
        )

    # =====================================================
    # VOICE INPUT
    # =====================================================

    def _handle_voice_input(
        self,
    ):

        self._wait_for_voice_idle()

        speech_input = (
            self._get_speech_input()
        )

        if speech_input is None:

            print(
                "Speech input is unavailable."
            )

            print(
                "Use text mode for now."
            )

            return

        try:

            text = (
                speech_input.listen()
            )

        except Exception as exc:

            print(
                "SPEECH_INPUT_ERROR:",
                repr(exc),
            )

            return

        if not text:

            print(
                "No usable speech was detected."
            )

            return

        self.handle_text(
            text
        )

    # =====================================================
    # PROCESS USER MESSAGE
    # =====================================================

    def handle_text(
        self,
        text: str,
    ) -> Optional[str]:

        if not text:
            return None

        text = str(
            text
        ).strip()

        if not text:
            return None

        print(
            "\n================================"
        )

        print(
            "YOU"
        )

        print(
            "================================"
        )

        print(
            text
        )

        print(
            "================================"
        )

        # =================================================
        # ROUTE USER REQUEST
        # =================================================

        try:

            decision = (
                self.intent_router.route(
                    text
                )
            )

        except Exception as exc:

            print(
                "INTENT_ROUTER_ERROR:",
                repr(exc),
            )

            # Router failure must never break normal
            # Companion conversation.

            decision = None

        # =================================================
        # RESEARCH ROUTE
        # =================================================

        if (
            decision is not None
            and
            decision.intent
            == "research"
        ):

            return (
                self._handle_research(
                    decision.query
                )
            )

        # =================================================
        # NORMAL COMPANION CHAT
        # =================================================

        return (
            self._handle_chat(
                text
            )
        )

    # =====================================================
    # NORMAL COMPANION CHAT
    # =====================================================

    def _handle_chat(
        self,
        text: str,
    ) -> Optional[str]:

        try:

            response = (
                self.chat_service.chat(
                    text
                )
            )

        except Exception as exc:

            print(
                "CONVERSATION_ERROR:",
                repr(exc),
            )

            return None

        if not response:

            print(
                "Orion returned no response."
            )

            return None

        response = str(
            response
        ).strip()

        if not response:
            return None

        self._present_response(
            response,
            source="conversation",
        )

        return response

    # =====================================================
    # RESEARCH REQUEST
    # =====================================================

    def _handle_research(
        self,
        research_question: Optional[str],
    ) -> Optional[str]:

        if not research_question:

            response = (
                "Tell me what you'd like "
                "me to research."
            )

            self._present_response(
                response,
                source="research",
            )

            return response

        research_question = str(
            research_question
        ).strip()

        if not research_question:

            response = (
                "Tell me what you'd like "
                "me to research."
            )

            self._present_response(
                response,
                source="research",
            )

            return response

        # =================================================
        # START RESEARCH V2
        # =================================================

        try:

            job_id = (
                self.research_service
                .start_research(
                    research_question
                )
            )

        except Exception as exc:

            print(
                "RESEARCH_START_ERROR:",
                repr(exc),
            )

            response = (
                "I couldn't start the "
                "research right now."
            )

            self._present_response(
                response,
                source="research",
            )

            return response

        if not job_id:

            response = (
                "I couldn't start the "
                "research because the "
                "question was empty."
            )

            self._present_response(
                response,
                source="research",
            )

            return response

        # =================================================
        # TRACK COMPANION-STARTED JOB
        # =================================================

        self.active_research_jobs[
            job_id
        ] = {
            "question": (
                research_question
            ),
            "notified": False,
        }

        # =================================================
        # IMMEDIATE ACKNOWLEDGEMENT
        # =================================================

        response = (
            "I've started researching "
            f"{research_question} "
            "in the background. "
            "You can keep talking to me "
            "while I work on it."
        )

        print(
            "\n================================"
        )

        print(
            "RESEARCH JOB"
        )

        print(
            "================================"
        )

        print(
            "Job ID:",
            job_id,
        )

        print(
            "Question:",
            research_question,
        )

        print(
            "Status: running"
        )

        print(
            "================================"
        )

        self._present_response(
            response,
            source="research",
        )

        return response

    # =====================================================
    # PRESENT ORION RESPONSE
    # =====================================================

    def _present_response(
        self,
        response: str,
        source: str,
    ):

        print(
            "\n================================"
        )

        print(
            "ORION"
        )

        print(
            "================================"
        )

        print(
            response
        )

        print(
            "================================"
        )

        # =================================================
        # ASYNC TTS
        # =================================================

        submitted = (
            self.voice_worker.submit(
                VoiceJob(
                    text=response,
                    source=source,
                )
            )
        )

        if not submitted:

            print(
                "VOICE_SUBMISSION_FAILED"
            )

    # =====================================================
    # LAZY SPEECH INPUT INITIALIZATION
    # =====================================================

    def _get_speech_input(
        self,
    ) -> Optional[SpeechInputService]:

        if (
            self.speech_input
            is not None
        ):

            return self.speech_input

        print(
            "\nInitializing Orion "
            "speech input..."
        )

        try:

            self.speech_input = (
                SpeechInputService(
                    model_size=(
                        self.speech_model_size
                    ),
                    sample_rate=(
                        self.sample_rate
                    ),
                    record_seconds=(
                        self.record_seconds
                    ),
                    input_device=(
                        self.input_device
                    ),
                )
            )

        except Exception as exc:

            print(
                "SPEECH_INPUT_INIT_ERROR:",
                repr(exc),
            )

            self.speech_input = None

            return None

        return self.speech_input

    # =====================================================
    # WAIT FOR VOICE OUTPUT
    # =====================================================

    def _wait_for_voice_idle(
        self,
        timeout_seconds: float = 30.0,
    ):

        started = (
            time.monotonic()
        )

        while (
            self.voice_worker
            .is_processing()
        ):

            elapsed = (
                time.monotonic()
                - started
            )

            if (
                elapsed
                > timeout_seconds
            ):

                print(
                    "VOICE_WAIT_TIMEOUT"
                )

                return

            time.sleep(
                0.05
            )

        time.sleep(
            0.15
        )

    # =====================================================
    # VOICE RESULT CALLBACK
    # =====================================================

    def _on_voice_result(
        self,
        result: VoiceResult,
    ):

        if result.success:

            print(
                "Conversation speech "
                "completed."
            )

            return

        print(
            "CONVERSATION_VOICE_ERROR:",
            result.error,
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    conversation_loop = (
        ConversationLoop(
            speech_model_size=(
                "small.en"
            ),
            sample_rate=16000,
            record_seconds=4.0,
        )
    )

    conversation_loop.run()