import threading
import time
from enum import Enum
from typing import Optional

import cv2
import numpy as np

from app.services.camera_services import CameraService

from app.companion.adaptive_vision_manager import (
    AdaptiveVisionManager,
    TriggerReason,
)

from app.companion.vlm_worker import (
    VLMWorker,
    VisionResult,
)

from app.companion.memory.scene_models import (
    StructuredScene,
)

from app.companion.memory.scene_stabilizer import (
    SceneStabilizer,
)

from app.companion.memory.shared_memory import (
    memory_manager,
    working_memory,
    scene_intelligence,
    context_reasoner,
    temporal_world_state,
    goal_context,
    goal_progress_reasoner,
    proactive_policy,
    goal_candidate_generator,
    proactive_message_service,
)

from app.companion.proactive.proactive_reasoner import (
    ProactiveReasoner,
)

from app.companion.proactive.proactive_reasoner_worker import (
    ProactiveReasonerWorker,
    ProactiveReasoningJob,
    ProactiveReasoningWorkerResult,
)

from app.companion.proactive.proactive_message_worker import (
    ProactiveMessageWorker,
    ProactiveMessageJob,
    ProactiveMessageResult,
)

from app.companion.voice.voice_service import (
    VoiceService,
)

from app.companion.voice.voice_worker import (
    VoiceWorker,
    VoiceJob,
    VoiceResult,
)


# =========================================================
# REQUEST KIND
# =========================================================

class VisionRequestKind(
    str,
    Enum,
):

    FIRST_FRAME = "FIRST_FRAME"
    USER_REQUEST = "USER_REQUEST"
    FORCED_REFRESH = "FORCED_REFRESH"
    CURRENT_STATE = "CURRENT_STATE"
    EVENT_CAPTURE = "EVENT_CAPTURE"
    TRANSITION_CANDIDATE = "TRANSITION_CANDIDATE"
    DRIFT_RECOVERY = "DRIFT_RECOVERY"


# =========================================================
# VISION LOOP
# =========================================================

