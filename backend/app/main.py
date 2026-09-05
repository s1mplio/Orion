import threading
import time

from app.companion.vision_loop import VisionLoop
from app.companion.voice.conversation_loop import (
    ConversationLoop,
)


class OrionApplication:
    """
    Orion PC MVP V1.0

    Starts the two major runtime systems:

    1. Vision / proactive companion
       - Camera
       - Adaptive vision
       - VLM
       - Scene intelligence
       - Memory
       - Temporal world state
       - Goal progress
       - Proactive reasoning
       - Proactive speech

    2. Conversational companion
       - Typed input
       - Speech input
       - Context-aware chat
       - Automatic goal capture
       - Conversational TTS

    Shared context is provided through Orion's existing
    shared memory/context services.
    """

    def __init__(
        self,
    ):
        self.vision_loop = VisionLoop()

        self.conversation_loop = (
            ConversationLoop(
                speech_model_size="small.en",
                sample_rate=16000,
                record_seconds=4.0,
            )
        )

        self.conversation_thread = None

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

        print(
            "\n========================================"
        )
        print(
            "ORION PC MVP V1.0"
        )
        print(
            "========================================"
        )
        print(
            "Starting companion systems..."
        )
        print(
            "========================================\n"
        )

        # =================================================
        # CONVERSATION
        #
        # Run console / conversational interaction
        # separately so the main thread remains available
        # for OpenCV's vision window.
        # =================================================

        self.conversation_thread = (
            threading.Thread(
                target=self._run_conversation,
                daemon=True,
                name="OrionConversationLoop",
            )
        )

        self.conversation_thread.start()

        # Give the conversation worker a moment to start
        # before launching the camera loop.

        time.sleep(
            0.25
        )

        # =================================================
        # VISION
        #
        # Keep OpenCV vision processing on the main thread.
        #
        # VisionLoop.start() blocks until:
        #
        #     Q is pressed
        #     Ctrl+C occurs
        #     or the loop is stopped.
        # =================================================

        try:
            self.vision_loop.start()

        except KeyboardInterrupt:
            print(
                "\nORION INTERRUPTED"
            )

        except Exception as exc:
            print(
                "\nORION_VISION_FATAL_ERROR:",
                repr(exc),
            )

        finally:
            self.stop()

    # =====================================================
    # CONVERSATION THREAD
    # =====================================================

    def _run_conversation(
        self,
    ):
        try:
            self.conversation_loop.run()

        except Exception as exc:
            print(
                "\nORION_CONVERSATION_FATAL_ERROR:",
                repr(exc),
            )

        finally:
            # Conversation ending does not automatically
            # kill vision.
            #
            # The user may quit text/voice interaction and
            # still allow the visual companion to run.

            print(
                "\nConversation interface ended."
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
            "\n========================================"
        )
        print(
            "STOPPING ORION"
        )
        print(
            "========================================"
        )

        self.running = False

        # Conversation loop owns its conversational
        # VoiceWorker.

        try:
            self.conversation_loop.stop()

        except Exception as exc:
            print(
                "CONVERSATION_STOP_ERROR:",
                repr(exc),
            )

        # VisionLoop owns:
        #
        # - camera
        # - VLM worker
        # - proactive reasoner worker
        # - proactive message worker
        # - proactive VoiceWorker

        try:
            self.vision_loop.stop()

        except Exception as exc:
            print(
                "VISION_STOP_ERROR:",
                repr(exc),
            )

        print(
            "========================================"
        )
        print(
            "ORION STOPPED"
        )
        print(
            "========================================"
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    OrionApplication().start()