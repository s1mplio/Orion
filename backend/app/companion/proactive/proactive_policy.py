from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional


# =========================================================
# DECISION
# =========================================================

@dataclass
class ProactiveDecision:
    """
    Result produced by Orion's proactive policy.

    Important:

    should_speak=True here means:

        "This is a candidate worth sending
         to Proactive Reasoner V2."

    It does NOT mean Orion has actually spoken yet.
    """

    should_speak: bool
    reason: Optional[str]
    priority: int

    message_hint: Optional[str]

    generated_at: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


# =========================================================
# PROACTIVE POLICY
# =========================================================

class ProactivePolicy:
    """
    ORION Proactive Policy V1.

    Purpose:

        Cheap deterministic candidate gate.

    Pipeline:

        ContextReasoner
              ↓
        ProactivePolicy V1
              ↓
        candidate?
              ↓
        ProactiveReasoner V2
              ↓
        useful?
              ↓
        actual speech approval
              ↓
        register_spoken()

    Important:

        - deterministic
        - no VLM calls
        - no LLM calls
        - intentionally conservative

    V1 reacts only to:

        1. meaningful active object interaction
        2. repeated recent actions
        3. strongly notable current event

    Cooldown semantics:

        Candidate generation does NOT start cooldown.

        Cooldown begins only after the downstream
        reasoning pipeline approves actual speech and
        calls register_spoken().
    """

    def __init__(
        self,
        context_reasoner,
        cooldown_seconds: float = 20.0,
    ):

        self.context_reasoner = (
            context_reasoner
        )

        self.cooldown_seconds = (
            cooldown_seconds
        )

        # =================================================
        # ACTUAL APPROVED SPEECH STATE
        # =================================================

        self.last_spoken_at: Optional[
            datetime
        ] = None

        self.last_reason: Optional[
            str
        ] = None

        self.last_message_hint: Optional[
            str
        ] = None

    # =====================================================
    # PUBLIC API
    # =====================================================

    def evaluate(
        self,
    ) -> ProactiveDecision:

        snapshot = (
            self.context_reasoner
            .snapshot()
        )

        data = (
            snapshot.to_dict()
            if hasattr(
                snapshot,
                "to_dict",
            )
            else snapshot
        )

        if not isinstance(
            data,
            dict,
        ):

            return self._silent(
                reason="no_context",
            )

        if not data.get(
            "current_observation"
        ):

            return self._silent(
                reason="no_current_scene",
            )

        # =================================================
        # COOLDOWN
        #
        # This now refers ONLY to actual approved speech.
        # Rejected V2 candidates do not consume cooldown.
        # =================================================

        if self._in_cooldown():

            return self._silent(
                reason="cooldown",
            )

        # =================================================
        # PRIORITY 1
        # ACTIVE OBJECT INTERACTION
        # =================================================

        interaction_decision = (
            self._evaluate_active_interaction(
                data
            )
        )

        if interaction_decision:

            return (
                interaction_decision
            )

        # =================================================
        # PRIORITY 2
        # REPEATED ACTION
        # =================================================

        repeated_decision = (
            self._evaluate_repeated_action(
                data
            )
        )

        if repeated_decision:

            return (
                repeated_decision
            )

        # =================================================
        # PRIORITY 3
        # CURRENT NOTABLE EVENT
        # =================================================

        salient_decision = (
            self._evaluate_salient_event(
                data
            )
        )

        if salient_decision:

            return (
                salient_decision
            )

        return self._silent(
            reason="nothing_proactive",
        )

    # =====================================================
    # REGISTER ACTUAL APPROVED SPEECH
    # =====================================================

    def register_spoken(
        self,
        reason: Optional[str],
        message_hint: Optional[str],
    ) -> None:

        """
        Commit cooldown only after downstream reasoning
        has approved speech.

        This method must NOT be called for V2 SILENT
        decisions.

        VisionLoop calls this after V2 returns SPEAK.
        """

        now = (
            datetime.now()
        )

        self.last_spoken_at = (
            now
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
            "PROACTIVE_COOLDOWN_REGISTERED:",
            now.isoformat(),
        )

    # =====================================================
    # ACTIVE INTERACTION
    # =====================================================

    def _evaluate_active_interaction(
        self,
        data: Dict[str, Any],
    ) -> Optional[
        ProactiveDecision
    ]:

        interactions = (
            data.get(
                "active_interactions"
            )
            or []
        )

        if not interactions:

            return None

        for interaction in interactions:

            normalized = (
                str(
                    interaction
                )
                .strip()
                .lower()
            )

            # We do NOT create a candidate simply
            # because a hand is raised/resting/etc.

            if self._is_passive_interaction(
                normalized
            ):

                continue

            target = (
                self._extract_interaction_target(
                    normalized
                )
            )

            if target:

                hint = (
                    f"The user is currently "
                    f"interacting with {target}."
                )

            else:

                hint = (
                    "The user has started "
                    "a meaningful object interaction."
                )

            return self._candidate(
                reason=(
                    "active_object_interaction"
                ),
                priority=3,
                message_hint=hint,
            )

        return None

    # =====================================================
    # REPEATED ACTION
    # =====================================================

    def _evaluate_repeated_action(
        self,
        data: Dict[str, Any],
    ) -> Optional[
        ProactiveDecision
    ]:

        repeated = (
            data.get(
                "repeated_actions"
            )
            or []
        )

        if not repeated:

            return None

        action = (
            str(
                repeated[-1]
            )
            .strip()
        )

        if not action:

            return None

        return self._candidate(
            reason=(
                "repeated_action"
            ),
            priority=2,
            message_hint=(
                "The user has repeated this "
                f"recent action: {action}."
            ),
        )

    # =====================================================
    # SALIENT EVENT
    # =====================================================

    def _evaluate_salient_event(
        self,
        data: Dict[str, Any],
    ) -> Optional[
        ProactiveDecision
    ]:

        event = (
            data.get(
                "current_salient_event"
            )
        )

        if not event:

            return None

        normalized = (
            str(
                event
            )
            .strip()
            .lower()
        )

        if not normalized:

            return None

        if self._is_low_value_event(
            normalized
        ):

            return None

        return self._candidate(
            reason=(
                "salient_event"
            ),
            priority=1,
            message_hint=(
                "A notable current event "
                f"was observed: {event}."
            ),
        )

    # =====================================================
    # FILTERS
    # =====================================================

    def _is_passive_interaction(
        self,
        interaction: str,
    ) -> bool:

        passive_terms = {
            "raised",
            "resting",
            "free",
            "unknown",
        }

        for term in passive_terms:

            if term in interaction:

                return True

        return False

    # =====================================================

    def _is_low_value_event(
        self,
        event: str,
    ) -> bool:

        low_value_terms = {
            "looking at camera",
            "looking_at_camera",
            "facing forward",
            "sitting",
            "seated",
            "standing",
            "looking forward",
        }

        for term in low_value_terms:

            if term in event:

                return True

        return False

    # =====================================================
    # INTERACTION TARGET
    # =====================================================

    def _extract_interaction_target(
        self,
        interaction: str,
    ) -> Optional[str]:

        """
        Example:

            right hand holding scissors
                         ↓
                     scissors
        """

        relations = (
            "holding",
            "touching",
            "covering",
            "pointing_at",
            "resting_on",
            "near",
        )

        for relation in relations:

            token = (
                relation
                + " "
            )

            if token not in interaction:

                continue

            target = (
                interaction
                .split(
                    token,
                    1,
                )[1]
                .strip()
            )

            if target:

                return target

        return None

    # =====================================================
    # COOLDOWN
    # =====================================================

    def _in_cooldown(
        self,
    ) -> bool:

        if (
            self.last_spoken_at
            is None
        ):

            return False

        elapsed = (
            datetime.now()
            - self.last_spoken_at
        ).total_seconds()

        return (
            elapsed
            <
            self.cooldown_seconds
        )

    # =====================================================
    # CANDIDATE
    # =====================================================

    def _candidate(
        self,
        reason: str,
        priority: int,
        message_hint: str,
    ) -> ProactiveDecision:

        """
        Create a V2 candidate.

        IMPORTANT:

        This method does NOT mutate cooldown state.

        Creating a candidate is not the same thing
        as actually speaking.
        """

        # =================================================
        # DUPLICATE SUPPRESSION
        #
        # Compare only against the last ACTUALLY APPROVED
        # speech, not against rejected V2 candidates.
        # =================================================

        if (
            self.last_reason
            == reason
            and
            self.last_message_hint
            == message_hint
        ):

            return self._silent(
                reason=(
                    "duplicate_suppressed"
                ),
            )

        now = (
            datetime.now()
        )

        return ProactiveDecision(
            should_speak=True,
            reason=reason,
            priority=priority,
            message_hint=(
                message_hint
            ),
            generated_at=(
                now.isoformat()
            ),
        )

    # =====================================================
    # BACKWARD COMPATIBILITY
    # =====================================================

    def _speak(
        self,
        reason: str,
        priority: int,
        message_hint: str,
    ) -> ProactiveDecision:

        """
        Backward-compatible alias.

        Older code may still call _speak().

        It now creates a candidate only.
        It does NOT register actual speech.
        """

        return self._candidate(
            reason=reason,
            priority=priority,
            message_hint=message_hint,
        )

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
                datetime.now()
                .isoformat()
            ),
        )