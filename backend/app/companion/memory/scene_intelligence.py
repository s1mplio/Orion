from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.companion.memory.scene_models import StructuredScene


class SceneIntelligence:
    """
    Deterministic semantic reasoning layer for Orion.

    Responsibilities:

    1. Current / previous scene access
    2. Recent scene history
    3. Timeline/search helpers
    4. Structured state comparison
    5. Uncertainty-aware state interpretation
    6. Entity lifecycle interpretation
    7. Physical-context transition evaluation

    IMPORTANT:

    This class makes ZERO LLM/VLM calls.

    Core principle:

        perception difference != world change

    Examples:

        unknown -> seated
            information resolved
            NOT physical movement

        seated -> unknown
            information became uncertain
            NOT physical movement

        seated -> standing
            genuine state change

        touching chin -> no hand interaction
            genuine interaction change

    Architecture:

        VLM
          ↓
        StructuredScene
          ↓
        SceneStabilizer
          ↓
        SceneIntelligence
          ↓
        semantic events / context reasoning
    """

    def __init__(self, working_memory):
        self.working_memory = working_memory

    # =====================================================
    # CURRENT / PREVIOUS
    # =====================================================

    def current_scene(self):
        return self.working_memory.get_current_scene()

    def previous_scene(self):
        return self.working_memory.previous_scene()

    # =====================================================
    # RECENT SCENES
    # =====================================================

    def recent_scenes(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:

        events = self.working_memory.recent(
            limit=50
        )

        scenes = []

        for event in events:

            if (
                event.get("event_type")
                != "SCENE_ESTABLISHED"
            ):
                continue

            observation = event.get(
                "observation"
            )

            if not observation:
                continue

            metadata = (
                event.get("metadata")
                or {}
            )

            structured_scene = (
                event.get(
                    "structured_scene"
                )
            )

            if structured_scene is None:

                structured_scene = (
                    metadata.get(
                        "structured_scene"
                    )
                )

            scenes.append(
                {
                    "timestamp": event.get(
                        "timestamp"
                    ),

                    "memory_id": event.get(
                        "memory_id"
                    ),

                    "observation": observation,

                    "structured_scene": (
                        structured_scene
                    ),

                    "metadata": metadata,
                }
            )

        return scenes[-limit:]

    # =====================================================
    # TIMELINE
    # =====================================================

    def timeline(
        self,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:

        scenes = self.recent_scenes(
            limit=limit
        )

        timeline = []

        previous = None

        for scene in scenes:

            changed = False

            if previous is not None:

                changed = (
                    previous.get(
                        "memory_id"
                    )
                    != scene.get(
                        "memory_id"
                    )
                )

            timeline.append(
                {
                    "timestamp": scene.get(
                        "timestamp"
                    ),

                    "memory_id": scene.get(
                        "memory_id"
                    ),

                    "observation": scene.get(
                        "observation"
                    ),

                    "changed_from_previous": (
                        changed
                    ),
                }
            )

            previous = scene

        return timeline

    # =====================================================
    # RECENT SEARCH
    # =====================================================

    def find_recent(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:

        if not query:
            return []

        query = (
            query
            .lower()
            .strip()
        )

        scenes = self.recent_scenes(
            limit=50
        )

        matches = []

        for scene in reversed(
            scenes
        ):

            observation = (
                scene.get(
                    "observation",
                    "",
                )
                .lower()
            )

            if query in observation:
                matches.append(scene)

            if len(matches) >= limit:
                break

        return matches

    # =====================================================
    # GENERIC CLEANING
    # =====================================================

    def _clean(
        self,
        value: Optional[str],
    ) -> Optional[str]:

        """
        Formatting + uncertainty cleanup.

        Unknown-like values become None.

        We deliberately avoid a giant semantic
        normalization dictionary.
        """

        if value is None:
            return None

        value = " ".join(
            str(value)
            .lower()
            .strip()
            .split()
        )

        if value in {
            "",
            "unknown",
            "uncertain",
            "unclear",
            "not visible",
            "not sure",
            "cannot determine",
            "can't determine",
            "indeterminate",
            "none",
            "null",
        }:
            return None

        return value or None

    # =====================================================
    # UNCERTAINTY-AWARE SCALAR COMPARISON
    # =====================================================

    def _compare_known_state(
        self,
        previous: Optional[str],
        current: Optional[str],
    ) -> Dict[str, Any]:
        """
        Compare a single semantic state.

        Result types:

            unchanged
            changed
            resolved
            uncertain
            absent

        Rules:

            None -> known
                resolved

            known -> None
                uncertain

            known A -> known B
                changed

            known A -> known A
                unchanged

            None -> None
                absent
        """

        previous_clean = (
            self._clean(
                previous
            )
        )

        current_clean = (
            self._clean(
                current
            )
        )

        # ---------------------------------------------
        # BOTH UNKNOWN
        # ---------------------------------------------

        if (
            previous_clean is None
            and current_clean is None
        ):

            return {
                "changed": False,
                "resolved": False,
                "became_uncertain": False,
                "comparison": "absent",
                "previous": None,
                "current": None,
            }

        # ---------------------------------------------
        # UNKNOWN -> KNOWN
        # ---------------------------------------------

        if (
            previous_clean is None
            and current_clean is not None
        ):

            return {
                "changed": False,
                "resolved": True,
                "became_uncertain": False,
                "comparison": "resolved",
                "previous": None,
                "current": current_clean,
            }

        # ---------------------------------------------
        # KNOWN -> UNKNOWN
        # ---------------------------------------------

        if (
            previous_clean is not None
            and current_clean is None
        ):

            return {
                "changed": False,
                "resolved": False,
                "became_uncertain": True,
                "comparison": "uncertain",
                "previous": previous_clean,
                "current": None,
            }

        # ---------------------------------------------
        # KNOWN -> KNOWN
        # ---------------------------------------------

        changed = (
            previous_clean
            != current_clean
        )

        return {
            "changed": changed,
            "resolved": False,
            "became_uncertain": False,
            "comparison": (
                "changed"
                if changed
                else "unchanged"
            ),
            "previous": previous_clean,
            "current": current_clean,
        }

    # =====================================================
    # UNCERTAINTY-AWARE LIST COMPARISON
    # =====================================================

    def _compare_state_lists(
        self,
        previous: List[Optional[str]],
        current: List[Optional[str]],
    ) -> Dict[str, Any]:
        """
        Compare per-person state lists.

        This is intentionally index-based for V1 because
        Orion currently mainly tracks one primary person.

        Multi-person identity association belongs in the
        entity-tracking layer later.
        """

        maximum = max(
            len(previous),
            len(current),
        )

        changed = False
        resolved = False
        became_uncertain = False

        comparisons = []

        for index in range(
            maximum
        ):

            previous_value = (
                previous[index]
                if index < len(previous)
                else None
            )

            current_value = (
                current[index]
                if index < len(current)
                else None
            )

            result = (
                self._compare_known_state(
                    previous_value,
                    current_value,
                )
            )

            result["index"] = index

            comparisons.append(
                result
            )

            if result["changed"]:
                changed = True

            if result["resolved"]:
                resolved = True

            if result["became_uncertain"]:
                became_uncertain = True

        return {
            "changed": changed,
            "resolved": resolved,
            "became_uncertain": (
                became_uncertain
            ),
            "comparisons": comparisons,
        }

    # =====================================================
    # ENVIRONMENT
    # =====================================================

    def _environment_family(
        self,
        environment: Optional[str],
    ) -> Optional[str]:

        value = self._clean(
            environment
        )

        if value is None:
            return None

        outdoor_tokens = (
            "outdoor",
            "outside",
            "street",
            "road",
            "park",
            "garden",
            "field",
            "sidewalk",
            "pavement",
            "parking lot",
        )

        vehicle_tokens = (
            "car interior",
            "vehicle interior",
            "inside car",
            "inside vehicle",
            "bus interior",
            "train interior",
        )

        indoor_tokens = (
            "indoor",
            "room",
            "bedroom",
            "office",
            "kitchen",
            "bathroom",
            "living room",
            "hall",
            "corridor",
            "store",
            "shop",
            "restaurant",
            "classroom",
        )

        for token in vehicle_tokens:

            if token in value:
                return "vehicle"

        for token in outdoor_tokens:

            if token in value:
                return "outdoor"

        for token in indoor_tokens:

            if token in value:
                return "indoor"

        return None

    # =====================================================
    # OBJECTS
    # =====================================================

    def _object_labels(
        self,
        scene: StructuredScene,
    ) -> set[str]:

        labels = set()

        for obj in scene.objects:

            label = self._clean(
                obj.label
            )

            if label:
                labels.add(label)

        return labels

    # =====================================================
    # ACCESSORIES
    # =====================================================

    def _accessories(
        self,
        scene: StructuredScene,
    ) -> set[str]:

        result = set()

        for person in scene.people:

            for accessory in (
                person.visible_accessories
            ):

                value = self._clean(
                    accessory
                )

                if value:
                    result.add(value)

        return result

    # =====================================================
    # PEOPLE COUNT
    # =====================================================

    def _person_count(
        self,
        scene: StructuredScene,
    ) -> int:

        return len(
            scene.people
        )

    # =====================================================
    # ACTIVITY
    # =====================================================

    def _activity_states(
        self,
        scene: StructuredScene,
    ) -> List[Optional[str]]:

        states = []

        for person in scene.people:

            if person.activity is None:

                states.append(None)
                continue

            states.append(
                self._clean(
                    person.activity.type
                )
            )

        return states

    # =====================================================
    # BODY STATE
    # =====================================================

    def _body_states(
        self,
        scene: StructuredScene,
    ) -> List[Optional[str]]:

        states = []

        for person in scene.people:

            if person.pose is None:

                states.append(None)
                continue

            states.append(
                self._clean(
                    person.pose.body_state
                )
            )

        return states

    # =====================================================
    # HEAD DIRECTION
    # =====================================================

    def _head_directions(
        self,
        scene: StructuredScene,
    ) -> List[Optional[str]]:

        states = []

        for person in scene.people:

            if person.pose is None:

                states.append(None)
                continue

            states.append(
                self._clean(
                    person.pose.head_direction
                )
            )

        return states

    # =====================================================
    # HAND SIGNATURE
    # =====================================================

    def _hand_signature(
        self,
        hand,
    ) -> Optional[
        Tuple[
            Optional[str],
            Optional[str],
        ]
    ]:

        if hand is None:
            return None

        relation = self._clean(
            hand.relation
        )

        target = self._clean(
            hand.target
        )

        if (
            relation is None
            and target is None
        ):
            return None

        return (
            relation,
            target,
        )

    # =====================================================
    # LEFT HAND
    # =====================================================

    def _left_hand_states(
        self,
        scene: StructuredScene,
    ) -> List[Any]:

        states = []

        for person in scene.people:

            if person.pose is None:

                states.append(None)
                continue

            states.append(
                self._hand_signature(
                    person.pose.left_hand
                )
            )

        return states

    # =====================================================
    # RIGHT HAND
    # =====================================================

    def _right_hand_states(
        self,
        scene: StructuredScene,
    ) -> List[Any]:

        states = []

        for person in scene.people:

            if person.pose is None:

                states.append(None)
                continue

            states.append(
                self._hand_signature(
                    person.pose.right_hand
                )
            )

        return states

    # =====================================================
    # HAND COMPARISON
    # =====================================================

    def _compare_hand_lists(
        self,
        previous: List[Any],
        current: List[Any],
    ) -> Dict[str, Any]:
        """
        Hand state is different from generic uncertain
        fields.

        Why?

        If we previously saw:

            touching chin

        and now see:

            no hand interaction

        that is often the meaningful event:

            hand lowered / interaction ended

        Therefore known -> None is allowed to count as a
        hand-state change.

        But None -> known is also meaningful because an
        interaction started.
        """

        maximum = max(
            len(previous),
            len(current),
        )

        changed = False
        started = False
        ended = False

        comparisons = []

        for index in range(
            maximum
        ):

            previous_value = (
                previous[index]
                if index < len(previous)
                else None
            )

            current_value = (
                current[index]
                if index < len(current)
                else None
            )

            item_changed = (
                previous_value
                != current_value
            )

            interaction_started = (
                previous_value is None
                and current_value is not None
            )

            interaction_ended = (
                previous_value is not None
                and current_value is None
            )

            if item_changed:
                changed = True

            if interaction_started:
                started = True

            if interaction_ended:
                ended = True

            comparisons.append(
                {
                    "index": index,

                    "previous": (
                        previous_value
                    ),

                    "current": (
                        current_value
                    ),

                    "changed": (
                        item_changed
                    ),

                    "interaction_started": (
                        interaction_started
                    ),

                    "interaction_ended": (
                        interaction_ended
                    ),
                }
            )

        return {
            "changed": changed,
            "interaction_started": started,
            "interaction_ended": ended,
            "comparisons": comparisons,
        }

    # =====================================================
    # SALIENT EVENT
    # =====================================================

    def _salient_event_changed(
        self,
        previous: StructuredScene,
        current: StructuredScene,
    ) -> bool:

        """
        Do not compare generated salient-event text.

        Only compare whether a salient event exists.

        Relational structured state remains the primary
        semantic signal.
        """

        previous_present = bool(
            self._clean(
                previous.salient_event
            )
        )

        current_present = bool(
            self._clean(
                current.salient_event
            )
        )

        return (
            previous_present
            != current_present
        )

    # =====================================================
    # LIFECYCLE SET
    # =====================================================

    def _lifecycle_set(
        self,
        lifecycle_changes: Dict[str, Any],
        key: str,
    ) -> set[str]:

        values = (
            lifecycle_changes.get(
                key,
                [],
            )
        )

        if not values:
            return set()

        result = set()

        for value in values:

            cleaned = self._clean(
                value
            )

            if cleaned:
                result.add(
                    cleaned
                )

        return result

    # =====================================================
    # PHYSICAL CONTEXT TRANSITION
    # =====================================================

    def evaluate_context_transition(
        self,
        previous: Optional[
            StructuredScene
        ],
        candidate: StructuredScene,
    ) -> Dict[str, Any]:

        if previous is None:

            return {
                "confirmed": False,

                "score": 0.0,

                "reason": (
                    "No previous structured context "
                    "available."
                ),

                "environment_changed": False,

                "environment_family_changed": False,

                "previous_environment": None,

                "current_environment": (
                    self._clean(
                        candidate.environment
                    )
                ),

                "previous_environment_family": None,

                "current_environment_family": (
                    self._environment_family(
                        candidate.environment
                    )
                ),

                "previous_objects": [],

                "current_objects": sorted(
                    self._object_labels(
                        candidate
                    )
                ),

                "shared_objects": [],

                "shared_object_count": 0,

                "object_overlap_ratio": 0.0,

                "object_replacement_count": 0,

                "strong_object_shift": False,

                "extreme_object_shift": False,

                "person_count_changed": False,
            }

        # =================================================
        # ENVIRONMENT
        # =================================================

        previous_environment = (
            self._clean(
                previous.environment
            )
        )

        current_environment = (
            self._clean(
                candidate.environment
            )
        )

        previous_family = (
            self._environment_family(
                previous.environment
            )
        )

        current_family = (
            self._environment_family(
                candidate.environment
            )
        )

        # Unknown -> known and known -> unknown are NOT
        # considered environment changes.

        environment_comparison = (
            self._compare_known_state(
                previous_environment,
                current_environment,
            )
        )

        environment_changed = (
            environment_comparison[
                "changed"
            ]
        )

        family_comparison = (
            self._compare_known_state(
                previous_family,
                current_family,
            )
        )

        environment_family_changed = (
            family_comparison[
                "changed"
            ]
        )

        # =================================================
        # OBJECT CONTINUITY
        # =================================================

        previous_objects = (
            self._object_labels(
                previous
            )
        )

        current_objects = (
            self._object_labels(
                candidate
            )
        )

        shared_objects = (
            previous_objects
            & current_objects
        )

        all_objects = (
            previous_objects
            | current_objects
        )

        if all_objects:

            overlap_ratio = (
                len(shared_objects)
                / len(all_objects)
            )

        else:

            overlap_ratio = 1.0

        removed_objects = (
            previous_objects
            - current_objects
        )

        added_objects = (
            current_objects
            - previous_objects
        )

        object_replacement_count = (
            len(removed_objects)
            + len(added_objects)
        )

        strong_object_shift = (
            len(previous_objects) >= 2
            and len(current_objects) >= 2
            and overlap_ratio <= 0.25
            and object_replacement_count >= 4
        )

        extreme_object_shift = (
            len(previous_objects) >= 3
            and len(current_objects) >= 3
            and len(shared_objects) == 0
            and object_replacement_count >= 6
        )

        # =================================================
        # PERSON COUNT
        # =================================================

        previous_person_count = (
            self._person_count(
                previous
            )
        )

        current_person_count = (
            self._person_count(
                candidate
            )
        )

        person_count_changed = (
            previous_person_count
            != current_person_count
        )

        # =================================================
        # TRANSITION SCORE
        # =================================================

        score = 0.0

        reasons = []

        if environment_family_changed:

            score += 0.60

            reasons.append(
                "environment family changed"
            )

        elif environment_changed:

            score += 0.15

            reasons.append(
                "environment description changed"
            )

        if strong_object_shift:

            score += 0.30

            reasons.append(
                "strong persistent object-layout shift"
            )

        if extreme_object_shift:

            score += 0.25

            reasons.append(
                "extreme object replacement"
            )

        score = min(
            score,
            1.0,
        )

        # =================================================
        # CONFIRMATION
        # =================================================

        confirmed_by_family = (
            environment_family_changed
            and (
                strong_object_shift
                or object_replacement_count >= 2
            )
        )

        confirmed_by_environment_and_structure = (
            environment_changed
            and strong_object_shift
        )

        confirmed_by_extreme_structure = (
            extreme_object_shift
        )

        confirmed = any(
            [
                confirmed_by_family,
                confirmed_by_environment_and_structure,
                confirmed_by_extreme_structure,
            ]
        )

        if confirmed:

            if confirmed_by_family:

                reasons.append(
                    "physical context confirmed by "
                    "environment-family + structural change"
                )

            elif (
                confirmed_by_environment_and_structure
            ):

                reasons.append(
                    "physical context confirmed by "
                    "environment + object change"
                )

            elif confirmed_by_extreme_structure:

                reasons.append(
                    "physical context confirmed by "
                    "extreme structural replacement"
                )

        else:

            reasons.append(
                "insufficient evidence for a new "
                "physical context"
            )

        return {
            "confirmed": confirmed,

            "score": float(
                score
            ),

            "reason": (
                "; ".join(
                    reasons
                )
            ),

            "environment_changed": (
                environment_changed
            ),

            "environment_family_changed": (
                environment_family_changed
            ),

            "environment_resolved": (
                environment_comparison[
                    "resolved"
                ]
            ),

            "environment_became_uncertain": (
                environment_comparison[
                    "became_uncertain"
                ]
            ),

            "previous_environment": (
                previous_environment
            ),

            "current_environment": (
                current_environment
            ),

            "previous_environment_family": (
                previous_family
            ),

            "current_environment_family": (
                current_family
            ),

            "previous_objects": sorted(
                previous_objects
            ),

            "current_objects": sorted(
                current_objects
            ),

            "shared_objects": sorted(
                shared_objects
            ),

            "shared_object_count": (
                len(
                    shared_objects
                )
            ),

            "object_overlap_ratio": float(
                overlap_ratio
            ),

            "object_replacement_count": (
                object_replacement_count
            ),

            "strong_object_shift": (
                strong_object_shift
            ),

            "extreme_object_shift": (
                extreme_object_shift
            ),

            "person_count_changed": (
                person_count_changed
            ),
        }

    # =====================================================
    # SCENE COMPARISON
    # =====================================================

    def compare_scenes(
        self,
        previous: Optional[
            StructuredScene
        ],
        current: StructuredScene,
        lifecycle_changes: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Dict[str, Any]:

        lifecycle_changes = (
            lifecycle_changes
            or {}
        )

        # =================================================
        # ENTITY LIFECYCLE
        # =================================================

        objects_initially_confirmed = (
            self._lifecycle_set(
                lifecycle_changes,
                "objects_initially_confirmed",
            )
        )

        objects_appeared = (
            self._lifecycle_set(
                lifecycle_changes,
                "objects_appeared",
            )
        )

        objects_reappeared = (
            self._lifecycle_set(
                lifecycle_changes,
                "objects_reappeared",
            )
        )

        objects_became_absent = (
            self._lifecycle_set(
                lifecycle_changes,
                "objects_became_absent",
            )
        )

        accessories_initially_confirmed = (
            self._lifecycle_set(
                lifecycle_changes,
                "accessories_initially_confirmed",
            )
        )

        accessories_appeared = (
            self._lifecycle_set(
                lifecycle_changes,
                "accessories_appeared",
            )
        )

        accessories_reappeared = (
            self._lifecycle_set(
                lifecycle_changes,
                "accessories_reappeared",
            )
        )

        accessories_became_absent = (
            self._lifecycle_set(
                lifecycle_changes,
                "accessories_became_absent",
            )
        )

        # =================================================
        # FIRST SCENE
        # =================================================

        if previous is None:

            return {
                "is_first_scene": True,

                "environment_changed": False,
                "environment_resolved": False,
                "environment_became_uncertain": False,

                "activity_changed": False,
                "activity_resolved": False,
                "activity_became_uncertain": False,

                "pose_changed": False,

                "body_state_changed": False,
                "body_state_resolved": False,
                "body_state_became_uncertain": False,

                "head_direction_changed": False,
                "head_direction_resolved": False,
                "head_direction_became_uncertain": False,

                "left_hand_changed": False,
                "right_hand_changed": False,

                "left_hand_interaction_started": False,
                "left_hand_interaction_ended": False,

                "right_hand_interaction_started": False,
                "right_hand_interaction_ended": False,

                "objects_added": [],
                "objects_removed": [],

                "accessories_added": [],
                "accessories_removed": [],

                "raw_objects_added": [],
                "raw_objects_removed": [],

                "raw_accessories_added": [],
                "raw_accessories_removed": [],

                "objects_initially_confirmed": sorted(
                    objects_initially_confirmed
                ),

                "objects_appeared": sorted(
                    objects_appeared
                ),

                "objects_reappeared": sorted(
                    objects_reappeared
                ),

                "objects_became_absent": sorted(
                    objects_became_absent
                ),

                "accessories_initially_confirmed": sorted(
                    accessories_initially_confirmed
                ),

                "accessories_appeared": sorted(
                    accessories_appeared
                ),

                "accessories_reappeared": sorted(
                    accessories_reappeared
                ),

                "accessories_became_absent": sorted(
                    accessories_became_absent
                ),

                "salient_event_changed": False,

                "information_resolved": False,

                "information_became_uncertain": False,

                "state_changed": False,

                "interaction_changed": False,

                "persistent_world_changed": False,

                "meaningful_event": False,

                "major_scene_change": False,

                "reason": (
                    "Initial structured scene baseline."
                ),
            }

        # =================================================
        # ENVIRONMENT
        # =================================================

        environment_comparison = (
            self._compare_known_state(
                previous.environment,
                current.environment,
            )
        )

        environment_changed = (
            environment_comparison[
                "changed"
            ]
        )

        environment_resolved = (
            environment_comparison[
                "resolved"
            ]
        )

        environment_became_uncertain = (
            environment_comparison[
                "became_uncertain"
            ]
        )

        # =================================================
        # RAW OBJECT DIFFERENCE
        # =================================================

        previous_objects = (
            self._object_labels(
                previous
            )
        )

        current_objects = (
            self._object_labels(
                current
            )
        )

        raw_objects_added = (
            current_objects
            - previous_objects
        )

        raw_objects_removed = (
            previous_objects
            - current_objects
        )

        # =================================================
        # RAW ACCESSORY DIFFERENCE
        # =================================================

        previous_accessories = (
            self._accessories(
                previous
            )
        )

        current_accessories = (
            self._accessories(
                current
            )
        )

        raw_accessories_added = (
            current_accessories
            - previous_accessories
        )

        raw_accessories_removed = (
            previous_accessories
            - current_accessories
        )

        # =================================================
        # SEMANTIC ENTITY EVENTS
        # =================================================

        objects_added = sorted(
            (
                raw_objects_added
                - objects_initially_confirmed
            )
            | objects_appeared
            | objects_reappeared
        )

        objects_removed = sorted(
            objects_became_absent
        )

        accessories_added = sorted(
            (
                raw_accessories_added
                - accessories_initially_confirmed
            )
            | accessories_appeared
            | accessories_reappeared
        )

        accessories_removed = sorted(
            accessories_became_absent
        )

        # =================================================
        # ACTIVITY
        # =================================================

        activity_comparison = (
            self._compare_state_lists(
                self._activity_states(
                    previous
                ),
                self._activity_states(
                    current
                ),
            )
        )

        activity_changed = (
            activity_comparison[
                "changed"
            ]
        )

        activity_resolved = (
            activity_comparison[
                "resolved"
            ]
        )

        activity_became_uncertain = (
            activity_comparison[
                "became_uncertain"
            ]
        )

        # =================================================
        # BODY STATE
        # =================================================

        body_comparison = (
            self._compare_state_lists(
                self._body_states(
                    previous
                ),
                self._body_states(
                    current
                ),
            )
        )

        body_state_changed = (
            body_comparison[
                "changed"
            ]
        )

        body_state_resolved = (
            body_comparison[
                "resolved"
            ]
        )

        body_state_became_uncertain = (
            body_comparison[
                "became_uncertain"
            ]
        )

        # =================================================
        # HEAD DIRECTION
        # =================================================

        head_comparison = (
            self._compare_state_lists(
                self._head_directions(
                    previous
                ),
                self._head_directions(
                    current
                ),
            )
        )

        head_direction_changed = (
            head_comparison[
                "changed"
            ]
        )

        head_direction_resolved = (
            head_comparison[
                "resolved"
            ]
        )

        head_direction_became_uncertain = (
            head_comparison[
                "became_uncertain"
            ]
        )

        # =================================================
        # LEFT HAND
        # =================================================

        left_hand_comparison = (
            self._compare_hand_lists(
                self._left_hand_states(
                    previous
                ),
                self._left_hand_states(
                    current
                ),
            )
        )

        left_hand_changed = (
            left_hand_comparison[
                "changed"
            ]
        )

        # =================================================
        # RIGHT HAND
        # =================================================

        right_hand_comparison = (
            self._compare_hand_lists(
                self._right_hand_states(
                    previous
                ),
                self._right_hand_states(
                    current
                ),
            )
        )

        right_hand_changed = (
            right_hand_comparison[
                "changed"
            ]
        )

        # =================================================
        # POSE
        # =================================================

        pose_changed = any(
            [
                body_state_changed,
                head_direction_changed,
                left_hand_changed,
                right_hand_changed,
            ]
        )

        # =================================================
        # SALIENT EVENT
        # =================================================

        salient_event_changed = (
            self._salient_event_changed(
                previous,
                current,
            )
        )

        # =================================================
        # INTERACTION
        # =================================================

        interaction_changed = (
            left_hand_changed
            or right_hand_changed
        )

        # =================================================
        # INFORMATION QUALITY
        # =================================================

        information_resolved = any(
            [
                environment_resolved,
                activity_resolved,
                body_state_resolved,
                head_direction_resolved,
            ]
        )

        information_became_uncertain = any(
            [
                environment_became_uncertain,
                activity_became_uncertain,
                body_state_became_uncertain,
                head_direction_became_uncertain,
            ]
        )

        # =================================================
        # PERSISTENT WORLD
        # =================================================

        persistent_world_changed = any(
            [
                bool(
                    objects_appeared
                ),

                bool(
                    objects_reappeared
                ),

                bool(
                    objects_became_absent
                ),

                bool(
                    accessories_appeared
                ),

                bool(
                    accessories_reappeared
                ),

                bool(
                    accessories_became_absent
                ),
            ]
        )

        # =================================================
        # BASELINE KNOWLEDGE
        # =================================================

        baseline_knowledge_changed = any(
            [
                bool(
                    objects_initially_confirmed
                ),

                bool(
                    accessories_initially_confirmed
                ),
            ]
        )

        # =================================================
        # STATE CHANGED
        # =================================================
        #
        # Important:
        #
        # information_resolved and
        # information_became_uncertain
        #
        # are NOT world-state changes.

        state_changed = any(
            [
                environment_changed,

                activity_changed,

                body_state_changed,

                head_direction_changed,

                left_hand_changed,

                right_hand_changed,

                bool(
                    raw_objects_added
                ),

                bool(
                    raw_objects_removed
                ),

                bool(
                    raw_accessories_added
                ),

                bool(
                    raw_accessories_removed
                ),

                baseline_knowledge_changed,

                salient_event_changed,
            ]
        )

        # =================================================
        # MEMORY-WORTHY EVENT
        # =================================================

        meaningful_event = any(
            [
                environment_changed,

                activity_changed,

                body_state_changed,

                interaction_changed,

                persistent_world_changed,
            ]
        )

        # =================================================
        # MAJOR STRUCTURED CHANGE
        # =================================================

        persistent_change_count = (
            len(
                objects_appeared
            )
            + len(
                objects_reappeared
            )
            + len(
                objects_became_absent
            )
            + len(
                accessories_appeared
            )
            + len(
                accessories_reappeared
            )
            + len(
                accessories_became_absent
            )
        )

        major_scene_change = (
            persistent_change_count >= 4
        )

        # =================================================
        # REASONS
        # =================================================

        reasons = []

        # ---------------------------------------------
        # REAL CHANGES
        # ---------------------------------------------

        if environment_changed:

            reasons.append(
                "environment changed"
            )

        if activity_changed:

            reasons.append(
                "activity changed"
            )

        if body_state_changed:

            reasons.append(
                "body state changed"
            )

        if head_direction_changed:

            reasons.append(
                "head direction changed"
            )

        if left_hand_changed:

            reasons.append(
                "left hand relation changed"
            )

        if right_hand_changed:

            reasons.append(
                "right hand relation changed"
            )

        # ---------------------------------------------
        # INFORMATION RESOLUTION
        # ---------------------------------------------

        if activity_resolved:

            reasons.append(
                "activity information resolved"
            )

        if body_state_resolved:

            reasons.append(
                "body state information resolved"
            )

        if head_direction_resolved:

            reasons.append(
                "head direction information resolved"
            )

        if environment_resolved:

            reasons.append(
                "environment information resolved"
            )

        # ---------------------------------------------
        # INFORMATION LOSS
        # ---------------------------------------------

        if activity_became_uncertain:

            reasons.append(
                "activity became uncertain"
            )

        if body_state_became_uncertain:

            reasons.append(
                "body state became uncertain"
            )

        if head_direction_became_uncertain:

            reasons.append(
                "head direction became uncertain"
            )

        if environment_became_uncertain:

            reasons.append(
                "environment became uncertain"
            )

        # ---------------------------------------------
        # ENTITY LIFECYCLE
        # ---------------------------------------------

        if objects_initially_confirmed:

            reasons.append(
                "baseline objects confirmed: "
                + ", ".join(
                    sorted(
                        objects_initially_confirmed
                    )
                )
            )

        if accessories_initially_confirmed:

            reasons.append(
                "baseline accessories confirmed: "
                + ", ".join(
                    sorted(
                        accessories_initially_confirmed
                    )
                )
            )

        if objects_appeared:

            reasons.append(
                "objects appeared: "
                + ", ".join(
                    sorted(
                        objects_appeared
                    )
                )
            )

        if objects_reappeared:

            reasons.append(
                "objects reappeared: "
                + ", ".join(
                    sorted(
                        objects_reappeared
                    )
                )
            )

        if objects_became_absent:

            reasons.append(
                "objects became absent: "
                + ", ".join(
                    sorted(
                        objects_became_absent
                    )
                )
            )

        if accessories_appeared:

            reasons.append(
                "accessories appeared: "
                + ", ".join(
                    sorted(
                        accessories_appeared
                    )
                )
            )

        if accessories_reappeared:

            reasons.append(
                "accessories reappeared: "
                + ", ".join(
                    sorted(
                        accessories_reappeared
                    )
                )
            )

        if accessories_became_absent:

            reasons.append(
                "accessories became absent: "
                + ", ".join(
                    sorted(
                        accessories_became_absent
                    )
                )
            )

        if (
            salient_event_changed
            and not meaningful_event
        ):

            reasons.append(
                "salient event visibility changed"
            )

        # =================================================
        # RESULT
        # =================================================

        return {
            "is_first_scene": False,

            # -----------------------------------------
            # ENVIRONMENT
            # -----------------------------------------

            "environment_changed": (
                environment_changed
            ),

            "environment_resolved": (
                environment_resolved
            ),

            "environment_became_uncertain": (
                environment_became_uncertain
            ),

            # -----------------------------------------
            # ACTIVITY
            # -----------------------------------------

            "activity_changed": (
                activity_changed
            ),

            "activity_resolved": (
                activity_resolved
            ),

            "activity_became_uncertain": (
                activity_became_uncertain
            ),

            # -----------------------------------------
            # POSE
            # -----------------------------------------

            "pose_changed": (
                pose_changed
            ),

            "body_state_changed": (
                body_state_changed
            ),

            "body_state_resolved": (
                body_state_resolved
            ),

            "body_state_became_uncertain": (
                body_state_became_uncertain
            ),

            "head_direction_changed": (
                head_direction_changed
            ),

            "head_direction_resolved": (
                head_direction_resolved
            ),

            "head_direction_became_uncertain": (
                head_direction_became_uncertain
            ),

            # -----------------------------------------
            # HANDS
            # -----------------------------------------

            "left_hand_changed": (
                left_hand_changed
            ),

            "right_hand_changed": (
                right_hand_changed
            ),

            "left_hand_interaction_started": (
                left_hand_comparison[
                    "interaction_started"
                ]
            ),

            "left_hand_interaction_ended": (
                left_hand_comparison[
                    "interaction_ended"
                ]
            ),

            "right_hand_interaction_started": (
                right_hand_comparison[
                    "interaction_started"
                ]
            ),

            "right_hand_interaction_ended": (
                right_hand_comparison[
                    "interaction_ended"
                ]
            ),

            # -----------------------------------------
            # OBJECTS
            # -----------------------------------------

            "objects_added": (
                objects_added
            ),

            "objects_removed": (
                objects_removed
            ),

            "raw_objects_added": sorted(
                raw_objects_added
            ),

            "raw_objects_removed": sorted(
                raw_objects_removed
            ),

            "objects_initially_confirmed": sorted(
                objects_initially_confirmed
            ),

            "objects_appeared": sorted(
                objects_appeared
            ),

            "objects_reappeared": sorted(
                objects_reappeared
            ),

            "objects_became_absent": sorted(
                objects_became_absent
            ),

            # -----------------------------------------
            # ACCESSORIES
            # -----------------------------------------

            "accessories_added": (
                accessories_added
            ),

            "accessories_removed": (
                accessories_removed
            ),

            "raw_accessories_added": sorted(
                raw_accessories_added
            ),

            "raw_accessories_removed": sorted(
                raw_accessories_removed
            ),

            "accessories_initially_confirmed": sorted(
                accessories_initially_confirmed
            ),

            "accessories_appeared": sorted(
                accessories_appeared
            ),

            "accessories_reappeared": sorted(
                accessories_reappeared
            ),

            "accessories_became_absent": sorted(
                accessories_became_absent
            ),

            # -----------------------------------------
            # INFORMATION QUALITY
            # -----------------------------------------

            "information_resolved": (
                information_resolved
            ),

            "information_became_uncertain": (
                information_became_uncertain
            ),

            # -----------------------------------------
            # HIGH LEVEL
            # -----------------------------------------

            "salient_event_changed": (
                salient_event_changed
            ),

            "state_changed": (
                state_changed
            ),

            "interaction_changed": (
                interaction_changed
            ),

            "persistent_world_changed": (
                persistent_world_changed
            ),

            "meaningful_event": (
                meaningful_event
            ),

            "major_scene_change": (
                major_scene_change
            ),

            "reason": (
                "; ".join(
                    reasons
                )
                if reasons
                else (
                    "No meaningful semantic change."
                )
            ),
        }

    # =====================================================
    # UNIQUE RECENT SCENES
    # =====================================================

    def unique_recent_scenes(
        self,
        limit: int = 10,
    ):

        scenes = self.recent_scenes(
            limit=50
        )

        results = []

        seen = set()

        for scene in reversed(
            scenes
        ):

            memory_id = (
                scene.get(
                    "memory_id"
                )
            )

            if memory_id is not None:

                key = (
                    "memory",
                    memory_id,
                )

            else:

                key = (
                    "observation",
                    scene.get(
                        "observation",
                        "",
                    )
                    .lower()
                    .strip(),
                )

            if key in seen:
                continue

            seen.add(
                key
            )

            results.append(
                scene
            )

            if len(results) >= limit:
                break

        results.reverse()

        return results

    # =====================================================
    # ACTIVE MEMORY IDS
    # =====================================================

    def active_memory_ids(
        self,
        limit: int = 20,
    ):

        scenes = self.recent_scenes(
            limit=limit
        )

        ids = []

        for scene in scenes:

            memory_id = scene.get(
                "memory_id"
            )

            if (
                memory_id is not None
                and memory_id not in ids
            ):

                ids.append(
                    memory_id
                )

        return ids

    # =====================================================
    # CONTEXT SNAPSHOT
    # =====================================================

    def context_snapshot(
        self,
    ):

        scenes = self.recent_scenes(
            limit=10
        )

        memory_ids = [
            scene.get(
                "memory_id"
            )
            for scene in scenes
            if (
                scene.get(
                    "memory_id"
                )
                is not None
            )
        ]

        frequencies = Counter(
            memory_ids
        )

        return {
            "current_scene": (
                self.current_scene()
            ),

            "previous_scene": (
                self.previous_scene()
            ),

            "recent_scenes": scenes,

            "recent_scene_count": (
                len(
                    scenes
                )
            ),

            "active_memory_ids": (
                list(
                    frequencies.keys()
                )
            ),

            "memory_frequency": (
                dict(
                    frequencies
                )
            ),
        }