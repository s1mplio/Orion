from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import time

import cv2
import numpy as np


class MotionState(str, Enum):
    STABLE = "STABLE"
    MODERATE = "MODERATE"
    HIGH_MOTION = "HIGH_MOTION"


class CaptureState(str, Enum):
    IDLE = "IDLE"
    CAPTURING = "CAPTURING"


class TriggerReason(str, Enum):
    FIRST_FRAME = "FIRST_FRAME"
    USER_REQUEST = "USER_REQUEST"
    FORCED_REFRESH = "FORCED_REFRESH"

    # Fast frame-to-frame semantic movement.
    MEANINGFUL_CHANGE = "MEANINGFUL_CHANGE"

    # V4:
    # Slow movement may have tiny frame-to-frame differences but can
    # accumulate into a meaningful difference from the established scene.
    PERSISTENT_CHANGE = "PERSISTENT_CHANGE"

    # Large accumulated visual change requiring semantic confirmation.
    SCENE_TRANSITION_CANDIDATE = "SCENE_TRANSITION_CANDIDATE"

    EVENT_CAPTURING = "EVENT_CAPTURING"
    EVENT_READY = "EVENT_READY"

    CAMERA_MOTION_ONLY = "CAMERA_MOTION_ONLY"
    COOLDOWN = "COOLDOWN"
    BELOW_THRESHOLD = "BELOW_THRESHOLD"


@dataclass
class VisionDecision:
    should_analyze: bool
    trigger_reason: TriggerReason

    frame_diff_score: float
    global_motion_score: float
    local_change_score: float
    scene_reference_diff: float
    adaptive_threshold: float
    event_score: float
    motion_state: MotionState

    selected_event_frame: bool = False

    capture_active: bool = False
    capture_age_seconds: float = 0.0

    peak_event_score: float = 0.0

    captured_trigger_reason: Optional[TriggerReason] = None
    selected_frame_type: Optional[str] = None

    max_reference_diff: float = 0.0
    settled_reference_diff: float = 0.0
    settled_ratio: Optional[float] = None

    # V4 persistent-change diagnostics.
    persistent_candidate_active: bool = False
    persistent_candidate_age: float = 0.0
    persistent_armed: bool = True


