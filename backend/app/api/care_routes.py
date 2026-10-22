import re
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from app.care import telegram
from app.care.care_service import CareError, care_service
from app.care.care_store import care_store


router = APIRouter(
    prefix="/care",
    tags=["Care Companion"],
)

TIME_PATTERN = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _raise(error: CareError):
    raise HTTPException(status_code=error.status_code, detail=str(error))


# =========================================================
# REQUEST MODELS
# =========================================================

class MedicationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    dose: str = Field(default="", max_length=100)
    instructions: str = Field(default="", max_length=500)
    # "HH:MM", 24-hour
    times: List[str] = Field(min_length=1, max_length=12)
    # 0 = Monday ... 6 = Sunday; empty means every day
    days: List[int] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Medicine name is required.")

        return value

    @field_validator("times")
    @classmethod
    def check_times(cls, values):
        cleaned = sorted({value.strip() for value in values})

        for value in cleaned:
            if not TIME_PATTERN.match(value):
                raise ValueError(f"Invalid time {value!r}; use HH:MM.")

        return cleaned

    @field_validator("days")
    @classmethod
    def check_days(cls, values):
        cleaned = sorted(set(values))

        if any(day < 0 or day > 6 for day in cleaned):
            raise ValueError("Days must be 0 (Monday) to 6 (Sunday).")

        # All seven days is the same as every day.
        return [] if len(cleaned) == 7 else cleaned


class ObjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)


class SettingsRequest(BaseModel):
    person_name: Optional[str] = Field(default=None, max_length=60)
    grace_minutes: Optional[int] = Field(default=None, ge=10, le=240)
    repeat_minutes: Optional[int] = Field(default=None, ge=1, le=60)
    summary_time: Optional[str] = None

    @field_validator("summary_time")
    @classmethod
    def check_summary_time(cls, value):
        if value is not None and not TIME_PATTERN.match(value):
            raise ValueError("Use HH:MM for the summary time.")

        return value


class ContactRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    telegram_chat_id: str = Field(min_length=1, max_length=40)


# =========================================================
# TODAY SCREEN
# =========================================================

@router.get("/today")
def today():
    return care_service.today()


@router.post("/doses/{dose_id}/confirm")
async def confirm_dose(
    dose_id: int,
    method: str = Form("tap"),
    image: Optional[UploadFile] = File(None),
):
    image_bytes = await image.read() if image is not None else None

    try:
        return await run_in_threadpool(
            care_service.confirm_dose,
            dose_id,
            "voice" if method == "voice" else "tap",
            image_bytes,
        )
    except CareError as error:
        _raise(error)


@router.post("/ask")
async def ask(
    question: str = Form(..., min_length=1, max_length=500),
    image: Optional[UploadFile] = File(None),
):
    """
    Answer a question. The current camera frame is optional;
    it lets Orion look for an object right now.
    """

    image_bytes = await image.read() if image is not None else None

    try:
        return await run_in_threadpool(
            care_service.ask,
            question,
            image_bytes or None,
        )
    except CareError as error:
        _raise(error)


@router.post("/frames")
async def room_frame(image: UploadFile = File(...)):
    image_bytes = await image.read()

    if not image_bytes:
        raise HTTPException(status_code=400, detail="Image is empty.")

    try:
        return await run_in_threadpool(care_service.process_frame, image_bytes)
    except CareError as error:
        _raise(error)
    except Exception as error:
        print("Care frame error:", repr(error))
        raise HTTPException(status_code=500, detail=str(error))


@router.get("/photos/{name}")
def photo(name: str):
    path = care_store.photo_path(name)

    if path is None:
        raise HTTPException(status_code=404, detail="Photo not found.")

    return FileResponse(path, media_type="image/jpeg")


# =========================================================
# MEDICATIONS
# =========================================================

@router.get("/medications")
def list_medications():
    return {"medications": care_store.list_medications()}


