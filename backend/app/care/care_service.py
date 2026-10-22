import re
import threading
from datetime import date, datetime, timedelta

import cv2
import numpy as np

from app.agents.llm_json import parse_llm_json
from app.care import telegram
from app.care.care_store import care_store


# Photos (room snapshots, dose confirmations) are deleted
# after this many days. Text records are kept.
PHOTO_RETENTION_DAYS = 7

# A dose can be confirmed this many minutes before it is due.
EARLY_CONFIRM_MINUTES = 60

# A tracked object seen in the same place again within this
# window is not recorded again.
SIGHTING_REPEAT_MINUTES = 10

MAX_IMAGE_SIDE = 640

MEDICINE_WORDS = {
    "medicine", "medicines", "medication", "medications", "meds",
    "pill", "pills", "tablet", "tablets", "capsule", "capsules",
    "dose", "doses", "dosage", "insulin", "drops", "syrup",
}

WHERE_WORDS = {"where", "find", "lost", "seen", "misplaced", "put", "left"}

# "what time is it", "what's the date", "what day is it today"
CLOCK_PATTERN = re.compile(
    r"\b(what|which|tell me)\b.*\b(time|date|day)\b"
    r"|\btoday'?s date\b"
)

# Words skipped when pulling the object name out of a
# "where is ..." question ("where is m trimmer" -> "trimmer").
WHERE_FILLER = {
    "where", "is", "are", "was", "were", "my", "m", "the", "our", "a", "an",
    "did", "do", "i", "leave", "left", "put", "you", "have", "has", "seen",
    "find", "lost", "misplaced", "can", "could", "help", "me", "to", "s",
    "please", "orion", "know", "tell", "if",
}

# Words that end the object name ("my keys now" -> "keys").
WHERE_STOP = {
    "is", "are", "go", "went", "gone", "now", "today", "please", "again",
    "at", "in", "on", "from", "yesterday", "kept",
}


class CareError(Exception):
    """A request the care service refused, with a user-facing reason."""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


# =========================================================
# FORMATTING
# =========================================================

def _parse(timestamp):
    return datetime.fromisoformat(timestamp)


def clock_text(timestamp):
    """'8:05 AM' from an ISO timestamp."""
    return _parse(timestamp).strftime("%I:%M %p").lstrip("0")


def day_phrase(timestamp):
    moment = _parse(timestamp)
    today = date.today()

    if moment.date() == today:
        return f"today at {clock_text(timestamp)}"

    if moment.date() == today - timedelta(days=1):
        return f"yesterday at {clock_text(timestamp)}"

    return f"on {moment:%A %d %B} at {clock_text(timestamp)}"


def _words(text):
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def _downscale_jpeg(image_bytes):
    frame = cv2.imdecode(
        np.frombuffer(image_bytes, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )

    if frame is None:
        raise CareError("Unable to decode image.")

    height, width = frame.shape[:2]
    scale = MAX_IMAGE_SIDE / max(height, width)

    if scale < 1:
        frame = cv2.resize(
            frame,
            (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )

    ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])

    if not ok:
        raise CareError("Unable to encode image.")

    return frame, encoded.tobytes()


