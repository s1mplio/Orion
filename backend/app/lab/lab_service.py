import re
from datetime import datetime

import cv2
import numpy as np

from app.agents.llm_json import ensure_str_list, parse_llm_json
from app.lab.lab_store import lab_store
from app.services.vision_services import VisionService


LAB_FRAME_PROMPT = """
You are logging a laboratory or workshop session for the
researcher's notebook. Look at this camera frame.

Describe ONLY what is clearly visible. Do not guess
quantities, concentrations or substances you cannot read
on a label or display.

Return ONLY valid JSON:

{
    "is_working": true,
    "activity": "specific action, e.g. 'pipetting a clear liquid into a labelled test tube'",
    "materials": ["visible substances, samples or consumables"],
    "equipment": ["visible instruments or tools in use"],
    "observation": "notable visible result, e.g. a colour change, bubbling, a reading on a display; empty if none",
    "visible_text": ["legible labels, measurements or display readings"],
    "safety_concern": "a clearly visible safety issue, or null"
}

Set "is_working" to false when nobody is doing hands-on work
(empty bench, person idle or away). Then the other fields
may be empty.
"""

# Same activity seen again within this window extends the
# previous entry instead of creating a new one.
MERGE_WINDOW_SECONDS = 180

MERGE_SIMILARITY = 0.6

MAX_IMAGE_SIDE = 640


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", str(text or "").lower()))


def _similarity(a, b):
    tokens_a = _tokens(a)
    tokens_b = _tokens(b)

    if not tokens_a or not tokens_b:
        return 0.0

    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _merge_lists(first, second):
    merged = list(first or [])

    for item in second or []:
        if item.lower() not in {existing.lower() for existing in merged}:
            merged.append(item)

    return merged


class LabService:
    """Turns camera frames into notebook log entries."""

    def __init__(self, vision_service=None):
        self.vision = vision_service or VisionService()

    # =====================================================
    # FRAME ANALYSIS
    # =====================================================

    def process_frame(self, session_id, image_bytes):
        frame = cv2.imdecode(
            np.frombuffer(image_bytes, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        if frame is None:
            raise ValueError("Unable to decode image.")

        frame = self._downscale(frame)

        raw = self.vision.analyze_frame(frame, LAB_FRAME_PROMPT)
        data = parse_llm_json(raw)

        if data is None:
            raise RuntimeError(
                "The vision model did not return a readable observation."
            )

        details = {
            "materials": ensure_str_list(data.get("materials")),
            "equipment": ensure_str_list(data.get("equipment")),
            "observation": str(data.get("observation") or "").strip(),
            "visible_text": ensure_str_list(data.get("visible_text")),
            "safety_concern": (
                str(data.get("safety_concern")).strip()
                if data.get("safety_concern")
                and str(data.get("safety_concern")).strip().lower()
                not in {"null", "none"}
                else None
            ),
        }

        activity = str(data.get("activity") or "").strip()

        if data.get("is_working") is False or not activity:
            return {"status": "idle", "entry": None}

        with lab_store.lock:
            previous = lab_store.last_observation(session_id)

            if previous and self._continues(previous, activity, details):
                merged = dict(previous["details"])

                for key in ("materials", "equipment", "visible_text"):
                    merged[key] = _merge_lists(merged.get(key), details[key])

                # Keep new observations and safety issues; they are
                # the changes worth recording.
                if details["observation"]:
                    merged["observation"] = details["observation"]

                if details["safety_concern"]:
                    merged["safety_concern"] = details["safety_concern"]

                entry = lab_store.extend_entry(
                    session_id,
                    previous["entry_id"],
                    merged,
                )

                return {"status": "merged", "entry": entry}

            ok, encoded = cv2.imencode(
                ".jpg",
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, 80],
            )

            entry = lab_store.add_entry(
                session_id,
                kind="observation",
                activity=activity,
                details=details,
                image_bytes=encoded.tobytes() if ok else None,
            )

        return {"status": "logged", "entry": entry}

    def _continues(self, previous, activity, details):
        # A new safety concern always gets its own entry.
        if details["safety_concern"] and not previous["details"].get(
            "safety_concern"
        ):
            return False

        try:
            ended = datetime.fromisoformat(previous["ended_at"])
        except ValueError:
            return False

        if (datetime.now() - ended).total_seconds() > MERGE_WINDOW_SECONDS:
            return False

        return _similarity(previous["activity"], activity) >= MERGE_SIMILARITY

    def _downscale(self, frame):
        height, width = frame.shape[:2]
        scale = MAX_IMAGE_SIDE / max(height, width)

        if scale >= 1:
            return frame

        return cv2.resize(
            frame,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    # =====================================================
    # NOTES
    # =====================================================

    def add_note(self, session_id, text):
        return lab_store.add_entry(
            session_id,
            kind="note",
            activity=text,
            details={},
        )


lab_service = LabService()