@router.post("/medications")
def add_medication(request: MedicationRequest):
    med = care_store.add_medication(
        request.name,
        request.dose.strip(),
        request.instructions.strip(),
        request.times,
        request.days,
    )
    care_store.log_event("setup", f"Added medicine {med['name']}")
    return med


@router.put("/medications/{med_id}")
def update_medication(med_id: int, request: MedicationRequest):
    if care_store.get_medication(med_id) is None:
        raise HTTPException(status_code=404, detail="Medicine not found.")

    return care_store.update_medication(
        med_id,
        request.name,
        request.dose.strip(),
        request.instructions.strip(),
        request.times,
        request.days,
    )


@router.delete("/medications/{med_id}")
def delete_medication(med_id: int):
    med = care_store.get_medication(med_id)

    if med is None:
        raise HTTPException(status_code=404, detail="Medicine not found.")

    # Kept for the history; only stops future reminders.
    care_store.deactivate_medication(med_id)
    care_store.log_event("setup", f"Stopped medicine {med['name']}")
    return {"deleted": True}


@router.get("/doses")
def dose_log(day: Optional[date] = None):
    day = day or date.today()

    if day == date.today():
        care_service.ensure_doses(day)

    return {
        "day": day.isoformat(),
        "doses": [
            care_service.serialize_dose(dose)
            for dose in care_store.doses_for_day(day)
        ],
    }


# =========================================================
# TRACKED OBJECTS
# =========================================================

@router.get("/objects")
def list_objects():
    return {"objects": care_store.list_objects()}


@router.post("/objects")
def add_object(request: ObjectRequest):
    name = request.name.strip().lower()

    if not name:
        raise HTTPException(status_code=400, detail="Name is required.")

    return {"objects": care_store.add_object(name)}


@router.delete("/objects/{object_id}")
def delete_object(object_id: int):
    care_store.delete_object(object_id)
    return {"deleted": True}


# =========================================================
# SETTINGS
# =========================================================

@router.get("/settings")
def get_settings():
    return care_store.get_settings()


@router.put("/settings")
def update_settings(request: SettingsRequest):
    values = request.model_dump(exclude_none=True)

    if "person_name" in values:
        values["person_name"] = values["person_name"].strip()

    return care_store.update_settings(values)


# =========================================================
# FAMILY CONTACTS (TELEGRAM)
# =========================================================

@router.get("/telegram")
def telegram_status():
    status = {
        "configured": telegram.is_configured(),
        "contacts": care_store.list_contacts(),
        "recent_chats": [],
        "error": None,
    }

    if status["configured"]:
        try:
            known = {c["telegram_chat_id"] for c in status["contacts"]}
            status["recent_chats"] = [
                chat for chat in telegram.recent_chats()
                if chat["telegram_chat_id"] not in known
            ]
        except Exception as error:
            status["error"] = str(error)

    return status


@router.post("/contacts")
def add_contact(request: ContactRequest):
    return {
        "contacts": care_store.add_contact(
            request.name.strip(),
            request.telegram_chat_id.strip(),
        )
    }


@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: int):
    care_store.delete_contact(contact_id)
    return {"deleted": True}


@router.post("/contacts/test")
def test_contacts():
    contacts = care_store.list_contacts()

    if not contacts:
        raise HTTPException(status_code=400, detail="Add a family contact first.")

    try:
        delivered = telegram.notify_family(
            contacts,
            "\U0001f44b Test message from Orion Care. Alerts about "
            "missed medicines will arrive here.",
        )
    except RuntimeError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not delivered:
        raise HTTPException(
            status_code=502,
            detail="No message could be delivered. Check the bot token.",
        )

    return {"delivered": delivered}


# =========================================================
# DAILY SUMMARY
# =========================================================

@router.get("/summary")
def summary(day: Optional[date] = None):
    return {"text": care_service.build_summary(day or date.today())}


@router.post("/summary/send")
def send_summary():
    if not telegram.is_configured() or not care_store.list_contacts():
        raise HTTPException(
            status_code=400,
            detail="Set up Telegram and add a family contact first.",
        )

    return care_service.send_summary()