class CareService:
    """
    Medication reminders, object finding and family alerts.

    Safety rules:
    - Only the person's own confirmation marks a dose taken;
      the camera never does.
    - Answers about medicines come from the schedule and dose
      log, never from the language model.
    """

    def __init__(self, store=care_store):
        self.store = store
        self._vision = None
        self._llm = None

        self._scheduler = None
        self._stop = threading.Event()
        self._last_cleanup = None

    # Model clients are created on first use so the care
    # module stays cheap to import.
    # Interactive answers use the fast model route.
    @property
    def vision(self):
        if self._vision is None:
            from app.services.llm_service import OMNIROUTE_FAST_MODEL
            from app.services.vision_services import VisionService
            self._vision = VisionService(model=OMNIROUTE_FAST_MODEL)
        return self._vision

    @property
    def llm(self):
        if self._llm is None:
            from app.services.llm_service import (
                OMNIROUTE_FAST_MODEL,
                LLMService,
            )
            self._llm = LLMService(model=OMNIROUTE_FAST_MODEL)
        return self._llm

    # =====================================================
    # SCHEDULE
    # =====================================================

    def ensure_doses(self, day=None):
        """Create the pending doses scheduled for a day."""
        day = day or date.today()

        for med in self.store.list_medications():
            if med["days"] and day.weekday() not in med["days"]:
                continue

            for time_text in med["times"]:
                hour, minute = (int(part) for part in time_text.split(":"))
                scheduled = datetime.combine(day, datetime.min.time()).replace(
                    hour=hour,
                    minute=minute,
                )

                # Doses scheduled before the medicine was added
                # were never expected.
                if scheduled < _parse(med["created_at"]).replace(second=0):
                    continue

                self.store.create_dose(
                    med["med_id"],
                    scheduled.isoformat(timespec="seconds"),
                )

    def serialize_dose(self, dose):
        return {
            "dose_id": dose["dose_id"],
            "med_id": dose["med_id"],
            "name": dose["name"],
            "amount": dose["amount"],
            "instructions": dose["instructions"],
            "scheduled_for": dose["scheduled_for"],
            "time": clock_text(dose["scheduled_for"]),
            "status": dose["status"],
            "confirmed_time": (
                clock_text(dose["confirmed_at"])
                if dose["confirmed_at"]
                else None
            ),
            "late": bool(dose["late"]),
            "photo": dose["photo"],
        }

    def today(self):
        """Everything the person's Today screen shows."""
        self.ensure_doses()

        now = datetime.now()
        settings = self.store.get_settings()

        due, upcoming, taken, missed = [], [], [], []

        for dose in self.store.doses_for_day(now.date()):
            item = self.serialize_dose(dose)

            if dose["status"] == "taken":
                taken.append(item)
            elif dose["status"] == "missed":
                missed.append(item)
            elif _parse(dose["scheduled_for"]) <= now:
                due.append(item)
            else:
                upcoming.append(item)

        return {
            "person_name": settings["person_name"],
            "time": now.strftime("%I:%M %p").lstrip("0"),
            "date": now.strftime("%A, %d %B %Y"),
            "repeat_minutes": self.store.setting_int("repeat_minutes"),
            "due": due,
            "upcoming": upcoming,
            "taken": taken,
            "missed": missed,
        }

    # =====================================================
    # CONFIRM A DOSE
    # =====================================================

    def confirm_dose(self, dose_id, method="tap", image_bytes=None):
        with self.store.lock:
            dose = self.store.get_dose(dose_id)

            if dose is None:
                raise CareError("Dose not found.", 404)

            if dose["status"] == "taken":
                # Never let a second confirmation suggest a
                # second dose is fine.
                raise CareError(
                    f"{dose['name']} was already taken at "
                    f"{clock_text(dose['confirmed_at'])}.",
                    409,
                )

            now = datetime.now()
            scheduled = _parse(dose["scheduled_for"])

            if scheduled - now > timedelta(minutes=EARLY_CONFIRM_MINUTES):
                raise CareError(
                    f"{dose['name']} is not due until "
                    f"{clock_text(dose['scheduled_for'])}.",
                    409,
                )

            grace = timedelta(minutes=self.store.setting_int("grace_minutes"))
            late = now > scheduled + grace

            photo = None

            if image_bytes:
                try:
                    _, jpeg = _downscale_jpeg(image_bytes)
                    photo = self.store.save_photo("dose", jpeg)
                except CareError:
                    photo = None

            was_alerted = bool(dose["alerted"])

            self.store.mark_taken(dose_id, method, late, photo)

        label = f"{dose['name']} ({clock_text(dose['scheduled_for'])})"

        self.store.log_event(
            "dose_taken",
            f"{label} confirmed{' late' if late else ''} by {method}",
        )

        # Family was told it was missed; tell them it is resolved.
        if was_alerted:
            self._notify(
                f"✅ {self._person()} confirmed {label} "
                f"late, at {now.strftime('%I:%M %p').lstrip('0')}."
            )

        return self.serialize_dose(self.store.get_dose(dose_id))

    # =====================================================
    # QUESTIONS
    # =====================================================

    def ask(self, question, image_bytes=None):
        """
        Answer a question from the person.

        image_bytes is the current camera frame, used to look
        for an object right now when they ask where it is.
        """

        question = (question or "").strip()

        if not question:
            raise CareError("Please ask a question.")

        self.store.log_event("question", question)

        words = set(_words(question))

        medicines = self.store.list_medications()
        med_names = {
            med["med_id"]: set(_words(med["name"]))
            for med in medicines
        }

        named = [
            med for med in medicines
            if med_names[med["med_id"]] and med_names[med["med_id"]] <= words
        ]

        if words & MEDICINE_WORDS or named:
            return {
                "type": "medicine",
                "answer": self._medicine_answer(named),
            }

        # Answered from the clock: instant and always right.
        if CLOCK_PATTERN.search(question.lower()) and not words & WHERE_WORDS:
            return {
                "type": "clock",
                "answer": self._clock_answer(words),
            }

        # Where-questions are never sent to the chat model:
        # it would guess a plausible place.
        if words & WHERE_WORDS:
            obj = self._match_object(words)
            name = obj["name"] if obj else self._where_target(question)

            if name:
                return self._where_answer(name, obj, image_bytes)

        return {
            "type": "chat",
            "answer": self._chat_answer(question),
        }

    def _medicine_answer(self, named):
        """Built from the dose log only; never generated."""
        self.ensure_doses()

        now = datetime.now()
        doses = self.store.doses_for_day(now.date())

        if named:
            ids = {med["med_id"] for med in named}
            doses = [dose for dose in doses if dose["med_id"] in ids]

        if not self.store.list_medications():
            return "I don't have any medicines on your schedule."

        if not doses:
            return "There are no medicines scheduled for you today."

        sentences = []

        for dose in doses:
            name = dose["name"]
            when = clock_text(dose["scheduled_for"])

            if dose["status"] == "taken":
                sentences.append(
                    f"You took your {when} {name} at "
                    f"{clock_text(dose['confirmed_at'])}."
                )
            elif dose["status"] == "missed":
                sentences.append(
                    f"Your {when} {name} was not confirmed as taken."
                )
            elif _parse(dose["scheduled_for"]) <= now:
                sentences.append(
                    f"Your {when} {name} is due now and not taken yet."
                )
            else:
                sentences.append(f"Your next {name} is at {when}.")

        sentences.append(
            "If you are unsure, please check with your family or "
            "doctor before taking another dose."
        )

        return " ".join(sentences)

    def _match_object(self, words):
        for obj in self.store.list_objects():
            name_words = set(_words(obj["name"]))
            singular = {word.rstrip("s") for word in name_words}
            question_singular = {word.rstrip("s") for word in words}

            if name_words and (
                name_words <= words or singular <= question_singular
            ):
                return obj

        return None

    def _clock_answer(self, words):
        now = datetime.now()
        time_text = now.strftime("%I:%M %p").lstrip("0")
        date_text = now.strftime("%A, %d %B %Y")

        if "time" in words and not words & {"date", "day"}:
            return f"It's {time_text}."

        if "time" not in words:
            return f"Today is {date_text}."

        return f"It's {time_text} on {date_text}."

    def _where_target(self, question):
        """Object name from a where-question, or None."""
        tokens = _words(question)

        start = next(
            (index for index, token in enumerate(tokens) if token in WHERE_WORDS),
            None,
        )

        if start is None:
            return None

        name = []

        for token in tokens[start + 1:]:
            if not name and token in WHERE_FILLER:
                continue

            if token in WHERE_STOP or len(name) == 3:
                break

            name.append(token)

        # "where is it" names nothing.
        if not name or name in (["it"], ["they"], ["them"], ["that"], ["this"]):
            return None

        return " ".join(name)

    def _where_answer(self, name, obj, image_bytes):
        # 1. Look right now.
        if image_bytes:
            try:
                seen = self._look_for(name, obj, image_bytes)
            except Exception as error:
                print("CARE_LIVE_LOOK_ERROR:", repr(error))
                seen = None

            if seen:
                return {
                    "type": "object",
                    "answer": f"I can see your {name} right now. It's {seen['location']}.",
                    "photo": seen["photo"],
                }

        looked = "I can't see your {name} right now" if image_bytes else None

        # 2. Remembered sighting of a tracked object.
        if obj is not None and obj["last_seen_at"]:
            remembered = (
                f"I last saw your {name} {obj['last_location']}, "
                f"{day_phrase(obj['last_seen_at'])}."
            )

            return {
                "type": "object",
                "answer": (
                    f"{looked.format(name=name)}. {remembered}"
                    if looked
                    else remembered
                ),
                "photo": obj["last_photo"],
            }

        # 3. Honest answer; never a guess.
        if obj is not None:
            answer = (
                f"{looked.format(name=name)}, and I haven't seen it earlier either."
                if looked
                else f"I haven't seen your {name} yet. I can only notice "
                "things the camera can see."
            )
        else:
            answer = (
                f"{looked.format(name=name) if looked else f'I am not sure where your {name} is'}. "
                f"I'm not keeping track of your {name} yet. Your family can "
                "add it under \u201cThings to keep track of\u201d so I remember "
                "where I last saw it."
            )

        return {"type": "object", "answer": answer, "photo": None}

    def _look_for(self, name, obj, image_bytes):
        """Check the current frame for one object."""
        frame, jpeg = _downscale_jpeg(image_bytes)

        prompt = f"""
Is there a {name} clearly visible in this photo?

If yes, say where it is in plain words a person can use,
starting with a preposition, e.g. "in your right hand" or
"on the table next to the lamp". Do not guess; if you are
not sure it is a {name}, answer false.

Return ONLY valid JSON:
{{"visible": true, "location": ""}}
"""

        data = parse_llm_json(self.vision.analyze_frame(frame, prompt)) or {}
        location = str(data.get("location") or "").strip().rstrip(".")

        if data.get("visible") is not True or not location:
            return None

        photo = self.store.save_photo("room", jpeg)

        if obj is not None:
            self.store.add_sighting(obj["object_id"], location, photo)

        return {"location": location, "photo": photo}

    def _chat_answer(self, question):
        now = datetime.now()

        prompt = f"""
You are Orion, a patient and kind companion for an older
person at home{f' named {self._person()}' if self._person() else ''}.

Current date and time: {now:%A, %d %B %Y, %I:%M %p}

Answer the question below in one to three short, simple
sentences. Speak warmly and plainly.

You know only the date and time above. You cannot see the
home, the weather, the sky or anyone's activities, so never
describe them or say what is happening, even to be friendly
(no "the house is quiet", "the sun is shining"). Never guess
where things are; if asked, say you can't tell from here.
Never invent facts about the person, their family or their day.

Never give medical advice and never answer questions about
medicines, doses or symptoms. For those, say: "Please ask me
'did I take my medicine' for your schedule, or check with
your family or doctor."

Question: {question}
"""

        try:
            answer = (self.llm.generate(prompt) or "").strip()
        except Exception as error:
            print("CARE_CHAT_ERROR:", repr(error))
            answer = ""

        return answer or "Sorry, I couldn't answer that right now."

    # =====================================================
    # ROOM CAMERA
    # =====================================================

    def process_frame(self, image_bytes):
        """Record where tracked objects are visible."""
        objects = self.store.list_objects()

        if not objects:
            return {"seen": []}

        frame, jpeg = _downscale_jpeg(image_bytes)

        names = ", ".join(obj["name"] for obj in objects)

        prompt = f"""
Look at this photo of a home. Which of these objects are
clearly visible: {names}?

For each visible one, describe where it is in plain words a
person can use to find it, starting with a preposition,
e.g. "on the kitchen table next to the fruit bowl".

Only include objects you can clearly see. Do not guess.

Return ONLY valid JSON:
{{"objects": [{{"name": "exact name from the list", "location": ""}}]}}
"""

        data = parse_llm_json(self.vision.analyze_frame(frame, prompt)) or {}

        by_name = {obj["name"].lower(): obj for obj in objects}
        recorded = []
        photo = None

        for item in data.get("objects") or []:
            if not isinstance(item, dict):
                continue

            obj = by_name.get(str(item.get("name") or "").strip().lower())
            location = str(item.get("location") or "").strip()

            if obj is None or not location:
                continue

            if self._recently_seen_there(obj, location):
                continue

            if photo is None:
                photo = self.store.save_photo("room", jpeg)

            self.store.add_sighting(obj["object_id"], location, photo)
            recorded.append({"name": obj["name"], "location": location})

        return {"seen": recorded}

    def _recently_seen_there(self, obj, location):
        if not obj["last_seen_at"]:
            return False

        age = datetime.now() - _parse(obj["last_seen_at"])

        if age > timedelta(minutes=SIGHTING_REPEAT_MINUTES):
            return False

        old = set(_words(obj["last_location"]))
        new = set(_words(location))

        if not old or not new:
            return False

        return len(old & new) / len(old | new) >= 0.6

    # =====================================================
    # MISSED DOSES + SUMMARY
    # =====================================================

    def _person(self):
        return self.store.get_settings()["person_name"].strip()

    def _notify(self, text):
        contacts = self.store.list_contacts()

        if not contacts or not telegram.is_configured():
            return 0

        return telegram.notify_family(contacts, text)

    def check_missed(self):
        grace = timedelta(minutes=self.store.setting_int("grace_minutes"))
        cutoff = (datetime.now() - grace).isoformat(timespec="seconds")

        alerts = 0

        with self.store.lock:
            overdue = self.store.overdue_pending(cutoff)

            for dose in overdue:
                self.store.mark_missed(dose["dose_id"])

        for dose in overdue:
            label = f"{dose['name']} {dose['amount']}".strip()
            when = clock_text(dose["scheduled_for"])

            self.store.log_event("dose_missed", f"{label} ({when}) not confirmed")

            delivered = self._notify(
                f"⚠️ {self._person() or 'Your family member'} has "
                f"not confirmed taking {label}, scheduled for {when}. "
                "Please check in with them."
            )

            if delivered:
                self.store.mark_alerted(dose["dose_id"])
                alerts += 1

        return alerts

    def build_summary(self, day=None):
        day = day or date.today()

        lines = [
            f"Daily summary for {self._person() or 'your family member'}, "
            f"{day:%A %d %B}"
        ]

        doses = self.store.doses_for_day(day)

        if doses:
            lines.append("")
            lines.append("Medicines:")

            for dose in doses:
                label = f"{dose['name']} {dose['amount']}".strip()
                when = clock_text(dose["scheduled_for"])

                if dose["status"] == "taken":
                    mark = "⚠️" if dose["late"] else "✅"
                    late = " (late)" if dose["late"] else ""
                    lines.append(
                        f"{mark} {when} {label}: taken at "
                        f"{clock_text(dose['confirmed_at'])}{late}"
                    )
                elif dose["status"] == "missed":
                    lines.append(f"❌ {when} {label}: not confirmed")
                else:
                    lines.append(f"⏳ {when} {label}: not yet due/confirmed")
        else:
            lines.append("No medicines were scheduled.")

        questions = [
            event["text"]
            for event in self.store.events_for_day(day)
            if event["kind"] == "question"
        ]

        if questions:
            lines.append("")
            lines.append(f"Questions asked: {len(questions)}")

            for text in questions[-5:]:
                lines.append(f"• “{text}”")

        return "\n".join(lines)

    def send_summary(self, day=None):
        day = day or date.today()
        text = self.build_summary(day)
        delivered = self._notify(text)
        self.store.save_summary(day, text, sent=bool(delivered))
        return {"text": text, "delivered": delivered}

    def _summary_due(self, now):
        try:
            hour, minute = (
                int(part)
                for part in self.store.get_settings()["summary_time"].split(":")
            )
        except ValueError:
            return False

        if now.time() < now.replace(hour=hour, minute=minute).time():
            return False

        return self.store.get_summary(now.date()) is None

    # =====================================================
    # SCHEDULER
    # =====================================================

    def tick(self):
        """One scheduler pass. Safe to call repeatedly."""
        now = datetime.now()

        self.ensure_doses(now.date())
        self.check_missed()

        if self._summary_due(now):
            self.send_summary(now.date())

        if self._last_cleanup is None or now - self._last_cleanup > timedelta(hours=1):
            self.store.delete_photos_older_than(PHOTO_RETENTION_DAYS)
            self._last_cleanup = now

    def start_scheduler(self, interval_seconds=30):
        if self._scheduler is not None:
            return

        self._stop.clear()

        def loop():
            while not self._stop.is_set():
                try:
                    self.tick()
                except Exception as error:
                    print("CARE_SCHEDULER_ERROR:", repr(error))

                self._stop.wait(interval_seconds)

        self._scheduler = threading.Thread(
            target=loop,
            name="orion-care-scheduler",
            daemon=True,
        )
        self._scheduler.start()

    def stop_scheduler(self):
        self._stop.set()
        self._scheduler = None


care_service = CareService()