class AdaptiveVisionManager:
    """
    ORION Adaptive Vision Manager - Event Capture V4

    Cheap CV runs on every camera frame.

    Three independent semantic triggers:

    1. MEANINGFUL_CHANGE
       Fast frame-to-frame change.

    2. PERSISTENT_CHANGE
       Slow accumulated change from the accepted scene.

       Example:
           hand slowly moves to chin
           frame-to-frame motion remains tiny
           but current frame becomes substantially different
           from the accepted scene.

    3. SCENE_TRANSITION_CANDIDATE
       Very large accumulated visual change.

    Event Capture V3 frame-selection logic is preserved:

       persistent final state
           -> settled frame

       transient action returning toward baseline
           -> max-reference frame

    Important:
       Local OpenCV capture remains active while the VLM is busy
       or inside its cooldown.

    No extra VLM call is introduced by persistent-change detection.
    """

    def __init__(
        self,
        min_vlm_interval_seconds: float = 4.0,
        max_silence_seconds: float = 25.0,
        history_size: int = 30,
        minimum_threshold: float = 0.025,
        maximum_threshold: float = 0.18,
        scene_transition_threshold: float = 0.12,
        event_capture_min_seconds: float = 0.35,
        event_capture_max_seconds: float = 1.25,
        event_settle_seconds: float = 0.25,
        event_settle_ratio: float = 0.45,
        event_settle_floor: float = 0.018,
        persistent_state_ratio: float = 0.70,

        # -------------------------------------------------
        # V4 persistent accumulated-change detector
        # -------------------------------------------------

        persistent_change_threshold: float = 0.045,
        persistent_change_seconds: float = 0.20,
        persistent_release_threshold: float = 0.025,
        persistent_max_global_motion: float = 0.02,
    ):
        self.min_vlm_interval_seconds = (
            min_vlm_interval_seconds
        )

        self.max_silence_seconds = (
            max_silence_seconds
        )

        self.minimum_threshold = minimum_threshold
        self.maximum_threshold = maximum_threshold

        self.scene_transition_threshold = (
            scene_transition_threshold
        )

        self.event_capture_min_seconds = (
            event_capture_min_seconds
        )

        self.event_capture_max_seconds = (
            event_capture_max_seconds
        )

        self.event_settle_seconds = (
            event_settle_seconds
        )

        self.event_settle_ratio = (
            event_settle_ratio
        )

        self.event_settle_floor = (
            event_settle_floor
        )

        self.persistent_state_ratio = (
            persistent_state_ratio
        )

        # =================================================
        # V4 persistent detector configuration
        # =================================================

        self.persistent_change_threshold = (
            persistent_change_threshold
        )

        self.persistent_change_seconds = (
            persistent_change_seconds
        )

        self.persistent_release_threshold = (
            persistent_release_threshold
        )

        self.persistent_max_global_motion = (
            persistent_max_global_motion
        )

        # =================================================
        # Frame state
        # =================================================

        self.previous_gray = None
        self.scene_reference_gray = None

        # =================================================
        # Adaptive threshold history
        # =================================================

        self.event_history = deque(
            maxlen=history_size
        )

        self.motion_history = deque(
            maxlen=history_size
        )

        # =================================================
        # VLM state
        # =================================================

        self.last_vlm_time = 0.0

        self.force_next_analysis = False

        self.vlm_busy = False

        # =================================================
        # Event capture state
        # =================================================

        self.capture_state = CaptureState.IDLE

        self.capture_started_at = 0.0

        self.capture_last_active_at = 0.0

        self.capture_trigger_reason = (
            TriggerReason.MEANINGFUL_CHANGE
        )

        # -------------------------------------------------
        # Start frame
        # -------------------------------------------------

        self.capture_start_frame: Optional[
            np.ndarray
        ] = None

        self.capture_start_reference_diff = 0.0

        # -------------------------------------------------
        # Peak event-score frame
        # -------------------------------------------------

        self.capture_peak_frame: Optional[
            np.ndarray
        ] = None

        self.capture_peak_score = 0.0

        self.capture_peak_reference_diff = 0.0

        # -------------------------------------------------
        # Maximum displacement from accepted scene
        # -------------------------------------------------

        self.capture_max_reference_frame: Optional[
            np.ndarray
        ] = None

        self.capture_max_reference_diff = 0.0

        # -------------------------------------------------
        # Latest frame
        # -------------------------------------------------

        self.capture_latest_frame: Optional[
            np.ndarray
        ] = None

        self.capture_latest_reference_diff = 0.0

        # -------------------------------------------------
        # Settled frame
        # -------------------------------------------------

        self.capture_settled_frame: Optional[
            np.ndarray
        ] = None

        self.capture_settled_reference_diff = 0.0

        # =================================================
        # One completed pending event
        # =================================================

        self.ready_event_frame: Optional[
            np.ndarray
        ] = None

        self.ready_event_reason: Optional[
            TriggerReason
        ] = None

        self.ready_event_peak_score = 0.0

        self.ready_event_reference_diff = 0.0

        self.ready_event_frame_type: Optional[
            str
        ] = None

        self.ready_event_max_reference_diff = 0.0

        self.ready_event_settled_reference_diff = 0.0

        self.ready_event_settled_ratio: Optional[
            float
        ] = None

        # =================================================
        # V4 persistent accumulated-change state
        # =================================================

        self.persistent_candidate_started_at: Optional[
            float
        ] = None

        # Hysteresis latch.
        #
        # True:
        #     persistent detector may trigger.
        #
        # False:
        #     it already triggered and must wait until
        #     scene returns near baseline before triggering
        #     another persistent event.
        self.persistent_armed = True

    # =====================================================
    # PUBLIC STATE
    # =====================================================

    def set_vlm_busy(
        self,
        busy: bool,
    ):
        self.vlm_busy = bool(busy)

    def request_analysis(self):
        self.force_next_analysis = True

    def mark_analysis_started(self):
        self.last_vlm_time = time.time()

    def confirm_scene(
        self,
        frame,
    ):
        """
        Accept this frame as the current cheap-CV scene reference.

        Whenever a new semantic state becomes accepted, accumulated
        reference deviation must restart from that state.
        """

        if frame is None:
            return

        self.scene_reference_gray = (
            self._prepare_frame(frame).copy()
        )

        # The accepted physical/semantic reference changed.
        # Restart the persistent detector.
        self._reset_persistent_detector(
            rearm=True
        )

        print("SCENE_REFERENCE_UPDATED")

    # =====================================================
    # PERSISTENT DETECTOR
    # =====================================================

    def _reset_persistent_detector(
        self,
        rearm: bool = True,
    ):
        self.persistent_candidate_started_at = None

        if rearm:
            self.persistent_armed = True

    def _persistent_candidate_age(
        self,
        now,
    ) -> float:
        if (
            self.persistent_candidate_started_at
            is None
        ):
            return 0.0

        return max(
            0.0,
            now
            - self.persistent_candidate_started_at,
        )

    def _update_persistent_detector(
        self,
        reference_diff: float,
        global_motion: float,
        now: float,
    ):
        """
        Returns:

            trigger_persistent,
            candidate_active,
            candidate_age

        Hysteresis:

            armed
              |
              | reference >= 0.045
              | low camera motion
              | sustained ~0.20 s
              v
            trigger once
              |
              v
            disarmed
              |
              | reference <= 0.025
              v
            armed again
        """

        # ---------------------------------------------
        # Release/re-arm
        # ---------------------------------------------

        if (
            not self.persistent_armed
            and
            reference_diff
            <= self.persistent_release_threshold
        ):
            self.persistent_armed = True

            self.persistent_candidate_started_at = None

            print(
                "\nPERSISTENT_CHANGE_REARMED"
            )

        # ---------------------------------------------
        # Already fired for this deviation
        # ---------------------------------------------

        if not self.persistent_armed:
            return (
                False,
                False,
                0.0,
            )

        # ---------------------------------------------
        # Must be meaningfully different from baseline
        # ---------------------------------------------

        above_threshold = (
            reference_diff
            >= self.persistent_change_threshold
        )

        # ---------------------------------------------
        # Must not look like strong camera movement
        # ---------------------------------------------

        camera_stable_enough = (
            global_motion
            <= self.persistent_max_global_motion
        )

        if (
            not above_threshold
            or
            not camera_stable_enough
        ):
            self.persistent_candidate_started_at = None

            return (
                False,
                False,
                0.0,
            )

        # ---------------------------------------------
        # Start candidate timer
        # ---------------------------------------------

        if (
            self.persistent_candidate_started_at
            is None
        ):
            self.persistent_candidate_started_at = now

            return (
                False,
                True,
                0.0,
            )

        age = self._persistent_candidate_age(
            now
        )

        # ---------------------------------------------
        # Sustained long enough
        # ---------------------------------------------

        if age >= self.persistent_change_seconds:

            self.persistent_candidate_started_at = None

            # Disarm BEFORE event capture.
            self.persistent_armed = False

            print(
                "\nPERSISTENT_CHANGE_CONFIRMED"
            )

            print(
                "Reference diff:",
                f"{reference_diff:.4f}",
            )

            print(
                "Sustained:",
                f"{age:.3f}s",
            )

            print(
                "Global motion:",
                f"{global_motion:.4f}",
            )

            return (
                True,
                False,
                age,
            )

        return (
            False,
            True,
            age,
        )

    # =====================================================
    # READY EVENT
    # =====================================================

    def consume_ready_event_frame(
        self,
    ) -> Optional[np.ndarray]:

        if self.ready_event_frame is None:
            return None

        frame = self.ready_event_frame.copy()

        self.ready_event_frame = None

        self.ready_event_reason = None

        self.ready_event_peak_score = 0.0

        self.ready_event_reference_diff = 0.0

        self.ready_event_frame_type = None

        self.ready_event_max_reference_diff = 0.0

        self.ready_event_settled_reference_diff = 0.0

        self.ready_event_settled_ratio = None

        return frame

    # =====================================================
    # CAPTURE RESET
    # =====================================================

    def _reset_active_capture(
        self,
    ):
        self.capture_state = CaptureState.IDLE

        self.capture_started_at = 0.0

        self.capture_last_active_at = 0.0

        self.capture_trigger_reason = (
            TriggerReason.MEANINGFUL_CHANGE
        )

        self.capture_start_frame = None
        self.capture_start_reference_diff = 0.0

        self.capture_peak_frame = None
        self.capture_peak_score = 0.0
        self.capture_peak_reference_diff = 0.0

        self.capture_max_reference_frame = None
        self.capture_max_reference_diff = 0.0

        self.capture_latest_frame = None
        self.capture_latest_reference_diff = 0.0

        self.capture_settled_frame = None
        self.capture_settled_reference_diff = 0.0

    def cancel_event_capture(
        self,
    ):
        self._reset_active_capture()

        self.ready_event_frame = None

        self.ready_event_reason = None

        self.ready_event_peak_score = 0.0

        self.ready_event_reference_diff = 0.0

        self.ready_event_frame_type = None

        self.ready_event_max_reference_diff = 0.0

        self.ready_event_settled_reference_diff = 0.0

        self.ready_event_settled_ratio = None

        self._reset_persistent_detector(
            rearm=True
        )

    # =====================================================
    # CHEAP CV
    # =====================================================

    def _prepare_frame(
        self,
        frame,
    ):
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.resize(
            gray,
            (320, 180),
        )

        gray = cv2.GaussianBlur(
            gray,
            (5, 5),
            0,
        )

        return gray

    def _calculate_frame_difference(
        self,
        frame_a,
        frame_b,
    ) -> float:

        difference = cv2.absdiff(
            frame_a,
            frame_b,
        )

        score = (
            float(np.mean(difference))
            / 255.0
        )

        return float(
            np.clip(
                score,
                0.0,
                1.0,
            )
        )

    def _calculate_global_motion(
        self,
        previous_gray,
        current_gray,
    ) -> float:

        points = cv2.goodFeaturesToTrack(
            previous_gray,
            maxCorners=100,
            qualityLevel=0.01,
            minDistance=7,
            blockSize=7,
        )

        if points is None:
            return 0.0

        (
            next_points,
            status,
            _,
        ) = cv2.calcOpticalFlowPyrLK(
            previous_gray,
            current_gray,
            points,
            None,
        )

        if (
            next_points is None
            or
            status is None
        ):
            return 0.0

        mask = (
            status.flatten() == 1
        )

        good_old = points[mask]
        good_new = next_points[mask]

        if len(good_old) < 5:
            return 0.0

        vectors = (
            good_new - good_old
        ).reshape(
            -1,
            2,
        )

        magnitudes = np.linalg.norm(
            vectors,
            axis=1,
        )

        global_motion = (
            np.median(magnitudes)
            / 320.0
        )

        return float(
            np.clip(
                global_motion,
                0.0,
                1.0,
            )
        )

    def _calculate_local_change(
        self,
        frame_diff,
        global_motion,
    ) -> float:

        value = (
            frame_diff
            - 0.7 * global_motion
        )

        return float(
            np.clip(
                value,
                0.0,
                1.0,
            )
        )

    def _get_motion_state(
        self,
        global_motion,
    ) -> MotionState:

        self.motion_history.append(
            global_motion
        )

        recent_motion = float(
            np.mean(
                self.motion_history
            )
        )

        if recent_motion < 0.015:
            return MotionState.STABLE

        if recent_motion < 0.05:
            return MotionState.MODERATE

        return MotionState.HIGH_MOTION

    # =====================================================
    # ADAPTIVE THRESHOLD
    # =====================================================

    def _calculate_adaptive_threshold(
        self,
        motion_state,
    ) -> float:

        if len(self.event_history) < 5:
            threshold = 0.04

        else:
            values = np.asarray(
                self.event_history,
                dtype=np.float32,
            )

            mean = float(
                np.mean(values)
            )

            std = float(
                np.std(values)
            )

            threshold = (
                mean
                + 2.0 * std
            )

        if (
            motion_state
            == MotionState.MODERATE
        ):
            threshold *= 1.20

        elif (
            motion_state
            == MotionState.HIGH_MOTION
        ):
            threshold *= 1.50

        return float(
            np.clip(
                threshold,
                self.minimum_threshold,
                self.maximum_threshold,
            )
        )

    def _learn_quiet_baseline(
        self,
        event_score,
    ):
        self.event_history.append(
            float(event_score)
        )

    # =====================================================
    # START EVENT CAPTURE
    # =====================================================

    def _start_event_capture(
        self,
        frame,
        event_score,
        reference_diff,
        reason,
        now,
    ):
        self.capture_state = (
            CaptureState.CAPTURING
        )

        self.capture_started_at = now

        self.capture_last_active_at = now

        self.capture_trigger_reason = reason

        # ---------------------------------------------
        # Start frame
        # ---------------------------------------------

        self.capture_start_frame = (
            frame.copy()
        )

        self.capture_start_reference_diff = (
            float(reference_diff)
        )

        # ---------------------------------------------
        # Peak event frame
        # ---------------------------------------------

        self.capture_peak_frame = (
            frame.copy()
        )

        self.capture_peak_score = (
            float(event_score)
        )

        self.capture_peak_reference_diff = (
            float(reference_diff)
        )

        # ---------------------------------------------
        # Maximum reference displacement
        # ---------------------------------------------

        self.capture_max_reference_frame = (
            frame.copy()
        )

        self.capture_max_reference_diff = (
            float(reference_diff)
        )

        # ---------------------------------------------
        # Latest frame
        # ---------------------------------------------

        self.capture_latest_frame = (
            frame.copy()
        )

        self.capture_latest_reference_diff = (
            float(reference_diff)
        )

        # ---------------------------------------------
        # Settled frame
        # ---------------------------------------------

        self.capture_settled_frame = None

        self.capture_settled_reference_diff = 0.0

        print(
            "\nEVENT_CAPTURE_STARTED"
        )

        print(
            "Reason:",
            reason.value,
        )

        print(
            "Initial score:",
            f"{event_score:.4f}",
        )

        print(
            "Initial reference diff:",
            f"{reference_diff:.4f}",
        )

    # =====================================================
    # UPDATE EVENT CAPTURE
    # =====================================================

    def _update_event_capture(
        self,
        frame,
        event_score,
        reference_diff,
        threshold,
        now,
    ):
        if (
            self.capture_state
            != CaptureState.CAPTURING
        ):
            return

        # ---------------------------------------------
        # Always retain newest frame
        # ---------------------------------------------

        self.capture_latest_frame = (
            frame.copy()
        )

        self.capture_latest_reference_diff = (
            float(reference_diff)
        )

        # ---------------------------------------------
        # Peak event score
        # ---------------------------------------------

        if (
            event_score
            > self.capture_peak_score
        ):
            self.capture_peak_score = (
                float(event_score)
            )

            self.capture_peak_reference_diff = (
                float(reference_diff)
            )

            self.capture_peak_frame = (
                frame.copy()
            )

        # ---------------------------------------------
        # Maximum displacement from accepted scene
        # ---------------------------------------------

        if (
            reference_diff
            > self.capture_max_reference_diff
        ):
            self.capture_max_reference_diff = (
                float(reference_diff)
            )

            self.capture_max_reference_frame = (
                frame.copy()
            )

        # ---------------------------------------------
        # Determine whether movement has settled
        # ---------------------------------------------

        settle_threshold = max(
            self.event_settle_floor,
            threshold
            * self.event_settle_ratio,
        )

        if event_score > settle_threshold:

            self.capture_last_active_at = now

            self.capture_settled_frame = None

            self.capture_settled_reference_diff = 0.0

        else:

            quiet_for = (
                now
                - self.capture_last_active_at
            )

            if (
                quiet_for
                >= self.event_settle_seconds
            ):
                self.capture_settled_frame = (
                    frame.copy()
                )

                self.capture_settled_reference_diff = (
                    float(reference_diff)
                )

    # =====================================================
    # EVENT READY?
    # =====================================================

    def _event_capture_ready(
        self,
        now,
    ) -> bool:

        if (
            self.capture_state
            != CaptureState.CAPTURING
        ):
            return False

        age = (
            now
            - self.capture_started_at
        )

        quiet_for = (
            now
            - self.capture_last_active_at
        )

        if (
            age
            >= self.event_capture_max_seconds
        ):
            return True

        if (
            age
            >= self.event_capture_min_seconds
            and
            quiet_for
            >= self.event_settle_seconds
        ):
            return True

        return False

    # =====================================================
    # REPRESENTATIVE FRAME
    # =====================================================

    def _select_event_frame(
        self,
    ):
        """
        Persistent action:

            baseline -> hand on chin -> hand stays there

        settled/max-reference remains high.

        Choose settled frame.


        Transient action:

            baseline -> arms up -> arms down

        settled/max-reference becomes low.

        Choose maximum-reference frame.
        """

        max_diff = float(
            self.capture_max_reference_diff
        )

        settled_diff = float(
            self.capture_settled_reference_diff
        )

        settled_ratio = None

        if max_diff > 1e-6:
            settled_ratio = (
                settled_diff
                / max_diff
            )

        # ---------------------------------------------
        # Settled state exists
        # ---------------------------------------------

        if (
            self.capture_settled_frame
            is not None
        ):

            if (
                settled_ratio is not None
                and
                settled_ratio
                >= self.persistent_state_ratio
            ):
                return (
                    self.capture_settled_frame.copy(),
                    settled_diff,
                    "settled_persistent",
                    settled_ratio,
                )

            # Returned toward baseline.
            if (
                self.capture_max_reference_frame
                is not None
            ):
                return (
                    self.capture_max_reference_frame.copy(),
                    max_diff,
                    "max_reference_transient",
                    settled_ratio,
                )

        # ---------------------------------------------
        # Timeout/no settled frame
        # ---------------------------------------------

        if (
            self.capture_max_reference_frame
            is not None
        ):
            return (
                self.capture_max_reference_frame.copy(),
                max_diff,
                "max_reference",
                settled_ratio,
            )

        if (
            self.capture_latest_frame
            is not None
        ):
            return (
                self.capture_latest_frame.copy(),
                self.capture_latest_reference_diff,
                "latest",
                settled_ratio,
            )

        if (
            self.capture_peak_frame
            is not None
        ):
            return (
                self.capture_peak_frame.copy(),
                self.capture_peak_reference_diff,
                "peak_event",
                settled_ratio,
            )

        return (
            None,
            0.0,
            None,
            settled_ratio,
        )

    # =====================================================
    # FINALIZE CAPTURE
    # =====================================================

    def _finalize_event_capture(
        self,
    ):
        (
            selected_frame,
            selected_reference_diff,
            selected_type,
            settled_ratio,
        ) = self._select_event_frame()

        if selected_frame is None:
            self._reset_active_capture()
            return

        self.ready_event_frame = (
            selected_frame.copy()
        )

        self.ready_event_reason = (
            self.capture_trigger_reason
        )

        self.ready_event_peak_score = (
            self.capture_peak_score
        )

        self.ready_event_reference_diff = (
            float(
                selected_reference_diff
            )
        )

        self.ready_event_frame_type = (
            selected_type
        )

        self.ready_event_max_reference_diff = (
            float(
                self.capture_max_reference_diff
            )
        )

        self.ready_event_settled_reference_diff = (
            float(
                self.capture_settled_reference_diff
            )
        )

        self.ready_event_settled_ratio = (
            settled_ratio
        )

        print(
            "\nEVENT_CAPTURE_READY"
        )

        print(
            "Original reason:",
            self.ready_event_reason.value,
        )

        print(
            "Selected frame:",
            selected_type,
        )

        print(
            "Peak event score:",
            f"{self.capture_peak_score:.4f}",
        )

        print(
            "Max reference diff:",
            f"{self.capture_max_reference_diff:.4f}",
        )

        print(
            "Settled reference diff:",
            f"{self.capture_settled_reference_diff:.4f}",
        )

        print(
            "Settled/max ratio:",
            (
                f"{settled_ratio:.3f}"
                if settled_ratio is not None
                else None
            ),
        )

        self._reset_active_capture()

    # =====================================================
    # DECISION FACTORY
    # =====================================================

    def _decision(
        self,
        should_analyze,
        reason,
        frame_diff,
        global_motion,
        local_change,
        reference_diff,
        threshold,
        event_score,
        motion_state,
        selected_event_frame=False,
        capture_active=False,
        capture_age_seconds=0.0,
        peak_event_score=0.0,
        captured_trigger_reason=None,
        selected_frame_type=None,
        max_reference_diff=0.0,
        settled_reference_diff=0.0,
        settled_ratio=None,
        persistent_candidate_active=False,
        persistent_candidate_age=0.0,
        persistent_armed=None,
    ):
        if persistent_armed is None:
            persistent_armed = (
                self.persistent_armed
            )

        return VisionDecision(
            should_analyze=should_analyze,
            trigger_reason=reason,

            frame_diff_score=frame_diff,
            global_motion_score=global_motion,
            local_change_score=local_change,
            scene_reference_diff=reference_diff,
            adaptive_threshold=threshold,
            event_score=event_score,
            motion_state=motion_state,

            selected_event_frame=selected_event_frame,

            capture_active=capture_active,

            capture_age_seconds=(
                capture_age_seconds
            ),

            peak_event_score=peak_event_score,

            captured_trigger_reason=(
                captured_trigger_reason
            ),

            selected_frame_type=(
                selected_frame_type
            ),

            max_reference_diff=(
                max_reference_diff
            ),

            settled_reference_diff=(
                settled_reference_diff
            ),

            settled_ratio=settled_ratio,

            persistent_candidate_active=(
                persistent_candidate_active
            ),

            persistent_candidate_age=(
                persistent_candidate_age
            ),

            persistent_armed=(
                persistent_armed
            ),
        )

    def _ready_event_decision(
        self,
        frame_diff,
        global_motion,
        local_change,
        threshold,
        event_score,
        motion_state,
    ):
        return self._decision(
            True,
            TriggerReason.EVENT_READY,

            frame_diff,
            global_motion,
            local_change,

            self.ready_event_reference_diff,

            threshold,

            self.ready_event_peak_score,

            motion_state,

            selected_event_frame=True,

            capture_active=False,

            peak_event_score=(
                self.ready_event_peak_score
            ),

            captured_trigger_reason=(
                self.ready_event_reason
            ),

            selected_frame_type=(
                self.ready_event_frame_type
            ),

            max_reference_diff=(
                self.ready_event_max_reference_diff
            ),

            settled_reference_diff=(
                self.ready_event_settled_reference_diff
            ),

            settled_ratio=(
                self.ready_event_settled_ratio
            ),
        )

    # =====================================================
    # MAIN EVALUATION
    # =====================================================

    def evaluate(
        self,
        frame,
    ) -> VisionDecision:

        now = time.time()

        current_gray = (
            self._prepare_frame(frame)
        )

        # =================================================
        # FIRST FRAME
        # =================================================

        if self.previous_gray is None:

            self.previous_gray = (
                current_gray.copy()
            )

            self.scene_reference_gray = (
                current_gray.copy()
            )

            self._reset_persistent_detector(
                rearm=True
            )

            return self._decision(
                True,
                TriggerReason.FIRST_FRAME,

                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
                1.0,

                MotionState.STABLE,
            )

        # =================================================
        # CHEAP CV
        # =================================================

        frame_diff = (
            self._calculate_frame_difference(
                self.previous_gray,
                current_gray,
            )
        )

        global_motion = (
            self._calculate_global_motion(
                self.previous_gray,
                current_gray,
            )
        )

        local_change = (
            self._calculate_local_change(
                frame_diff,
                global_motion,
            )
        )

        if (
            self.scene_reference_gray
            is None
        ):
            reference_diff = 0.0

        else:
            reference_diff = (
                self._calculate_frame_difference(
                    self.scene_reference_gray,
                    current_gray,
                )
            )

        motion_state = (
            self._get_motion_state(
                global_motion
            )
        )

        event_score = (
            0.65 * local_change
            + 0.35 * frame_diff
            - 0.30 * global_motion
        )

        event_score = float(
            np.clip(
                event_score,
                0.0,
                1.0,
            )
        )

        threshold = (
            self._calculate_adaptive_threshold(
                motion_state
            )
        )

        self.previous_gray = (
            current_gray.copy()
        )

        time_since_last_vlm = (
            now
            - self.last_vlm_time
        )

        vlm_available = (
            not self.vlm_busy
            and
            time_since_last_vlm
            >= self.min_vlm_interval_seconds
        )

        # =================================================
        # USER REQUEST
        # =================================================

        if self.force_next_analysis:

            # Don't lose user request while VLM is processing.
            if self.vlm_busy:

                return self._decision(
                    False,
                    TriggerReason.COOLDOWN,

                    frame_diff,
                    global_motion,
                    local_change,
                    reference_diff,
                    threshold,
                    event_score,
                    motion_state,
                )

            self.force_next_analysis = False

            return self._decision(
                True,
                TriggerReason.USER_REQUEST,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,
            )

        # =================================================
        # ACTIVE EVENT CAPTURE
        # =================================================

        if (
            self.capture_state
            == CaptureState.CAPTURING
        ):

            self._update_event_capture(
                frame=frame,
                event_score=event_score,
                reference_diff=reference_diff,
                threshold=threshold,
                now=now,
            )

            age = (
                now
                - self.capture_started_at
            )

            if (
                self._event_capture_ready(
                    now
                )
            ):
                self._finalize_event_capture()

                if vlm_available:

                    return (
                        self._ready_event_decision(
                            frame_diff,
                            global_motion,
                            local_change,
                            threshold,
                            event_score,
                            motion_state,
                        )
                    )

                # Completed event remains in local RAM
                # until VLM becomes available.
                return self._decision(
                    False,
                    TriggerReason.COOLDOWN,

                    frame_diff,
                    global_motion,
                    local_change,
                    reference_diff,
                    threshold,
                    event_score,
                    motion_state,

                    captured_trigger_reason=(
                        self.ready_event_reason
                    ),

                    selected_frame_type=(
                        self.ready_event_frame_type
                    ),

                    peak_event_score=(
                        self.ready_event_peak_score
                    ),

                    max_reference_diff=(
                        self.ready_event_max_reference_diff
                    ),

                    settled_reference_diff=(
                        self.ready_event_settled_reference_diff
                    ),

                    settled_ratio=(
                        self.ready_event_settled_ratio
                    ),
                )

            return self._decision(
                False,
                TriggerReason.EVENT_CAPTURING,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                capture_active=True,

                capture_age_seconds=age,

                peak_event_score=(
                    self.capture_peak_score
                ),

                captured_trigger_reason=(
                    self.capture_trigger_reason
                ),

                max_reference_diff=(
                    self.capture_max_reference_diff
                ),

                settled_reference_diff=(
                    self.capture_settled_reference_diff
                ),
            )

        # =================================================
        # COMPLETED EVENT WAITING FOR VLM
        # =================================================

        if (
            self.ready_event_frame
            is not None
        ):

            if vlm_available:

                return (
                    self._ready_event_decision(
                        frame_diff,
                        global_motion,
                        local_change,
                        threshold,
                        event_score,
                        motion_state,
                    )
                )

            return self._decision(
                False,
                TriggerReason.COOLDOWN,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                peak_event_score=(
                    self.ready_event_peak_score
                ),

                captured_trigger_reason=(
                    self.ready_event_reason
                ),

                selected_frame_type=(
                    self.ready_event_frame_type
                ),

                max_reference_diff=(
                    self.ready_event_max_reference_diff
                ),

                settled_reference_diff=(
                    self.ready_event_settled_reference_diff
                ),

                settled_ratio=(
                    self.ready_event_settled_ratio
                ),
            )

        # =================================================
        # FAST CHANGE
        # =================================================

        meaningful_change = (
            event_score
            >= threshold
        )

        # =================================================
        # LARGE PHYSICAL CONTEXT CHANGE
        # =================================================

        transition_candidate = (
            reference_diff
            >= self.scene_transition_threshold
        )

        # =================================================
        # CAMERA MOTION
        # =================================================

        camera_motion_only = (
            global_motion > 0.05
            and
            local_change < threshold
        )

        # =================================================
        # V4 PERSISTENT ACCUMULATED CHANGE
        # =================================================
        #
        # We do not run this for an obvious transition.
        # We also don't run it for camera-motion-only frames.

        persistent_trigger = False
        persistent_candidate_active = False
        persistent_candidate_age = 0.0

        if (
            not transition_candidate
            and
            not camera_motion_only
        ):
            (
                persistent_trigger,
                persistent_candidate_active,
                persistent_candidate_age,
            ) = self._update_persistent_detector(
                reference_diff=reference_diff,
                global_motion=global_motion,
                now=now,
            )

        else:
            # Don't let camera motion accumulate a fake
            # persistent semantic candidate.
            self.persistent_candidate_started_at = None

        # =================================================
        # START CAPTURE
        # =================================================

        if (
            not camera_motion_only
            and
            (
                transition_candidate
                or
                meaningful_change
                or
                persistent_trigger
            )
        ):

            if transition_candidate:

                reason = (
                    TriggerReason
                    .SCENE_TRANSITION_CANDIDATE
                )

            elif meaningful_change:

                reason = (
                    TriggerReason
                    .MEANINGFUL_CHANGE
                )

            else:

                reason = (
                    TriggerReason
                    .PERSISTENT_CHANGE
                )

            self._start_event_capture(
                frame=frame,
                event_score=event_score,
                reference_diff=reference_diff,
                reason=reason,
                now=now,
            )

            return self._decision(
                False,
                TriggerReason.EVENT_CAPTURING,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                capture_active=True,

                capture_age_seconds=0.0,

                peak_event_score=event_score,

                captured_trigger_reason=reason,

                max_reference_diff=(
                    reference_diff
                ),

                persistent_candidate_active=False,

                persistent_candidate_age=(
                    persistent_candidate_age
                ),
            )

        # =================================================
        # CAMERA MOVEMENT
        # =================================================

        if camera_motion_only:

            return self._decision(
                False,
                TriggerReason.CAMERA_MOTION_ONLY,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,
            )

        # =================================================
        # QUIET BASELINE LEARNING
        # =================================================
        #
        # Important V4 detail:
        #
        # Do NOT teach the adaptive motion threshold that a
        # persistent semantic deviation is normal noise.

        if (
            not persistent_candidate_active
            and
            reference_diff
            < self.persistent_change_threshold
        ):
            self._learn_quiet_baseline(
                event_score
            )

        # =================================================
        # FORCED REFRESH
        # =================================================

        if (
            time_since_last_vlm
            >= self.max_silence_seconds
            and
            not self.vlm_busy
        ):

            return self._decision(
                True,
                TriggerReason.FORCED_REFRESH,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                persistent_candidate_active=(
                    persistent_candidate_active
                ),

                persistent_candidate_age=(
                    persistent_candidate_age
                ),
            )

        # =================================================
        # BUSY / COOLDOWN
        # =================================================
        #
        # Notice:
        # event detection has already happened above.
        #
        # Therefore VLM cooldown does NOT stop local event
        # capture.

        if self.vlm_busy:

            return self._decision(
                False,
                TriggerReason.COOLDOWN,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                persistent_candidate_active=(
                    persistent_candidate_active
                ),

                persistent_candidate_age=(
                    persistent_candidate_age
                ),
            )

        if (
            time_since_last_vlm
            < self.min_vlm_interval_seconds
        ):

            return self._decision(
                False,
                TriggerReason.COOLDOWN,

                frame_diff,
                global_motion,
                local_change,
                reference_diff,
                threshold,
                event_score,
                motion_state,

                persistent_candidate_active=(
                    persistent_candidate_active
                ),

                persistent_candidate_age=(
                    persistent_candidate_age
                ),
            )

        # =================================================
        # NOTHING INTERESTING
        # =================================================

        return self._decision(
            False,
            TriggerReason.BELOW_THRESHOLD,

            frame_diff,
            global_motion,
            local_change,
            reference_diff,
            threshold,
            event_score,
            motion_state,

            persistent_candidate_active=(
                persistent_candidate_active
            ),

            persistent_candidate_age=(
                persistent_candidate_age
            ),
        )