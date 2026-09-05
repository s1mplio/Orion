from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# =========================================================
# OBJECT WORLD STATE
# =========================================================

@dataclass
class ObjectWorldState:
    """
    Temporal state for one real observed scene object.

    Example:

        laptop
            currently_present = True
            current_position = "desk"
            first_seen = ...
            last_seen = ...
            last_interacted = ...
            last_interaction = "touching"

    Important:

    Objects are created only from StructuredScene.objects.

    An interaction target such as:

        chin
        face
        hand

    does NOT automatically become a world object.
    """

    label: str

    currently_present: bool = False

    current_position: Optional[str] = None
    current_state: Optional[str] = None

    first_seen: Optional[str] = None
    last_seen: Optional[str] = None

    last_interacted: Optional[str] = None
    last_interaction: Optional[str] = None

    seen_count: int = 0

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "label": self.label,

            "currently_present": (
                self.currently_present
            ),

            "current_position": (
                self.current_position
            ),

            "current_state": (
                self.current_state
            ),

            "first_seen": (
                self.first_seen
            ),

            "last_seen": (
                self.last_seen
            ),

            "last_interacted": (
                self.last_interacted
            ),

            "last_interaction": (
                self.last_interaction
            ),

            "seen_count": (
                self.seen_count
            ),
        }


# =========================================================
# WORLD INTERACTION
# =========================================================

@dataclass
class WorldInteraction:
    """
    One structured interaction observed between
    a person's hand and a target.

    Example:

        right hand holding smartphone

    Important:

    The interaction target does not have to be a
    tracked environmental object.

    Example:

        touching chin

    is still valid interaction history even though
    chin is not placed into object_history.
    """

    timestamp: Optional[str]

    hand: Optional[str]
    relation: Optional[str]
    target: Optional[str]

    activity: Optional[str]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "timestamp": (
                self.timestamp
            ),

            "hand": (
                self.hand
            ),

            "relation": (
                self.relation
            ),

            "target": (
                self.target
            ),

            "activity": (
                self.activity
            ),
        }


# =========================================================
# TEMPORAL WORLD SNAPSHOT
# =========================================================

@dataclass
class TemporalWorldSnapshot:
    """
    Deterministic short-term representation
    of Orion's physical world context.

    It describes:

        - what objects exist now
        - which objects were seen recently
        - when objects were last seen
        - current interactions
        - recent interactions
        - object lifecycle changes
    """

    generated_at: str

    memory_id: Optional[int]
    generation: Optional[int]

    environment: Optional[str]

    current_objects: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    object_history: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    active_interactions: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    recent_interactions: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    recently_appeared_objects: List[
        str
    ] = field(
        default_factory=list
    )

    recently_disappeared_objects: List[
        str
    ] = field(
        default_factory=list
    )

    recently_reappeared_objects: List[
        str
    ] = field(
        default_factory=list
    )

    observed_scene_count: int = 0

    confidence: float = 0.0

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "generated_at": (
                self.generated_at
            ),

            "memory_id": (
                self.memory_id
            ),

            "generation": (
                self.generation
            ),

            "environment": (
                self.environment
            ),

            "current_objects": (
                self.current_objects
            ),

            "object_history": (
                self.object_history
            ),

            "active_interactions": (
                self.active_interactions
            ),

            "recent_interactions": (
                self.recent_interactions
            ),

            "recently_appeared_objects": (
                self.recently_appeared_objects
            ),

            "recently_disappeared_objects": (
                self.recently_disappeared_objects
            ),

            "recently_reappeared_objects": (
                self.recently_reappeared_objects
            ),

            "observed_scene_count": (
                self.observed_scene_count
            ),

            "confidence": (
                self.confidence
            ),
        }


# =========================================================
# TEMPORAL WORLD STATE
# =========================================================

