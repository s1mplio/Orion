from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any, Dict, List, Optional


@dataclass
class GoalProgressState:
    goal_id: int
    description: str

    status: str = "pending"

    relevant_objects: List[str] = field(default_factory=list)
    instruction: Optional[str] = None

    observed_relevant_objects: List[str] = field(default_factory=list)
    currently_present_objects: List[str] = field(default_factory=list)

    active_relevant_interactions: List[Dict[str, Any]] = field(
        default_factory=list
    )
    recent_relevant_interactions: List[Dict[str, Any]] = field(
        default_factory=list
    )

    disappeared_relevant_objects: List[str] = field(default_factory=list)
    reappeared_relevant_objects: List[str] = field(default_factory=list)

    evidence_count: int = 0
    relevance_score: float = 0.0

    should_consider_reminder: bool = False
    reminder_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "status": self.status,
            "relevant_objects": list(self.relevant_objects),
            "instruction": self.instruction,
            "observed_relevant_objects": list(
                self.observed_relevant_objects
            ),
            "currently_present_objects": list(
                self.currently_present_objects
            ),
            "active_relevant_interactions": list(
                self.active_relevant_interactions
            ),
            "recent_relevant_interactions": list(
                self.recent_relevant_interactions
            ),
            "disappeared_relevant_objects": list(
                self.disappeared_relevant_objects
            ),
            "reappeared_relevant_objects": list(
                self.reappeared_relevant_objects
            ),
            "evidence_count": self.evidence_count,
            "relevance_score": self.relevance_score,
            "should_consider_reminder": self.should_consider_reminder,
            "reminder_reason": self.reminder_reason,
        }


@dataclass
class GoalProgressSnapshot:
    generated_at: str

    goals: List[GoalProgressState] = field(default_factory=list)

    active_goal_count: int = 0
    progressing_goal_count: int = 0
    reminder_candidate_count: int = 0

    max_relevance_score: float = 0.0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "goals": [
                goal.to_dict()
                for goal in self.goals
            ],
            "active_goal_count": self.active_goal_count,
            "progressing_goal_count": self.progressing_goal_count,
            "reminder_candidate_count": self.reminder_candidate_count,
            "max_relevance_score": self.max_relevance_score,
            "confidence": self.confidence,
        }


