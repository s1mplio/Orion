from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import json
import os
import tempfile
import threading


# =========================================================
# GOAL MODEL
# =========================================================

@dataclass
class Goal:
    id: int
    description: str
    created_at: str

    status: str = "active"

    relevant_objects: List[str] = field(
        default_factory=list
    )

    instruction: Optional[str] = None

    source: str = "user"

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "created_at": self.created_at,
            "status": self.status,
            "relevant_objects": list(
                self.relevant_objects
            ),
            "instruction": self.instruction,
            "source": self.source,
            "metadata": dict(
                self.metadata
            ),
            "completed_at": self.completed_at,
        }


# =========================================================
# GOAL CONTEXT SNAPSHOT
# =========================================================

@dataclass
class GoalContextSnapshot:
    generated_at: str

    active_goals: List[
        Dict[str, Any]
    ]

    active_goal_count: int

    relevant_objects: List[str]

    active_instructions: List[str]

    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "active_goals": list(
                self.active_goals
            ),
            "active_goal_count": (
                self.active_goal_count
            ),
            "relevant_objects": list(
                self.relevant_objects
            ),
            "active_instructions": list(
                self.active_instructions
            ),
            "confidence": self.confidence,
        }


# =========================================================
# GOAL CONTEXT
# =========================================================