class TemporalWorldState:
    """
    ORION Temporal World State V1.

    This component builds a deterministic model
    of how the currently observed physical world
    evolves over time.

    Sources:

        WorkingMemory.current_scene
        recent SEMANTIC_EVENT events
        structured scenes
        SceneIntelligence lifecycle metadata

    It does NOT:

        - call the VLM
        - call an LLM
        - infer intentions
        - infer ownership
        - guess future actions
        - create giant object vocabularies

    Example:

        Observation 1:
            laptop present

        Observation 2:
            person touching laptop

        Observation 3:
            laptop still present
            person holding backpack

    TemporalWorldState stores those facts.

    Later, ProactiveReasoner decides whether those
    facts justify speaking.
    """

    def __init__(
        self,
        working_memory,
        recent_event_limit: int = 40,
        recent_interaction_limit: int = 10,
    ):

        self.working_memory = (
            working_memory
        )

        self.recent_event_limit = (
            recent_event_limit
        )

        self.recent_interaction_limit = (
            recent_interaction_limit
        )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def snapshot(
        self,
    ) -> TemporalWorldSnapshot:

        # =================================================
        # CURRENT PHYSICAL CONTEXT
        # =================================================

        current_scene = (
            self.working_memory
            .get_current_scene()
        )

        if not current_scene:

            return (
                self._empty_snapshot()
            )

        memory_id = (
            current_scene.get(
                "memory_id"
            )
        )

        generation = (
            current_scene.get(
                "generation"
            )
        )

        current_timestamp = (
            current_scene.get(
                "timestamp"
            )
        )

        current_structured = (
            current_scene.get(
                "structured_scene"
            )
        )

        # =================================================
        # RECENT WORKING MEMORY
        # =================================================

        events = (
            self.working_memory
            .recent(
                limit=(
                    self.recent_event_limit
                )
            )
        )

        # =================================================
        # ONLY CURRENT PHYSICAL CONTEXT
        # =================================================

        context_events = [
            event
            for event in events
            if (
                event.get(
                    "memory_id"
                )
                == memory_id
            )
        ]

        semantic_events = [
            event
            for event in context_events
            if (
                event.get(
                    "event_type"
                )
                == "SEMANTIC_EVENT"
            )
        ]

        # =================================================
        # BUILD CHRONOLOGICAL STRUCTURED OBSERVATIONS
        # =================================================

        observations = []

        for event in semantic_events:

            structured_scene = (
                self._structured_scene_from_event(
                    event
                )
            )

            if not structured_scene:

                continue

            observations.append(
                {
                    "timestamp": (
                        event.get(
                            "timestamp"
                        )
                    ),

                    "scene": (
                        structured_scene
                    ),

                    "metadata": (
                        event.get(
                            "metadata"
                        )
                        or {}
                    ),
                }
            )

        # =================================================
        # BACKWARD-COMPATIBILITY
        #
        # Older working_memory.json files may not have
        # structured_scene in current_scene.
        #
        # In that case use the latest valid semantic
        # observation as a fallback.
        # =================================================

        if not isinstance(
            current_structured,
            dict,
        ):

            if observations:

                current_structured = (
                    observations[-1][
                        "scene"
                    ]
                )

                current_timestamp = (
                    observations[-1][
                        "timestamp"
                    ]
                )

            else:

                current_structured = None

        # =================================================
        # ENVIRONMENT
        # =================================================

        environment = None

        if isinstance(
            current_structured,
            dict,
        ):

            environment = (
                current_structured.get(
                    "environment"
                )
            )

        # =================================================
        # CURRENT OBJECTS
        # =================================================

        current_objects = (
            self._objects_from_scene(
                current_structured
            )
        )

        # =================================================
        # OBJECT HISTORY
        # =================================================

        object_states = (
            self._build_object_history(
                observations=(
                    observations
                ),

                current_scene=(
                    current_structured
                ),

                current_timestamp=(
                    current_timestamp
                ),
            )
        )

        # =================================================
        # HISTORICAL INTERACTIONS
        # =================================================

        recent_interactions = (
            self._interaction_history(
                observations
            )
        )

        # =================================================
        # CURRENT INTERACTIONS
        # =================================================

        active_interactions = (
            self._interactions_from_scene(
                current_structured,

                timestamp=(
                    current_timestamp
                ),
            )
        )

        # =================================================
        # ATTACH HISTORICAL INTERACTIONS TO REAL OBJECTS
        # =================================================

        self._attach_interaction_history(
            states=(
                object_states
            ),

            interactions=(
                recent_interactions
            ),
        )

        # =================================================
        # ATTACH CURRENT INTERACTIONS TO REAL OBJECTS
        # =================================================

        self._attach_interaction_history(
            states=(
                object_states
            ),

            interactions=(
                active_interactions
            ),
        )

        # =================================================
        # OBJECT LIFECYCLE
        # =================================================

        appeared = (
            self._collect_lifecycle_labels(
                semantic_events,

                key=(
                    "objects_appeared"
                ),
            )
        )

        disappeared = (
            self._collect_lifecycle_labels(
                semantic_events,

                key=(
                    "objects_became_absent"
                ),
            )
        )

        reappeared = (
            self._collect_lifecycle_labels(
                semantic_events,

                key=(
                    "objects_reappeared"
                ),
            )
        )

        # =================================================
        # CONFIDENCE
        # =================================================

        confidence = (
            self._confidence(
                current_structured=(
                    current_structured
                ),

                observations=(
                    observations
                ),

                object_states=(
                    object_states
                ),
            )
        )

        # =================================================
        # RETURN SNAPSHOT
        # =================================================

        return TemporalWorldSnapshot(
            generated_at=(
                datetime.now()
                .isoformat()
            ),

            memory_id=(
                memory_id
            ),

            generation=(
                generation
            ),

            environment=(
                environment
            ),

            current_objects=[
                dict(
                    item
                )
                for item
                in current_objects
            ],

            object_history=[
                state.to_dict()
                for state
                in object_states.values()
            ],

            active_interactions=[
                interaction.to_dict()
                for interaction
                in active_interactions
            ],

            recent_interactions=[
                interaction.to_dict()
                for interaction
                in recent_interactions[
                    -self.recent_interaction_limit:
                ]
            ],

            recently_appeared_objects=(
                appeared
            ),

            recently_disappeared_objects=(
                disappeared
            ),

            recently_reappeared_objects=(
                reappeared
            ),

            observed_scene_count=(
                len(
                    observations
                )
            ),

            confidence=(
                confidence
            ),
        )

    # =====================================================
    # EMPTY SNAPSHOT
    # =====================================================

    def _empty_snapshot(
        self,
    ) -> TemporalWorldSnapshot:

        return TemporalWorldSnapshot(
            generated_at=(
                datetime.now()
                .isoformat()
            ),

            memory_id=None,

            generation=None,

            environment=None,

            current_objects=[],

            object_history=[],

            active_interactions=[],

            recent_interactions=[],

            recently_appeared_objects=[],

            recently_disappeared_objects=[],

            recently_reappeared_objects=[],

            observed_scene_count=0,

            confidence=0.0,
        )

    # =====================================================
    # STRUCTURED SCENE FROM EVENT
    # =====================================================

    def _structured_scene_from_event(
        self,
        event,
    ) -> Optional[
        Dict[str, Any]
    ]:

        metadata = (
            event.get(
                "metadata"
            )
            or {}
        )

        # =================================================
        # HISTORICAL-ONLY EVENTS
        #
        # These are useful records of transient actions,
        # but they should not become authoritative world
        # state because the live view had already changed.
        # =================================================

        if metadata.get(
            "historical_only",
            False,
        ):

            return None

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
    # EXTRACT OBJECTS
    # =====================================================

    def _objects_from_scene(
        self,
        scene,
    ) -> List[
        Dict[str, Any]
    ]:

        if not isinstance(
            scene,
            dict,
        ):

            return []

        objects = (
            scene.get(
                "objects"
            )
            or []
        )

        results = []

        seen = set()

        for item in objects:

            if not isinstance(
                item,
                dict,
            ):

                continue

            label = (
                item.get(
                    "label"
                )
            )

            if not label:

                continue

            label_text = (
                str(label)
                .strip()
            )

            if not label_text:

                continue

            normalized = (
                label_text.lower()
            )

            # Avoid duplicates inside one scene.

            if normalized in seen:

                continue

            seen.add(
                normalized
            )

            results.append(
                {
                    "label": (
                        label_text
                    ),

                    "position": (
                        item.get(
                            "position"
                        )
                    ),

                    "state": (
                        item.get(
                            "state"
                        )
                    ),
                }
            )

        return results

    # =====================================================
    # BUILD OBJECT HISTORY
    # =====================================================

    def _build_object_history(
        self,
        observations,
        current_scene,
        current_timestamp,
    ) -> Dict[
        str,
        ObjectWorldState
    ]:

        states: Dict[
            str,
            ObjectWorldState
        ] = {}

        # =================================================
        # HISTORICAL OBSERVATIONS
        # =================================================

        for observation in observations:

            timestamp = (
                observation.get(
                    "timestamp"
                )
            )

            scene = (
                observation.get(
                    "scene"
                )
            )

            objects = (
                self._objects_from_scene(
                    scene
                )
            )

            for item in objects:

                label = (
                    item.get(
                        "label"
                    )
                )

                if not label:

                    continue

                label_text = (
                    str(label)
                    .strip()
                )

                if not label_text:

                    continue

                key = (
                    label_text.lower()
                )

                if key not in states:

                    states[key] = (
                        ObjectWorldState(
                            label=(
                                label_text
                            ),

                            first_seen=(
                                timestamp
                            ),
                        )
                    )

                state = (
                    states[key]
                )

                if (
                    state.first_seen
                    is None
                ):

                    state.first_seen = (
                        timestamp
                    )

                state.last_seen = (
                    timestamp
                )

                state.seen_count += 1

        # =================================================
        # AUTHORITATIVE CURRENT SCENE
        # =================================================

        current_objects = (
            self._objects_from_scene(
                current_scene
            )
        )

        for item in current_objects:

            label = (
                item.get(
                    "label"
                )
            )

            if not label:

                continue

            label_text = (
                str(label)
                .strip()
            )

            if not label_text:

                continue

            key = (
                label_text.lower()
            )

            # ---------------------------------------------
            # New object first observed in current scene.
            # ---------------------------------------------

            if key not in states:

                states[key] = (
                    ObjectWorldState(
                        label=(
                            label_text
                        ),

                        first_seen=(
                            current_timestamp
                        ),
                    )
                )

            state = (
                states[key]
            )

            # ---------------------------------------------
            # Count the current scene as an observation.
            #
            # But avoid double-counting if the latest
            # semantic event and current scene have the
            # exact same timestamp.
            # ---------------------------------------------

            if (
                current_timestamp
                and
                state.last_seen
                != current_timestamp
            ):

                state.seen_count += 1

            elif (
                state.seen_count
                == 0
            ):

                # A brand-new current object must have
                # at least one observation.
                state.seen_count = 1

            # ---------------------------------------------
            # Current state
            # ---------------------------------------------

            state.currently_present = (
                True
            )

            state.current_position = (
                item.get(
                    "position"
                )
            )

            state.current_state = (
                item.get(
                    "state"
                )
            )

            if current_timestamp:

                state.last_seen = (
                    current_timestamp
                )

            if (
                state.first_seen
                is None
            ):

                state.first_seen = (
                    current_timestamp
                )

        return states

    # =====================================================
    # EXTRACT INTERACTIONS
    # =====================================================

    def _interactions_from_scene(
        self,
        scene,
        timestamp=None,
    ) -> List[
        WorldInteraction
    ]:

        if not isinstance(
            scene,
            dict,
        ):

            return []

        people = (
            scene.get(
                "people"
            )
            or []
        )

        interactions = []

        for person in people:

            if not isinstance(
                person,
                dict,
            ):

                continue

            activity = (
                person.get(
                    "activity"
                )
                or {}
            )

            activity_type = (
                activity.get(
                    "type"
                )
            )

            pose = (
                person.get(
                    "pose"
                )
                or {}
            )

            for hand_name in (
                "left_hand",
                "right_hand",
            ):

                hand = (
                    pose.get(
                        hand_name
                    )
                )

                if not isinstance(
                    hand,
                    dict,
                ):

                    continue

                relation = (
                    hand.get(
                        "relation"
                    )
                )

                target = (
                    hand.get(
                        "target"
                    )
                )

                if not relation:

                    continue

                relation_text = (
                    str(relation)
                    .strip()
                )

                if not relation_text:

                    continue

                normalized_relation = (
                    relation_text.lower()
                )

                # -----------------------------------------
                # Ignore non-interaction states.
                # -----------------------------------------

                if normalized_relation in {
                    "free",
                    "unknown",
                }:

                    continue

                explicit_hand = (
                    hand.get(
                        "hand"
                    )
                )

                if explicit_hand:

                    hand_value = (
                        str(
                            explicit_hand
                        )
                        .strip()
                    )

                else:

                    hand_value = (
                        "left"
                        if (
                            hand_name
                            == "left_hand"
                        )
                        else
                        "right"
                    )

                target_value = None

                if target:

                    target_value = (
                        str(target)
                        .strip()
                    )

                    if not target_value:

                        target_value = None

                activity_value = None

                if activity_type:

                    activity_value = (
                        str(
                            activity_type
                        )
                        .strip()
                    )

                    if not activity_value:

                        activity_value = None

                interactions.append(
                    WorldInteraction(
                        timestamp=(
                            timestamp
                        ),

                        hand=(
                            hand_value
                        ),

                        relation=(
                            relation_text
                        ),

                        target=(
                            target_value
                        ),

                        activity=(
                            activity_value
                        ),
                    )
                )

        return interactions

    # =====================================================
    # CHRONOLOGICAL INTERACTION HISTORY
    # =====================================================

    def _interaction_history(
        self,
        observations,
    ) -> List[
        WorldInteraction
    ]:

        results = []

        previous_key = None

        for observation in observations:

            timestamp = (
                observation.get(
                    "timestamp"
                )
            )

            scene = (
                observation.get(
                    "scene"
                )
            )

            interactions = (
                self._interactions_from_scene(
                    scene=(
                        scene
                    ),

                    timestamp=(
                        timestamp
                    ),
                )
            )

            for interaction in interactions:

                hand_key = (
                    interaction.hand
                    or ""
                )

                relation_key = (
                    interaction.relation
                    or ""
                )

                target_key = (
                    interaction.target
                    or ""
                )

                key = (
                    hand_key
                    .strip()
                    .lower(),

                    relation_key
                    .strip()
                    .lower(),

                    target_key
                    .strip()
                    .lower(),
                )

                # -----------------------------------------
                # Consecutive duplicate suppression.
                #
                # Example:
                #
                # holding phone
                # holding phone
                # holding phone
                #
                # becomes one interaction entry.
                # -----------------------------------------

                if (
                    previous_key
                    == key
                ):

                    continue

                previous_key = (
                    key
                )

                results.append(
                    interaction
                )

        return results

    # =====================================================
    # ATTACH INTERACTION HISTORY TO REAL OBJECTS
    # =====================================================

    def _attach_interaction_history(
        self,
        states,
        interactions,
    ):
        """
        Update interaction metadata only for objects
        that have actually appeared in StructuredScene.objects.

        This prevents interaction targets from
        accidentally becoming world objects.

        Example:

            touching chin

        remains inside recent_interactions.

        But:

            chin

        is NOT inserted into object_history.

        Example:

            holding smartphone

        updates smartphone's object history only if
        smartphone was actually observed as a scene object.

        This avoids requiring a hardcoded list of body
        parts or special object categories.
        """

        for interaction in interactions:

            target = (
                interaction.target
            )

            if not target:

                continue

            target_text = (
                str(target)
                .strip()
            )

            if not target_text:

                continue

            key = (
                target_text.lower()
            )

            # ---------------------------------------------
            # IMPORTANT:
            #
            # Do not manufacture ObjectWorldState from an
            # arbitrary interaction target.
            # ---------------------------------------------

            if key not in states:

                continue

            state = (
                states[key]
            )

            state.last_interacted = (
                interaction.timestamp
            )

            state.last_interaction = (
                interaction.relation
            )

    # =====================================================
    # OBJECT LIFECYCLE HISTORY
    # =====================================================

    def _collect_lifecycle_labels(
        self,
        events,
        key,
    ) -> List[str]:

        values = []

        normalized_seen = set()

        for event in events:

            metadata = (
                event.get(
                    "metadata"
                )
                or {}
            )

            labels = (
                metadata.get(
                    key
                )
                or []
            )

            if not isinstance(
                labels,
                list,
            ):

                continue

            for label in labels:

                value = (
                    str(label)
                    .strip()
                )

                if not value:

                    continue

                normalized = (
                    value.lower()
                )

                if (
                    normalized
                    in normalized_seen
                ):

                    continue

                normalized_seen.add(
                    normalized
                )

                values.append(
                    value
                )

        return (
            values[-8:]
        )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    def _confidence(
        self,
        current_structured,
        observations,
        object_states,
    ) -> float:
        """
        Confidence here means:

            "How much structured temporal evidence
            does Orion currently have?"

        It does NOT mean:

            VLM probability
            object detection confidence
            factual certainty
        """

        score = 0.0

        # ---------------------------------------------
        # Authoritative structured current scene
        # ---------------------------------------------

        if current_structured:

            score += 0.45

        # ---------------------------------------------
        # Physical objects available
        # ---------------------------------------------

        if object_states:

            score += 0.20

        # ---------------------------------------------
        # At least one historical observation
        # ---------------------------------------------

        if (
            len(
                observations
            )
            >= 1
        ):

            score += 0.15

        # ---------------------------------------------
        # Several observations
        # ---------------------------------------------

        if (
            len(
                observations
            )
            >= 3
        ):

            score += 0.10

        # ---------------------------------------------
        # Strong temporal history
        # ---------------------------------------------

        if (
            len(
                observations
            )
            >= 5
        ):

            score += 0.10

        return round(
            min(
                score,
                1.0,
            ),
            2,
        )