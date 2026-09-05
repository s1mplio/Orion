from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from app.companion.memory.scene_models import (
    PersonState,
    SceneObject,
    StructuredScene,
)


@dataclass
class TrackedEntity:
    """
    Persistence state for an object/accessory.

    Lifecycle:

        unknown
          ↓
        candidate
          ↓
        confirmed
          ↓
        missing
          ↓
        absent
          ↓
        candidate
          ↓
        confirmed again

    Important distinction:

    First confirmation:
        Orion learned that an entity belongs to the
        existing scene.

    Reconfirmation after confirmed absence:
        Entity genuinely reappeared and may represent
        an event.
    """

    label: str

    seen_count: int = 0
    miss_count: int = 0

    confirmed: bool = False

    # Has this entity ever previously reached
    # confirmed state?
    ever_confirmed: bool = False

    # Has it been confirmed absent after previously
    # being confirmed present?
    confirmed_absent: bool = False

    last_position: Optional[str] = None
    last_state: Optional[str] = None


class SceneStabilizer:
    """
    Stabilizes noisy StructuredScene output.

    Persistent:
        objects
        accessories

    Dynamic:
        activity
        pose
        head direction
        hand relationships

    No VLM/LLM calls happen here.

    Add hysteresis:
        2 consecutive sightings by default.

    Removal hysteresis:
        3 consecutive misses by default.

    Most importantly:

        first confirmation != appearance event

    Only an entity that was previously confirmed,
    subsequently confirmed absent, and then confirmed
    again is considered "reappeared".
    """

    def __init__(
        self,
        object_add_threshold: int = 2,
        object_miss_threshold: int = 3,
        accessory_add_threshold: int = 2,
        accessory_miss_threshold: int = 3,
    ):
        self.object_add_threshold = (
            object_add_threshold
        )

        self.object_miss_threshold = (
            object_miss_threshold
        )

        self.accessory_add_threshold = (
            accessory_add_threshold
        )

        self.accessory_miss_threshold = (
            accessory_miss_threshold
        )

        self.objects: Dict[
            str,
            TrackedEntity,
        ] = {}

        self.accessories: Dict[
            str,
            TrackedEntity,
        ] = {}

        # ---------------------------------------------
        # Transition metadata
        # ---------------------------------------------
        #
        # These describe what happened DURING the most
        # recent stabilizer update.
        #
        # SceneIntelligence can later use this to
        # distinguish:
        #
        # "Orion learned fan exists"
        #
        # from:
        #
        # "fan disappeared and later came back"

        self._last_changes = {
            "objects_initially_confirmed": set(),
            "objects_reappeared": set(),
            "objects_became_absent": set(),

            "accessories_initially_confirmed": set(),
            "accessories_reappeared": set(),
            "accessories_became_absent": set(),
        }

    # =================================================
    # CHANGE METADATA
    # =================================================

    def _reset_last_changes(
        self,
    ):
        self._last_changes = {
            "objects_initially_confirmed": set(),
            "objects_reappeared": set(),
            "objects_became_absent": set(),

            "accessories_initially_confirmed": set(),
            "accessories_reappeared": set(),
            "accessories_became_absent": set(),
        }

    def last_changes(
        self,
    ) -> Dict[str, List[str]]:
        """
        Return lifecycle changes produced by the most
        recent update().

        Returned as lists so this can be logged /
        serialized easily.
        """

        return {
            key: sorted(value)
            for key, value
            in self._last_changes.items()
        }

    # =================================================
    # LABEL CLEANING
    # =================================================

    def _clean_label(
        self,
        value: Optional[str],
    ) -> Optional[str]:

        if value is None:
            return None

        value = " ".join(
            value
            .lower()
            .strip()
            .split()
        )

        if not value:
            return None

        return value

    # =================================================
    # SMALL ALIAS LAYER
    # =================================================

    def _normalize_label(
        self,
        value: Optional[str],
    ) -> Optional[str]:
        """
        Deliberately tiny alias layer.

        This is NOT intended to become a dictionary
        containing every possible real-world object.

        Stable labels should primarily come from the
        structured VLM prompt.
        """

        value = self._clean_label(
            value
        )

        if value is None:
            return None

        aliases = {
            "chair": "office chair",
            "desk chair": "office chair",
            "computer chair": "office chair",
            "office seat": "office chair",

            "earphone": "earphones",
            "earbud": "earphones",
            "earbuds": "earphones",
            "wired earphone": "earphones",
            "wired earphones": "earphones",
            "wired earbuds": "earphones",

            "fan": "ceiling fan",

            "switch": "wall switch",
            "light switch": "wall switch",
            "switchboard": "wall switch",
            "switch board": "wall switch",

            "phone": "smartphone",
            "mobile": "smartphone",
            "mobile phone": "smartphone",
        }

        return aliases.get(
            value,
            value,
        )

    # =================================================
    # NORMALIZE OBJECTS
    # =================================================

    def _normalize_objects(
        self,
        objects: List[SceneObject],
    ) -> Dict[str, SceneObject]:

        result = {}

        for obj in objects:

            label = self._normalize_label(
                obj.label
            )

            if label is None:
                continue

            result[label] = SceneObject(
                label=label,
                position=obj.position,
                state=obj.state,
            )

        return result

    # =================================================
    # NORMALIZE ACCESSORIES
    # =================================================

    def _normalize_accessories(
        self,
        people: List[PersonState],
    ) -> Set[str]:

        result = set()

        for person in people:

            for accessory in (
                person.visible_accessories
            ):

                label = self._normalize_label(
                    accessory
                )

                if label:
                    result.add(
                        label
                    )

        return result

    # =================================================
    # OBJECT CONFIRMATION
    # =================================================

    def _confirm_object(
        self,
        tracked: TrackedEntity,
    ):
        """
        Entity crossed its add threshold.

        Decide whether this is:

            initial discovery

        or:

            genuine reappearance after confirmed
            absence.
        """

        if tracked.confirmed:
            return

        if tracked.confirmed_absent:
            # Previously existed, was confidently
            # removed, and is now confidently back.
            self._last_changes[
                "objects_reappeared"
            ].add(
                tracked.label
            )

        elif not tracked.ever_confirmed:
            # First time Orion has gathered enough
            # evidence for this object.
            #
            # This is baseline learning, NOT a
            # physical appearance event.
            self._last_changes[
                "objects_initially_confirmed"
            ].add(
                tracked.label
            )

        tracked.confirmed = True
        tracked.ever_confirmed = True
        tracked.confirmed_absent = False
        tracked.miss_count = 0

    # =================================================
    # ACCESSORY CONFIRMATION
    # =================================================

    def _confirm_accessory(
        self,
        tracked: TrackedEntity,
    ):

        if tracked.confirmed:
            return

        if tracked.confirmed_absent:

            self._last_changes[
                "accessories_reappeared"
            ].add(
                tracked.label
            )

        elif not tracked.ever_confirmed:

            self._last_changes[
                "accessories_initially_confirmed"
            ].add(
                tracked.label
            )

        tracked.confirmed = True
        tracked.ever_confirmed = True
        tracked.confirmed_absent = False
        tracked.miss_count = 0

    # =================================================
    # UPDATE OBJECTS
    # =================================================

    def _update_objects(
        self,
        raw_objects: List[SceneObject],
    ) -> List[SceneObject]:

        observed = self._normalize_objects(
            raw_objects
        )

        observed_labels = set(
            observed.keys()
        )

        # ---------------------------------------------
        # OBSERVED
        # ---------------------------------------------

        for label, obj in observed.items():

            tracked = self.objects.get(
                label
            )

            if tracked is None:

                tracked = TrackedEntity(
                    label=label
                )

                self.objects[label] = (
                    tracked
                )

            tracked.seen_count += 1
            tracked.miss_count = 0

            tracked.last_position = (
                obj.position
            )

            tracked.last_state = (
                obj.state
            )

            if (
                not tracked.confirmed
                and tracked.seen_count
                >= self.object_add_threshold
            ):
                self._confirm_object(
                    tracked
                )

        # ---------------------------------------------
        # NOT OBSERVED
        # ---------------------------------------------

        for label, tracked in (
            self.objects.items()
        ):

            if label in observed_labels:
                continue

            # Consecutive positive streak broken.
            tracked.seen_count = 0

            if not tracked.confirmed:
                continue

            tracked.miss_count += 1

            if (
                tracked.miss_count
                >= self.object_miss_threshold
            ):
                tracked.confirmed = False

                tracked.confirmed_absent = True

                self._last_changes[
                    "objects_became_absent"
                ].add(
                    label
                )

        # ---------------------------------------------
        # STABLE RESULT
        # ---------------------------------------------

        stable_objects = []

        for tracked in self.objects.values():

            if not tracked.confirmed:
                continue

            stable_objects.append(
                SceneObject(
                    label=tracked.label,
                    position=(
                        tracked.last_position
                    ),
                    state=(
                        tracked.last_state
                    ),
                )
            )

        stable_objects.sort(
            key=lambda obj: obj.label
        )

        return stable_objects

    # =================================================
    # UPDATE ACCESSORIES
    # =================================================

    def _update_accessories(
        self,
        raw_people: List[PersonState],
    ) -> List[str]:

        observed = (
            self._normalize_accessories(
                raw_people
            )
        )

        # ---------------------------------------------
        # OBSERVED
        # ---------------------------------------------

        for label in observed:

            tracked = (
                self.accessories.get(
                    label
                )
            )

            if tracked is None:

                tracked = TrackedEntity(
                    label=label
                )

                self.accessories[label] = (
                    tracked
                )

            tracked.seen_count += 1
            tracked.miss_count = 0

            if (
                not tracked.confirmed
                and tracked.seen_count
                >= self.accessory_add_threshold
            ):
                self._confirm_accessory(
                    tracked
                )

        # ---------------------------------------------
        # NOT OBSERVED
        # ---------------------------------------------

        for label, tracked in (
            self.accessories.items()
        ):

            if label in observed:
                continue

            tracked.seen_count = 0

            if not tracked.confirmed:
                continue

            tracked.miss_count += 1

            if (
                tracked.miss_count
                >= self.accessory_miss_threshold
            ):
                tracked.confirmed = False

                tracked.confirmed_absent = True

                self._last_changes[
                    "accessories_became_absent"
                ].add(
                    label
                )

        return sorted(
            label
            for label, tracked
            in self.accessories.items()
            if tracked.confirmed
        )

    # =================================================
    # PEOPLE
    # =================================================

    def _update_people(
        self,
        raw_people: List[PersonState],
        stable_accessories: List[str],
    ) -> List[PersonState]:

        stable_people = []

        for index, person in enumerate(
            raw_people
        ):

            # V1:
            # accessories associated with primary
            # person.
            #
            # Later entity persistence will associate
            # accessories per tracked person.
            accessories = (
                stable_accessories
                if index == 0
                else person.visible_accessories
            )

            stable_people.append(
                PersonState(
                    label=person.label,

                    activity=person.activity,

                    pose=person.pose,

                    position=person.position,

                    clothing=person.clothing,

                    visible_accessories=(
                        accessories
                    ),
                )
            )

        return stable_people

    # =================================================
    # MAIN UPDATE
    # =================================================

    def update(
        self,
        raw_scene: StructuredScene,
    ) -> StructuredScene:

        # Metadata always describes THIS update only.
        self._reset_last_changes()

        stable_objects = (
            self._update_objects(
                raw_scene.objects
            )
        )

        stable_accessories = (
            self._update_accessories(
                raw_scene.people
            )
        )

        stable_people = (
            self._update_people(
                raw_scene.people,
                stable_accessories,
            )
        )

        return StructuredScene(
            observation=(
                raw_scene.observation
            ),

            environment=(
                raw_scene.environment
            ),

            people=stable_people,

            objects=stable_objects,

            visible_text=(
                raw_scene.visible_text
            ),

            salient_event=(
                raw_scene.salient_event
            ),
        )

    # =================================================
    # RESET
    # =================================================

    def reset(
        self,
    ):
        """
        A genuine physical scene transition means the
        old persistent entity state should no longer
        define the new scene.
        """

        self.objects.clear()
        self.accessories.clear()

        self._reset_last_changes()

    # =================================================
    # DEBUG
    # =================================================

    def debug_state(
        self,
    ) -> Dict:

        return {
            "objects": {
                label: {
                    "confirmed": (
                        tracked.confirmed
                    ),

                    "ever_confirmed": (
                        tracked.ever_confirmed
                    ),

                    "confirmed_absent": (
                        tracked.confirmed_absent
                    ),

                    "seen_count": (
                        tracked.seen_count
                    ),

                    "miss_count": (
                        tracked.miss_count
                    ),

                    "position": (
                        tracked.last_position
                    ),

                    "state": (
                        tracked.last_state
                    ),
                }
                for label, tracked
                in self.objects.items()
            },

            "accessories": {
                label: {
                    "confirmed": (
                        tracked.confirmed
                    ),

                    "ever_confirmed": (
                        tracked.ever_confirmed
                    ),

                    "confirmed_absent": (
                        tracked.confirmed_absent
                    ),

                    "seen_count": (
                        tracked.seen_count
                    ),

                    "miss_count": (
                        tracked.miss_count
                    ),
                }
                for label, tracked
                in self.accessories.items()
            },

            "last_changes": (
                self.last_changes()
            ),
        }