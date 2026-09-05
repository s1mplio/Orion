from typing import List, Optional

from app.services.llm_service import LLMService


# =========================================================
# PROACTIVE MESSAGE SERVICE
# =========================================================

class ProactiveMessageService:
    """
    Generates Orion's natural-language proactive message.

    Responsibilities:
    - Receives an already-approved proactive trigger.
    - Receives deterministic contextual information.
    - Makes exactly ONE LLM call.
    - Produces one short, natural companion message.

    This service does NOT decide whether Orion should speak.

    That responsibility belongs to ProactivePolicy.
    """

    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
    ):

        self.llm = (
            llm_service
            if llm_service is not None
            else LLMService()
        )

    # =====================================================
    # GENERATE
    # =====================================================

    def generate(
        self,
        message_hint: str,
        current_activity: Optional[str] = None,
        current_salient_event: Optional[str] = None,
        active_interactions: Optional[List[str]] = None,
        recent_actions: Optional[List[str]] = None,
    ) -> Optional[str]:

        # ---------------------------------------------
        # BASIC VALIDATION
        # ---------------------------------------------

        if not message_hint:
            return None

        message_hint = (
            str(message_hint)
            .strip()
        )

        if not message_hint:
            return None

        active_interactions = (
            active_interactions or []
        )

        recent_actions = (
            recent_actions or []
        )

        # ---------------------------------------------
        # BUILD PROMPT
        # ---------------------------------------------

        prompt = self._build_prompt(
            message_hint=message_hint,
            current_activity=current_activity,
            current_salient_event=current_salient_event,
            active_interactions=active_interactions,
            recent_actions=recent_actions,
        )

        # ---------------------------------------------
        # EXACTLY ONE LLM CALL
        # ---------------------------------------------

        try:

            response = (
                self.llm.generate(
                    prompt
                )
            )

        except Exception as exc:

            print(
                "\nPROACTIVE_MESSAGE_LLM_ERROR:",
                repr(exc),
            )

            return None

        # ---------------------------------------------
        # VALIDATE RESPONSE
        # ---------------------------------------------

        if response is None:
            return None

        message = (
            str(response)
            .strip()
        )

        if not message:
            return None

        # ---------------------------------------------
        # LOCAL OUTPUT CLEANUP
        # ---------------------------------------------

        message = (
            self._clean_message(
                message
            )
        )

        return message

    # =====================================================
    # BUILD PROMPT
    # =====================================================

    def _build_prompt(
        self,
        message_hint: str,
        current_activity: Optional[str],
        current_salient_event: Optional[str],
        active_interactions: List[str],
        recent_actions: List[str],
    ) -> str:

        # ---------------------------------------------
        # ACTIVE INTERACTIONS
        # ---------------------------------------------

        if active_interactions:

            interactions_text = "\n".join(
                f"- {interaction}"
                for interaction
                in active_interactions
            )

        else:

            interactions_text = "none"

        # ---------------------------------------------
        # RECENT ACTIONS
        # ---------------------------------------------
        #
        # Only give the LLM a small recent window.
        # We do not need the entire working memory.

        recent = (
            recent_actions[-4:]
        )

        if recent:

            recent_text = "\n".join(
                f"- {action}"
                for action
                in recent
            )

        else:

            recent_text = "none"

        # ---------------------------------------------
        # PROMPT
        # ---------------------------------------------

        return f"""
You are Orion, a contextual AI companion.

A deterministic policy system has already decided that
this moment may be worth commenting on.

Your only job is to express the supplied factual context
as one short, natural companion message.

FACTUAL CONTEXT

Policy hint:
{message_hint}

Current activity:
{current_activity or "unknown"}

Current salient event:
{current_salient_event or "none"}

Active interactions:
{interactions_text}

Recent actions, oldest to newest:
{recent_text}


STRICT RULES

1. Use only the factual information supplied above.

2. Do not invent:
   - intentions,
   - emotions,
   - plans,
   - causes,
   - relationships,
   - identities,
   - future actions,
   - hidden objects,
   - unsupported details.

3. Describe the current situation naturally.

4. Recent actions are historical context.
   Do not claim a recent action is still happening unless
   the current activity or active interactions support it.

5. Do not mention:
   - cameras,
   - computer vision,
   - models,
   - AI detection,
   - policies,
   - prompts,
   - context systems,
   - working memory,
   - semantic events.

6. Do not say:
   - "I detected..."
   - "The system detected..."
   - "The user is..."
   - "According to my observation..."

7. Avoid "I can see..." unless absolutely necessary.

8. Do not give unnecessary advice.

9. Do not warn the user unless the supplied factual
   context clearly supports a genuine reason.

10. Do not ask a question unless the supplied context
    strongly justifies one.

11. Sound like a calm contextual companion,
    not a monitoring system.

12. Prefer ONE sentence.

13. Maximum 20 words.

14. Output ONLY the sentence Orion should say.

Do not include quotation marks.
Do not explain your reasoning.
""".strip()

    # =====================================================
    # CLEAN MESSAGE
    # =====================================================

    def _clean_message(
        self,
        message: str,
    ) -> Optional[str]:

        value = (
            message
            .strip()
        )

        # ---------------------------------------------
        # REMOVE COMMON QUOTE WRAPPING
        # ---------------------------------------------

        if (
            len(value) >= 2
            and
            (
                (
                    value.startswith('"')
                    and
                    value.endswith('"')
                )
                or
                (
                    value.startswith("'")
                    and
                    value.endswith("'")
                )
            )
        ):

            value = (
                value[1:-1]
                .strip()
            )

        if not value:
            return None

        # ---------------------------------------------
        # HARD LENGTH SAFETY
        # ---------------------------------------------
        #
        # Prompt asks for <=20 words.
        # 25 is a defensive upper bound in case
        # the model ignores that instruction.

        words = (
            value.split()
        )

        if len(words) > 25:

            value = " ".join(
                words[:25]
            )

            if value[-1] not in {
                ".",
                "!",
                "?",
            }:

                value += "."

        return value