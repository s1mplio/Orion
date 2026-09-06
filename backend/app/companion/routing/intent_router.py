from dataclasses import dataclass
from typing import Optional
import json
import re

from app.services.llm_service import LLMService


# =========================================================
# ROUTE DECISION
# =========================================================

@dataclass(frozen=True)
class RouteDecision:
    """
    Final routing decision for a Companion message.

    intent:
        "chat"
        "research"

    query:
        Research question/topic when intent == "research".

    confidence:
        Classifier confidence from 0.0 to 1.0.

    reason:
        Short internal/debug explanation.
    """

    intent: str
    query: Optional[str] = None
    confidence: float = 1.0
    reason: str = ""


# =========================================================
# INTENT ROUTER
# =========================================================

class IntentRouter:
    """
    Meaning-based Orion router.

    Architecture:

        obvious explicit control
                ↓
        deterministic fast path
                ↓
        ambiguous/natural request
                ↓
        small LLM classification call
                ↓
          chat / research

    The LLM classifier is allowed to see recent conversation
    turns so follow-ups such as:

        "yeah go ahead"
        "do it now"
        "do the full research"

    can resolve against what the user and Orion just discussed.

    IMPORTANT:
    The classifier NEVER performs research itself.
    It only decides whether ResearchJobService should run.
    """

    def __init__(self):
        self.llm = LLMService()

    # =====================================================
    # PUBLIC ROUTE METHOD
    # =====================================================

    def route(
        self,
        user_message: str,
        conversation_context: str = "",
    ) -> RouteDecision:

        message = (user_message or "").strip()

        if not message:
            return RouteDecision(
                intent="chat",
                confidence=1.0,
                reason="empty_message",
            )

        # -------------------------------------------------
        # 1. Deterministic explicit controls.
        #
        # These are product commands, not language
        # understanding. Keeping them deterministic gives
        # the user a guaranteed override.
        # -------------------------------------------------

        explicit_query = self._explicit_research_override(
            message
        )

        if explicit_query:
            return RouteDecision(
                intent="research",
                query=explicit_query,
                confidence=1.0,
                reason="explicit_research_override",
            )

        # -------------------------------------------------
        # 2. Very obvious ordinary Companion messages.
        #
        # Avoid paying for a classifier on greetings and
        # tiny conversational turns unless recent context
        # suggests the message may be confirming research.
        # -------------------------------------------------

        if (
            not conversation_context.strip()
            and self._obvious_chat(message)
        ):
            return RouteDecision(
                intent="chat",
                confidence=1.0,
                reason="obvious_chat_fast_path",
            )

        # -------------------------------------------------
        # 3. Meaning-based classifier.
        # -------------------------------------------------

        return self._classify_with_llm(
            message=message,
            conversation_context=conversation_context,
        )

    # =====================================================
    # EXPLICIT RESEARCH OVERRIDE
    # =====================================================

    def _explicit_research_override(
        self,
        message: str,
    ) -> Optional[str]:

        text = self._remove_orion_prefix(message)

        # Product-level commands. These intentionally cover
        # concise direct controls while normal language is
        # left to the classifier.
        patterns = (
            r"^\s*(?:please\s+)?(?:use|open|start|launch)\s+(?:the\s+)?(?:deep\s+)?research\s+mode(?:\s+(?:for|on)\s+this)?[\s,:-]*(.*)$",
            r"^\s*(?:please\s+)?(?:send|route)\s+this\s+to\s+(?:the\s+)?(?:deep\s+)?research(?:\s+mode)?[\s,:-]*(.*)$",
            r"^\s*(?:please\s+)?run\s+this\s+through\s+(?:the\s+)?(?:deep\s+)?research(?:\s+mode)?[\s,:-]*(.*)$",
        )

        for pattern in patterns:
            match = re.match(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            trailing_query = (
                match.group(1)
                if match.lastindex
                else ""
            )

            trailing_query = (
                trailing_query or ""
            ).strip(" ,:-")

            # If the direct control contains its topic,
            # use it immediately.
            if trailing_query:
                return trailing_query

            # A bare "open research mode" belongs in the
            # frontend button/page rather than starting an
            # empty backend research job.
            return None

        return None

    # =====================================================
    # OBVIOUS CHAT FAST PATH
    # =====================================================

    def _obvious_chat(
        self,
        message: str,
    ) -> bool:

        normalized = re.sub(
            r"\s+",
            " ",
            message.lower(),
        ).strip()

        obvious = (
            r"^(?:hi|hello|hey|yo|thanks|thank you|okay|ok|cool|nice|bye)[!. ]*$",
            r"^(?:what time is it|what is the time|what's the time)[?.! ]*$",
            r"^(?:what is the date|what's the date|what date is it)[?.! ]*$",
        )

        return any(
            re.match(pattern, normalized)
            for pattern in obvious
        )

    # =====================================================
    # LLM CLASSIFICATION
    # =====================================================

    def _classify_with_llm(
        self,
        message: str,
        conversation_context: str,
    ) -> RouteDecision:

        prompt = f"""
You are the intent-routing controller for Orion, an AI companion.

Your ONLY job is to decide whether the CURRENT USER MESSAGE
should be handled by normal Companion Chat or should actually
START Orion's Deep Research V2 pipeline.

You do not answer the user's question.
You do not perform research.
You only classify the action.

============================================================
AVAILABLE ACTIONS
============================================================

CHAT
Use normal Companion Chat when the user wants:
- normal conversation,
- a quick factual answer,
- a simple explanation,
- advice,
- a short list,
- visual/contextual assistance,
- or casually uses the word "research" without actually
  requesting Orion's full research workflow.

RESEARCH
Start Deep Research V2 when the user:
- explicitly asks Orion to start, perform, run or conduct
  research,
- explicitly asks for full/deep/proper research,
- asks for a literature review, evidence synthesis,
  scientific report, paper comparison, cited investigation,
  hypothesis/experiment-oriented investigation,
- explicitly insists that this particular request should
  use Orion's research system,
- OR clearly confirms a research action proposed/requested
  in the RECENT CONVERSATION.

============================================================
CRITICAL DISTINCTIONS
============================================================

The word "research" alone does not force RESEARCH.

Example:
User: "research which plants cats can't eat"
This can be CHAT because the underlying request is a quick
fact/list and the user did not clearly insist on the full
research workflow.

But explicit action intent DOES force RESEARCH.

Examples:
"I want you to specifically start research on better coffee"
-> RESEARCH

"do the full research on this"
-> RESEARCH when recent conversation identifies the topic.

"yeah go ahead"
-> RESEARCH only when recent conversation clearly shows that
the user is confirming a pending/proposed research action.
Otherwise it is CHAT.

"do it now"
-> RESEARCH only when recent conversation clearly refers to
starting research.

Never classify a message as RESEARCH merely because Orion
previously used words such as "research" in an unrelated
answer. There must be a clear current request or confirmation.

If the intended research topic can be recovered from recent
conversation, return that complete topic as research_query.

If the current message itself contains the topic, prefer the
current message's topic.

If uncertain, choose CHAT.

============================================================
RECENT CONVERSATION
============================================================

{conversation_context or "No recent conversation supplied."}

============================================================
CURRENT USER MESSAGE
============================================================

{message}

============================================================
OUTPUT
============================================================

Return ONLY valid JSON with exactly these keys:

{{
  "intent": "chat" or "research",
  "research_query": "topic/question" or null,
  "confidence": number from 0.0 to 1.0,
  "reason": "very short reason"
}}
"""

        try:
            raw = self.llm.generate(prompt)
        except Exception as exc:
            print(
                "INTENT_CLASSIFIER_ERROR:",
                repr(exc),
            )

            return RouteDecision(
                intent="chat",
                confidence=0.0,
                reason="classifier_error_default_chat",
            )

        parsed = self._parse_classifier_json(raw)

        if parsed is None:
            return RouteDecision(
                intent="chat",
                confidence=0.0,
                reason="classifier_parse_failure_default_chat",
            )

        intent = str(
            parsed.get("intent", "chat")
        ).strip().lower()

        confidence = self._safe_confidence(
            parsed.get("confidence")
        )

        reason = str(
            parsed.get("reason", "")
        ).strip()

        if intent != "research":
            return RouteDecision(
                intent="chat",
                confidence=confidence,
                reason=reason or "classifier_chat",
            )

        query = parsed.get("research_query")

        if query is not None:
            query = str(query).strip()

        # Never launch an empty research job.
        if not query:
            return RouteDecision(
                intent="chat",
                confidence=confidence,
                reason="research_without_query_default_chat",
            )

        return RouteDecision(
            intent="research",
            query=query,
            confidence=confidence,
            reason=reason or "classifier_research",
        )

    # =====================================================
    # CLASSIFIER JSON PARSER
    # =====================================================

    def _parse_classifier_json(
        self,
        raw,
    ) -> Optional[dict]:

        if not raw:
            return None

        text = str(raw).strip()

        # Strip common fenced output.
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(
            r"\s*```$",
            "",
            text,
        ).strip()

        try:
            data = json.loads(text)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

        # Conservative recovery if the model wrapped JSON
        # with accidental prose.
        start = text.find("{")
        end = text.rfind("}")

        if (
            start == -1
            or end == -1
            or end <= start
        ):
            return None

        try:
            data = json.loads(
                text[start:end + 1]
            )

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            return None

        return None

    # =====================================================
    # CONFIDENCE
    # =====================================================

    def _safe_confidence(
        self,
        value,
    ) -> float:

        try:
            confidence = float(value)
        except (TypeError, ValueError):
            return 0.5

        return max(
            0.0,
            min(1.0, confidence),
        )

    # =====================================================
    # ORION PREFIX
    # =====================================================

    def _remove_orion_prefix(
        self,
        message: str,
    ) -> str:

        return re.sub(
            r"^\s*(?:hey\s+)?orion[\s,:-]*",
            "",
            message,
            count=1,
            flags=re.IGNORECASE,
        ).strip()
