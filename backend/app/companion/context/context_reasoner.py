from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ContextSnapshot:
    """
    Deterministic summary of what Orion currently understands.

    This is NOT another memory store.

    It is derived from:
        - current working-memory scene
        - recent semantic events
    """

    generated_at: str

    memory_id: Optional[int]
    generation: Optional[int]

    current_observation: Optional[str]

    current_activity: Optional[str]
    current_salient_event: Optional[str]

    active_interactions: List[str] = field(
        default_factory=list
    )

    recent_actions: List[str] = field(
        default_factory=list
    )

    repeated_actions: List[str] = field(
        default_factory=list
    )

    recent_event_count: int = 0

    context_age_seconds: Optional[float] = None

    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "memory_id": self.memory_id,
            "generation": self.generation,
            "current_observation": self.current_observation,
            "current_activity": self.current_activity,
            "current_salient_event": self.current_salient_event,
            "active_interactions": self.active_interactions,
            "recent_actions": self.recent_actions,
            "repeated_actions": self.repeated_actions,
            "recent_event_count": self.recent_event_count,
            "context_age_seconds": self.context_age_seconds,
            "confidence": self.confidence,
        }


class ContextReasoner:
    """
    ORION Context Reasoner V1.

    Important design rule:

        ContextReasoner does NOT call the VLM.
        ContextReasoner does NOT call another LLM.

    It reasons over already-created structured events.

    This keeps context reasoning:
        - cheap
        - deterministic
        - fast
        - testable
    """

    def __init__(
        self,
        working_memory,
        recent_event_limit: int = 20,
    ):
        self.working_memory = working_memory
        self.recent_event_limit = recent_event_limit

    # =====================================================
    # PUBLIC API
    # =====================================================

    def snapshot(self) -> ContextSnapshot:

        current_scene = (
            self.working_memory.get_current_scene()
        )

        recent_events = (
            self.working_memory.recent(
                limit=self.recent_event_limit
            )
        )

        if not current_scene:
            return self._empty_snapshot()

        memory_id = current_scene.get(
            "memory_id"
        )

        generation = current_scene.get(
            "generation"
        )

        observation = current_scene.get(
            "observation"
        )

        # Only reason over events belonging to the
        # current physical context.
        context_events = self._events_for_context(
            events=recent_events,
            memory_id=memory_id,
        )

        semantic_events = [
            event
            for event in context_events
            if event.get("event_type")
            == "SEMANTIC_EVENT"
        ]

        (
            current_activity,
            salient_event,
            active_interactions,
        ) = self._current_structured_state(
            semantic_events
        )

        recent_actions = (
            self._recent_actions(
                semantic_events
            )
        )

        repeated_actions = (
            self._repeated_actions(
                semantic_events
            )
        )

        context_age = (
            self._context_age_seconds(
                context_events
            )
        )

        confidence = self._confidence(
            current_scene=current_scene,
            semantic_events=semantic_events,
            current_activity=current_activity,
        )

        return ContextSnapshot(
            generated_at=(
                datetime.now().isoformat()
            ),

            memory_id=memory_id,

            generation=generation,

            current_observation=observation,

            current_activity=current_activity,

            current_salient_event=salient_event,

            active_interactions=active_interactions,

            recent_actions=recent_actions,

            repeated_actions=repeated_actions,

            recent_event_count=len(
                semantic_events
            ),

            context_age_seconds=context_age,

            confidence=confidence,
        )

    # =====================================================
    # EMPTY STATE
    # =====================================================

    def _empty_snapshot(
        self,
    ) -> ContextSnapshot:

        return ContextSnapshot(
            generated_at=(
                datetime.now().isoformat()
            ),

            memory_id=None,
            generation=None,

            current_observation=None,

            current_activity=None,

            current_salient_event=None,

            active_interactions=[],

            recent_actions=[],

            repeated_actions=[],

            recent_event_count=0,

            context_age_seconds=None,

            confidence=0.0,
        )

    # =====================================================
    # CURRENT CONTEXT EVENTS
    # =====================================================

    def _events_for_context(
        self,
        events,
        memory_id,
    ):

        if memory_id is None:
            return []

        filtered = []

        for event in events:

            if (
                event.get("memory_id")
                == memory_id
            ):
                filtered.append(
                    event
                )

        return filtered

    # =====================================================
    # STRUCTURED SCENE
    # =====================================================

    def _get_structured_scene(
        self,
        event,
    ):

        metadata = (
            event.get("metadata")
            or {}
        )

        structured_scene = (
            metadata.get(
                "structured_scene"
            )
        )

        if not isinstance(
            structured_scene,
            dict,
        ):
            return None

        return structured_scene

    # =====================================================
    # CURRENT STRUCTURED STATE
    # =====================================================

    def _current_structured_state(
        self,
        semantic_events,
    ):

        if not semantic_events:

            return (
                None,
                None,
                [],
            )

        # WorkingMemory events are chronological,
        # so newest event is last.
        latest = semantic_events[-1]

        scene = (
            self._get_structured_scene(
                latest
            )
        )

        if not scene:

            return (
                None,
                None,
                [],
            )

        salient_event = scene.get(
            "salient_event"
        )

        people = (
            scene.get("people")
            or []
        )

        if not people:

            return (
                None,
                salient_event,
                [],
            )

        person = people[0]

        activity = (
            person.get("activity")
            or {}
        )

        activity_type = (
            activity.get("type")
        )

        active_interactions = (
            self._extract_interactions(
                person
            )
        )

        return (
            activity_type,
            salient_event,
            active_interactions,
        )

    # =====================================================
    # INTERACTIONS
    # =====================================================

    def _extract_interactions(
        self,
        person,
    ) -> List[str]:

        pose = (
            person.get("pose")
            or {}
        )

        interactions = []

        for hand_name in (
            "left_hand",
            "right_hand",
        ):

            hand = pose.get(
                hand_name
            )

            if not isinstance(
                hand,
                dict,
            ):
                continue

            relation = hand.get(
                "relation"
            )

            target = hand.get(
                "target"
            )

            if not relation:
                continue

            # Ignore states that do not describe
            # an interaction with something.
            if relation in {
                "free",
                "unknown",
            }:
                continue

            hand_label = (
                "left"
                if hand_name
                == "left_hand"
                else "right"
            )

            if target:

                interaction = (
                    f"{hand_label} hand "
                    f"{relation} {target}"
                )

            else:

                interaction = (
                    f"{hand_label} hand "
                    f"{relation}"
                )

            interactions.append(
                interaction
            )

        return interactions

    # =====================================================
    # ACTION NAME
    # =====================================================

    def _action_from_event(
        self,
        event,
    ) -> Optional[str]:

        scene = (
            self._get_structured_scene(
                event
            )
        )

        if not scene:
            return None

        salient = scene.get(
            "salient_event"
        )

        if salient:
            return str(
                salient
            ).strip()

        people = (
            scene.get("people")
            or []
        )

        if not people:
            return None

        activity = (
            people[0].get(
                "activity"
            )
            or {}
        )

        description = (
            activity.get(
                "description"
            )
        )

        if description:
            return str(
                description
            ).strip()

        activity_type = (
            activity.get("type")
        )

        if activity_type:
            return str(
                activity_type
            ).strip()

        return None

    # =====================================================
    # RECENT ACTIONS
    # =====================================================

    def _recent_actions(
        self,
        semantic_events,
    ) -> List[str]:

        actions = []

        for event in semantic_events:

            action = (
                self._action_from_event(
                    event
                )
            )

            if not action:
                continue

            # Avoid consecutive duplicate descriptions.
            if (
                actions
                and
                actions[-1].lower()
                == action.lower()
            ):
                continue

            actions.append(
                action
            )

        # We don't need the whole history inside
        # every ContextSnapshot.
        return actions[-8:]

    # =====================================================
    # REPEATED ACTIONS
    # =====================================================

    def _canonical_action(
        self,
        event,
    ) -> Optional[str]:

        """
        Create a lightweight structural action key.

        This deliberately does NOT contain a giant
        vocabulary or normalization dictionary.

        Example:

            holding_scissors
            holding_object + target=scissors

        can both become:

            holding:scissors
        """

        scene = (
            self._get_structured_scene(
                event
            )
        )

        if not scene:
            return None

        people = (
            scene.get("people")
            or []
        )

        if not people:
            return None

        person = people[0]

        pose = (
            person.get("pose")
            or {}
        )

        # Prefer structural hand interaction.
        for hand_name in (
            "left_hand",
            "right_hand",
        ):

            hand = pose.get(
                hand_name
            )

            if not isinstance(
                hand,
                dict,
            ):
                continue

            relation = hand.get(
                "relation"
            )

            target = hand.get(
                "target"
            )

            if relation and target:

                return (
                    f"{str(relation).lower()}:"
                    f"{str(target).lower()}"
                )

        activity = (
            person.get("activity")
            or {}
        )

        activity_type = (
            activity.get("type")
        )

        if activity_type:

            return (
                str(activity_type)
                .strip()
                .lower()
            )

        return None

    def _repeated_actions(
        self,
        semantic_events,
    ) -> List[str]:

        keys = []

        for event in semantic_events:

            key = (
                self._canonical_action(
                    event
                )
            )

            if key:
                keys.append(
                    key
                )

        counts = Counter(
            keys
        )

        repeated = []

        for key, count in counts.items():

            if count < 2:
                continue

            repeated.append(
                f"{key} ({count} times)"
            )

        return repeated

    # =====================================================
    # CONTEXT AGE
    # =====================================================

    def _context_age_seconds(
        self,
        events,
    ) -> Optional[float]:

        if not events:
            return None

        timestamps = []

        for event in events:

            raw = event.get(
                "timestamp"
            )

            if not raw:
                continue

            try:

                timestamps.append(
                    datetime.fromisoformat(
                        raw
                    )
                )

            except (
                ValueError,
                TypeError,
            ):
                continue

        if not timestamps:
            return None

        first = min(
            timestamps
        )

        age = (
            datetime.now()
            - first
        ).total_seconds()

        return round(
            max(
                0.0,
                age,
            ),
            2,
        )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    def _confidence(
        self,
        current_scene,
        semantic_events,
        current_activity,
    ) -> float:

        """
        V1 confidence means:

        "How much structured contextual information
        do I currently have?"

        It is NOT pretending to be VLM probability.
        """

        score = 0.0

        if current_scene:
            score += 0.40

        if semantic_events:
            score += 0.20

        if current_activity:
            score += 0.20

        if len(
            semantic_events
        ) >= 2:
            score += 0.10

        if len(
            semantic_events
        ) >= 4:
            score += 0.10

        return round(
            min(
                score,
                1.0,
            ),
            2,
        )