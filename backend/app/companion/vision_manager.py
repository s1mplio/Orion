import time
from typing import Optional

import cv2
import numpy as np


class VisionManager:
    """
    Controls how frequently Orion sends camera frames
    for expensive VLM analysis.

    Camera can run continuously at 30 FPS,
    but the VLM is called only when a frame is worth analyzing.
    """

    def __init__(
        self,
        min_interval_seconds: float = 3.0,
        change_threshold: float = 0.12,
    ):
        # Minimum time between VLM requests.
        self.min_interval_seconds = min_interval_seconds

        # How much the image must change before
        # we consider it a candidate for analysis.
        self.change_threshold = change_threshold

        self.previous_frame: Optional[np.ndarray] = None

        self.last_analysis_time = 0.0

    def should_analyze(self, frame: np.ndarray) -> bool:
        """
        Decide whether the current frame should be sent
        to the VLM.

        Returns:
            True  -> analyze frame
            False -> ignore frame
        """

        current_time = time.time()

        # --------------------------------------------------
        # 1. Rate limit
        # --------------------------------------------------

        if (
            current_time - self.last_analysis_time
            < self.min_interval_seconds
        ):
            return False

        # --------------------------------------------------
        # 2. First frame
        # --------------------------------------------------

        if self.previous_frame is None:

            self.previous_frame = frame.copy()

            self.last_analysis_time = current_time

            return True

        # --------------------------------------------------
        # 3. Compare current frame with previous frame
        # --------------------------------------------------

        current_gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY
        )

        previous_gray = cv2.cvtColor(
            self.previous_frame,
            cv2.COLOR_BGR2GRAY
        )

        # Resize to make comparison cheap.
        current_small = cv2.resize(
            current_gray,
            (160, 120)
        )

        previous_small = cv2.resize(
            previous_gray,
            (160, 120)
        )

        difference = cv2.absdiff(
            current_small,
            previous_small
        )

        # Normalize difference to 0-1.
        change_score = (
            np.mean(difference) / 255.0
        )

        print(
            f"Vision change score: "
            f"{change_score:.3f}"
        )

        # --------------------------------------------------
        # 4. Update reference frame
        # --------------------------------------------------

        self.previous_frame = frame.copy()

        # --------------------------------------------------
        # 5. Decide
        # --------------------------------------------------

        if change_score >= self.change_threshold:

            self.last_analysis_time = current_time

            return True

        return False