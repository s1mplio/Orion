from datetime import datetime
from typing import Any, Dict, Optional

from app.companion.proactive.proactive_policy import (
    ProactiveDecision,
)


class GoalCandidateGenerator:
    """
    ORION Goal-Driven Candidate Generator V1.

    Purpose:
        Convert deterministic GoalProgress evidence into a
        candidate that can be evaluated by ProactiveReasoner V2.

    Pipeline:

        GoalProgressReasoner
                ↓
        GoalCandidateGenerator
                ↓
        ProactiveDecision
                ↓
        ProactiveReasoner V2
                ↓
           SILENT / SPEAK

    Important:
        - no LLM calls
        - no VLM calls
        - does NOT generate final speech
        - does NOT decide that the user must be reminded
        - does NOT infer hidden intention

    should_speak=True means only:

        "This goal situation is worth asking
         ProactiveReasoner V2 to evaluate."

    It does NOT mean Orion should actually speak.
    """

    def __init__(
        self,
        goal_progress_reasoner,
        cooldown_seconds: float = 20.0,
        minimum_relevance_score: float = 0.5,
        minimum_confidence: float = 0.5,
    ):
        self.goal_progress_reasoner = (
            goal_progress_reasoner
        )

        self.cooldown_seconds = float(
            cooldown_seconds
        )

        self.minimum_relevance_score = float(
            minimum_relevance_score
        )

        self.minimum_confidence = float(
            minimum_confidence
        )

        # Tracks only ACTUAL approved goal-driven speech.
        #
        # Candidate generation itself never starts cooldown.
        self.last_spoken_at: Optional[datetime] = None

        self.last_goal_id: Optional[int] = None
        self.last_reason: Optional[str] = None
        self.last_message_hint: Optional[str] = None

    # =====================================================
    # PUBLIC API
    # =====================================================

    def evaluate(
        self,
    ) -> ProactiveDecision:
        """
        Evaluate current GoalProgress state.

        Returns either:
            - a candidate for ProactiveReasoner V2
            - a deterministic SILENT decision
        """

        data = self._get_progress_snapshot()

        if not data:
            return self._silent(
                reason="no_goal_progress",
            )

        active_goal_count = self._safe_int(
            data.get("active_goal_count")
        )

        if active_goal_count <= 0:
            return self._silent(
                reason="no_active_goals",
            )

        confidence = self._safe_float(
            data.get("confidence")
        )

        if confidence < self.minimum_confidence:
            return self._silent(
                reason="low_goal_progress_confidence",
            )

        if self._in_cooldown():
            return self._silent(
                reason="goal_candidate_cooldown",
            )

        goals = (
            data.get("goals")
            or []
        )

        if not isinstance(goals, list):
            return self._silent(
                reason="invalid_goal_progress",
            )

        best_goal: Optional[
            Dict[str, Any]
        ] = None

        best_score = -1.0

        for goal in goals:
            if not isinstance(goal, dict):
                continue

            if not goal.get(
                "should_consider_reminder"
            ):
                continue

            instruction = str(
                goal.get("instruction")
                or ""
            ).strip()

            if not instruction:
                continue

            relevance_score = self._safe_float(
                goal.get("relevance_score")
            )

            if (
                relevance_score
                < self.minimum_relevance_score
            ):
                continue

            if relevance_score > best_score:
                best_goal = goal
                best_score = relevance_score

        if best_goal is None:
            return self._silent(
                reason="no_goal_candidate",
            )

        return self._build_goal_candidate(
            best_goal
        )

    # =====================================================
    # REGISTER ACTUAL SPEECH
    # =====================================================

    def register_spoken(
        self,
        decision: Optional[
            ProactiveDecision
        ] = None,
        goal_id: Optional[int] = None,
        reason: Optional[str] = None,
        message_hint: Optional[str] = None,
    ) -> None:
        """
        Register actual approved speech.

        Call this ONLY after ProactiveReasoner V2 approves
        the goal-driven candidate and Orion actually accepts
        it for speech.

        Candidate generation alone must never call this.
        """

        if decision is not None:
            reason = decision.reason
            message_hint = (
                decision.message_hint
            )

        self.last_spoken_at = (
            datetime.now()
        )

        self.last_goal_id = (
            self._safe_int(
                goal_id,
                default=-1,
            )
            if goal_id is not None
            else None
        )

        self.last_reason = (
            str(reason).strip()
            if reason
            else None
        )

        self.last_message_hint = (
            str(message_hint).strip()
            if message_hint
            else None
        )

        print(
            "GOAL_CANDIDATE_COOLDOWN_REGISTERED:",
            self.last_spoken_at.isoformat(),
        )

    # =====================================================
    # BUILD CANDIDATE
    # =====================================================

    def _build_goal_candidate(
        self,
        goal: Dict[str, Any],
    ) -> ProactiveDecision:
        goal_id = self._safe_int(
            goal.get("goal_id"),
            default=-1,
        )

        description = str(
            goal.get("description")
            or ""
        ).strip()

        instruction = str(
            goal.get("instruction")
            or ""
        ).strip()

        reminder_reason = str(
            goal.get("reminder_reason")
            or ""
        ).strip()

        relevance_score = self._safe_float(
            goal.get("relevance_score")
        )

        currently_present = self._clean_list(
            goal.get(
                "currently_present_objects"
            )
        )

        disappeared = self._clean_list(
            goal.get(
                "disappeared_relevant_objects"
            )
        )

        active_interactions = (
            goal.get(
                "active_relevant_interactions"
            )
            or []
        )

        recent_interactions = (
            goal.get(
                "recent_relevant_interactions"
            )
            or []
        )

        hint_parts = []

        if description:
            hint_parts.append(
                f'Active goal: "{description}".'
            )

        if instruction:
            hint_parts.append(
                f'User instruction: "{instruction}".'
            )

        if reminder_reason:
            hint_parts.append(
                "Goal progress evidence: "
                f"{reminder_reason}."
            )

        if currently_present:
            hint_parts.append(
                "Relevant object currently present: "
                + ", ".join(
                    currently_present
                )
                + "."
            )

        if disappeared:
            hint_parts.append(
                "Relevant object lifecycle change: "
                + ", ".join(
                    disappeared
                )
                + "."
            )

        if active_interactions:
            hint_parts.append(
                "There is an active interaction "
                "with a goal-relevant object."
            )

        elif recent_interactions:
            hint_parts.append(
                "There was a recent interaction "
                "with a goal-relevant object."
            )

        hint_parts.append(
            "The downstream reasoner must decide "
            "whether speaking now would actually help."
        )

        message_hint = " ".join(
            hint_parts
        )

        # Duplicate suppression applies only against
        # previously approved goal-driven speech.
        if (
            self.last_goal_id == goal_id
            and
            self.last_reason
            == "goal_progress_candidate"
            and
            self.last_message_hint
            == message_hint
        ):
            return self._silent(
                reason="goal_duplicate_suppressed",
            )

        print(
            "GOAL_CANDIDATE_CREATED:",
            {
                "goal_id": goal_id,
                "relevance_score": relevance_score,
                "reminder_reason": reminder_reason,
            },
        )

        return ProactiveDecision(
            should_speak=True,
            reason="goal_progress_candidate",
            priority=4,
            message_hint=message_hint,
            generated_at=(
                datetime.now().isoformat()
            ),
        )

    # =====================================================
    # SNAPSHOT
    # =====================================================

    def _get_progress_snapshot(
        self,
    ) -> Dict[str, Any]:
        try:
            snapshot = (
                self.goal_progress_reasoner
                .snapshot()
            )

            if hasattr(
                snapshot,
                "to_dict",
            ):
                data = snapshot.to_dict()

            elif isinstance(
                snapshot,
                dict,
            ):
                data = snapshot

            else:
                data = {}

            if isinstance(data, dict):
                return data

        except Exception as exc:
            print(
                "GOAL_CANDIDATE_SNAPSHOT_ERROR:",
                repr(exc),
            )

        return {}

    # =====================================================
    # COOLDOWN
    # =====================================================

    def _in_cooldown(
        self,
    ) -> bool:
        if self.last_spoken_at is None:
            return False

        elapsed = (
            datetime.now()
            - self.last_spoken_at
        ).total_seconds()

        return (
            elapsed
            < self.cooldown_seconds
        )

    # =====================================================
    # HELPERS
    # =====================================================

    def _clean_list(
        self,
        values,
    ):
        if not isinstance(values, list):
            return []

        output = []

        for value in values:
            text = str(
                value or ""
            ).strip()

            if (
                text
                and text not in output
            ):
                output.append(text)

        return output

    def _safe_float(
        self,
        value: Any,
    ) -> float:
        try:
            return float(value)

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

    def _safe_int(
        self,
        value: Any,
        default: int = 0,
    ) -> int:
        try:
            return int(value)

        except (
            TypeError,
            ValueError,
        ):
            return default

    # =====================================================
    # SILENT
    # =====================================================

    def _silent(
        self,
        reason: str,
    ) -> ProactiveDecision:
        return ProactiveDecision(
            should_speak=False,
            reason=reason,
            priority=0,
            message_hint=None,
            generated_at=(
                datetime.now().isoformat()
            ),
        )