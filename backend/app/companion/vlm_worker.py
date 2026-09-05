import json
import queue
import re
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from app.services.vision_services import VisionService
from app.companion.memory.scene_models import StructuredScene


# =========================================================
# VISION JOB
# =========================================================

@dataclass
class VisionJob:
    """
    A frame submitted for asynchronous VLM analysis.
    """

    frame: np.ndarray
    generation: int


# =========================================================
# VISION RESULT
# =========================================================

@dataclass
class VisionResult:
    """
    Result returned by the VLM worker.

    observation:
        Human-readable scene summary used by the
        existing memory pipeline.

    structured_scene:
        Machine-readable relational scene state used
        by SceneStabilizer and SceneIntelligence.
    """

    frame: np.ndarray
    generation: int
    observation: Optional[str]

    structured_scene: Optional[StructuredScene] = None
    error: Optional[str] = None


# =========================================================
# VLM WORKER
# =========================================================

class VLMWorker:
    """
    Asynchronous VLM inference worker.

    Pipeline:

        frame
          ↓
        ONE VLM call
          ↓
        structured JSON
          ↓
        Pydantic validation
          ↓
        VisionResult

    Important:
    This worker NEVER makes an additional VLM call for
    semantic comparison, normalization, memory, or repair.

    Scene comparison happens later using deterministic
    Python logic.
    """

    def __init__(
        self,
        on_result: Optional[
            Callable[[VisionResult], None]
        ] = None,
    ):
        self.vision_service = VisionService()

        # Only one frame may wait.
        #
        # If another frame arrives while the worker is
        # processing, the newest waiting frame replaces
        # the older waiting frame.
        self.frame_queue = queue.Queue(
            maxsize=1
        )

        self.on_result = on_result

        self.running = False

        self.worker_thread: Optional[
            threading.Thread
        ] = None

        self.state_lock = threading.Lock()

        self.processing = False

        self.processing_generation: Optional[
            int
        ] = None

    # =====================================================
    # START
    # =====================================================

    def start(self):
        if self.running:
            return

        self.running = True

        self.worker_thread = threading.Thread(
            target=self._worker_loop,
            daemon=True,
        )

        self.worker_thread.start()

        print(
            "VLM Worker started."
        )

    # =====================================================
    # SUBMIT FRAME
    # =====================================================

    def submit(
        self,
        frame: np.ndarray,
        generation: int,
    ) -> bool:

        if not self.running:
            print(
                "VLM Worker is not running."
            )
            return False

        if frame is None:
            return False

        job = VisionJob(
            frame=frame.copy(),
            generation=generation,
        )

        # ---------------------------------------------
        # Try normal insert
        # ---------------------------------------------

        try:
            self.frame_queue.put_nowait(
                job
            )

            print(
                "Frame submitted to VLM worker "
                f"(generation={generation})."
            )

            return True

        except queue.Full:
            pass

        # ---------------------------------------------
        # Queue contains an older waiting frame.
        #
        # Drop it.
        #
        # This is important because Orion cares about
        # the latest visual state, not stale queued
        # camera frames.
        # ---------------------------------------------

        try:
            self.frame_queue.get_nowait()
            self.frame_queue.task_done()

        except queue.Empty:
            pass

        # ---------------------------------------------
        # Insert newest frame
        # ---------------------------------------------

        try:
            self.frame_queue.put_nowait(
                job
            )

            print(
                "Replaced queued frame with "
                "newest frame "
                f"(generation={generation})."
            )

            return True

        except queue.Full:
            return False

    # =====================================================
    # VLM PROMPT
    # =====================================================

    def _build_prompt(
        self,
    ) -> str:
        """
        IMPORTANT:

        This prompt produces BOTH:

        1. human-readable observation
        2. machine-readable relational state

        from ONE VLM request.

        We deliberately do NOT ask another LLM/VLM to
        normalize or compare the result later.
        """

        return """
You are Orion's visual perception system.

Analyze ONLY what is clearly visible in the CURRENT image.

You see only this image.
You do NOT have access to previous images or memory.

Return ONLY one valid JSON object.

Do not use Markdown.
Do not use ```json code fences.
Do not write any explanation before or after the JSON.

Use exactly this JSON structure:

{
  "observation": "Short factual summary of the important visible scene.",

  "environment": "Short stable physical environment label such as indoor room, bedroom, office, kitchen, outdoor street, vehicle interior, or unknown.",

  "people": [
    {
      "label": "person",

      "activity": {
        "type": "Short stable semantic action category, or null",
        "description": "Short factual description of the visible activity, or null"
      },

      "pose": {
        "body_state": "seated, standing, lying, crouching, walking, unknown, or null",

        "head_direction": "forward, left, right, upward, downward, unknown, or null",

        "left_hand": {
          "hand": "left",
          "relation": "touching, holding, covering, raised, resting_on, near, pointing_at, free, unknown, or null",
          "target": "Short visible target label such as chin, mouth, head, smartphone, table, or null"
        },

        "right_hand": {
          "hand": "right",
          "relation": "touching, holding, covering, raised, resting_on, near, pointing_at, free, unknown, or null",
          "target": "Short visible target label such as chin, mouth, head, smartphone, table, or null"
        }
      },

      "position": "Approximate image position such as center foreground, left background, or null",

      "clothing": "Clearly visible clothing description, or null",

      "visible_accessories": [
        "clearly visible accessories"
      ]
    }
  ],

  "objects": [
    {
      "label": "short specific object name",
      "position": "approximate visible location, or null",
      "state": "important clearly visible state, or null"
    }
  ],

  "visible_text": [
    "clearly readable visible text"
  ],

  "salient_event": "Short description of a notable action or state visible right now, or null"
}


GENERAL RULES:

1. Be concise and factual.

2. Describe ONLY what is visible in this image.

3. Do NOT infer:
- identity
- profession
- intention
- emotion
- health condition
- private information

4. Do not guess uncertain objects or actions.

Use null when information cannot be determined reliably.


CONSISTENCY RULES:

5. Prefer stable, short labels.

Do not unnecessarily rename the same visual concept.

For example, prefer:

"office chair"

instead of randomly alternating between:

"chair"
"desk chair"
"computer chair"
"office seat"

Prefer:

"earphones"

instead of randomly alternating between:

"earphone"
"earbuds"
"wired earbuds"
"wired earphones"

Prefer:

"smartphone"

instead of:

"phone"
"mobile"
"mobile phone"


ACTIVITY RULES:

6. activity.type represents the useful semantic category
of what the person is visibly doing.

Keep activity.type SHORT and STABLE.

Useful examples include:

"idle"
"looking_at_camera"
"looking_down"
"touching_face"
"covering_mouth"
"holding_phone"
"raising_hand"
"hands_on_head"
"drinking"
"typing"
"walking"

These examples are guidance, not an exhaustive list.

If another clearly visible activity is important, use a
short general semantic category for it.

Do NOT create an extremely specific activity type.

Bad:

"looking_forward_while_right_hand_is_touching_lower_chin"

Better:

"type": "touching_face"

"description":
"right hand resting on chin while facing forward"


7. Use activity.description for visible detail.

The description may be more descriptive than activity.type.

Example:

"type": "touching_face"

"description":
"right hand resting on chin while facing forward"


8. If the person is visible but doing nothing notable,
use a simple stable activity.

Example:

"type": "idle"

"description": "person seated facing forward"


POSE RULES:

9. Pose represents physical configuration separately
from the semantic activity.

body_state should describe the overall body state.

Examples:

"seated"
"standing"
"lying"
"crouching"
"walking"
"unknown"

Do not write a sentence in body_state.


10. head_direction should use a simple direction.

Prefer:

"forward"
"left"
"right"
"upward"
"downward"
"unknown"

Do not write a sentence in head_direction.


HAND RELATION RULES:

11. Hands are represented using:

RELATION + TARGET

Example: right hand touching chin

{
  "hand": "right",
  "relation": "touching",
  "target": "chin"
}

Example: right hand covering mouth

{
  "hand": "right",
  "relation": "covering",
  "target": "mouth"
}

Example: right hand holding smartphone

{
  "hand": "right",
  "relation": "holding",
  "target": "smartphone"
}

Example: hand resting on table

{
  "relation": "resting_on",
  "target": "table"
}


12. If both hands are touching the head:

left_hand:

{
  "hand": "left",
  "relation": "touching",
  "target": "head"
}

right_hand:

{
  "hand": "right",
  "relation": "touching",
  "target": "head"
}


13. If a hand is visible but not interacting with
anything important, relation may be:

"free"

and target should be null.


14. If a hand is not visible clearly enough:

use null for that hand.

Example:

"left_hand": null


15. NEVER guess left versus right.

If left/right cannot be determined reliably from the
image, prefer null rather than inventing a side.


OBJECT RULES:

16. Include useful objects relevant to understanding
the scene.

Examples:

"smartphone"
"office chair"
"ceiling fan"
"laptop"
"bottle"
"door"
"wall switch"
"table"

Ignore insignificant visual noise.


17. Object state must only contain state information
that can actually be inferred from the image.

Do NOT claim temporal state from one frame when it
cannot be determined.

For example:

A single image generally cannot reliably determine
whether a ceiling fan is moving or stationary.

In that situation:

"state": null

is better than guessing:

"stationary"
"off"
"moving"


ACCESSORY RULES:

18. Record clearly visible accessories such as:

"earphones"
"watch"
"wristband"
"glasses"
"hat"
"necklace"
"bag"

Only report an accessory when it is visibly supported
by the image.


19. Do NOT claim that an accessory was:

added
removed
put on
taken off

You only see the current image.


SALIENT EVENT RULES:

20. salient_event describes a notable visible action or
state happening RIGHT NOW.

Examples:

"person covering mouth with right hand"

"person holding smartphone"

"person has both hands on head"

If nothing sufficiently notable is happening:

"salient_event": null


21. Do NOT use salient_event to describe a change.

Bad:

"person has now raised their hand"

"person removed earphones"

"person moved from chin to mouth"

You do not know what happened before this image.

Good:

"person has both hands on head"

"person covering mouth with hand"


TEMPORAL RULES:

22. NEVER compare this image with an earlier scene.

Do not use phrases such as:

"now"
"still"
"again"
"changed"
"appeared"
"disappeared"
"removed"
"added"

unless those words describe something directly visible
without requiring knowledge of a previous image.


EMPTY VALUE RULES:

23. If no people are visible:

"people": []


24. If no useful objects are visible:

"objects": []


25. If no readable text is visible:

"visible_text": []


26. If there is no notable current event:

"salient_event": null


SCHEMA RULES:

27. Every object must contain:

"label"
"position"
"state"


28. Every person must contain:

"label"
"activity"
"pose"
"position"
"clothing"
"visible_accessories"


29. activity must contain:

"type"
"description"

unless activity itself is null.


30. pose must contain:

"body_state"
"head_direction"
"left_hand"
"right_hand"

unless pose itself is null.


31. A non-null hand must contain:

"hand"
"relation"
"target"


32. Return valid JSON only.
""".strip()

    # =====================================================
    # JSON EXTRACTION
    # =====================================================

    def _extract_json(
        self,
        raw_response: str,
    ) -> dict:
        """
        Extract one JSON object from the VLM response.

        This does NOT make another VLM call.

        Supported cases:
        - correct pure JSON
        - accidental Markdown JSON fence
        - small amount of text surrounding JSON
        """

        if not raw_response:
            raise ValueError(
                "VLM returned an empty response."
            )

        text = raw_response.strip()

        # ---------------------------------------------
        # Remove accidental opening code fence
        # ---------------------------------------------

        text = re.sub(
            r"^\s*```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )

        # ---------------------------------------------
        # Remove accidental closing code fence
        # ---------------------------------------------

        text = re.sub(
            r"\s*```\s*$",
            "",
            text,
        )

        text = text.strip()

        # ---------------------------------------------
        # First attempt: pure JSON
        # ---------------------------------------------

        try:
            parsed = json.loads(
                text
            )

            if not isinstance(
                parsed,
                dict,
            ):
                raise ValueError(
                    "VLM JSON root must be an object."
                )

            return parsed

        except json.JSONDecodeError:
            pass

        # ---------------------------------------------
        # Fallback:
        #
        # Extract first {...} region.
        #
        # Still NO second VLM call.
        # ---------------------------------------------

        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            raise ValueError(
                "Could not locate JSON object "
                "inside VLM response."
            )

        candidate = text[
            start:end + 1
        ]

        try:
            parsed = json.loads(
                candidate
            )

        except json.JSONDecodeError as error:
            raise ValueError(
                "VLM returned malformed JSON: "
                f"{error}"
            ) from error

        if not isinstance(
            parsed,
            dict,
        ):
            raise ValueError(
                "VLM JSON root must be an object."
            )

        return parsed

    # =====================================================
    # STRUCTURED SCENE VALIDATION
    # =====================================================

    def _parse_structured_scene(
        self,
        raw_response: str,
    ) -> StructuredScene:

        payload = self._extract_json(
            raw_response
        )

        # Pydantic validates the relational structure.
        scene = StructuredScene.model_validate(
            payload
        )

        # ---------------------------------------------
        # Observation
        # ---------------------------------------------

        if not scene.observation:
            raise ValueError(
                "Structured scene contains "
                "no observation."
            )

        scene.observation = (
            scene.observation.strip()
        )

        if not scene.observation:
            raise ValueError(
                "Structured scene observation "
                "is empty."
            )

        # ---------------------------------------------
        # Environment
        # ---------------------------------------------

        if scene.environment:

            scene.environment = (
                scene.environment.strip()
            )

        # ---------------------------------------------
        # Salient event
        # ---------------------------------------------

        if scene.salient_event:

            scene.salient_event = (
                scene.salient_event.strip()
            )

        # ---------------------------------------------
        # Clean object labels
        # ---------------------------------------------

        for obj in scene.objects:

            if obj.label:

                obj.label = (
                    obj.label
                    .strip()
                    .lower()
                )

        # ---------------------------------------------
        # Clean accessories
        # ---------------------------------------------

        for person in scene.people:

            person.visible_accessories = [
                accessory.strip().lower()
                for accessory
                in person.visible_accessories
                if accessory
                and accessory.strip()
            ]

            # -----------------------------------------
            # Clean activity type
            # -----------------------------------------

            if (
                person.activity
                and person.activity.type
            ):

                person.activity.type = (
                    person.activity.type
                    .strip()
                    .lower()
                    .replace(" ", "_")
                )

            # -----------------------------------------
            # Clean pose values
            # -----------------------------------------

            if person.pose:

                if person.pose.body_state:

                    person.pose.body_state = (
                        person.pose.body_state
                        .strip()
                        .lower()
                    )

                if person.pose.head_direction:

                    person.pose.head_direction = (
                        person.pose.head_direction
                        .strip()
                        .lower()
                    )

                # -------------------------------------
                # Clean hand values
                # -------------------------------------

                for hand in [
                    person.pose.left_hand,
                    person.pose.right_hand,
                ]:

                    if hand is None:
                        continue

                    if hand.hand:

                        hand.hand = (
                            hand.hand
                            .strip()
                            .lower()
                        )

                    if hand.relation:

                        hand.relation = (
                            hand.relation
                            .strip()
                            .lower()
                            .replace(
                                " ",
                                "_",
                            )
                        )

                    if hand.target:

                        hand.target = (
                            hand.target
                            .strip()
                            .lower()
                        )

        return scene

    # =====================================================
    # DEBUG PRINT
    # =====================================================

    def _print_structured_scene(
        self,
        scene: StructuredScene,
    ):

        print(
            "\nSTRUCTURED SCENE"
        )

        print(
            "=============================="
        )

        print(
            json.dumps(
                scene.model_dump(),
                indent=2,
                ensure_ascii=False,
            )
        )

        print(
            "=============================="
        )

    # =====================================================
    # WORKER LOOP
    # =====================================================

    def _worker_loop(
        self,
    ):

        print(
            "VLM background loop running."
        )

        while self.running:

            try:

                job = self.frame_queue.get(
                    timeout=0.5
                )

            except queue.Empty:

                continue

            try:

                # =====================================
                # MARK WORKER PROCESSING
                # =====================================

                with self.state_lock:

                    self.processing = True

                    self.processing_generation = (
                        job.generation
                    )

                print(
                    "\n=============================="
                )

                print(
                    "VLM PROCESSING"
                )

                print(
                    "Generation:",
                    job.generation,
                )

                print(
                    "=============================="
                )

                # =====================================
                # ONE AND ONLY VLM CALL
                # =====================================

                raw_answer = (
                    self.vision_service.analyze_frame(
                        job.frame,
                        self._build_prompt(),
                    )
                )

                if raw_answer:

                    raw_answer = (
                        raw_answer.strip()
                    )

                if not raw_answer:

                    raise RuntimeError(
                        "VLM returned an "
                        "empty response."
                    )

                # =====================================
                # LOCAL JSON PARSING
                #
                # No model call here.
                # =====================================

                structured_scene = (
                    self._parse_structured_scene(
                        raw_answer
                    )
                )

                # =====================================
                # DEBUG OUTPUT
                # =====================================

                self._print_structured_scene(
                    structured_scene
                )

                # =====================================
                # RETURN RESULT
                # =====================================

                result = VisionResult(
                    frame=job.frame,
                    generation=job.generation,

                    observation=(
                        structured_scene.observation
                    ),

                    structured_scene=(
                        structured_scene
                    ),

                    error=None,
                )

                self._emit_result(
                    result
                )

            except Exception as error:

                print(
                    "\n=============================="
                )

                print(
                    "VLM WORKER ERROR"
                )

                print(
                    "Generation:",
                    job.generation,
                )

                print(
                    "TYPE:",
                    type(error).__name__,
                )

                print(
                    "ERROR:",
                    repr(error),
                )

                traceback.print_exc()

                print(
                    "=============================="
                )

                # =====================================
                # RETURN FAILURE TO VISION LOOP
                #
                # Important because VisionLoop may
                # need to release transition_pending.
                # =====================================

                result = VisionResult(
                    frame=job.frame,
                    generation=job.generation,
                    observation=None,
                    structured_scene=None,
                    error=str(error),
                )

                self._emit_result(
                    result
                )

            finally:

                # =====================================
                # MARK WORKER FREE
                # =====================================

                with self.state_lock:

                    self.processing = False

                    self.processing_generation = (
                        None
                    )

                self.frame_queue.task_done()

    # =====================================================
    # RESULT CALLBACK
    # =====================================================

    def _emit_result(
        self,
        result: VisionResult,
    ):

        if self.on_result is None:
            return

        try:

            self.on_result(
                result
            )

        except Exception as error:

            print(
                "\nVLM RESULT CALLBACK ERROR:",
                repr(error),
            )

            traceback.print_exc()

    # =====================================================
    # WORKER STATE
    # =====================================================

    def is_processing(
        self,
    ) -> bool:

        with self.state_lock:

            return (
                self.processing
            )

    def get_processing_generation(
        self,
    ) -> Optional[int]:

        with self.state_lock:

            return (
                self.processing_generation
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
            "Stopping VLM Worker..."
        )

        self.running = False

        if self.worker_thread is not None:

            self.worker_thread.join(
                timeout=2.0
            )

        self.worker_thread = None

        # ---------------------------------------------
        # Clear waiting frames
        # ---------------------------------------------

        while True:

            try:

                self.frame_queue.get_nowait()

                self.frame_queue.task_done()

            except queue.Empty:

                break

        print(
            "VLM Worker stopped."
        )