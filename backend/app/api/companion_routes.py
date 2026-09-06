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

from app.companion.chat_service import CompanionChatService

from app.companion.routing.intent_router import (
    IntentRouter,
)

from app.services.research_job_service import (
    research_job_service,
)

from app.companion.vlm_worker import (
    VLMWorker,
)

from app.companion.memory.scene_models import (
    StructuredScene,
)

from app.companion.memory.shared_memory import (
    memory_manager,
    working_memory,
    scene_intelligence,
)


router = APIRouter(
    prefix="/companion",
    tags=["Companion"],
)


# =====================================================
# SERVICES
# =====================================================

chat_service = CompanionChatService()
intent_router = IntentRouter()

browser_vlm = VLMWorker()


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
    """
    Unified Companion endpoint.

    Routing now has access to recent conversation memory.

    This allows Orion to understand:

        User:
        "I want you to specifically start research on
         how to make better coffee"

    and follow-ups such as:

        "yeah go ahead"
        "do it now"
        "do the full research"

    without relying on brittle phrase matching.
    """

    try:
        message = request.message.strip()

        if not message:
            raise HTTPException(
                status_code=400,
                detail="Message cannot be empty.",
            )

        # -------------------------------------------------
        # Build compact chronological conversation context
        # BEFORE storing the current message.
        # -------------------------------------------------

        conversation_context = (
            _get_recent_conversation_context()
        )

        decision = intent_router.route(
            user_message=message,
            conversation_context=conversation_context,
        )

        print(
            "COMPANION_INTENT:",
            decision.intent,
        )

        print(
            "COMPANION_INTENT_CONFIDENCE:",
            decision.confidence,
        )

        print(
            "COMPANION_INTENT_REASON:",
            decision.reason,
        )

        # =================================================
        # RESEARCH
        # =================================================

        if decision.intent == "research":
            research_query = (
                decision.query or ""
            ).strip()

            if not research_query:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Research request did not contain "
                        "a recoverable research question."
                    ),
                )

            # -------------------------------------------------
            # IMPORTANT:
            # The research job is created BEFORE Orion claims
            # that research has started.
            # -------------------------------------------------

            job_id = (
                research_job_service
                .start_research(
                    research_query
                )
            )

            if not job_id:
                raise HTTPException(
                    status_code=500,
                    detail="Unable to start Research V2.",
                )

            answer = (
                "Deep Research started on: "
                f"{research_query}"
            )

            # Store the real action only after job creation.
            working_memory.add_event(
                event_type="USER_MESSAGE",
                observation=message,
                metadata={
                    "source": "companion_chat",
                    "role": "user",
                    "intent": "research",
                },
            )

            working_memory.add_event(
                event_type="RESEARCH_STARTED",
                observation=research_query,
                metadata={
                    "source": "companion_chat",
                    "role": "orion",
                    "intent": "research",
                    "job_id": job_id,
                },
            )

            working_memory.add_event(
                event_type="ORION_RESPONSE",
                observation=answer,
                metadata={
                    "source": "companion_chat",
                    "role": "orion",
                    "intent": "research",
                    "job_id": job_id,
                },
            )

            return {
                "success": True,
                "intent": "research",
                "answer": answer,
                "job_id": job_id,
                "question": research_query,
                "status": "running",
                "routing": {
                    "confidence": (
                        decision.confidence
                    ),
                    "reason": (
                        decision.reason
                    ),
                },
            }

        # =================================================
        # NORMAL COMPANION CHAT
        # =================================================

        answer = chat_service.chat(
            message
        )

        return {
            "success": True,
            "intent": "chat",
            "answer": answer,
            "job_id": None,
            "routing": {
                "confidence": (
                    decision.confidence
                ),
                "reason": (
                    decision.reason
                ),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Companion chat error:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# =====================================================
# RECENT CONVERSATION FOR ROUTING
# =====================================================

def _get_recent_conversation_context(
    limit: int = 8,
) -> str:
    """
    Return only recent USER_MESSAGE / ORION_RESPONSE /
    RESEARCH_STARTED events for the intent classifier.

    Vision events and unrelated internal memory events are
    intentionally excluded so they do not confuse routing.

    This is short-term conversational context, not a second
    chat history system.
    """

    try:
        events = working_memory.recent(
            limit=30
        )
    except Exception as exc:
        print(
            "ROUTER_CONTEXT_READ_ERROR:",
            repr(exc),
        )
        return ""

    if not events:
        return ""

    conversation_events = []

    for event in events:
        event_type = str(
            event.get(
                "event_type",
                ""
            )
        ).upper()

        if event_type not in {
            "USER_MESSAGE",
            "ORION_RESPONSE",
            "RESEARCH_STARTED",
        }:
            continue

        observation = str(
            event.get(
                "observation",
                ""
            )
            or ""
        ).strip()

        if not observation:
            continue

        metadata = (
            event.get("metadata")
            or {}
        )

        role = str(
            metadata.get(
                "role",
                ""
            )
        ).lower()

        if event_type == "USER_MESSAGE":
            speaker = "User"
        elif event_type == "RESEARCH_STARTED":
            speaker = "System action"
        elif role in {
            "assistant",
            "orion",
        }:
            speaker = "Orion"
        else:
            speaker = "Orion"

        conversation_events.append(
            f"{speaker}: {observation}"
        )

    if not conversation_events:
        return ""

    return "\n".join(
        conversation_events[-limit:]
    )


# =====================================================
# BROWSER VISION MEMORY INTEGRATION
# =====================================================

def _scene_to_payload(
    scene: StructuredScene,
) -> dict:
    try:
        return scene.model_dump()
    except AttributeError:
        return scene.dict()


def _load_previous_structured_scene():
    current_scene = (
        working_memory
        .get_current_scene()
    )

    if not current_scene:
        return (
            None,
            None,
        )

    memory_id = current_scene.get(
        "memory_id"
    )

    payload = current_scene.get(
        "structured_scene"
    )

    if not isinstance(
        payload,
        dict,
    ):
        return (
            None,
            memory_id,
        )

    try:
        scene = (
            StructuredScene
            .model_validate(
                payload
            )
        )

    except Exception as exc:
        print(
            "BROWSER_PREVIOUS_SCENE_PARSE_ERROR:",
            repr(exc),
        )

        return (
            None,
            memory_id,
        )

    return (
        scene,
        memory_id,
    )


def _store_browser_scene(
    scene: StructuredScene,
):
    observation = (
        scene.observation
        .strip()
    )

    (
        previous_scene,
        active_memory_id,
    ) = _load_previous_structured_scene()

    physical_transition = False
    transition_evaluation = None

    # =================================================
    # PHYSICAL SCENE TRANSITION
    # =================================================

    if previous_scene is not None:
        transition_evaluation = (
            scene_intelligence
            .evaluate_context_transition(
                previous=previous_scene,
                candidate=scene,
            )
        )

        physical_transition = bool(
            transition_evaluation.get(
                "confirmed",
                False,
            )
        )

        print(
            "BROWSER_SCENE_TRANSITION:",
            physical_transition,
        )

    # =================================================
    # SEMANTIC COMPARISON
    # =================================================

    semantic_result = (
        scene_intelligence
        .compare_scenes(
            previous=previous_scene,
            current=scene,
            lifecycle_changes={},
        )
    )

    # =================================================
    # RESOLVE PHYSICAL MEMORY IDENTITY
    # =================================================

    if physical_transition:
        working_memory.clear_current_scene(
            reason="browser_scene_transition"
        )

        if active_memory_id is not None:
            working_memory.add_event(
                event_type="SCENE_TRANSITION",
                memory_id=active_memory_id,
                metadata={
                    "source": "browser_camera",
                    "confirmation": (
                        transition_evaluation
                    ),
                },
            )

        memory_id = (
            memory_manager
            .resolve_new_context(
                observation=observation,
                allow_historical_reuse=True,
            )
        )

    elif active_memory_id is not None:
        continued = (
            memory_manager
            .continue_scene(
                memory_id=active_memory_id,
                confirmed=True,
            )
        )

        if continued:
            memory_id = active_memory_id
        else:
            memory_id = (
                memory_manager
                .resolve_new_context(
                    observation=observation,
                    allow_historical_reuse=True,
                )
            )

    else:
        memory_id = (
            memory_manager
            .resolve_new_context(
                observation=observation,
                allow_historical_reuse=True,
            )
        )

    if memory_id is None:
        raise RuntimeError(
            "Unable to resolve Orion scene memory."
        )

    # =================================================
    # GENERATION
    # =================================================

    current_scene = (
        working_memory
        .get_current_scene()
    )

    previous_generation = 0

    if current_scene:
        try:
            previous_generation = int(
                current_scene.get(
                    "generation"
                )
                or 0
            )
        except (
            TypeError,
            ValueError,
        ):
            previous_generation = 0

    generation = (
        previous_generation + 1
    )

    # =================================================
    # AUTHORITATIVE CURRENT SCENE
    # =================================================

    scene_payload = (
        _scene_to_payload(
            scene
        )
    )

    working_memory.set_current_scene(
        observation=observation,
        memory_id=memory_id,
        generation=generation,
        structured_scene=scene_payload,
    )

    # =================================================
    # MEANINGFUL SEMANTIC EVENT
    # =================================================

    if (
        previous_scene is not None
        and
        not physical_transition
        and
        semantic_result.get(
            "meaningful_event",
            False,
        )
    ):
        working_memory.add_event(
            event_type="SEMANTIC_EVENT",
            observation=observation,
            memory_id=memory_id,
            metadata={
                "generation": generation,
                "source": "browser_camera",
                "structured_scene": (
                    scene_payload
                ),
                "semantic_result": (
                    semantic_result
                ),
            },
        )

    print(
        "\n=============================="
    )
    print(
        "BROWSER SCENE ESTABLISHED"
    )
    print(
        "=============================="
    )
    print(
        "Generation:",
        generation,
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
        "Observation:",
        observation,
    )
    print(
        "==============================\n"
    )

    return {
        "memory_id": memory_id,
        "generation": generation,
        "physical_transition": (
            physical_transition
        ),
        "semantic_event": (
            semantic_result.get(
                "meaningful_event",
                False,
            )
        ),
    }


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
    try:
        image_bytes = await image.read()

        if not image_bytes:
            raise HTTPException(
                status_code=400,
                detail="Image is empty.",
            )

        image_array = np.frombuffer(
            image_bytes,
            dtype=np.uint8,
        )

        frame = cv2.imdecode(
            image_array,
            cv2.IMREAD_COLOR,
        )

        if frame is None:
            raise HTTPException(
                status_code=400,
                detail="Unable to decode image.",
            )

        raw_answer = (
            browser_vlm
            .vision_service
            .analyze_frame(
                frame,
                browser_vlm._build_prompt(),
            )
        )

        if raw_answer:
            raw_answer = raw_answer.strip()

        if not raw_answer:
            raise RuntimeError(
                "VLM returned an empty response."
            )

        structured_scene = (
            browser_vlm
            ._parse_structured_scene(
                raw_answer
            )
        )

        memory_result = (
            _store_browser_scene(
                structured_scene
            )
        )

        return {
            "success": True,
            "answer": (
                structured_scene.observation
            ),
            "memory": memory_result,
        }

    except HTTPException:
        raise

    except Exception as e:
        print(
            "Vision error:",
            repr(e),
        )

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
