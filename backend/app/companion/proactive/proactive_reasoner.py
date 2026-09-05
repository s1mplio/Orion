from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any, Dict

import json

from app.services.llm_service import LLMService


# =========================================================
# RESULT
# =========================================================

@dataclass
class ProactiveReasoningResult:
    should_speak: bool
    reason: Optional[str]
    priority: int
    message_hint: Optional[str]
    candidate_type: Optional[str]
    generated_at: str
    error: Optional[str] = None

    def to_dict(self):
        return {
            "should_speak": self.should_speak,
            "reason": self.reason,
            "priority": self.priority,
            "message_hint": self.message_hint,
            "candidate_type": self.candidate_type,
            "generated_at": self.generated_at,
            "error": self.error,
        }


# =========================================================
# PROACTIVE REASONER V2
# =========================================================

class ProactiveReasoner:
    """
    ORION Proactive Reasoner V2.

    Stage 1:
        ProactivePolicy V1 asks:

            "Is there something potentially interesting?"

    Stage 2:
        ProactiveReasoner V2 asks:

            "Would speaking right now actually help?"

    V2 reasons over:

        1. ContextReasoner
           - current activity
           - current event
           - recent actions
           - repeated actions

        2. TemporalWorldState
           - current objects
           - object history
           - interactions
           - lifecycle changes

        3. GoalContext
           - explicit user goals
           - relevant objects
           - explicit instructions

        4. GoalProgressReasoner
           - whether a goal is currently relevant
           - relevant-object presence
           - relevant interactions
           - goal progress
           - reminder consideration evidence

    The LLM does NOT perform perception here.

    GoalProgressReasoner does NOT decide to speak.

    Exactly ONE reasoning LLM call is allowed for each
    candidate that passes deterministic filtering.
    """

    def __init__(
        self,
        context_reasoner,
        llm: Optional[LLMService] = None,
        temporal_world_state=None,
        goal_context=None,
        goal_progress_reasoner=None,
    ):

        self.context_reasoner = (
            context_reasoner
        )

        # =================================================
        # TEMPORAL WORLD STATE
        # =================================================

        if temporal_world_state is not None:

            self.temporal_world_state = (
                temporal_world_state
            )

        else:

            try:

                from app.companion.memory.shared_memory import (
                    temporal_world_state as shared_temporal_world_state,
                )

                self.temporal_world_state = (
                    shared_temporal_world_state
                )

            except Exception as exc:

                print(
                    "TEMPORAL_WORLD_STATE_IMPORT_WARNING:",
                    repr(exc),
                )

                self.temporal_world_state = None

        # =================================================
        # GOAL CONTEXT
        # =================================================

        if goal_context is not None:

            self.goal_context = (
                goal_context
            )

        else:

            try:

                from app.companion.memory.shared_memory import (
                    goal_context as shared_goal_context,
                )

                self.goal_context = (
                    shared_goal_context
                )

            except Exception as exc:

                print(
                    "GOAL_CONTEXT_IMPORT_WARNING:",
                    repr(exc),
                )

                self.goal_context = None

        # =================================================
        # GOAL PROGRESS / RELEVANCE STATE
        # =================================================

        if goal_progress_reasoner is not None:

            self.goal_progress_reasoner = (
                goal_progress_reasoner
            )

        else:

            try:

                from app.companion.memory.shared_memory import (
                    goal_progress_reasoner as shared_goal_progress_reasoner,
                )

                self.goal_progress_reasoner = (
                    shared_goal_progress_reasoner
                )

            except Exception as exc:

                print(
                    "GOAL_PROGRESS_IMPORT_WARNING:",
                    repr(exc),
                )

                self.goal_progress_reasoner = None

        # =================================================
        # LLM
        # =================================================

        self.llm = (
            llm
            if llm is not None
            else LLMService()
        )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def evaluate_candidate(
        self,
        policy_decision: Any,
    ) -> ProactiveReasoningResult:

        # =================================================
        # POLICY DECISION
        # =================================================

        decision = (
            self._decision_to_dict(
                policy_decision
            )
        )

        if not decision:

            return self._silent(
                reason="invalid_policy_decision",
                candidate_type=None,
            )

        if not decision.get(
            "should_speak",
            False,
        ):

            return self._silent(
                reason="policy_rejected",
                candidate_type=(
                    decision.get(
                        "reason"
                    )
                ),
            )

        candidate_type = (
            decision.get(
                "reason"
            )
        )

        message_hint = (
            decision.get(
                "message_hint"
            )
        )

        try:

            priority = int(
                decision.get(
                    "priority",
                    0,
                )
                or 0
            )

        except Exception:

            priority = 0

        # =================================================
        # CURRENT CONTEXT
        # =================================================

        try:

            snapshot = (
                self.context_reasoner
                .snapshot()
            )

        except Exception as exc:

            return self._silent(
                reason="context_error",
                candidate_type=(
                    candidate_type
                ),
                error=repr(exc),
            )

        context = (
            self._snapshot_to_dict(
                snapshot
            )
        )

        if not context:

            return self._silent(
                reason="missing_context",
                candidate_type=(
                    candidate_type
                ),
            )

        # =================================================
        # CONTEXT CONFIDENCE
        # =================================================

        try:

            confidence = float(
                context.get(
                    "confidence",
                    0.0,
                )
                or 0.0
            )

        except Exception:

            confidence = 0.0

        if confidence < 0.5:

            return self._silent(
                reason="low_context_confidence",
                candidate_type=(
                    candidate_type
                ),
            )

        # =================================================
        # TEMPORAL WORLD STATE
        # =================================================

        world_context = (
            self._get_temporal_world_context()
        )

        # =================================================
        # GOAL CONTEXT
        # =================================================

        goal_context = (
            self._get_goal_context()
        )

        # =================================================
        # GOAL PROGRESS
        # =================================================

        goal_progress_context = (
            self._get_goal_progress_context()
        )

        # =================================================
        # PHYSICAL MEMORY CONSISTENCY
        # =================================================

        if (
            world_context
            and
            not self._contexts_match(
                context,
                world_context,
            )
        ):

            return self._silent(
                reason="temporal_context_mismatch",
                candidate_type=(
                    candidate_type
                ),
            )

        # =================================================
        # CHEAP LOW-VALUE FILTER
        # =================================================

        low_value_reason = (
            self._obvious_low_value_candidate(
                candidate_type=(
                    candidate_type
                ),
                message_hint=(
                    message_hint
                ),
                context=(
                    context
                ),
                world_context=(
                    world_context
                ),
                goal_context=(
                    goal_context
                ),
                goal_progress_context=(
                    goal_progress_context
                ),
            )
        )

        if low_value_reason:

            return self._silent(
                reason=(
                    low_value_reason
                ),
                candidate_type=(
                    candidate_type
                ),
            )

        # =================================================
        # PROMPT
        # =================================================

        prompt = (
            self._build_prompt(
                candidate_type=(
                    candidate_type
                ),
                priority=(
                    priority
                ),
                message_hint=(
                    message_hint
                ),
                context=(
                    context
                ),
                world_context=(
                    world_context
                ),
                goal_context=(
                    goal_context
                ),
                goal_progress_context=(
                    goal_progress_context
                ),
            )
        )

        # =================================================
        # EXACTLY ONE REASONING LLM CALL
        # =================================================

        try:

            raw = (
                self.llm.generate(
                    prompt
                )
            )

        except Exception as exc:

            return self._silent(
                reason="reasoning_llm_error",
                candidate_type=(
                    candidate_type
                ),
                error=repr(exc),
            )

        # =================================================
        # PARSE
        # =================================================

        return (
            self._parse_llm_result(
                raw=(
                    raw
                ),
                candidate_type=(
                    candidate_type
                ),
                fallback_hint=(
                    message_hint
                ),
                fallback_priority=(
                    priority
                ),
            )
        )

    # =====================================================
    # TEMPORAL WORLD CONTEXT
    # =====================================================

    def _get_temporal_world_context(
        self,
    ) -> Dict[str, Any]:

        if (
            self.temporal_world_state
            is None
        ):

            return {}

        try:

            snapshot = (
                self.temporal_world_state
                .snapshot()
            )

        except Exception as exc:

            print(
                "TEMPORAL_WORLD_STATE_ERROR:",
                repr(exc),
            )

            return {}

        return (
            self._snapshot_to_dict(
                snapshot
            )
        )

    # =====================================================
    # GOAL CONTEXT
    # =====================================================

    def _get_goal_context(
        self,
    ) -> Dict[str, Any]:

        if (
            self.goal_context
            is None
        ):

            return {}

        try:

            snapshot = (
                self.goal_context
                .snapshot()
            )

        except Exception as exc:

            print(
                "GOAL_CONTEXT_ERROR:",
                repr(exc),
            )

            return {}

        return (
            self._snapshot_to_dict(
                snapshot
            )
        )

    # =====================================================
    # GOAL PROGRESS CONTEXT
    # =====================================================

    def _get_goal_progress_context(
        self,
    ) -> Dict[str, Any]:

        if (
            self.goal_progress_reasoner
            is None
        ):

            return {}

        try:

            snapshot = (
                self.goal_progress_reasoner
                .snapshot()
            )

        except Exception as exc:

            print(
                "GOAL_PROGRESS_ERROR:",
                repr(exc),
            )

            return {}

        return (
            self._snapshot_to_dict(
                snapshot
            )
        )

    # =====================================================
    # CONTEXT CONSISTENCY
    # =====================================================

    def _contexts_match(
        self,
        context,
        world_context,
    ) -> bool:
        """
        ContextReasoner and TemporalWorldState should refer
        to the same physical memory.

        Generation equality is deliberately NOT required.

        Generation can change because of inference drift
        while memory_id remains the same physical scene.
        """

        context_memory_id = (
            context.get(
                "memory_id"
            )
        )

        world_memory_id = (
            world_context.get(
                "memory_id"
            )
        )

        if (
            context_memory_id is None
            or
            world_memory_id is None
        ):

            return True

        return (
            context_memory_id
            ==
            world_memory_id
        )

    # =====================================================
    # POLICY DECISION -> DICT
    # =====================================================

    def _decision_to_dict(
        self,
        decision,
    ):

        if decision is None:

            return {}

        if isinstance(
            decision,
            dict,
        ):

            return dict(
                decision
            )

        if hasattr(
            decision,
            "to_dict",
        ):

            try:

                return (
                    decision.to_dict()
                )

            except Exception:

                return {}

        return {
            "should_speak": getattr(
                decision,
                "should_speak",
                False,
            ),

            "reason": getattr(
                decision,
                "reason",
                None,
            ),

            "priority": getattr(
                decision,
                "priority",
                0,
            ),

            "message_hint": getattr(
                decision,
                "message_hint",
                None,
            ),
        }

    # =====================================================
    # SNAPSHOT -> DICT
    # =====================================================

    def _snapshot_to_dict(
        self,
        snapshot,
    ):

        if snapshot is None:

            return {}

        if isinstance(
            snapshot,
            dict,
        ):

            return dict(
                snapshot
            )

        if hasattr(
            snapshot,
            "to_dict",
        ):

            try:

                return (
                    snapshot.to_dict()
                )

            except Exception:

                return {}

        return {}

    # =====================================================
    # LOW VALUE PREFILTER
    # =====================================================

    def _obvious_low_value_candidate(
        self,
        candidate_type,
        message_hint,
        context,
        world_context,
        goal_context,
        goal_progress_context,
    ) -> Optional[str]:

        activity = str(
            context.get(
                "current_activity"
            )
            or ""
        ).strip().lower()

        active_interactions = (
            context.get(
                "active_interactions"
            )
            or []
        )

        active_goal_count = 0

        try:

            active_goal_count = int(
                goal_context.get(
                    "active_goal_count",
                    0,
                )
                or 0
            )

        except Exception:

            active_goal_count = 0

        reminder_candidate_count = 0

        try:

            reminder_candidate_count = int(
                goal_progress_context.get(
                    "reminder_candidate_count",
                    0,
                )
                or 0
            )

        except Exception:

            reminder_candidate_count = 0

        # =================================================
        # PASSIVE ACTIVITIES
        # =================================================

        low_value_activities = {
            "looking_at_camera",
            "looking_forward",
            "sitting",
            "seated",
            "standing",
            "idle",
        }

        if (
            activity
            in low_value_activities
            and
            not active_interactions
            and
            active_goal_count == 0
            and
            reminder_candidate_count == 0
        ):

            return (
                "ordinary_passive_state"
            )

        # =================================================
        # PASSIVE OBSERVATIONS
        # =================================================

        text = " ".join(
            [
                str(
                    message_hint
                    or ""
                ),

                str(
                    context.get(
                        "current_salient_event"
                    )
                    or ""
                ),
            ]
        ).lower()

        low_value_phrases = (
            "looking at camera",
            "looking_at_camera",
            "facing forward",
            "looking forward",
        )

        if (
            any(
                phrase in text
                for phrase
                in low_value_phrases
            )
            and
            not active_interactions
            and
            active_goal_count == 0
            and
            reminder_candidate_count == 0
        ):

            return (
                "ordinary_passive_observation"
            )

        return None

    # =====================================================
    # SAFE JSON
    # =====================================================

    def _json_for_prompt(
        self,
        value,
    ) -> str:

        try:

            return json.dumps(
                value,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        except Exception:

            return str(
                value
            )

    # =====================================================
    # PROMPT
    # =====================================================

    def _build_prompt(
        self,
        candidate_type,
        priority,
        message_hint,
        context,
        world_context,
        goal_context,
        goal_progress_context,
    ):

        # =================================================
        # WORLD STATE
        # =================================================

        current_objects = (
            world_context.get(
                "current_objects",
                [],
            )
            if world_context
            else []
        )

        object_history = (
            world_context.get(
                "object_history",
                [],
            )
            if world_context
            else []
        )

        current_world_interactions = (
            world_context.get(
                "active_interactions",
                [],
            )
            if world_context
            else []
        )

        recent_world_interactions = (
            world_context.get(
                "recent_interactions",
                [],
            )
            if world_context
            else []
        )

        appeared_objects = (
            world_context.get(
                "recently_appeared_objects",
                [],
            )
            if world_context
            else []
        )

        disappeared_objects = (
            world_context.get(
                "recently_disappeared_objects",
                [],
            )
            if world_context
            else []
        )

        reappeared_objects = (
            world_context.get(
                "recently_reappeared_objects",
                [],
            )
            if world_context
            else []
        )

        # =================================================
        # GOALS
        # =================================================

        active_goals = (
            goal_context.get(
                "active_goals",
                [],
            )
            if goal_context
            else []
        )

        relevant_objects = (
            goal_context.get(
                "relevant_objects",
                [],
            )
            if goal_context
            else []
        )

        active_instructions = (
            goal_context.get(
                "active_instructions",
                [],
            )
            if goal_context
            else []
        )

        goal_confidence = (
            goal_context.get(
                "confidence"
            )
            if goal_context
            else 0.0
        )

        # =================================================
        # GOAL PROGRESS
        # =================================================

        goal_progress_states = (
            goal_progress_context.get(
                "goals",
                [],
            )
            if goal_progress_context
            else []
        )

        progressing_goal_count = (
            goal_progress_context.get(
                "progressing_goal_count",
                0,
            )
            if goal_progress_context
            else 0
        )

        reminder_candidate_count = (
            goal_progress_context.get(
                "reminder_candidate_count",
                0,
            )
            if goal_progress_context
            else 0
        )

        max_relevance_score = (
            goal_progress_context.get(
                "max_relevance_score",
                0.0,
            )
            if goal_progress_context
            else 0.0
        )

        goal_progress_confidence = (
            goal_progress_context.get(
                "confidence",
                0.0,
            )
            if goal_progress_context
            else 0.0
        )

        return f"""
You are the proactive reasoning layer of Orion,
a contextual AI companion.

Your job is to decide whether Orion speaking right now
would provide genuine value to the user.

You are NOT a scene narrator.

You are NOT performing visual perception.

You receive four kinds of evidence:

1. CURRENT CONTEXT
   What the user appears to be doing now and recently.

2. TEMPORAL WORLD STATE
   What physical objects and interactions have been
   observed over time.

3. GOAL CONTEXT
   What the user has EXPLICITLY said matters.

4. GOAL PROGRESS
   Deterministic evidence describing whether an active
   goal is currently relevant or progressing.


=========================================================
CORE PRINCIPLE
=========================================================

Prefer SILENT.

Seeing an action is not enough to justify speaking.

A reminder candidate is also NOT automatically permission
to speak.

Speak only when interrupting the user provides concrete
value.


=========================================================
GOAL PROGRESS RULES
=========================================================

Goal Progress is deterministic supporting evidence.

Possible goal states include:

pending
    Little or no current evidence connects the world to
    the goal.

relevant
    Something associated with the goal is currently
    relevant or observed.

progressing
    Current or recent evidence indicates interaction with
    something associated with the goal.

The field:

    should_consider_reminder = true

means only:

    "There is enough evidence for the proactive reasoner
     to consider whether a reminder is useful."

It does NOT mean:

    "Speak automatically."


=========================================================
IMPORTANT REMINDER TIMING RULE
=========================================================

Do not give a reminder when the user's current action
already satisfies the reminder.

Example:

Instruction:
    "Remind me not to forget my watch."

Current evidence:
    user is currently picking up or holding the watch.

Normally stay SILENT.

The user is already handling the relevant object, so
telling them not to forget it may add no value.


=========================================================
GOAL CONTEXT RULES
=========================================================

Goal Context contains explicit user-provided information.

An active goal can make an otherwise ordinary event
relevant.

However:

Do NOT infer that the user is leaving merely because
they picked up a bag.

Do NOT infer that something was forgotten merely because
it is visible or absent from one frame.

Do NOT turn every interaction with a goal-related object
into a reminder.


=========================================================
EXPLICIT INSTRUCTIONS
=========================================================

Explicit instructions are high-value evidence.

But relevance and timing still matter.

A reminder should occur when the user could benefit from
the information, not merely because the instruction
exists.

Do not repeat reminders continuously.


=========================================================
NORMALLY STAY SILENT FOR
=========================================================

- ordinary body movement
- looking at the camera
- looking around
- raising a hand
- touching the face or head
- changing posture
- ordinary object pickup
- ordinary object holding
- ordinary phone interaction
- putting an object down
- an interaction that already satisfies the reminder
- things the user obviously already knows
- weak goal relevance
- visual events with no useful consequence


=========================================================
SPEAKING MAY BE JUSTIFIED WHEN
=========================================================

- an explicit user instruction becomes timely
- goal progress indicates a meaningful reminder condition
- a relevant object undergoes a confirmed lifecycle change
  that matters to an explicit goal
- temporal evidence and goal evidence combine into useful
  information
- multiple grounded facts suggest the user could reasonably
  benefit from hearing something now


=========================================================
TEMPORAL WORLD CAUTION
=========================================================

"current_objects" means objects represented in the latest
stabilized structured scene.

"object_history" means objects observed during this
physical context.

"recent_interactions" means previously observed
interactions.

"active_interactions" means current interactions.

Lifecycle arrays are stronger evidence:

- recently_appeared_objects
- recently_disappeared_objects
- recently_reappeared_objects

An object missing from current_objects alone is NOT enough
to claim disappearance.

currently_present = false alone is NOT enough to claim:

- removed
- lost
- forgotten
- left behind


=========================================================
DO NOT INVENT
=========================================================

Do not invent:

- intentions
- emotions
- plans
- causes
- ownership
- destinations
- relationships
- urgency
- danger
- forgotten objects
- whether the user is leaving
- whether the user needs something
- future actions

unless directly supported by the supplied evidence.


=========================================================
CURRENT CONTEXT
=========================================================

Current observation:
{context.get("current_observation")}

Current activity:
{context.get("current_activity")}

Current salient event:
{context.get("current_salient_event")}

Active interactions:
{self._json_for_prompt(
    context.get(
        "active_interactions"
    )
    or []
)}

Recent actions:
{self._json_for_prompt(
    context.get(
        "recent_actions"
    )
    or []
)}

Repeated actions:
{self._json_for_prompt(
    context.get(
        "repeated_actions"
    )
    or []
)}

Recent event count:
{context.get("recent_event_count")}

Context age seconds:
{context.get("context_age_seconds")}

Context confidence:
{context.get("confidence")}


=========================================================
TEMPORAL WORLD STATE
=========================================================

Environment:
{
    world_context.get(
        "environment"
    )
    if world_context
    else None
}

Current objects:
{self._json_for_prompt(
    current_objects
)}

Object history:
{self._json_for_prompt(
    object_history
)}

Current world interactions:
{self._json_for_prompt(
    current_world_interactions
)}

Recent world interactions:
{self._json_for_prompt(
    recent_world_interactions
)}

Recently appeared objects:
{self._json_for_prompt(
    appeared_objects
)}

Recently disappeared objects:
{self._json_for_prompt(
    disappeared_objects
)}

Recently reappeared objects:
{self._json_for_prompt(
    reappeared_objects
)}

Observed scene count:
{
    world_context.get(
        "observed_scene_count"
    )
    if world_context
    else 0
}

Temporal world confidence:
{
    world_context.get(
        "confidence"
    )
    if world_context
    else 0.0
}


=========================================================
GOAL & RELEVANCE CONTEXT
=========================================================

Active goals:
{self._json_for_prompt(
    active_goals
)}

Relevant objects:
{self._json_for_prompt(
    relevant_objects
)}

Active explicit instructions:
{self._json_for_prompt(
    active_instructions
)}

Goal context confidence:
{goal_confidence}


=========================================================
GOAL PROGRESS / RELEVANCE STATE
=========================================================

Goal progress states:
{self._json_for_prompt(
    goal_progress_states
)}

Progressing goal count:
{progressing_goal_count}

Reminder candidate count:
{reminder_candidate_count}

Maximum goal relevance score:
{max_relevance_score}

Goal progress confidence:
{goal_progress_confidence}


=========================================================
POLICY CANDIDATE
=========================================================

Candidate type:
{candidate_type}

Candidate priority:
{priority}

Candidate message hint:
{message_hint}


=========================================================
DECISION
=========================================================

Return EXACTLY one of:

SILENT|short_reason

or

SPEAK|short_reason|message_hint


=========================================================
OUTPUT RULES
=========================================================

- Prefer SILENT when speaking adds little value.

- GoalProgress should_consider_reminder=true does NOT
  automatically mean SPEAK.

- If the user is already interacting with the object
  mentioned by the reminder, normally choose SILENT.

- Choose SPEAK only when there is a concrete benefit.

- An active goal alone does NOT justify speaking.

- A visual event alone does NOT justify speaking.

- Explicit instructions should be respected.

- Use current context + temporal evidence + goal context
  + goal progress together.

- message_hint must contain only supported facts.

- message_hint is an internal instruction for the later
  message-generation component.

- Do not make message_hint conversational.

- Do not output Markdown.

- Do not output JSON.

- Do not output explanations.

- If uncertain, choose SILENT.
""".strip()

    # =====================================================
    # PARSE LLM RESULT
    # =====================================================

    def _parse_llm_result(
        self,
        raw,
        candidate_type,
        fallback_hint,
        fallback_priority,
    ) -> ProactiveReasoningResult:

        if raw is None:

            return self._silent(
                reason="empty_reasoning_response",
                candidate_type=(
                    candidate_type
                ),
            )

        text = str(
            raw
        ).strip()

        if not text:

            return self._silent(
                reason="empty_reasoning_response",
                candidate_type=(
                    candidate_type
                ),
            )

        text = (
            text.replace(
                "```text",
                "",
            )
            .replace(
                "```plaintext",
                "",
            )
            .replace(
                "```",
                "",
            )
            .strip()
        )

        lines = [
            line.strip()
            for line
            in text.splitlines()
            if line.strip()
        ]

        if not lines:

            return self._silent(
                reason="malformed_reasoning_response",
                candidate_type=(
                    candidate_type
                ),
            )

        text = (
            lines[0]
        )

        parts = [
            part.strip()
            for part
            in text.split(
                "|",
                2,
            )
        ]

        if not parts:

            return self._silent(
                reason="malformed_reasoning_response",
                candidate_type=(
                    candidate_type
                ),
            )

        command = (
            parts[0]
            .strip()
            .upper()
        )

        # =================================================
        # SILENT
        # =================================================

        if command == "SILENT":

            reason = (
                parts[1]
                if (
                    len(parts) >= 2
                    and
                    parts[1]
                )
                else
                "reasoner_rejected_candidate"
            )

            return self._silent(
                reason=(
                    reason
                ),
                candidate_type=(
                    candidate_type
                ),
            )

        # =================================================
        # SPEAK
        # =================================================

        if command == "SPEAK":

            if len(parts) < 3:

                return self._silent(
                    reason="malformed_speak_response",
                    candidate_type=(
                        candidate_type
                    ),
                )

            reason = (
                parts[1].strip()
                or
                "useful_context"
            )

            message_hint = (
                parts[2].strip()
            )

            if not message_hint:

                message_hint = str(
                    fallback_hint
                    or ""
                ).strip()

            if not message_hint:

                return self._silent(
                    reason="missing_message_hint",
                    candidate_type=(
                        candidate_type
                    ),
                )

            try:

                output_priority = max(
                    int(
                        fallback_priority
                        or 0
                    ),
                    1,
                )

            except Exception:

                output_priority = 1

            return ProactiveReasoningResult(
                should_speak=True,

                reason=(
                    reason
                ),

                priority=(
                    output_priority
                ),

                message_hint=(
                    message_hint
                ),

                candidate_type=(
                    candidate_type
                ),

                generated_at=(
                    datetime.now()
                    .isoformat()
                ),
            )

        # =================================================
        # CONSERVATIVE FALLBACK
        # =================================================

        return self._silent(
            reason="unrecognized_reasoning_response",
            candidate_type=(
                candidate_type
            ),
        )

    # =====================================================
    # SILENT RESULT
    # =====================================================

    def _silent(
        self,
        reason,
        candidate_type,
        error=None,
    ) -> ProactiveReasoningResult:

        return ProactiveReasoningResult(
            should_speak=False,

            reason=(
                reason
            ),

            priority=0,

            message_hint=None,

            candidate_type=(
                candidate_type
            ),

            generated_at=(
                datetime.now()
                .isoformat()
            ),

            error=(
                error
            ),
        )