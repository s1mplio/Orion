from dataclasses import dataclass
from typing import Optional
import re


# =========================================================
# ROUTE DECISION
# =========================================================

@dataclass(frozen=True)
class RouteDecision:
    """
    Result produced by Orion's deterministic intent router.

    intent:
        "chat"
        "research"

    query:
        Normalized research question when research is
        explicitly requested.

        None for normal companion conversation.
    """

    intent: str
    query: Optional[str] = None


# =========================================================
# INTENT ROUTER
# =========================================================

class IntentRouter:
    """
    Lightweight V1 router between:

        1. Normal Companion conversation
        2. Deep Research V2

    IMPORTANT:

    This router intentionally does NOT use another LLM call.

    Research V2 is expensive, so it should only start when
    the user clearly expresses research/investigation intent.

    Ordinary scientific questions remain normal chat.
    """

    RESEARCH_PATTERNS = (
        r"\bresearch\b",
        r"\binvestigate\b",
        r"\bdo\s+(?:some\s+)?research\b",
        r"\bresearch\s+into\b",
        r"\bresearch\s+about\b",
        r"\blook\s+into\b",
        r"\bdeep\s+dive\b",
        r"\bdeep\s+research\b",
    )

    def route(
        self,
        user_message: str,
    ) -> RouteDecision:

        if not user_message:
            return RouteDecision(
                intent="chat"
            )

        message = user_message.strip()

        if not message:
            return RouteDecision(
                intent="chat"
            )

        # -------------------------------------------------
        # Explicit research intent
        # -------------------------------------------------

        if self._has_research_intent(
            message
        ):

            query = (
                self._extract_research_query(
                    message
                )
            )

            if query:
                return RouteDecision(
                    intent="research",
                    query=query,
                )

        # -------------------------------------------------
        # Default
        # -------------------------------------------------

        return RouteDecision(
            intent="chat"
        )

    # =====================================================
    # RESEARCH INTENT DETECTION
    # =====================================================

    def _has_research_intent(
        self,
        message: str,
    ) -> bool:

        text = message.lower()

        for pattern in self.RESEARCH_PATTERNS:

            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                return True

        return False

    # =====================================================
    # RESEARCH QUERY EXTRACTION
    # =====================================================

    def _extract_research_query(
        self,
        message: str,
    ) -> Optional[str]:

        query = message.strip()

        # -------------------------------------------------
        # Remove optional Orion wake-name prefix
        # -------------------------------------------------

        query = re.sub(
            r"^\s*orion[\s,:-]*",
            "",
            query,
            flags=re.IGNORECASE,
        )

        # -------------------------------------------------
        # Remove common command prefixes
        # -------------------------------------------------

        command_patterns = (
            r"^\s*please\s+do\s+(?:some\s+)?research\s+(?:on|about|into)\s+",
            r"^\s*please\s+research\s+",
            r"^\s*do\s+(?:some\s+)?research\s+(?:on|about|into)\s+",
            r"^\s*research\s+(?:on|about|into)\s+",
            r"^\s*research\s+",
            r"^\s*please\s+investigate\s+",
            r"^\s*investigate\s+",
            r"^\s*please\s+look\s+into\s+",
            r"^\s*look\s+into\s+",
            r"^\s*do\s+a\s+deep\s+dive\s+(?:on|into|about)\s+",
            r"^\s*deep\s+research\s+(?:on|into|about)\s+",
        )

        for pattern in command_patterns:

            cleaned = re.sub(
                pattern,
                "",
                query,
                count=1,
                flags=re.IGNORECASE,
            )

            if cleaned != query:
                query = cleaned
                break

        query = query.strip()

        # Remove accidental punctuation left by command.
        query = query.lstrip(
            " ,:-"
        ).strip()

        if not query:
            return None

        # -------------------------------------------------
        # Keep the research question natural.
        #
        # We intentionally do NOT try to rewrite the
        # scientific question here.
        #
        # Research V2's Planner Agent handles decomposition.
        # -------------------------------------------------

        return query