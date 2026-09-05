from datetime import datetime
from typing import Optional

from app.companion.memory.faiss_memory import FAISSMemory


class MemoryManager:
    """
    Orion long-term memory controller.

    Important distinction:

    - Scene identity is controlled by the vision /
      scene-intelligence layer.

    - FAISS is used for semantic long-term recall.

    A different activity description should NOT
    automatically create or switch physical scene IDs.
    """

    def __init__(self):
        self.store = FAISSMemory(
            max_memories=100
        )

        # Used only when explicitly trying to recover
        # a historical scene, not during normal
        # same-scene continuation.
        self.historical_match_threshold = 0.88

    # =================================================
    # CREATE SCENE MEMORY
    # =================================================

    def create_scene(
        self,
        observation: str,
    ) -> Optional[int]:
        """
        Create a new long-term scene/context memory.

        Call this only when the vision layer determines
        that Orion has entered a genuinely new context.
        """

        if not observation:
            return None

        observation = observation.strip()

        if not observation:
            return None

        memory = self.store.add(
            observation
        )

        if not memory:
            return None

        memory_id = memory.get("id")

        print(
            "NEW_SCENE_MEMORY:",
            memory_id,
        )

        return memory_id

    # =================================================
    # CONTINUE SCENE
    # =================================================

    def continue_scene(
        self,
        memory_id: int,
        confirmed: bool = True,
    ) -> bool:
        """
        Continue observing the same physical context.

        No embedding similarity check is performed.
        """

        if memory_id is None:
            return False

        now = datetime.now().isoformat()

        if confirmed:
            updated = (
                self.store.update_temporal_state(
                    memory_id=memory_id,
                    last_confirmed=now,
                    last_observed=now,
                )
            )
        else:
            updated = (
                self.store.update_temporal_state(
                    memory_id=memory_id,
                    last_observed=now,
                )
            )

        if updated:
            print(
                "SCENE_CONTINUED:",
                memory_id,
            )

        return updated

    # =================================================
    # HISTORICAL SCENE RECOVERY
    # =================================================

    def find_historical_scene(
        self,
        observation: str,
    ) -> Optional[int]:
        """
        Search long-term semantic memory for a strong
        historical match.

        This should be used only when Scene Intelligence
        has already decided that the current physical
        context changed.
        """

        if not observation:
            return None

        results = self.store.search(
            observation,
            limit=1,
        )

        if not results:
            return None

        closest = results[0]

        similarity = closest.get(
            "similarity",
            0.0,
        )

        print(
            "Historical scene similarity:",
            f"{similarity:.3f}",
        )

        if (
            similarity
            < self.historical_match_threshold
        ):
            return None

        memory_id = closest.get("id")

        if memory_id is None:
            return None

        print(
            "HISTORICAL_SCENE_MATCH:",
            memory_id,
        )

        return memory_id

    # =================================================
    # RESOLVE NEW CONTEXT
    # =================================================

    def resolve_new_context(
        self,
        observation: str,
        allow_historical_reuse: bool = True,
    ) -> Optional[int]:
        """
        Called after the vision layer has decided
        that Orion entered a different context.

        Optionally reuse a very strong historical
        scene match. Otherwise create a new one.
        """

        if allow_historical_reuse:
            historical_id = (
                self.find_historical_scene(
                    observation
                )
            )

            if historical_id is not None:
                self.continue_scene(
                    historical_id,
                    confirmed=True,
                )

                return historical_id

        return self.create_scene(
            observation
        )

    # =================================================
    # BACKWARD-COMPATIBLE REMEMBER
    # =================================================

    def remember(
        self,
        observation: str,
        current_memory_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Compatibility helper.

        If a current memory ID exists, Orion assumes
        the caller has already determined that the
        same physical scene is active.

        Therefore:
            current ID -> continue it
            no current ID -> create / recover context

        No semantic similarity is used to override
        an active scene ID.
        """

        if not observation:
            return None

        observation = observation.strip()

        if not observation:
            return None

        if current_memory_id is not None:

            current_memory = (
                self.store.get_by_id(
                    current_memory_id
                )
            )

            if current_memory is not None:

                self.continue_scene(
                    current_memory_id,
                    confirmed=True,
                )

                return current_memory_id

        return self.resolve_new_context(
            observation=observation,
            allow_historical_reuse=True,
        )

    # =================================================
    # MARK OBSERVED
    # =================================================

    def mark_observed(
        self,
        memory_id: int,
    ) -> bool:
        """
        Camera/event layer indicates that the active
        physical context is still present.

        Only last_observed changes.
        """

        return self.continue_scene(
            memory_id=memory_id,
            confirmed=False,
        )

    # =================================================
    # GET BY ID
    # =================================================

    def get_by_id(
        self,
        memory_id: int,
    ):
        return self.store.get_by_id(
            memory_id
        )

    # =================================================
    # SEMANTIC RECALL
    # =================================================

    def recall(
        self,
        query: str,
        limit: int = 5,
    ):
        return self.store.search(
            query,
            limit,
        )

    # =================================================
    # RECENT
    # =================================================

    def recent(
        self,
        limit: int = 10,
    ):
        return self.store.recent(
            limit
        )

    # =================================================
    # TIME RECALL
    # =================================================

    def recent_minutes(
        self,
        minutes: int = 10,
    ):
        return self.store.recent_minutes(
            minutes
        )