class GoalContext:
    """
    Shared explicit user-goal context for Orion.

    This component stores things the user has explicitly
    said matter.

    Examples:

        Goal:
            "leave for office"

        Relevant object:
            "laptop"

        Instruction:
            "remind me not to forget my laptop"


    IMPORTANT:

    GoalContext does NOT infer goals from vision.

    Vision may provide physical evidence later, but goals
    should originate from:

        - explicit user statements
        - trusted conversation logic
        - trusted application logic


    =====================================================
    CROSS-PROCESS STORAGE
    =====================================================

    Goals are persisted to goal_context.json.

    Public reads reload the JSON file so multiple Orion
    processes can observe the same goal state.

    Public mutations reload the latest state before
    modifying it and then atomically save the result.
    """

    VALID_STATUSES = {
        "active",
        "completed",
        "cancelled",
    }

    def __init__(
        self,
        max_goals: int = 50,
        file_path: Optional[str] = None,
    ):

        self.max_goals = max(
            1,
            int(max_goals),
        )

        self._lock = (
            threading.RLock()
        )

        # =================================================
        # STORAGE PATH
        # =================================================

        if file_path:

            self.file_path = Path(
                file_path
            )

        else:

            self.file_path = (
                Path(__file__)
                .resolve()
                .parent
                / "goal_context.json"
            )

        self.file_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # =================================================
        # IN-MEMORY REPRESENTATION
        # =================================================

        self._goals: Dict[
            int,
            Goal,
        ] = {}

        self._next_id = 1

        # =================================================
        # INITIAL LOAD
        # =================================================

        with self._lock:

            self._load_from_disk()

            if not self.file_path.exists():

                self._save_to_disk()

    # =====================================================
    # ADD GOAL
    # =====================================================

    def add_goal(
        self,
        description: str,
        relevant_objects: Optional[
            List[str]
        ] = None,
        instruction: Optional[str] = None,
        source: str = "user",
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ) -> Goal:

        description = str(
            description
            or ""
        ).strip()

        if not description:
            raise ValueError(
                "Goal description cannot be empty."
            )

        source = str(
            source
            or "user"
        ).strip()

        if not source:
            source = "user"

        clean_objects = (
            self._clean_objects(
                relevant_objects
                or []
            )
        )

        clean_instruction = (
            str(
                instruction
                or ""
            ).strip()
            or None
        )

        clean_metadata = (
            dict(metadata)
            if isinstance(
                metadata,
                dict,
            )
            else {}
        )

        with self._lock:

            # Always reload before mutation so another
            # process's recent changes are visible.
            self._load_from_disk()

            goal = Goal(
                id=self._next_id,

                description=(
                    description
                ),

                created_at=(
                    datetime.now()
                    .isoformat()
                ),

                status="active",

                relevant_objects=(
                    clean_objects
                ),

                instruction=(
                    clean_instruction
                ),

                source=(
                    source
                ),

                metadata=(
                    clean_metadata
                ),
            )

            self._goals[
                goal.id
            ] = goal

            self._next_id += 1

            self._trim_if_needed()

            self._save_to_disk()

            return Goal(
                **goal.to_dict()
            )

    # =====================================================
    # GET GOAL
    # =====================================================

    def get_goal(
        self,
        goal_id: int,
    ) -> Optional[Goal]:

        with self._lock:

            self._load_from_disk()

            goal = self._goals.get(
                int(goal_id)
            )

            if goal is None:
                return None

            return Goal(
                **goal.to_dict()
            )

    # =====================================================
    # ACTIVE GOALS
    # =====================================================

    def active_goals(
        self,
    ) -> List[Goal]:

        with self._lock:

            self._load_from_disk()

            goals = [
                goal
                for goal
                in self._goals.values()
                if goal.status == "active"
            ]

            goals.sort(
                key=lambda goal: (
                    goal.id
                )
            )

            return [
                Goal(
                    **goal.to_dict()
                )
                for goal
                in goals
            ]

    # =====================================================
    # ALL GOALS
    # =====================================================

    def all_goals(
        self,
    ) -> List[Goal]:

        with self._lock:

            self._load_from_disk()

            goals = list(
                self._goals.values()
            )

            goals.sort(
                key=lambda goal: (
                    goal.id
                )
            )

            return [
                Goal(
                    **goal.to_dict()
                )
                for goal
                in goals
            ]

    # =====================================================
    # COMPLETE
    # =====================================================

    def complete_goal(
        self,
        goal_id: int,
    ) -> bool:

        return self._set_status(
            goal_id=goal_id,
            status="completed",
        )

    # =====================================================
    # CANCEL
    # =====================================================

    def cancel_goal(
        self,
        goal_id: int,
    ) -> bool:

        return self._set_status(
            goal_id=goal_id,
            status="cancelled",
        )

    # =====================================================
    # REACTIVATE
    # =====================================================

    def reactivate_goal(
        self,
        goal_id: int,
    ) -> bool:

        return self._set_status(
            goal_id=goal_id,
            status="active",
        )

    # =====================================================
    # GOALS FOR OBJECT
    # =====================================================

    def goals_for_object(
        self,
        object_label: str,
    ) -> List[Goal]:

        target = str(
            object_label
            or ""
        ).strip().lower()

        if not target:
            return []

        with self._lock:

            self._load_from_disk()

            matches = []

            for goal in (
                self._goals.values()
            ):

                if (
                    goal.status
                    != "active"
                ):
                    continue

                for label in (
                    goal.relevant_objects
                ):

                    if (
                        str(label)
                        .strip()
                        .lower()
                        ==
                        target
                    ):

                        matches.append(
                            Goal(
                                **goal.to_dict()
                            )
                        )

                        break

            matches.sort(
                key=lambda goal: (
                    goal.id
                )
            )

            return matches

    # =====================================================
    # SNAPSHOT
    # =====================================================

    def snapshot(
        self,
    ) -> GoalContextSnapshot:

        with self._lock:

            self._load_from_disk()

            active = [
                goal
                for goal
                in self._goals.values()
                if goal.status == "active"
            ]

            active.sort(
                key=lambda goal: (
                    goal.id
                )
            )

            # =============================================
            # ACTIVE RELEVANT OBJECTS
            # =============================================

            relevant_objects = []

            seen_objects = set()

            for goal in active:

                for label in (
                    goal.relevant_objects
                ):

                    clean = str(
                        label
                    ).strip()

                    if not clean:
                        continue

                    key = clean.lower()

                    if key in seen_objects:
                        continue

                    seen_objects.add(
                        key
                    )

                    relevant_objects.append(
                        clean
                    )

            # =============================================
            # ACTIVE INSTRUCTIONS
            # =============================================

            active_instructions = []

            seen_instructions = set()

            for goal in active:

                instruction = str(
                    goal.instruction
                    or ""
                ).strip()

                if not instruction:
                    continue

                key = (
                    instruction.lower()
                )

                if (
                    key
                    in seen_instructions
                ):
                    continue

                seen_instructions.add(
                    key
                )

                active_instructions.append(
                    instruction
                )

            confidence = (
                self._confidence(
                    active_goals=active,
                    relevant_objects=(
                        relevant_objects
                    ),
                    active_instructions=(
                        active_instructions
                    ),
                )
            )

            return GoalContextSnapshot(
                generated_at=(
                    datetime.now()
                    .isoformat()
                ),

                active_goals=[
                    goal.to_dict()
                    for goal
                    in active
                ],

                active_goal_count=len(
                    active
                ),

                relevant_objects=(
                    relevant_objects
                ),

                active_instructions=(
                    active_instructions
                ),

                confidence=(
                    confidence
                ),
            )

    # =====================================================
    # CLEAR
    # =====================================================

    def clear(
        self,
    ):

        with self._lock:

            # Reload first so this method is explicitly
            # operating on the latest shared state.
            self._load_from_disk()

            self._goals = {}

            self._next_id = 1

            self._save_to_disk()

    # =====================================================
    # SET STATUS
    # =====================================================

    def _set_status(
        self,
        goal_id: int,
        status: str,
    ) -> bool:

        if (
            status
            not in self.VALID_STATUSES
        ):
            raise ValueError(
                f"Invalid goal status: {status}"
            )

        try:
            goal_id = int(
                goal_id
            )

        except Exception:
            return False

        with self._lock:

            self._load_from_disk()

            goal = self._goals.get(
                goal_id
            )

            if goal is None:
                return False

            goal.status = status

            if status == "completed":

                goal.completed_at = (
                    datetime.now()
                    .isoformat()
                )

            else:

                goal.completed_at = None

            self._save_to_disk()

            return True

    # =====================================================
    # CLEAN OBJECT LABELS
    # =====================================================

    def _clean_objects(
        self,
        objects: List[str],
    ) -> List[str]:

        result = []

        seen = set()

        for value in objects:

            label = str(
                value
                or ""
            ).strip()

            if not label:
                continue

            key = (
                label.lower()
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            result.append(
                label
            )

        return result

    # =====================================================
    # TRIM
    # =====================================================

    def _trim_if_needed(
        self,
    ):

        while (
            len(self._goals)
            >
            self.max_goals
        ):

            inactive = [
                goal
                for goal
                in self._goals.values()
                if goal.status
                != "active"
            ]

            if inactive:

                oldest = min(
                    inactive,
                    key=lambda goal: (
                        goal.id
                    ),
                )

            else:

                oldest = min(
                    self._goals.values(),
                    key=lambda goal: (
                        goal.id
                    ),
                )

            self._goals.pop(
                oldest.id,
                None,
            )

    # =====================================================
    # CONFIDENCE
    # =====================================================

    def _confidence(
        self,
        active_goals: List[Goal],
        relevant_objects: List[str],
        active_instructions: List[str],
    ) -> float:

        if not active_goals:
            return 0.0

        confidence = 0.50

        if relevant_objects:
            confidence += 0.20

        if active_instructions:
            confidence += 0.30

        return min(
            confidence,
            1.0,
        )

    # =====================================================
    # LOAD
    # =====================================================

    def _load_from_disk(
        self,
    ):

        if not self.file_path.exists():

            self._goals = {}

            self._next_id = 1

            return

        try:

            raw_text = (
                self.file_path
                .read_text(
                    encoding="utf-8"
                )
                .strip()
            )

            if not raw_text:

                self._goals = {}

                self._next_id = 1

                return

            data = json.loads(
                raw_text
            )

        except Exception as exc:

            print(
                "GOAL_CONTEXT_READ_ERROR:",
                repr(exc),
            )

            # Keep existing in-memory state rather than
            # destroying it if the file cannot be read.
            return

        # =================================================
        # SUPPORT CURRENT STORAGE FORMAT
        # =================================================

        if isinstance(
            data,
            dict,
        ):

            raw_goals = (
                data.get(
                    "goals",
                    []
                )
            )

        elif isinstance(
            data,
            list,
        ):

            # Backward-friendly fallback.
            raw_goals = data

        else:

            raw_goals = []

        loaded_goals: Dict[
            int,
            Goal,
        ] = {}

        max_id = 0

        for raw_goal in (
            raw_goals
        ):

            if not isinstance(
                raw_goal,
                dict,
            ):
                continue

            try:

                goal_id = int(
                    raw_goal.get(
                        "id"
                    )
                )

            except Exception:
                continue

            if goal_id <= 0:
                continue

            description = str(
                raw_goal.get(
                    "description"
                )
                or ""
            ).strip()

            if not description:
                continue

            status = str(
                raw_goal.get(
                    "status",
                    "active",
                )
                or "active"
            ).strip().lower()

            if (
                status
                not in self.VALID_STATUSES
            ):

                status = "active"

            created_at = str(
                raw_goal.get(
                    "created_at"
                )
                or datetime.now()
                .isoformat()
            )

            relevant_objects = (
                raw_goal.get(
                    "relevant_objects",
                    [],
                )
            )

            if not isinstance(
                relevant_objects,
                list,
            ):

                relevant_objects = []

            metadata = (
                raw_goal.get(
                    "metadata",
                    {},
                )
            )

            if not isinstance(
                metadata,
                dict,
            ):

                metadata = {}

            instruction = (
                str(
                    raw_goal.get(
                        "instruction"
                    )
                    or ""
                ).strip()
                or None
            )

            source = str(
                raw_goal.get(
                    "source",
                    "user",
                )
                or "user"
            ).strip()

            completed_at = (
                raw_goal.get(
                    "completed_at"
                )
            )

            if completed_at is not None:

                completed_at = str(
                    completed_at
                )

            goal = Goal(
                id=goal_id,

                description=(
                    description
                ),

                created_at=(
                    created_at
                ),

                status=(
                    status
                ),

                relevant_objects=(
                    self._clean_objects(
                        relevant_objects
                    )
                ),

                instruction=(
                    instruction
                ),

                source=(
                    source
                ),

                metadata=(
                    metadata
                ),

                completed_at=(
                    completed_at
                ),
            )

            loaded_goals[
                goal_id
            ] = goal

            max_id = max(
                max_id,
                goal_id,
            )

        self._goals = (
            loaded_goals
        )

        self._next_id = (
            max_id + 1
            if max_id > 0
            else 1
        )

    # =====================================================
    # SAVE
    # =====================================================

    def _save_to_disk(
        self,
    ):

        data = {
            "version": 1,

            "updated_at": (
                datetime.now()
                .isoformat()
            ),

            "goals": [
                goal.to_dict()
                for goal
                in sorted(
                    self._goals.values(),
                    key=lambda goal: (
                        goal.id
                    ),
                )
            ],
        }

        temp_path = None

        try:

            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                delete=False,
                dir=str(
                    self.file_path.parent
                ),
                prefix=(
                    self.file_path.name
                    + "."
                ),
                suffix=".tmp",
            ) as temp_file:

                json.dump(
                    data,
                    temp_file,
                    ensure_ascii=False,
                    indent=2,
                )

                temp_file.flush()

                os.fsync(
                    temp_file.fileno()
                )

                temp_path = Path(
                    temp_file.name
                )

            os.replace(
                str(temp_path),
                str(self.file_path),
            )

        except Exception as exc:

            print(
                "GOAL_CONTEXT_WRITE_ERROR:",
                repr(exc),
            )

            if (
                temp_path is not None
                and
                temp_path.exists()
            ):

                try:

                    temp_path.unlink()

                except Exception:
                    pass

            raise