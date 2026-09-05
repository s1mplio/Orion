import json
import os
import threading

from datetime import (
    datetime,
    timedelta,
)

from pathlib import Path

from typing import (
    Optional,
    Dict,
    Any,
)


class WorkingMemory:
    """
    Orion short-term chronological working memory.

    This memory persists to JSON so different
    Orion Python processes can share the latest
    short-term state.

    Architecture:

        VisionLoop
            ↓
        working_memory.json
            ↑
        Chat / Context / Proactive systems

    Working memory is:

        - chronological
        - temporary
        - small
        - human-readable
        - cross-process accessible

    Long-term semantic memory remains separate.

    V2 addition:

        current_scene may now also contain:

            structured_scene

        This allows deterministic temporal world
        reasoning to inspect the current objects,
        interactions, environment, etc.
    """

    def __init__(
        self,
        max_events: int = 50,
        retention_minutes: int = 10,
    ):

        self.max_events = (
            max_events
        )

        self.retention_minutes = (
            retention_minutes
        )

        # =================================================
        # STORAGE LOCATION
        # =================================================

        self.base_path = (
            Path(__file__)
            .resolve()
            .parent
        )

        self.file_path = (
            self.base_path
            / "working_memory.json"
        )

        # =================================================
        # THREAD PROTECTION
        # =================================================

        self.lock = (
            threading.RLock()
        )

        self._ensure_file()

    # =====================================================
    # DEFAULT STRUCTURE
    # =====================================================

    def _default_data(
        self,
    ):

        return {
            "current_scene": None,
            "events": [],
        }

    # =====================================================
    # ENSURE FILE
    # =====================================================

    def _ensure_file(
        self,
    ):

        if self.file_path.exists():

            return

        self._write_data(
            self._default_data()
        )

        print(
            "Created Orion working memory:",
            self.file_path,
        )

    # =====================================================
    # READ DATA
    # =====================================================

    def _read_data(
        self,
    ):
        """
        Read the newest version from disk.

        Every public read reloads the JSON file.

        This allows another Python process to write
        new data and this process to immediately see it.
        """

        with self.lock:

            if not self.file_path.exists():

                return (
                    self._default_data()
                )

            try:

                with open(
                    self.file_path,
                    "r",
                    encoding="utf-8",
                ) as file:

                    data = (
                        json.load(
                            file
                        )
                    )

            except (
                json.JSONDecodeError,
                OSError,
            ) as error:

                print(
                    "WORKING_MEMORY_READ_ERROR:",
                    repr(error),
                )

                return (
                    self._default_data()
                )

            if not isinstance(
                data,
                dict,
            ):

                return (
                    self._default_data()
                )

            if (
                "current_scene"
                not in data
            ):

                data[
                    "current_scene"
                ] = None

            if (
                "events"
                not in data
                or
                not isinstance(
                    data["events"],
                    list,
                )
            ):

                data[
                    "events"
                ] = []

            return data

    # =====================================================
    # WRITE DATA
    # =====================================================

    def _write_data(
        self,
        data,
    ):
        """
        Atomic JSON write.

        Data is written to a temporary file first,
        fsynced, then atomically replaces the main file.

        This reduces chances of another process seeing
        a partially written JSON document.
        """

        with self.lock:

            temp_path = (
                self.file_path
                .with_suffix(
                    ".tmp"
                )
            )

            try:

                with open(
                    temp_path,
                    "w",
                    encoding="utf-8",
                ) as file:

                    json.dump(
                        data,
                        file,
                        ensure_ascii=False,
                        indent=2,
                    )

                    file.flush()

                    os.fsync(
                        file.fileno()
                    )

                os.replace(
                    temp_path,
                    self.file_path,
                )

            except OSError as error:

                print(
                    "WORKING_MEMORY_WRITE_ERROR:",
                    repr(error),
                )

                try:

                    if temp_path.exists():

                        temp_path.unlink()

                except OSError:

                    pass

    # =====================================================
    # CLEANUP
    # =====================================================

    def _cleanup(
        self,
        data,
    ):
        """
        Remove expired events and enforce the
        maximum number of short-term events.
        """

        cutoff = (
            datetime.now()
            - timedelta(
                minutes=(
                    self.retention_minutes
                )
            )
        )

        valid_events = []

        for event in data.get(
            "events",
            [],
        ):

            timestamp_text = (
                event.get(
                    "timestamp"
                )
            )

            if not timestamp_text:

                continue

            try:

                timestamp = (
                    datetime.fromisoformat(
                        timestamp_text
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

            if timestamp >= cutoff:

                valid_events.append(
                    event
                )

        valid_events = (
            valid_events[
                -self.max_events:
            ]
        )

        data[
            "events"
        ] = valid_events

        return data

    # =====================================================
    # ADD EVENT
    # =====================================================

    def add_event(
        self,
        event_type: str,
        observation: Optional[
            str
        ] = None,
        memory_id: Optional[
            int
        ] = None,
        metadata: Optional[
            dict
        ] = None,
    ):

        if not event_type:

            return None

        event = {
            "timestamp": (
                datetime.now()
                .isoformat()
            ),

            "event_type": (
                event_type
            ),

            "memory_id": (
                memory_id
            ),

            "observation": (
                observation
            ),

            "metadata": (
                metadata
                or {}
            ),
        }

        with self.lock:

            data = (
                self._read_data()
            )

            data = (
                self._cleanup(
                    data
                )
            )

            data[
                "events"
            ].append(
                event
            )

            data[
                "events"
            ] = (
                data["events"][
                    -self.max_events:
                ]
            )

            self._write_data(
                data
            )

        print(
            "WORKING_MEMORY_EVENT:",
            event_type,
        )

        return event

    # =====================================================
    # SET CURRENT SCENE
    # =====================================================

    def set_current_scene(
        self,
        observation: str,
        memory_id: Optional[
            int
        ],
        generation: Optional[
            int
        ] = None,
        structured_scene: Optional[
            Dict[str, Any]
        ] = None,
    ):
        """
        Store Orion's authoritative current scene.

        V2 addition:

            structured_scene

        This contains the complete stabilized scene:

            environment
            people
            activity
            pose
            objects
            visible text
            salient event

        This means temporal world reasoning does not
        need another VLM call to understand what
        currently exists.
        """

        now = (
            datetime.now()
            .isoformat()
        )

        if isinstance(
            structured_scene,
            dict,
        ):

            scene_payload = (
                structured_scene
            )

        else:

            scene_payload = None

        scene = {
            "timestamp": (
                now
            ),

            "memory_id": (
                memory_id
            ),

            "generation": (
                generation
            ),

            "observation": (
                observation
            ),

            "structured_scene": (
                scene_payload
            ),
        }

        event = {
            "timestamp": (
                now
            ),

            "event_type": (
                "SCENE_ESTABLISHED"
            ),

            "memory_id": (
                memory_id
            ),

            "observation": (
                observation
            ),

            "metadata": {
                "generation": (
                    generation
                ),
            },
        }

        with self.lock:

            data = (
                self._read_data()
            )

            data = (
                self._cleanup(
                    data
                )
            )

            data[
                "current_scene"
            ] = scene

            data[
                "events"
            ].append(
                event
            )

            data[
                "events"
            ] = (
                data["events"][
                    -self.max_events:
                ]
            )

            self._write_data(
                data
            )

        print(
            "WORKING_MEMORY_CURRENT_SCENE:",
            memory_id,
        )

        return scene

    # =====================================================
    # CLEAR CURRENT SCENE
    # =====================================================

    def clear_current_scene(
        self,
        reason: str = (
            "scene_transition"
        ),
    ):

        now = (
            datetime.now()
            .isoformat()
        )

        with self.lock:

            data = (
                self._read_data()
            )

            data = (
                self._cleanup(
                    data
                )
            )

            old_scene = (
                data.get(
                    "current_scene"
                )
            )

            data[
                "current_scene"
            ] = None

            event = {
                "timestamp": (
                    now
                ),

                "event_type": (
                    "SCENE_CLEARED"
                ),

                "memory_id": (
                    old_scene.get(
                        "memory_id"
                    )
                    if old_scene
                    else None
                ),

                "observation": (
                    old_scene.get(
                        "observation"
                    )
                    if old_scene
                    else None
                ),

                "metadata": {
                    "reason": (
                        reason
                    ),
                },
            }

            data[
                "events"
            ].append(
                event
            )

            data[
                "events"
            ] = (
                data["events"][
                    -self.max_events:
                ]
            )

            self._write_data(
                data
            )

        print(
            "WORKING_MEMORY_SCENE_CLEARED:",
            reason,
        )

    # =====================================================
    # GET CURRENT SCENE
    # =====================================================

    def get_current_scene(
        self,
    ):

        data = (
            self._read_data()
        )

        scene = (
            data.get(
                "current_scene"
            )
        )

        if scene is None:

            return None

        return dict(
            scene
        )

    # =====================================================
    # RECENT EVENTS
    # =====================================================

    def recent(
        self,
        limit: int = 20,
    ):

        if limit <= 0:

            return []

        data = (
            self._read_data()
        )

        data = (
            self._cleanup(
                data
            )
        )

        events = (
            data.get(
                "events",
                [],
            )
        )

        return [
            dict(event)
            for event
            in events[
                -limit:
            ]
        ]

    # =====================================================
    # RECENT MINUTES
    # =====================================================

    def recent_minutes(
        self,
        minutes: int = 5,
    ):

        if minutes <= 0:

            return []

        cutoff = (
            datetime.now()
            - timedelta(
                minutes=minutes
            )
        )

        data = (
            self._read_data()
        )

        results = []

        for event in data.get(
            "events",
            [],
        ):

            timestamp_text = (
                event.get(
                    "timestamp"
                )
            )

            if not timestamp_text:

                continue

            try:

                timestamp = (
                    datetime.fromisoformat(
                        timestamp_text
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

            if timestamp >= cutoff:

                results.append(
                    dict(
                        event
                    )
                )

        return results

    # =====================================================
    # PREVIOUS SCENE
    # =====================================================

    def previous_scene(
        self,
    ):
        """
        Return the SCENE_ESTABLISHED event immediately
        before the latest SCENE_ESTABLISHED event.

        Example:

            person
                ↓
            fan
                ↓
            tube light

        previous_scene() -> fan
        """

        data = (
            self._read_data()
        )

        events = (
            data.get(
                "events",
                [],
            )
        )

        scene_events = [
            event
            for event
            in events
            if (
                event.get(
                    "event_type"
                )
                == "SCENE_ESTABLISHED"
            )
        ]

        if len(
            scene_events
        ) < 2:

            return None

        return dict(
            scene_events[-2]
        )

    # =====================================================
    # LAST SCENE
    # =====================================================

    def last_scene(
        self,
    ):
        """
        Return the newest established scene event.
        """

        data = (
            self._read_data()
        )

        for event in reversed(
            data.get(
                "events",
                [],
            )
        ):

            if (
                event.get(
                    "event_type"
                )
                == "SCENE_ESTABLISHED"
            ):

                return dict(
                    event
                )

        return None

    # =====================================================
    # CLEAR ALL
    # =====================================================

    def clear(
        self,
    ):
        """
        Clear short-term memory.

        Useful during development and testing.
        """

        self._write_data(
            self._default_data()
        )

        print(
            "WORKING_MEMORY_CLEARED"
        )