class VisionLoop:

    def __init__(
        self,
    ):

        # =================================================
        # CAMERA
        # =================================================

        self.camera = (
            CameraService()
        )

        # =================================================
        # ADAPTIVE VISION V4
        # =================================================

        self.vision_manager = (
            AdaptiveVisionManager(
                min_vlm_interval_seconds=4.0,
                max_silence_seconds=25.0,

                history_size=30,

                minimum_threshold=0.025,
                maximum_threshold=0.18,

                scene_transition_threshold=0.12,

                event_capture_min_seconds=0.35,
                event_capture_max_seconds=1.25,

                event_settle_seconds=0.25,
                event_settle_ratio=0.45,
                event_settle_floor=0.018,

                persistent_state_ratio=0.70,

                persistent_change_threshold=0.045,
                persistent_change_seconds=0.20,

                persistent_release_threshold=0.025,
                persistent_max_global_motion=0.02,
            )
        )

        # =================================================
        # LATEST FRAME
        # =================================================

        self.latest_frame: Optional[
            np.ndarray
        ] = None

        self.latest_frame_lock = (
            threading.Lock()
        )

        # =================================================
        # SCENE STATE
        # =================================================

        self.scene_lock = (
            threading.RLock()
        )

        self.scene_generation = 0

        self.transition_pending = False

        self.transition_candidate_pending = (
            False
        )

        self.transition_candidate_reference_diff = (
            0.0
        )

        # =================================================
        # PHYSICAL CONTEXT
        # =================================================

        self.current_memory_id: Optional[
            int
        ] = None

        self.current_structured_scene: Optional[
            StructuredScene
        ] = None

        # =================================================
        # ACTIVE REQUEST
        # =================================================

        self.active_request_kind: Optional[
            VisionRequestKind
        ] = None

        self.active_request_generation: Optional[
            int
        ] = None

        # =================================================
        # STABILIZER
        # =================================================

        self.scene_stabilizer = (
            SceneStabilizer(
                object_add_threshold=2,
                object_miss_threshold=3,

                accessory_add_threshold=2,
                accessory_miss_threshold=3,
            )
        )

        # =================================================
        # VLM WORKER
        # =================================================

        self.vlm_worker = (
            VLMWorker(
                on_result=(
                    self._on_vlm_result
                )
            )
        )

        # =================================================
        # PROACTIVE REASONER V2
        # =================================================

        self.proactive_reasoner = (
            ProactiveReasoner(
                context_reasoner=(
                    context_reasoner
                ),
                temporal_world_state=(
                    temporal_world_state
                ),
                goal_context=(
                    goal_context
                ),
                goal_progress_reasoner=(
                    goal_progress_reasoner
                ),
            )
        )

        # =================================================
        # PROACTIVE REASONER WORKER
        # =================================================

        self.proactive_reasoner_worker = (
            ProactiveReasonerWorker(
                reasoner=(
                    self.proactive_reasoner
                ),

                on_result=(
                    self._on_proactive_reasoning_result
                ),
            )
        )

        # =================================================
        # PROACTIVE MESSAGE WORKER
        # =================================================

        self.proactive_message_worker = (
            ProactiveMessageWorker(
                on_result=(
                    self._on_proactive_message_result
                ),

                message_service=(
                    proactive_message_service
                ),
            )
        )

        # =================================================
        # VOICE
        # =================================================

        self.voice_service = (
            VoiceService(
                rate=175,
                volume=1.0,
            )
        )

        self.voice_worker = (
            VoiceWorker(
                on_result=(
                    self._on_voice_result
                ),

                voice_service=(
                    self.voice_service
                ),
            )
        )

        # =================================================
        # INFERENCE DRIFT
        # =================================================

        self.inference_drift_threshold = (
            0.10
        )

        # =================================================
        # TEMPORAL OBSERVATION
        # =================================================

        self.last_observed_update = (
            0.0
        )

        self.observed_update_interval = (
            5.0
        )

        # =================================================
        # DEBUG
        # =================================================

        self.last_debug_time = (
            0.0
        )

        self.debug_interval_seconds = (
            1.0
        )

        self.running = False

    # =====================================================
    # ACTIVE REQUEST
    # =====================================================

    def _set_active_request(
        self,
        kind: VisionRequestKind,
        generation: int,
    ):

        with self.scene_lock:

            self.active_request_kind = (
                kind
            )

            self.active_request_generation = (
                generation
            )

        print(
            "VLM_REQUEST_KIND:",
            kind.value,
        )

    # =====================================================

    def _consume_active_request(
        self,
        generation: int,
    ) -> VisionRequestKind:

        with self.scene_lock:

            if (
                self.active_request_kind
                is not None
                and
                self.active_request_generation
                == generation
            ):

                kind = (
                    self.active_request_kind
                )

            else:

                kind = (
                    VisionRequestKind
                    .CURRENT_STATE
                )

            self.active_request_kind = (
                None
            )

            self.active_request_generation = (
                None
            )

        return kind

    # =====================================================

    def _clear_active_request(
        self,
    ):

        with self.scene_lock:

            self.active_request_kind = (
                None
            )

            self.active_request_generation = (
                None
            )

    # =====================================================
    # START
    # =====================================================

    def start(
        self,
    ):

        print(
            "\n===================================="
        )

        print(
            "STARTING ORION VISION V4 + "
            "PROACTIVE REASONING V2"
        )

        print(
            "===================================="
        )

        print(
            "Working memory:",
            working_memory.file_path,
        )

        self.camera.start()

        self.vlm_worker.start()

        self.proactive_reasoner_worker.start()

        self.proactive_message_worker.start()

        self.voice_worker.start()

        self.running = True

        print(
            "Event Capture V4 active."
        )

        print(
            "Context Reasoner V1 active."
        )

        print(
            "Temporal World State storage active."
        )

        print(
            "Proactive Policy V1 active."
        )

        print(
            "Proactive Reasoner V2 active."
        )

        print(
            "Proactive Message Worker active."
        )

        print(
            "Voice Output V1 active."
        )

        print(
            "Q = quit"
        )

        print(
            "F = force analysis"
        )

        print(
            "====================================\n"
        )

        try:

            while self.running:

                frame = (
                    self.camera.get_frame()
                )

                if frame is None:

                    continue

                with self.latest_frame_lock:

                    self.latest_frame = (
                        frame.copy()
                    )

                self.vision_manager.set_vlm_busy(
                    self.vlm_worker
                    .is_processing()
                )

                decision = (
                    self.vision_manager
                    .evaluate(
                        frame
                    )
                )

                self._print_debug(
                    decision
                )

                if decision.should_analyze:

                    analysis_frame = (
                        frame
                    )

                    if (
                        decision.trigger_reason
                        ==
                        TriggerReason.EVENT_READY
                    ):

                        selected_frame = (
                            self.vision_manager
                            .consume_ready_event_frame()
                        )

                        if (
                            selected_frame
                            is not None
                        ):

                            analysis_frame = (
                                selected_frame
                            )

                            print(
                                "\nUSING V4 EVENT FRAME"
                            )

                            print(
                                "Frame type:",
                                decision.selected_frame_type,
                            )

                            print(
                                "Original trigger:",
                                (
                                    decision
                                    .captured_trigger_reason
                                    .value
                                    if
                                    decision
                                    .captured_trigger_reason
                                    else None
                                ),
                            )

                            print(
                                "Max reference:",
                                f"{decision.max_reference_diff:.4f}",
                            )

                            print(
                                "Settled reference:",
                                f"{decision.settled_reference_diff:.4f}",
                            )

                            print(
                                "Settled ratio:",
                                decision.settled_ratio,
                            )

                    is_transition_capture = (
                        decision.trigger_reason
                        ==
                        TriggerReason.EVENT_READY

                        and

                        decision.captured_trigger_reason
                        ==
                        TriggerReason
                        .SCENE_TRANSITION_CANDIDATE
                    )

                    if is_transition_capture:

                        self._handle_transition_candidate(
                            analysis_frame,
                            decision,
                        )

                    else:

                        self._handle_normal_event(
                            analysis_frame,
                            decision,
                        )

                self._update_scene_persistence(
                    decision
                )

                cv2.imshow(
                    "Orion Adaptive Vision V4",
                    frame,
                )

                key = (
                    cv2.waitKey(1)
                    & 0xFF
                )

                if key == ord("q"):

                    break

                if key == ord("f"):

                    print(
                        "\nUSER REQUESTED "
                        "VISION ANALYSIS"
                    )

                    self.vision_manager.request_analysis()

        except KeyboardInterrupt:

            print(
                "\nKeyboard interrupt."
            )

        finally:

            self.stop()

    # =====================================================
    # TRANSITION CANDIDATE
    # =====================================================

    def _handle_transition_candidate(
        self,
        frame,
        decision,
    ):

        with self.scene_lock:

            if self.transition_pending:

                return

            if self.transition_candidate_pending:

                return

            if self.vlm_worker.is_processing():

                return

            generation = (
                self.scene_generation
            )

            memory_id = (
                self.current_memory_id
            )

            self.transition_candidate_pending = (
                True
            )

            self.transition_candidate_reference_diff = (
                float(
                    decision.scene_reference_diff
                )
            )

        print(
            "\n================================"
        )

        print(
            "SCENE TRANSITION CANDIDATE"
        )

        print(
            "================================"
        )

        print(
            "Generation:",
            generation,
        )

        print(
            "Memory:",
            memory_id,
        )

        print(
            "Reference diff:",
            f"{decision.scene_reference_diff:.4f}",
        )

        print(
            "Representative:",
            decision.selected_frame_type,
        )

        print(
            "================================"
        )

        self._set_active_request(
            VisionRequestKind
            .TRANSITION_CANDIDATE,
            generation,
        )

        submitted = (
            self.vlm_worker.submit(
                frame,
                generation,
            )
        )

        if submitted:

            self.vision_manager.mark_analysis_started()

        else:

            self._clear_active_request()

            with self.scene_lock:

                self.transition_candidate_pending = (
                    False
                )

                self.transition_candidate_reference_diff = (
                    0.0
                )

    # =====================================================
    # NORMAL EVENT
    # =====================================================

    def _handle_normal_event(
        self,
        frame,
        decision,
    ):

        with self.scene_lock:

            if self.transition_pending:

                return

            if self.transition_candidate_pending:

                return

            if self.vlm_worker.is_processing():

                return

            generation = (
                self.scene_generation
            )

        if (
            decision.trigger_reason
            ==
            TriggerReason.EVENT_READY
        ):

            request_kind = (
                VisionRequestKind
                .EVENT_CAPTURE
            )

        elif (
            decision.trigger_reason
            ==
            TriggerReason.USER_REQUEST
        ):

            request_kind = (
                VisionRequestKind
                .USER_REQUEST
            )

        elif (
            decision.trigger_reason
            ==
            TriggerReason.FORCED_REFRESH
        ):

            request_kind = (
                VisionRequestKind
                .FORCED_REFRESH
            )

        elif (
            decision.trigger_reason
            ==
            TriggerReason.FIRST_FRAME
        ):

            request_kind = (
                VisionRequestKind
                .FIRST_FRAME
            )

        else:

            request_kind = (
                VisionRequestKind
                .CURRENT_STATE
            )

        print(
            "\n=============================="
        )

        print(
            "VISION EVENT"
        )

        print(
            "=============================="
        )

        print(
            "Trigger:",
            decision.trigger_reason.value,
        )

        print(
            "Captured trigger:",
            (
                decision
                .captured_trigger_reason
                .value
                if
                decision
                .captured_trigger_reason
                else None
            ),
        )

        print(
            "Frame type:",
            decision.selected_frame_type,
        )

        print(
            "Request:",
            request_kind.value,
        )

        print(
            "Generation:",
            generation,
        )

        print(
            "=============================="
        )

        self._set_active_request(
            request_kind,
            generation,
        )

        submitted = (
            self.vlm_worker.submit(
                frame,
                generation,
            )
        )

        if submitted:

            self.vision_manager.mark_analysis_started()

        else:

            self._clear_active_request()

    # =====================================================
    # VLM RESULT
    # =====================================================

    def _on_vlm_result(
        self,
        result: VisionResult,
    ):

        self.vision_manager.set_vlm_busy(
            False
        )

        request_kind = (
            self._consume_active_request(
                result.generation
            )
        )

        print(
            "\n=============================="
        )

        print(
            "VLM RESULT"
        )

        print(
            "=============================="
        )

        print(
            "Generation:",
            result.generation,
        )

        print(
            "Request:",
            request_kind.value,
        )

        with self.scene_lock:

            current_generation = (
                self.scene_generation
            )

        if (
            result.generation
            != current_generation
        ):

            print(
                "STALE GENERATION DISCARDED"
            )

            return

        if result.error is not None:

            print(
                "VLM ERROR:",
                result.error,
            )

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        if not result.observation:

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        observation = (
            result.observation
            .strip()
        )

        if not observation:

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        if (
            result.structured_scene
            is None
        ):

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        print(
            "\nORION OBSERVATION:"
        )

        print(
            observation
        )

        latest_frame = (
            self._get_latest_frame()
        )

        if latest_frame is None:

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        drift = (
            self._calculate_inference_drift(
                result.frame,
                latest_frame,
            )
        )

        print(
            "\nINFERENCE DRIFT:",
            f"{drift:.4f}",
        )

        print(
            "Threshold:",
            f"{self.inference_drift_threshold:.4f}",
        )

        # =================================================
        # FIRST FRAME
        # =================================================

        if (
            request_kind
            ==
            VisionRequestKind.FIRST_FRAME
        ):

            print(
                "FIRST FRAME -> baseline"
            )

            self._establish_scene(
                result,
                observation,
                latest_frame,
            )

            return

        # =================================================
        # INFERENCE DRIFT
        # =================================================

        if (
            drift
            >= self.inference_drift_threshold
        ):

            if (
                request_kind
                ==
                VisionRequestKind.EVENT_CAPTURE
            ):

                handled = (
                    self._handle_drifted_event_capture(
                        result,
                        observation,
                        latest_frame,
                        drift,
                    )
                )

                if handled:

                    return

            if (
                request_kind
                ==
                VisionRequestKind
                .TRANSITION_CANDIDATE
            ):

                handled = (
                    self._handle_drifted_transition_candidate(
                        result,
                        observation,
                        latest_frame,
                        drift,
                    )
                )

                if handled:

                    return

            if (
                request_kind
                ==
                VisionRequestKind.DRIFT_RECOVERY
            ):

                print(
                    "Recovery result still drifted."
                )

                print(
                    "No third VLM call."
                )

                self._establish_scene(
                    result,
                    observation,
                    latest_frame,
                )

                return

            self._handle_inference_drift(
                result,
                observation,
                latest_frame,
                drift,
                request_kind,
            )

            return

        # =================================================
        # NORMAL RESULT
        # =================================================

        self._establish_scene(
            result,
            observation,
            latest_frame,
        )

    # =====================================================
    # TRANSIENT SCENE CHECK
    # =====================================================

    def _is_meaningful_transient_scene(
        self,
        scene,
    ):

        if scene is None:

            return False

        salient = getattr(
            scene,
            "salient_event",
            None,
        )

        if salient:

            value = (
                str(salient)
                .strip()
                .lower()
            )

            if value not in {
                "",
                "none",
                "null",
                "unknown",
                "uncertain",
            }:

                return True

        passive_activities = {
            "",
            "idle",
            "looking",
            "looking_at_camera",
            "looking_forward",
            "looking_down",
            "unknown",
            "none",
        }

        meaningful_relations = {
            "touching",
            "holding",
            "covering",
            "raised",
            "resting_on",
            "pointing_at",
        }

        people = (
            getattr(
                scene,
                "people",
                [],
            )
            or []
        )

        for person in people:

            activity = getattr(
                person,
                "activity",
                None,
            )

            if activity is not None:

                activity_type = getattr(
                    activity,
                    "type",
                    None,
                )

                if activity_type:

                    value = (
                        str(activity_type)
                        .strip()
                        .lower()
                    )

                    if (
                        value
                        not in passive_activities
                    ):

                        return True

            pose = getattr(
                person,
                "pose",
                None,
            )

            if pose is None:

                continue

            for hand_name in (
                "left_hand",
                "right_hand",
            ):

                hand = getattr(
                    pose,
                    hand_name,
                    None,
                )

                if hand is None:

                    continue

                relation = getattr(
                    hand,
                    "relation",
                    None,
                )

                if relation is None:

                    continue

                relation_value = (
                    str(relation)
                    .strip()
                    .lower()
                )

                if (
                    relation_value
                    in meaningful_relations
                ):

                    return True

        return False

    # =====================================================
    # DRIFTED EVENT CAPTURE
    # =====================================================

    def _handle_drifted_event_capture(
        self,
        result,
        observation,
        latest_frame,
        drift,
    ):

        scene = (
            result.structured_scene
        )

        if scene is None:

            return False

        meaningful = (
            self._is_meaningful_transient_scene(
                scene
            )
        )

        if not meaningful:

            return False

        with self.scene_lock:

            memory_id = (
                self.current_memory_id
            )

            generation = (
                self.scene_generation
            )

        try:

            payload = (
                scene.model_dump()
            )

        except AttributeError:

            payload = (
                scene.dict()
            )

        working_memory.add_event(
            event_type="SEMANTIC_EVENT",

            observation=(
                observation
            ),

            memory_id=(
                memory_id
            ),

            metadata={
                "generation": generation,

                "reason": (
                    "captured transient event; "
                    "live view changed before "
                    "VLM completed"
                ),

                "source": (
                    "event_capture"
                ),

                "historical_only": True,

                "current_state_applied": False,

                "drift_score": (
                    float(
                        drift
                    )
                ),

                "salient_event": (
                    getattr(
                        scene,
                        "salient_event",
                        None,
                    )
                ),

                "structured_scene": (
                    payload
                ),
            },
        )

        print(
            "\nTRANSIENT EVENT PRESERVED"
        )

        print(
            "Observation:",
            observation,
        )

        print(
            "Second VLM call: False"
        )

        self.vision_manager.confirm_scene(
            latest_frame
        )

        return True

    # =====================================================
    # DRIFTED TRANSITION CANDIDATE
    # =====================================================

    def _handle_drifted_transition_candidate(
        self,
        result,
        observation,
        latest_frame,
        drift,
    ):

        candidate = (
            result.structured_scene
        )

        if candidate is None:

            return False

        with self.scene_lock:

            previous = (
                self.current_structured_scene
            )

            memory_id = (
                self.current_memory_id
            )

            generation = (
                self.scene_generation
            )

        if previous is None:

            return False

        evaluation = (
            scene_intelligence
            .evaluate_context_transition(
                previous=previous,
                candidate=candidate,
            )
        )

        self._print_context_transition(
            evaluation
        )

        confirmed = bool(
            evaluation.get(
                "confirmed",
                False,
            )
        )

        if confirmed:

            return False

        meaningful = (
            self._is_meaningful_transient_scene(
                candidate
            )
        )

        if meaningful:

            try:

                payload = (
                    candidate.model_dump()
                )

            except AttributeError:

                payload = (
                    candidate.dict()
                )

            working_memory.add_event(
                event_type="SEMANTIC_EVENT",

                observation=(
                    observation
                ),

                memory_id=(
                    memory_id
                ),

                metadata={
                    "generation": (
                        generation
                    ),

                    "reason": (
                        "semantic action captured "
                        "during rejected physical "
                        "transition candidate"
                    ),

                    "source": (
                        "transition_candidate"
                    ),

                    "historical_only": True,

                    "current_state_applied": False,

                    "drift_score": (
                        float(
                            drift
                        )
                    ),

                    "transition_rejected": True,

                    "salient_event": (
                        getattr(
                            candidate,
                            "salient_event",
                            None,
                        )
                    ),

                    "structured_scene": (
                        payload
                    ),
                },
            )

        with self.scene_lock:

            self.transition_candidate_pending = (
                False
            )

            self.transition_candidate_reference_diff = (
                0.0
            )

            self.transition_pending = (
                False
            )

        self.vision_manager.confirm_scene(
            latest_frame
        )

        print(
            "\nFALSE TRANSITION REJECTED"
        )

        print(
            "Memory preserved:",
            memory_id,
        )

        print(
            "Transient preserved:",
            meaningful,
        )

        print(
            "Second VLM call: False"
        )

        return True

    # =====================================================
    # ESTABLISH / UPDATE SCENE
    # =====================================================

    def _establish_scene(
        self,
        result,
        observation,
        latest_frame,
    ):

        raw_scene = (
            result.structured_scene
        )

        if raw_scene is None:

            self._recover_from_vlm_failure(
                result.generation
            )

            return

        with self.scene_lock:

            if (
                result.generation
                != self.scene_generation
            ):

                return

            active_memory_id = (
                self.current_memory_id
            )

            previous_scene = (
                self.current_structured_scene
            )

            transition_candidate = (
                self.transition_candidate_pending
            )

            candidate_reference_diff = (
                self.transition_candidate_reference_diff
            )

        context_evaluation = None

        physical_transition = False

        # =================================================
        # PHYSICAL TRANSITION VALIDATION
        # =================================================

        if (
            transition_candidate
            and
            previous_scene is not None
        ):

            context_evaluation = (
                scene_intelligence
                .evaluate_context_transition(
                    previous=(
                        previous_scene
                    ),

                    candidate=(
                        raw_scene
                    ),
                )
            )

            physical_transition = (
                bool(
                    context_evaluation.get(
                        "confirmed",
                        False,
                    )
                )
            )

            self._print_context_transition(
                context_evaluation
            )

        accepted_generation = (
            result.generation
        )

        # =================================================
        # CONFIRMED PHYSICAL TRANSITION
        # =================================================

        if physical_transition:

            with self.scene_lock:

                old_memory_id = (
                    self.current_memory_id
                )

                self.scene_generation += 1

                accepted_generation = (
                    self.scene_generation
                )

                self.current_memory_id = (
                    None
                )

                self.current_structured_scene = (
                    None
                )

                self.transition_candidate_pending = (
                    False
                )

                self.transition_candidate_reference_diff = (
                    0.0
                )

                self.transition_pending = (
                    False
                )

            working_memory.clear_current_scene(
                reason="scene_transition"
            )

            working_memory.add_event(
                event_type=(
                    "SCENE_TRANSITION"
                ),

                memory_id=(
                    old_memory_id
                ),

                metadata={
                    "generation": (
                        accepted_generation
                    ),

                    "reference_diff": (
                        candidate_reference_diff
                    ),

                    "confirmation": (
                        context_evaluation
                    ),
                },
            )

            self.scene_stabilizer.reset()

            self.vision_manager.cancel_event_capture()

            active_memory_id = None

            previous_scene = None

            print(
                "\nPHYSICAL TRANSITION CONFIRMED"
            )

        elif transition_candidate:

            with self.scene_lock:

                self.transition_candidate_pending = (
                    False
                )

                self.transition_candidate_reference_diff = (
                    0.0
                )

                self.transition_pending = (
                    False
                )

            print(
                "\nTRANSITION CANDIDATE REJECTED"
            )

        # =================================================
        # STABILIZE SCENE
        # =================================================

        stable_scene = (
            self.scene_stabilizer
            .update(
                raw_scene
            )
        )

        lifecycle = (
            self.scene_stabilizer
            .last_changes()
        )

        # =================================================
        # SEMANTIC COMPARISON
        # =================================================

        semantic_result = (
            scene_intelligence
            .compare_scenes(
                previous=(
                    previous_scene
                ),

                current=(
                    stable_scene
                ),

                lifecycle_changes=(
                    lifecycle
                ),
            )
        )

        self._print_semantic_result(
            semantic_result
        )

        # =================================================
        # PHYSICAL MEMORY IDENTITY
        # =================================================

        memory_id = None

        if active_memory_id is not None:

            continued = (
                memory_manager
                .continue_scene(
                    memory_id=(
                        active_memory_id
                    ),

                    confirmed=True,
                )
            )

            if continued:

                memory_id = (
                    active_memory_id
                )

            else:

                memory_id = (
                    memory_manager
                    .resolve_new_context(
                        observation=(
                            observation
                        ),

                        allow_historical_reuse=True,
                    )
                )

        else:

            memory_id = (
                memory_manager
                .resolve_new_context(
                    observation=(
                        observation
                    ),

                    allow_historical_reuse=True,
                )
            )

        if memory_id is None:

            self._recover_from_vlm_failure(
                accepted_generation
            )

            return

        # =================================================
        # APPLY CURRENT STATE
        # =================================================

        with self.scene_lock:

            if (
                accepted_generation
                != self.scene_generation
            ):

                return

            self.current_memory_id = (
                memory_id
            )

            self.current_structured_scene = (
                stable_scene
            )

            self.transition_pending = (
                False
            )

            self.transition_candidate_pending = (
                False
            )

            self.transition_candidate_reference_diff = (
                0.0
            )

        # =================================================
        # NEW TEMPORAL WORLD STATE SUPPORT
        #
        # Store the full stabilized structured scene
        # inside WorkingMemory.current_scene.
        #
        # This gives TemporalWorldState authoritative
        # access to:
        #
        #     current objects
        #     object states
        #     activity
        #     hand interactions
        #     environment
        #     visible text
        # =================================================

        try:

            current_scene_payload = (
                stable_scene.model_dump()
            )

        except AttributeError:

            current_scene_payload = (
                stable_scene.dict()
            )

        working_memory.set_current_scene(
            observation=(
                observation
            ),

            memory_id=(
                memory_id
            ),

            generation=(
                accepted_generation
            ),

            structured_scene=(
                current_scene_payload
            ),
        )

        # =================================================
        # STORE MEANINGFUL SEMANTIC EVENT
        # =================================================

        if (
            not physical_transition
            and
            not semantic_result.get(
                "is_first_scene",
                False,
            )
            and
            semantic_result.get(
                "meaningful_event",
                False,
            )
        ):

            self._store_semantic_event(
                generation=(
                    accepted_generation
                ),

                memory_id=(
                    memory_id
                ),

                structured_scene=(
                    stable_scene
                ),

                semantic_result=(
                    semantic_result
                ),
            )

            # =============================================
            # PROACTIVE PIPELINE
            # =============================================

            self._evaluate_proactive_companion()

        # =================================================
        # CONFIRM CV REFERENCE
        # =================================================

        self.vision_manager.confirm_scene(
            latest_frame
        )

        self.last_observed_update = (
            time.time()
        )

        print(
            "\n=============================="
        )

        print(
            "SCENE ESTABLISHED"
        )

        print(
            "=============================="
        )

        print(
            "Generation:",
            accepted_generation,
        )

        print(
            "Memory ID:",
            memory_id,
        )

        print(
            "Physical transition:",
            physical_transition,
        )

        print(
            "Semantic event:",
            semantic_result.get(
                "meaningful_event",
                False,
            ),
        )

        print(
            "Structured current scene stored: True"
        )

        print(
            "=============================="
        )

    # =====================================================
    # STORE SEMANTIC EVENT
    # =====================================================

    def _store_semantic_event(
        self,
        generation,
        memory_id,
        structured_scene,
        semantic_result,
    ):

        try:

            payload = (
                structured_scene
                .model_dump()
            )

        except AttributeError:

            payload = (
                structured_scene
                .dict()
            )

        metadata = (
            dict(
                semantic_result
            )
        )

        metadata.update(
            {
                "generation": (
                    generation
                ),

                "historical_only": (
                    False
                ),

                "current_state_applied": (
                    True
                ),

                "structured_scene": (
                    payload
                ),
            }
        )

        working_memory.add_event(
            event_type=(
                "SEMANTIC_EVENT"
            ),

            observation=(
                structured_scene
                .observation
            ),

            memory_id=(
                memory_id
            ),

            metadata=(
                metadata
            ),
        )

        print(
            "\n=============================="
        )

        print(
            "SEMANTIC EVENT"
        )

        print(
            "=============================="
        )

        print(
            "Memory:",
            memory_id,
        )

        print(
            "Reason:",
            semantic_result.get(
                "reason"
            ),
        )

        print(
            "=============================="
        )

    # =====================================================
    # PROACTIVE COMPANION
    # =====================================================

    def _evaluate_proactive_companion(
        self,
    ):

        # =================================================
        # UNIFIED PROACTIVE CANDIDATE GENERATION
        #
        # Candidate source 1:
        #     visual/context ProactivePolicy
        #
        # Candidate source 2:
        #     GoalCandidateGenerator
        #
        # Neither source decides to speak.
        # ProactiveReasoner V2 remains the final gate.
        # =================================================

        visual_decision = None
        goal_decision = None

        # =================================================
        # VISUAL / CONTEXT CANDIDATE
        # =================================================

        try:

            visual_decision = (
                proactive_policy
                .evaluate()
            )

        except Exception as exc:

            print(
                "\nPROACTIVE POLICY ERROR:",
                repr(exc),
            )

        # =================================================
        # GOAL-DRIVEN CANDIDATE
        # =================================================

        try:

            goal_decision = (
                goal_candidate_generator
                .evaluate()
            )

        except Exception as exc:

            print(
                "\nGOAL CANDIDATE ERROR:",
                repr(exc),
            )

        # =================================================
        # DEBUG
        # =================================================

        print(
            "\n================================"
        )

        print(
            "UNIFIED PROACTIVE CANDIDATES"
        )

        print(
            "================================"
        )

        if visual_decision is not None:

            print(
                "Visual candidate:"
            )

            print(
                "  should_speak:",
                visual_decision.should_speak,
            )

            print(
                "  reason:",
                visual_decision.reason,
            )

            print(
                "  priority:",
                visual_decision.priority,
            )

        else:

            print(
                "Visual candidate: unavailable"
            )

        if goal_decision is not None:

            print(
                "Goal candidate:"
            )

            print(
                "  should_speak:",
                goal_decision.should_speak,
            )

            print(
                "  reason:",
                goal_decision.reason,
            )

            print(
                "  priority:",
                goal_decision.priority,
            )

        else:

            print(
                "Goal candidate: unavailable"
            )

        print(
            "================================"
        )

        # =================================================
        # COLLECT VALID CANDIDATES
        # =================================================

        candidates = []

        if (
            visual_decision is not None
            and
            visual_decision.should_speak
            and
            visual_decision.message_hint
        ):

            candidates.append(
                visual_decision
            )

        if (
            goal_decision is not None
            and
            goal_decision.should_speak
            and
            goal_decision.message_hint
        ):

            candidates.append(
                goal_decision
            )

        if not candidates:

            print(
                "UNIFIED PROACTIVE: "
                "no candidate for V2."
            )

            return

        # =================================================
        # SELECT HIGHEST PRIORITY CANDIDATE
        #
        # Goal candidate: priority 4
        # Visual interaction: priority 3
        # Repeated action: priority 2
        # Salient event: priority 1
        #
        # Priority decides which candidate V2 evaluates.
        # It does NOT approve speech.
        # =================================================

        decision = max(
            candidates,
            key=lambda item: (
                item.priority
            ),
        )

        print(
            "\n================================"
        )

        print(
            "PROACTIVE CANDIDATE SELECTED"
        )

        print(
            "================================"
        )

        print(
            "Reason:",
            decision.reason,
        )

        print(
            "Priority:",
            decision.priority,
        )

        print(
            "Message hint:",
            decision.message_hint,
        )

        print(
            "================================"
        )

        # =================================================
        # PHYSICAL CONTEXT
        # =================================================

        with self.scene_lock:

            memory_id = (
                self.current_memory_id
            )

            generation = (
                self.scene_generation
            )

        # =================================================
        # SEND TO EXISTING ASYNC V2 WORKER
        # =================================================

        job = (
            ProactiveReasoningJob(
                policy_decision=(
                    decision
                ),
                memory_id=(
                    memory_id
                ),
                generation=(
                    generation
                ),
            )
        )

        submitted = (
            self.proactive_reasoner_worker
            .submit(
                job
            )
        )

        if not submitted:

            print(
                "\nPROACTIVE REASONING JOB "
                "NOT SUBMITTED"
            )

            return

        print(
            "\nPROACTIVE REASONING JOB ACCEPTED"
        )

        print(
            "Candidate source:",
            decision.reason,
        )

        print(
            "Vision callback continues "
            "without waiting for reasoning LLM."
        )

    # =====================================================
    # PROACTIVE REASONING RESULT
    # =====================================================

    def _on_proactive_reasoning_result(
        self,
        result: ProactiveReasoningWorkerResult,
    ):

        if result.error is not None:

            print(
                "\nPROACTIVE REASONING ERROR:",
                result.error,
            )

            return

        reasoning = (
            result.reasoning
        )

        if reasoning is None:

            print(
                "\nPROACTIVE REASONING EMPTY"
            )

            return

        # =================================================
        # STALE CONTEXT CHECK
        # =================================================

        with self.scene_lock:

            current_generation = (
                self.scene_generation
            )

            current_memory_id = (
                self.current_memory_id
            )

        if (
            result.generation
            is not None

            and

            result.generation
            != current_generation
        ):

            print(
                "\n================================"
            )

            print(
                "PROACTIVE REASONING DISCARDED"
            )

            print(
                "================================"
            )

            print(
                "Reason: stale generation"
            )

            print(
                "Reasoning generation:",
                result.generation,
            )

            print(
                "Current generation:",
                current_generation,
            )

            print(
                "================================"
            )

            return

        if (
            result.memory_id
            is not None

            and

            current_memory_id
            is not None

            and

            result.memory_id
            != current_memory_id
        ):

            print(
                "\n================================"
            )

            print(
                "PROACTIVE REASONING DISCARDED"
            )

            print(
                "================================"
            )

            print(
                "Reason: physical context changed"
            )

            print(
                "Reasoning memory:",
                result.memory_id,
            )

            print(
                "Current memory:",
                current_memory_id,
            )

            print(
                "================================"
            )

            return

        # =================================================
        # V2 RESULT
        # =================================================

        print(
            "\n================================"
        )

        print(
            "PROACTIVE REASONER V2"
        )

        print(
            "================================"
        )

        print(
            "Should speak:",
            reasoning.should_speak,
        )

        print(
            "Reason:",
            reasoning.reason,
        )

        print(
            "Candidate type:",
            reasoning.candidate_type,
        )

        print(
            "Priority:",
            reasoning.priority,
        )

        print(
            "Message hint:",
            reasoning.message_hint,
        )

        print(
            "================================"
        )

        # =================================================
        # V2 REJECTED
        # =================================================

        if not reasoning.should_speak:

            print(
                "V2 DECISION: SILENT"
            )

            return

        if not reasoning.message_hint:

            return

        # =================================================
        # V2 APPROVED
        #
        # Cooldown starts ONLY here.
        # =================================================

        proactive_policy.register_spoken(
            reason=(
                reasoning.reason
            ),
            message_hint=(
                reasoning.message_hint
            ),
        )

        goal_candidate_generator.register_spoken(
            reason=(
                reasoning.reason
            ),
            message_hint=(
                reasoning.message_hint
            ),
        )

        # =================================================
        # GET FRESH CONTEXT FOR MESSAGE GENERATION
        # =================================================

        try:

            snapshot = (
                context_reasoner
                .snapshot()
            )

        except Exception as exc:

            print(
                "\nPROACTIVE CONTEXT ERROR:",
                repr(exc),
            )

            return

        if snapshot is None:

            return

        if hasattr(
            snapshot,
            "to_dict",
        ):

            data = (
                snapshot.to_dict()
            )

        elif isinstance(
            snapshot,
            dict,
        ):

            data = (
                snapshot
            )

        else:

            print(
                "\nPROACTIVE CONTEXT ERROR: "
                "unsupported snapshot type"
            )

            return

        # =================================================
        # MESSAGE GENERATION
        # =================================================

        message_job = (
            ProactiveMessageJob(
                message_hint=(
                    reasoning.message_hint
                ),

                current_activity=(
                    data.get(
                        "current_activity"
                    )
                ),

                current_salient_event=(
                    data.get(
                        "current_salient_event"
                    )
                ),

                active_interactions=(
                    data.get(
                        "active_interactions"
                    )
                    or []
                ),

                recent_actions=(
                    data.get(
                        "recent_actions"
                    )
                    or []
                ),

                memory_id=(
                    result.memory_id
                ),

                generation=(
                    result.generation
                ),

                reason=(
                    reasoning.reason
                ),

                priority=(
                    reasoning.priority
                ),
            )
        )

        submitted = (
            self.proactive_message_worker
            .submit(
                message_job
            )
        )

        if not submitted:

            print(
                "\nPROACTIVE MESSAGE JOB "
                "NOT SUBMITTED"
            )

            return

        print(
            "\nPROACTIVE MESSAGE JOB ACCEPTED"
        )

        print(
            "V2 approved candidate."
        )

    # =====================================================
    # PROACTIVE MESSAGE RESULT
    # =====================================================

    def _on_proactive_message_result(
        self,
        result: ProactiveMessageResult,
    ):

        if result.error is not None:

            print(
                "\nPROACTIVE MESSAGE RESULT ERROR:",
                result.error,
            )

            return

        if not result.message:

            print(
                "\nPROACTIVE MESSAGE EMPTY"
            )

            return

        message = (
            result.message
            .strip()
        )

        if not message:

            return

        # =================================================
        # STALE CONTEXT CHECK
        # =================================================

        with self.scene_lock:

            current_generation = (
                self.scene_generation
            )

            current_memory_id = (
                self.current_memory_id
            )

        if (
            result.generation
            is not None

            and

            result.generation
            != current_generation
        ):

            print(
                "\n================================"
            )

            print(
                "PROACTIVE MESSAGE DISCARDED"
            )

            print(
                "================================"
            )

            print(
                "Reason: stale generation"
            )

            print(
                "Message generation:",
                result.generation,
            )

            print(
                "Current generation:",
                current_generation,
            )

            print(
                "================================"
            )

            return

        if (
            result.memory_id
            is not None

            and

            current_memory_id
            is not None

            and

            result.memory_id
            != current_memory_id
        ):

            print(
                "\n================================"
            )

            print(
                "PROACTIVE MESSAGE DISCARDED"
            )

            print(
                "================================"
            )

            print(
                "Reason: physical context changed"
            )

            print(
                "Message memory:",
                result.memory_id,
            )

            print(
                "Current memory:",
                current_memory_id,
            )

            print(
                "================================"
            )

            return

        # =================================================
        # STORE MESSAGE
        # =================================================

        working_memory.add_event(
            event_type=(
                "PROACTIVE_MESSAGE"
            ),

            observation=(
                message
            ),

            memory_id=(
                result.memory_id
            ),

            metadata={
                "generation": (
                    result.generation
                ),

                "reason": (
                    result.reason
                ),

                "priority": (
                    result.priority
                ),

                "message_hint": (
                    result.message_hint
                ),

                "message": (
                    message
                ),

                "source": (
                    "proactive_message_worker"
                ),
            },
        )

        print(
            "\n================================"
        )

        print(
            "ORION PROACTIVE MESSAGE"
        )

        print(
            "================================"
        )

        print(
            message
        )

        print(
            "================================"
        )

        # =================================================
        # VOICE
        # =================================================

        voice_job = (
            VoiceJob(
                text=(
                    message
                ),

                memory_id=(
                    result.memory_id
                ),

                generation=(
                    result.generation
                ),

                source="proactive",
            )
        )

        submitted = (
            self.voice_worker
            .submit(
                voice_job
            )
        )

        if submitted:

            print(
                "VOICE JOB ACCEPTED"
            )

        else:

            print(
                "VOICE JOB NOT SUBMITTED"
            )

    # =====================================================
    # VOICE RESULT
    # =====================================================

    def _on_voice_result(
        self,
        result: VoiceResult,
    ):

        if result.error is not None:

            print(
                "\nVOICE RESULT ERROR:",
                result.error,
            )

            return

        if not result.success:

            print(
                "\nVOICE OUTPUT FAILED"
            )

            return

        working_memory.add_event(
            event_type=(
                "VOICE_OUTPUT"
            ),

            observation=(
                result.text
            ),

            memory_id=(
                result.memory_id
            ),

            metadata={
                "generation": (
                    result.generation
                ),

                "source": (
                    result.source
                ),

                "success": True,
            },
        )

        print(
            "\n================================"
        )

        print(
            "ORION VOICE COMPLETE"
        )

        print(
            "================================"
        )

        print(
            result.text
        )

        print(
            "================================"
        )

    # =====================================================
    # INFERENCE DRIFT
    # =====================================================

    def _handle_inference_drift(
        self,
        result,
        observation,
        latest_frame,
        drift,
        request_kind,
    ):

        with self.scene_lock:

            if (
                result.generation
                != self.scene_generation
            ):

                return

            memory_id = (
                self.current_memory_id
            )

        metadata = {
            "generation": (
                result.generation
            ),

            "request_kind": (
                request_kind.value
            ),

            "drift_score": (
                float(
                    drift
                )
            ),
        }

        if (
            result.structured_scene
            is not None
        ):

            try:

                metadata[
                    "structured_scene"
                ] = (
                    result
                    .structured_scene
                    .model_dump()
                )

            except AttributeError:

                metadata[
                    "structured_scene"
                ] = (
                    result
                    .structured_scene
                    .dict()
                )

        working_memory.add_event(
            event_type=(
                "INFERENCE_DRIFT"
            ),

            observation=(
                observation
            ),

            memory_id=(
                memory_id
            ),

            metadata=(
                metadata
            ),
        )

        with self.scene_lock:

            self.scene_generation += 1

            new_generation = (
                self.scene_generation
            )

            self.transition_pending = (
                True
            )

        working_memory.add_event(
            event_type=(
                "DRIFT_RECOVERY_STARTED"
            ),

            memory_id=(
                memory_id
            ),

            metadata={
                "generation": (
                    new_generation
                ),

                "previous_generation": (
                    result.generation
                ),

                "context_preserved": (
                    True
                ),

                "original_request_kind": (
                    request_kind.value
                ),
            },
        )

        self.vision_manager.confirm_scene(
            latest_frame
        )

        self._set_active_request(
            VisionRequestKind
            .DRIFT_RECOVERY,

            new_generation,
        )

        submitted = (
            self.vlm_worker.submit(
                latest_frame,
                new_generation,
            )
        )

        if submitted:

            self.vision_manager.mark_analysis_started()

        else:

            self._clear_active_request()

            with self.scene_lock:

                self.transition_pending = (
                    False
                )

                self.transition_candidate_pending = (
                    False
                )

                self.transition_candidate_reference_diff = (
                    0.0
                )

    # =====================================================
    # VLM FAILURE
    # =====================================================

    def _recover_from_vlm_failure(
        self,
        generation,
    ):

        self._clear_active_request()

        working_memory.add_event(
            event_type=(
                "VLM_FAILURE"
            ),

            metadata={
                "generation": (
                    generation
                ),
            },
        )

        latest = (
            self._get_latest_frame()
        )

        with self.scene_lock:

            if (
                generation
                != self.scene_generation
            ):

                return

            self.transition_pending = (
                False
            )

            self.transition_candidate_pending = (
                False
            )

            self.transition_candidate_reference_diff = (
                0.0
            )

        if latest is not None:

            self.vision_manager.confirm_scene(
                latest
            )

    # =====================================================
    # GET LATEST FRAME
    # =====================================================

    def _get_latest_frame(
        self,
    ):

        with self.latest_frame_lock:

            if self.latest_frame is None:

                return None

            return (
                self.latest_frame.copy()
            )

    # =====================================================
    # INFERENCE DRIFT CALCULATION
    # =====================================================

    def _calculate_inference_drift(
        self,
        frame_a,
        frame_b,
    ):

        gray_a = (
            cv2.cvtColor(
                frame_a,
                cv2.COLOR_BGR2GRAY,
            )
        )

        gray_b = (
            cv2.cvtColor(
                frame_b,
                cv2.COLOR_BGR2GRAY,
            )
        )

        gray_a = (
            cv2.resize(
                gray_a,
                (320, 180),
            )
        )

        gray_b = (
            cv2.resize(
                gray_b,
                (320, 180),
            )
        )

        gray_a = (
            cv2.GaussianBlur(
                gray_a,
                (5, 5),
                0,
            )
        )

        gray_b = (
            cv2.GaussianBlur(
                gray_b,
                (5, 5),
                0,
            )
        )

        diff = (
            cv2.absdiff(
                gray_a,
                gray_b,
            )
        )

        return float(
            np.clip(
                float(
                    np.mean(
                        diff
                    )
                )
                / 255.0,

                0.0,
                1.0,
            )
        )

    # =====================================================
    # SCENE PERSISTENCE
    # =====================================================

    def _update_scene_persistence(
        self,
        decision,
    ):

        now = (
            time.time()
        )

        if (
            now
            - self.last_observed_update
            <
            self.observed_update_interval
        ):

            return

        if (
            decision.trigger_reason
            !=
            TriggerReason.BELOW_THRESHOLD
        ):

            return

        with self.scene_lock:

            if self.transition_pending:

                return

            if self.transition_candidate_pending:

                return

            memory_id = (
                self.current_memory_id
            )

        if memory_id is None:

            return

        if (
            memory_manager
            .mark_observed(
                memory_id
            )
        ):

            self.last_observed_update = (
                now
            )

    # =====================================================
    # PHYSICAL CONTEXT DEBUG
    # =====================================================

    def _print_context_transition(
        self,
        result,
    ):

        print(
            "\n================================"
        )

        print(
            "PHYSICAL CONTEXT EVALUATION"
        )

        print(
            "================================"
        )

        for key in [
            "confirmed",
            "score",

            "previous_environment",
            "current_environment",

            "previous_environment_family",
            "current_environment_family",

            "shared_objects",

            "object_overlap_ratio",

            "object_replacement_count",

            "strong_object_shift",

            "extreme_object_shift",

            "reason",
        ]:

            print(
                f"{key}:",
                result.get(
                    key
                ),
            )

        print(
            "================================"
        )

    # =====================================================
    # SEMANTIC DEBUG
    # =====================================================

    def _print_semantic_result(
        self,
        result,
    ):

        print(
            "\n=============================="
        )

        print(
            "SCENE INTELLIGENCE"
        )

        print(
            "=============================="
        )

        for key in [
            "is_first_scene",

            "state_changed",

            "meaningful_event",

            "information_resolved",

            "information_became_uncertain",

            "activity_changed",

            "pose_changed",

            "interaction_changed",

            "persistent_world_changed",

            "objects_appeared",

            "objects_reappeared",

            "objects_became_absent",

            "accessories_appeared",

            "accessories_reappeared",

            "accessories_became_absent",

            "major_scene_change",

            "reason",
        ]:

            print(
                f"{key}:",
                result.get(
                    key
                ),
            )

        print(
            "=============================="
        )

    # =====================================================
    # DEBUG
    # =====================================================

    def _print_debug(
        self,
        decision,
    ):

        now = (
            time.time()
        )

        if (
            not decision.should_analyze

            and

            (
                now
                - self.last_debug_time
                <
                self.debug_interval_seconds
            )
        ):

            return

        self.last_debug_time = (
            now
        )

        with self.scene_lock:

            generation = (
                self.scene_generation
            )

            memory_id = (
                self.current_memory_id
            )

            request_kind = (
                self.active_request_kind
            )

        print(
            "\n---------- VISION STATE ----------"
        )

        print(
            "Frame diff      :",
            f"{decision.frame_diff_score:.4f}",
        )

        print(
            "Reference diff  :",
            f"{decision.scene_reference_diff:.4f}",
        )

        print(
            "Global motion   :",
            f"{decision.global_motion_score:.4f}",
        )

        print(
            "Local change    :",
            f"{decision.local_change_score:.4f}",
        )

        print(
            "Event score     :",
            f"{decision.event_score:.4f}",
        )

        print(
            "Threshold       :",
            f"{decision.adaptive_threshold:.4f}",
        )

        print(
            "Decision        :",
            decision.trigger_reason.value,
        )

        print(
            "Capture active  :",
            decision.capture_active,
        )

        print(
            "Capture trigger :",
            (
                decision
                .captured_trigger_reason
                .value
                if
                decision
                .captured_trigger_reason
                else None
            ),
        )

        print(
            "Selected frame  :",
            decision.selected_frame_type,
        )

        print(
            "Max ref diff    :",
            f"{decision.max_reference_diff:.4f}",
        )

        print(
            "Settled ref diff:",
            f"{decision.settled_reference_diff:.4f}",
        )

        print(
            "Settled ratio   :",
            decision.settled_ratio,
        )

        print(
            "Persistent cand.:",
            decision.persistent_candidate_active,
        )

        print(
            "Persistent age  :",
            f"{decision.persistent_candidate_age:.3f}",
        )

        print(
            "Persistent armed:",
            decision.persistent_armed,
        )

        print(
            "Generation      :",
            generation,
        )

        print(
            "Memory ID       :",
            memory_id,
        )

        print(
            "Active request  :",
            (
                request_kind.value
                if request_kind
                else None
            ),
        )

        print(
            "VLM processing  :",
            self.vlm_worker
            .is_processing(),
        )

        print(
            "Reasoner worker :",
            self.proactive_reasoner_worker
            .is_processing(),
        )

        print(
            "Message worker  :",
            self.proactive_message_worker
            .is_processing(),
        )

        print(
            "Voice worker    :",
            self.voice_worker
            .is_processing(),
        )

        print(
            "----------------------------------"
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
            "\nStopping Orion..."
        )

        self.running = False

        self.vlm_worker.stop()

        self.proactive_reasoner_worker.stop()

        self.proactive_message_worker.stop()

        self.voice_worker.stop()

        self.camera.stop()

        cv2.destroyAllWindows()

        print(
            "Orion stopped."
        )


# =========================================================
# ENTRY POINT
# =========================================================

if __name__ == "__main__":

    VisionLoop().start()