class GoalProgressReasoner:
    """
    Deterministic goal-progress and relevance layer.

    Combines:
        ContextReasoner
        TemporalWorldState
        GoalContext

    This component does NOT:
        - call an LLM
        - call a VLM
        - generate speech
        - infer hidden intentions
        - infer that the user is leaving
        - infer that something is forgotten

    It only organizes evidence for the proactive reasoning layer.
    """

    def __init__(
        self,
        context_reasoner,
        temporal_world_state,
        goal_context,
    ):
        self.context_reasoner = context_reasoner
        self.temporal_world_state = temporal_world_state
        self.goal_context = goal_context

    def snapshot(self) -> GoalProgressSnapshot:
        generated_at = datetime.now().isoformat()

        context = self._safe_snapshot(
            self.context_reasoner
        )

        world = self._safe_snapshot(
            self.temporal_world_state
        )

        goal_context = self._safe_snapshot(
            self.goal_context
        )

        active_goals = (
            goal_context.get("active_goals")
            or []
        )

        goal_states: List[GoalProgressState] = []

        for goal in active_goals:
            if not isinstance(goal, dict):
                continue

            goal_state = self._evaluate_goal(
                goal=goal,
                context=context,
                world=world,
            )

            goal_states.append(goal_state)

        progressing_count = sum(
            1
            for state in goal_states
            if state.status in {
                "relevant",
                "progressing",
            }
        )

        reminder_count = sum(
            1
            for state in goal_states
            if state.should_consider_reminder
        )

        max_relevance = max(
            (
                state.relevance_score
                for state in goal_states
            ),
            default=0.0,
        )

        confidence = self._confidence(
            active_goals=active_goals,
            context=context,
            world=world,
        )

        return GoalProgressSnapshot(
            generated_at=generated_at,
            goals=goal_states,
            active_goal_count=len(goal_states),
            progressing_goal_count=progressing_count,
            reminder_candidate_count=reminder_count,
            max_relevance_score=max_relevance,
            confidence=confidence,
        )

    def _evaluate_goal(
        self,
        goal: Dict[str, Any],
        context: Dict[str, Any],
        world: Dict[str, Any],
    ) -> GoalProgressState:
        goal_id = self._safe_int(
            goal.get("id"),
            default=-1,
        )

        description = str(
            goal.get("description") or ""
        ).strip()

        instruction = goal.get("instruction")

        if instruction is not None:
            instruction = (
                str(instruction).strip()
                or None
            )

        relevant_objects = self._clean_labels(
            goal.get("relevant_objects")
            or []
        )

        current_objects = self._current_world_objects(
            world
        )

        object_history = self._object_history_entries(
            world
        )

        active_interactions = (
            world.get("active_interactions")
            or []
        )

        recent_interactions = (
            world.get("recent_interactions")
            or []
        )

        disappeared_objects = self._clean_labels(
            world.get(
                "recently_disappeared_objects"
            )
            or []
        )

        reappeared_objects = self._clean_labels(
            world.get(
                "recently_reappeared_objects"
            )
            or []
        )

        observed_relevant_objects: List[str] = []
        currently_present_objects: List[str] = []

        for label in relevant_objects:
            histories = self._histories_for_label(
                object_history,
                label,
            )

            if histories:
                observed_relevant_objects.append(
                    label
                )

            if self._label_in_current_objects(
                label,
                current_objects,
            ):
                currently_present_objects.append(
                    label
                )

        relevant_active_interactions = (
            self._filter_interactions_for_objects(
                active_interactions,
                relevant_objects,
            )
        )

        relevant_recent_interactions = (
            self._filter_interactions_for_objects(
                recent_interactions,
                relevant_objects,
            )
        )

        relevant_disappeared = self._intersection(
            relevant_objects,
            disappeared_objects,
        )

        relevant_reappeared = self._intersection(
            relevant_objects,
            reappeared_objects,
        )

        # Current world state is more authoritative than
        # older lifecycle events in the recent memory window.
        relevant_disappeared = [
            label
            for label in relevant_disappeared
            if not self._contains_label(
                currently_present_objects,
                label,
            )
        ]

        # Also check object-history presence across equivalent labels.
        # Example:
        #
        # goal = "watch"
        # old lifecycle = "watch disappeared"
        # current object = "smartwatch", currently_present=True
        #
        # The physical object is present, so disappearance must not win.
        for label in relevant_objects:
            histories = self._histories_for_label(
                object_history,
                label,
            )

            equivalent_currently_present = any(
                history.get("currently_present") is True
                for history in histories
                if isinstance(history, dict)
            )

            if equivalent_currently_present:
                relevant_disappeared = [
                    disappeared
                    for disappeared in relevant_disappeared
                    if not self._labels_match(
                        disappeared,
                        label,
                    )
                ]

        evidence_count = 0
        relevance_score = 0.0

        if observed_relevant_objects:
            evidence_count += 1
            relevance_score += 0.20

        if currently_present_objects:
            evidence_count += 1
            relevance_score += 0.20

        if relevant_recent_interactions:
            evidence_count += 1
            relevance_score += 0.20

        if relevant_active_interactions:
            evidence_count += 1
            relevance_score += 0.20

        if relevant_disappeared:
            evidence_count += 1
            relevance_score += 0.30

        if relevant_reappeared:
            evidence_count += 1
            relevance_score += 0.10

        if instruction:
            relevance_score += 0.10

        relevance_score = min(
            round(relevance_score, 3),
            1.0,
        )

        status = self._derive_status(
            relevant_objects=relevant_objects,
            observed_relevant_objects=(
                observed_relevant_objects
            ),
            currently_present_objects=(
                currently_present_objects
            ),
            active_interactions=(
                relevant_active_interactions
            ),
            recent_interactions=(
                relevant_recent_interactions
            ),
            disappeared_objects=(
                relevant_disappeared
            ),
            context=context,
        )

        (
            should_consider_reminder,
            reminder_reason,
        ) = self._derive_reminder_candidate(
            instruction=instruction,
            relevant_objects=relevant_objects,
            observed_relevant_objects=(
                observed_relevant_objects
            ),
            currently_present_objects=(
                currently_present_objects
            ),
            active_interactions=(
                relevant_active_interactions
            ),
            recent_interactions=(
                relevant_recent_interactions
            ),
            disappeared_objects=(
                relevant_disappeared
            ),
            status=status,
        )

        return GoalProgressState(
            goal_id=goal_id,
            description=description,
            status=status,
            relevant_objects=relevant_objects,
            instruction=instruction,
            observed_relevant_objects=(
                observed_relevant_objects
            ),
            currently_present_objects=(
                currently_present_objects
            ),
            active_relevant_interactions=(
                relevant_active_interactions
            ),
            recent_relevant_interactions=(
                relevant_recent_interactions
            ),
            disappeared_relevant_objects=(
                relevant_disappeared
            ),
            reappeared_relevant_objects=(
                relevant_reappeared
            ),
            evidence_count=evidence_count,
            relevance_score=relevance_score,
            should_consider_reminder=(
                should_consider_reminder
            ),
            reminder_reason=reminder_reason,
        )

    def _derive_status(
        self,
        relevant_objects: List[str],
        observed_relevant_objects: List[str],
        currently_present_objects: List[str],
        active_interactions: List[Dict[str, Any]],
        recent_interactions: List[Dict[str, Any]],
        disappeared_objects: List[str],
        context: Dict[str, Any],
    ) -> str:
        if disappeared_objects:
            return "relevant"

        if active_interactions:
            return "progressing"

        if recent_interactions:
            return "progressing"

        if (
            observed_relevant_objects
            or currently_present_objects
        ):
            return "relevant"

        if self._has_meaningful_current_context(
            context
        ):
            return "pending"

        if relevant_objects:
            return "pending"

        return "pending"

    def _derive_reminder_candidate(
        self,
        instruction: Optional[str],
        relevant_objects: List[str],
        observed_relevant_objects: List[str],
        currently_present_objects: List[str],
        active_interactions: List[Dict[str, Any]],
        recent_interactions: List[Dict[str, Any]],
        disappeared_objects: List[str],
        status: str,
    ):
        if not instruction:
            return False, None

        if not relevant_objects:
            return False, None

        if disappeared_objects:
            objects_text = ", ".join(
                disappeared_objects
            )

            return (
                True,
                (
                    "relevant object lifecycle changed: "
                    f"{objects_text}"
                ),
            )

        if active_interactions:
            objects_text = ", ".join(
                self._interaction_targets(
                    active_interactions
                )
            )

            return (
                True,
                (
                    "user is actively interacting "
                    "with relevant object: "
                    f"{objects_text}"
                ),
            )

        if recent_interactions:
            objects_text = ", ".join(
                self._interaction_targets(
                    recent_interactions
                )
            )

            return (
                True,
                (
                    "recent interaction with "
                    "relevant object: "
                    f"{objects_text}"
                ),
            )

        if (
            status == "relevant"
            and observed_relevant_objects
            and currently_present_objects
        ):
            return (
                False,
                (
                    "relevant object is currently "
                    "observed but no stronger reminder "
                    "condition exists"
                ),
            )

        return False, None

    def _current_world_objects(
        self,
        world: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raw = (
            world.get("current_objects")
            or []
        )

        if isinstance(raw, dict):
            result = []

            for label, value in raw.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault(
                        "label",
                        label,
                    )
                    result.append(item)

                else:
                    result.append(
                        {
                            "label": label,
                            "value": value,
                        }
                    )

            return result

        if isinstance(raw, list):
            return [
                item
                for item in raw
                if isinstance(item, dict)
            ]

        return []

    def _object_history_entries(
        self,
        world: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        raw = (
            world.get("object_history")
            or []
        )

        if isinstance(raw, list):
            return [
                item
                for item in raw
                if isinstance(item, dict)
            ]

        if isinstance(raw, dict):
            result = []

            for label, value in raw.items():
                if isinstance(value, dict):
                    item = dict(value)
                    item.setdefault(
                        "label",
                        label,
                    )
                    result.append(item)

            return result

        return []

    def _histories_for_label(
        self,
        history: List[Dict[str, Any]],
        label: str,
    ) -> List[Dict[str, Any]]:
        matches = []

        for item in history:
            if not isinstance(item, dict):
                continue

            item_label = item.get("label")

            if not item_label:
                continue

            if self._labels_match(
                label,
                item_label,
            ):
                matches.append(item)

        return matches

    def _history_for_label(
        self,
        history: List[Dict[str, Any]],
        label: str,
    ) -> Optional[Dict[str, Any]]:
        matches = self._histories_for_label(
            history,
            label,
        )

        if not matches:
            return None

        # Prefer a currently-present equivalent label.
        for item in matches:
            if item.get("currently_present") is True:
                return item

        return matches[0]

    def _label_in_current_objects(
        self,
        label: str,
        current_objects: List[Dict[str, Any]],
    ) -> bool:
        for item in current_objects:
            object_label = item.get("label")

            if not object_label:
                continue

            if self._labels_match(
                label,
                object_label,
            ):
                return True

        return False

    def _filter_interactions_for_objects(
        self,
        interactions,
        relevant_objects: List[str],
    ) -> List[Dict[str, Any]]:
        if not isinstance(
            interactions,
            list,
        ):
            return []

        output = []

        for interaction in interactions:
            if not isinstance(
                interaction,
                dict,
            ):
                continue

            target = interaction.get(
                "target"
            )

            if not target:
                continue

            if any(
                self._labels_match(
                    target,
                    relevant_object,
                )
                for relevant_object in relevant_objects
            ):
                output.append(
                    dict(interaction)
                )

        return output

    def _interaction_targets(
        self,
        interactions: List[Dict[str, Any]],
    ) -> List[str]:
        output = []

        for interaction in interactions:
            target = interaction.get(
                "target"
            )

            if not target:
                continue

            target = str(
                target
            ).strip()

            if (
                target
                and target not in output
            ):
                output.append(target)

        return output

    def _intersection(
        self,
        first: List[str],
        second: List[str],
    ) -> List[str]:
        output = []

        for first_value in first:
            if any(
                self._labels_match(
                    first_value,
                    second_value,
                )
                for second_value in second
            ):
                output.append(
                    first_value
                )

        return output

    def _contains_label(
        self,
        labels: List[str],
        wanted: str,
    ) -> bool:
        return any(
            self._labels_match(
                label,
                wanted,
            )
            for label in labels
        )

    def _labels_match(
        self,
        first: Any,
        second: Any,
    ) -> bool:
        """
        Conservative semantic-equivalence helper for object labels.

        This is intentionally NOT a large alias dictionary.

        Matching order:

        1. Exact normalized equality.
        2. Compact equality after punctuation/spacing removal.
        3. Conservative compound-word containment.

        Examples:
            watch <-> smartwatch
            watch <-> wristwatch
            phone <-> smartphone

        We deliberately avoid broad fuzzy matching because:
            book should not automatically equal notebook
            glass should not automatically equal glasses
            table should not equal tablet
        """

        first_normalized = self._normalise_label(
            first
        )

        second_normalized = self._normalise_label(
            second
        )

        if (
            not first_normalized
            or not second_normalized
        ):
            return False

        if first_normalized == second_normalized:
            return True

        first_compact = self._compact_label(
            first_normalized
        )

        second_compact = self._compact_label(
            second_normalized
        )

        if (
            not first_compact
            or not second_compact
        ):
            return False

        if first_compact == second_compact:
            return True

        shorter = (
            first_compact
            if len(first_compact) <= len(second_compact)
            else second_compact
        )

        longer = (
            second_compact
            if shorter == first_compact
            else first_compact
        )

        # Avoid matching very short generic substrings.
        #
        # Example:
        # "pen" should not accidentally become a match
        # for an unrelated longer word simply because
        # those letters occur inside it.
        if len(shorter) < 4:
            return False

        if shorter not in longer:
            return False

        # Compound matching should remain conservative.
        #
        # We accept when the shorter object term occurs
        # at the beginning or end of the longer label.
        #
        # watch -> smartwatch
        # watch -> wristwatch
        # phone -> smartphone
        #
        # But this avoids arbitrary middle-substring matches.
        if (
            longer.startswith(shorter)
            or longer.endswith(shorter)
        ):
            return True

        return False

    def _compact_label(
        self,
        value: Any,
    ) -> str:
        normalized = self._normalise_label(
            value
        )

        return re.sub(
            r"[^a-z0-9]+",
            "",
            normalized,
        )

    def _clean_labels(
        self,
        values,
    ) -> List[str]:
        if not isinstance(values, list):
            return []

        output = []
        seen = set()

        for value in values:
            if value is None:
                continue

            text = str(value).strip()

            if not text:
                continue

            key = self._normalise_label(
                text
            )

            if key in seen:
                continue

            seen.add(key)
            output.append(text)

        return output

    def _normalise_label(
        self,
        value: Any,
    ) -> str:
        return " ".join(
            str(
                value or ""
            )
            .strip()
            .lower()
            .split()
        )

    def _has_meaningful_current_context(
        self,
        context: Dict[str, Any],
    ) -> bool:
        if context.get(
            "current_activity"
        ):
            return True

        if context.get(
            "current_salient_event"
        ):
            return True

        if context.get(
            "active_interactions"
        ):
            return True

        return False

    def _safe_snapshot(
        self,
        provider,
    ) -> Dict[str, Any]:
        try:
            snapshot = provider.snapshot()

            if hasattr(
                snapshot,
                "to_dict",
            ):
                result = snapshot.to_dict()

            elif isinstance(
                snapshot,
                dict,
            ):
                result = snapshot

            else:
                result = {}

            if isinstance(
                result,
                dict,
            ):
                return result

        except Exception as exc:
            print(
                "GOAL_PROGRESS_SNAPSHOT_ERROR:",
                repr(exc),
            )

        return {}

    def _confidence(
        self,
        active_goals,
        context: Dict[str, Any],
        world: Dict[str, Any],
    ) -> float:
        if not active_goals:
            return 0.0

        confidence = 0.40

        context_confidence = (
            self._safe_float(
                context.get("confidence")
            )
        )

        world_confidence = (
            self._safe_float(
                world.get("confidence")
            )
        )

        if context_confidence >= 0.5:
            confidence += 0.25

        if world_confidence >= 0.5:
            confidence += 0.25

        if world.get("current_objects"):
            confidence += 0.10

        return min(
            round(confidence, 3),
            1.0,
        )

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