from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
)

from pydantic import BaseModel

import numpy as np
import cv2

from app.services.vision_services import VisionService
from app.companion.chat_service import CompanionChatService


router = APIRouter(
    prefix="/companion",
    tags=["Companion"],
)


# =====================================================
# SERVICES
# =====================================================

vision_service = VisionService()

chat_service = CompanionChatService()


# =====================================================
# REQUEST MODELS
# =====================================================

class ChatRequest(BaseModel):

    message: str


# =====================================================
# CHAT
# =====================================================

@router.post("/chat")
async def companion_chat(
    request: ChatRequest,
):

    try:

        answer = chat_service.chat(
            request.message
        )

        return {
            "success": True,
            "answer": answer,
        }

    except Exception as e:

        print(
            "Companion chat error:",
            e,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================================
# VISION
# =====================================================

@router.post("/vision")
async def analyze_vision(
    image: UploadFile = File(...),
    prompt: str = Form(
        "What can you see in this image?"
    ),
):
    """
    Receive an image from the frontend
    and ask Orion's vision model to analyze it.
    """

    try:

        # ---------------------------------------------
        # Read uploaded image
        # ---------------------------------------------

        image_bytes = await image.read()

        if not image_bytes:

            raise HTTPException(
                status_code=400,
                detail="Image is empty.",
            )

        # ---------------------------------------------
        # Convert bytes → NumPy array
        # ---------------------------------------------

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        # ---------------------------------------------
        # Decode image → OpenCV frame
        # ---------------------------------------------

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if frame is None:

            raise HTTPException(
                status_code=400,
                detail="Unable to decode image.",
            )

        # ---------------------------------------------
        # Send frame to VisionService
        # ---------------------------------------------

        answer = vision_service.analyze_frame(
            frame,
            prompt,
        )

        return {
            "success": True,
            "answer": answer,
        }

    except HTTPException:

        raise

    except Exception as e:

        print(
            "Vision error:",
            e,
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )