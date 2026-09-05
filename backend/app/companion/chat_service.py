import re

from app.services.llm_service import LLMService

from app.companion.memory.shared_memory import (
    memory_manager,
    working_memory,
    context_reasoner,
    goal_context,
)

from app.companion.context.goal_extractor import (
    GoalExtractor,
)


class CompanionChatService:
    """
    Orion conversational brain.

    Context priority:

    1. Context Reasoner
       Interpreted current/recent situation.

    2. Working memory
       Recent chronological events.

    3. Temporal semantic memory
       Memories observed within a requested time window.

    4. FAISS semantic memory
       Older memories related by meaning.

    5. Explicit user goals
       Goals, reminders and instructions explicitly
       provided through conversation.

    IMPORTANT:

    Goal extraction does NOT make another LLM call.

    The same conversational LLM response contains:

        - the normal conversational answer
        - an optional structured goal block

    GoalExtractor parses that block locally.

    Therefore there is still exactly ONE conversational
    LLM call per chat request.
    """

    def __init__(
        self,
    ):

        self.llm = (
            LLMService()
        )

        self.goal_extractor = (
            GoalExtractor()
        )

    # =====================================================
    # CHAT
    # =====================================================

    def chat(
        self,
        question: str,
    ):

        if not question:

            return (
                "Please ask me something."
            )

        question = (
            question.strip()
        )

        if not question:

            return (
                "Please ask me something."
            )

        # =================================================
        # CONTEXT REASONER
        # =================================================

        context_snapshot = (
            context_reasoner
            .snapshot()
        )

        reasoning_context = (
            self._format_context_snapshot(
                context_snapshot
            )
        )

        # =================================================
        # CURRENT WORKING CONTEXT
        # =================================================

        current_scene = (
            working_memory
            .get_current_scene()
        )

        previous_scene = (
            working_memory
            .previous_scene()
        )

        recent_events = (
            working_memory
            .recent(
                limit=15
            )
        )

        # =================================================
        # ACTIVE GOALS
        # =================================================

        active_goals = (
            self._get_active_goals()
        )

        goal_context_text = (
            self._format_active_goals(
                active_goals
            )
        )

        # =================================================
        # TIME QUERY
        # =================================================

        requested_minutes = (
            self._extract_minutes(
                question
            )
        )

        temporal_memories = []

        if (
            requested_minutes
            is not None
        ):

            print(
                "Time-based memory query:",
                (
                    f"last "
                    f"{requested_minutes} minutes"
                ),
            )

            temporal_memories = (
                memory_manager
                .recent_minutes(
                    requested_minutes
                )
            )

        # =================================================
        # SEMANTIC FAISS SEARCH
        # =================================================

        semantic_memories = (
            memory_manager
            .recall(
                question,
                limit=5,
            )
        )

        # =================================================
        # FORMAT CONTEXT
        # =================================================

        current_scene_context = (
            self._format_current_scene(
                current_scene
            )
        )

        previous_scene_context = (
            self._format_previous_scene(
                previous_scene
            )
        )

        working_context = (
            self._format_working_memory(
                recent_events
            )
        )

        temporal_context = (
            self._format_semantic_memories(
                temporal_memories
            )
        )

        semantic_context = (
            self._format_semantic_memories(
                semantic_memories,
                include_similarity=True,
            )
        )

        # =================================================
        # DEBUG
        # =================================================

        print(
            "\n=============================="
        )

        print(
            "CONTEXT REASONER"
        )

        print(
            "=============================="
        )

        print(
            reasoning_context
        )

        print(
            "\n=============================="
        )

        print(
            "CURRENT SCENE"
        )

        print(
            "=============================="
        )

        print(
            current_scene_context
        )

        print(
            "\n=============================="
        )

        print(
            "PREVIOUS SCENE"
        )

        print(
            "=============================="
        )

        print(
            previous_scene_context
        )

        print(
            "\n=============================="
        )

        print(
            "WORKING MEMORY"
        )

        print(
            "=============================="
        )

        print(
            working_context
        )

        print(
            "\n=============================="
        )

        print(
            "ACTIVE GOALS"
        )

        print(
            "=============================="
        )

        print(
            goal_context_text
        )

        if (
            requested_minutes
            is not None
        ):

            print(
                "\n=============================="
            )

            print(
                "TIME-BASED MEMORIES"
            )

            print(
                "=============================="
            )

            print(
                temporal_context
            )

        print(
            "\n=============================="
        )

        print(
            "SEMANTIC MEMORIES"
        )

        print(
            "=============================="
        )

        print(
            semantic_context
        )

        print(
            "==============================\n"
        )

        # =================================================
        # SINGLE CONVERSATIONAL LLM PROMPT
        # =================================================

        prompt = f"""
You are Orion, a contextual AI companion with visual memory.

The user said:

{question}


INTERPRETED CURRENT CONTEXT:

{reasoning_context}


CURRENT VISUAL SCENE:

{current_scene_context}


PREVIOUS VISUAL SCENE:

{previous_scene_context}


RECENT CHRONOLOGICAL WORKING MEMORY:

{working_context}


ACTIVE USER GOALS:

{goal_context_text}


MEMORIES FROM THE REQUESTED TIME WINDOW:

{temporal_context}


SEMANTICALLY RELATED LONG-TERM MEMORIES:

{semantic_context}


============================================================
CONVERSATIONAL RESPONSE
============================================================

Answer naturally using Orion's available context.

Rules:

1. INTERPRETED CURRENT CONTEXT is Orion's deterministic
   summary of the current physical context and recent
   actions.

2. Prefer CURRENT VISUAL SCENE when the user asks about
   what is happening or visible now.

3. Prefer PREVIOUS VISUAL SCENE and recent chronological
   memory when the user asks what happened before.

4. RECENT ACTIONS are chronological. Do not treat all
   recent actions as happening simultaneously.

5. ACTIVE INTERACTIONS describe the latest interpreted
   physical interactions.

6. Do not claim an older action is still happening merely
   because it appears in recent memory.

7. Prefer time-window memories when the user explicitly
   asks about the last N minutes or hours.

8. Use semantically related long-term memories for older
   remembered context.

9. ACTIVE USER GOALS are explicit goals previously given
   by the user. They may help answer questions about the
   user's plans or reminders.

10. Do not invent objects, people, actions, locations,
    intentions, causes, plans or details unsupported by
    the supplied information.

11. Distinguish between:
    - currently happening,
    - recently happened,
    - remembered from earlier,
    - explicitly planned by the user.

12. If the available context genuinely cannot answer the
    question, say that you do not have enough context.

13. Do not mention:
    - FAISS,
    - vector databases,
    - embeddings,
    - prompts,
    - context snapshots,
    - working-memory implementation,
    - agents,
    - generation IDs,
    - internal confidence calculations,
    - goal extraction implementation.

14. Answer naturally and concisely like a companion.


============================================================
OPTIONAL EXPLICIT GOAL CAPTURE
============================================================

In addition to answering the user, determine whether the
CURRENT USER MESSAGE explicitly creates a future goal,
task, reminder or instruction that Orion should remember.

IMPORTANT:

Only capture a goal when it is explicitly supported by the
CURRENT USER MESSAGE.

Do NOT create a goal merely because:

- an object is visible,
- the user is performing an action,
- Orion thinks something would be useful,
- an old memory suggests a possible intention,
- an existing goal is mentioned by the supplied context.

Do not infer hidden intentions.

Examples that SHOULD create a goal:

"I'm leaving for work soon. Remind me not to forget my
watch."

"I need to submit my report today."

"Make sure I take my keys when I leave."

"I want to finish the Orion project this week."

"Remind me to take my medicine before I go."

Examples that should NOT create a goal:

"What am I holding?"

"Where did I put my watch?"

"I'm holding my keys."

"What was I doing before?"

"Do you remember seeing my laptop?"

If the current message explicitly creates a goal, append
EXACTLY ONE block after the conversational response:

<ORION_GOAL>
{{
  "has_goal": true,
  "description": "short description of the explicit goal",
  "relevant_objects": [
    "physical object if explicitly relevant"
  ],
  "instruction": "explicit reminder/instruction if one exists, otherwise null"
}}
</ORION_GOAL>

Rules for the goal block:

1. Output valid JSON.

2. description must be concise.

3. relevant_objects must contain only concrete physical
   objects explicitly relevant to the user's goal.

4. Do not put abstract concepts, locations or actions in
   relevant_objects.

5. Do not invent relevant objects.

6. instruction should preserve the user's explicit
   reminder/instruction.

7. If there is no explicit reminder instruction, use null.

8. Do not include completed or past actions as new goals.

9. Do not output a goal block at all when the current
   message does not explicitly establish a goal.

10. Never mention the ORION_GOAL block in the
    conversational answer.
"""

        # =================================================
        # EXACTLY ONE LLM CALL
        # =================================================

        raw_answer = (
            self.llm.generate(
                prompt
            )
        )

        if not raw_answer:

            return (
                "I don't have enough context "
                "to answer that."
            )

        # =================================================
        # LOCAL GOAL EXTRACTION
        # =================================================

        extraction = (
            self.goal_extractor
            .parse(
                raw_answer
            )
        )

        # =================================================
        # STORE EXPLICIT GOAL
        # =================================================

        if extraction.has_goal:

            self._store_extracted_goal(
                extraction
            )

        # =================================================
        # USER-FACING ANSWER
        # =================================================

        answer = (
            extraction.answer
            .strip()
        )

        if not answer:

            return (
                "Okay."
            )

        return answer

    # =====================================================
    # STORE EXTRACTED GOAL
    # =====================================================

    def _store_extracted_goal(
        self,
        extraction,
    ):

        description = (
            extraction.description
            or ""
        ).strip()

        if not description:

            return

        relevant_objects = (
            extraction.relevant_objects
            or []
        )

        instruction = (
            extraction.instruction
        )

        # =================================================
        # SIMPLE DUPLICATE PROTECTION
        #
        # We do not want:
        #
        #   "don't forget my watch"
        #
        # to create another identical active goal every
        # time the same message is processed.
        # =================================================

        try:

            active_goals = (
                goal_context
                .active_goals()
            )

        except Exception as exc:

            print(
                "GOAL_CONTEXT_READ_ERROR:",
                repr(exc),
            )

            active_goals = []

        normalized_description = (
            self._normalize_goal_text(
                description
            )
        )

        normalized_instruction = (
            self._normalize_goal_text(
                instruction
            )
        )

        for goal in active_goals:

            if hasattr(
                goal,
                "to_dict",
            ):

                data = (
                    goal.to_dict()
                )

            elif isinstance(
                goal,
                dict,
            ):

                data = goal

            else:

                continue

            existing_description = (
                self._normalize_goal_text(
                    data.get(
                        "description"
                    )
                )
            )

            existing_instruction = (
                self._normalize_goal_text(
                    data.get(
                        "instruction"
                    )
                )
            )

            if (
                existing_description
                ==
                normalized_description
                and
                existing_instruction
                ==
                normalized_instruction
            ):

                print(
                    "GOAL_CAPTURE_DUPLICATE_SKIPPED:",
                    description,
                )

                return

        # =================================================
        # SAVE GOAL
        # =================================================

        try:

            goal = (
                goal_context
                .add_goal(
                    description=(
                        description
                    ),

                    relevant_objects=(
                        relevant_objects
                    ),

                    instruction=(
                        instruction
                    ),

                    source=(
                        "conversation"
                    ),

                    metadata={
                        "capture_method": (
                            "single_chat_llm"
                        ),
                    },
                )
            )

        except Exception as exc:

            print(
                "GOAL_CAPTURE_ERROR:",
                repr(exc),
            )

            return

        # =================================================
        # DEBUG
        # =================================================

        if hasattr(
            goal,
            "to_dict",
        ):

            goal_data = (
                goal.to_dict()
            )

        elif isinstance(
            goal,
            dict,
        ):

            goal_data = goal

        else:

            goal_data = {
                "description": (
                    description
                ),

                "relevant_objects": (
                    relevant_objects
                ),

                "instruction": (
                    instruction
                ),
            }

        print(
            "\n================================"
        )

        print(
            "ORION GOAL CAPTURED"
        )

        print(
            "================================"
        )

        print(
            "Description:",
            goal_data.get(
                "description"
            ),
        )

        print(
            "Relevant objects:",
            goal_data.get(
                "relevant_objects"
            ),
        )

        print(
            "Instruction:",
            goal_data.get(
                "instruction"
            ),
        )

        print(
            "Source:",
            goal_data.get(
                "source",
                "conversation",
            ),
        )

        print(
            "================================"
        )

    # =====================================================
    # ACTIVE GOALS
    # =====================================================

    def _get_active_goals(
        self,
    ):

        try:

            return (
                goal_context
                .active_goals()
            )

        except Exception as exc:

            print(
                "GOAL_CONTEXT_READ_ERROR:",
                repr(exc),
            )

            return []

    # =====================================================
    # ACTIVE GOAL FORMAT
    # =====================================================

    def _format_active_goals(
        self,
        goals,
    ):

        if not goals:

            return (
                "No active explicit user goals."
            )

        lines = []

        for goal in goals:

            if hasattr(
                goal,
                "to_dict",
            ):

                data = (
                    goal.to_dict()
                )

            elif isinstance(
                goal,
                dict,
            ):

                data = goal

            else:

                continue

            description = (
                data.get(
                    "description"
                )
            )

            instruction = (
                data.get(
                    "instruction"
                )
            )

            relevant_objects = (
                data.get(
                    "relevant_objects"
                )
                or []
            )

            if description:

                lines.append(
                    "- Goal: "
                    f"{description}"
                )

            if relevant_objects:

                lines.append(
                    "  Relevant objects: "
                    +
                    ", ".join(
                        str(item)
                        for item
                        in relevant_objects
                    )
                )

            if instruction:

                lines.append(
                    "  Instruction: "
                    f"{instruction}"
                )

        if not lines:

            return (
                "No active explicit user goals."
            )

        return "\n".join(
            lines
        )

    # =====================================================
    # GOAL NORMALIZATION
    # =====================================================

    def _normalize_goal_text(
        self,
        value,
    ):

        if value is None:

            return ""

        text = (
            str(value)
            .strip()
            .lower()
        )

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text

    # =====================================================
    # CONTEXT REASONER FORMAT
    # =====================================================

    def _format_context_snapshot(
        self,
        snapshot,
    ):

        if snapshot is None:

            return (
                "No interpreted current context "
                "is available."
            )

        if hasattr(
            snapshot,
            "to_dict",
        ):

            data = (
                snapshot.to_dict()
            )

        elif isinstance(
            snapshot,
            dict,
        ):

            data = snapshot

        else:

            return (
                "No interpreted current context "
                "is available."
            )

        current_observation = (
            data.get(
                "current_observation"
            )
        )

        current_activity = (
            data.get(
                "current_activity"
            )
        )

        current_salient_event = (
            data.get(
                "current_salient_event"
            )
        )

        active_interactions = (
            data.get(
                "active_interactions"
            )
            or []
        )

        recent_actions = (
            data.get(
                "recent_actions"
            )
            or []
        )

        repeated_actions = (
            data.get(
                "repeated_actions"
            )
            or []
        )

        recent_event_count = (
            data.get(
                "recent_event_count",
                0,
            )
        )

        context_age_seconds = (
            data.get(
                "context_age_seconds"
            )
        )

        confidence = (
            data.get(
                "confidence"
            )
        )

        lines = []

        # =================================================
        # CURRENT STATE
        # =================================================

        if current_observation:

            lines.append(
                "Current observation: "
                f"{current_observation}"
            )

        else:

            lines.append(
                "Current observation: unknown"
            )

        if current_activity:

            lines.append(
                "Current activity: "
                f"{current_activity}"
            )

        else:

            lines.append(
                "Current activity: unknown"
            )

        if current_salient_event:

            lines.append(
                "Current notable event: "
                f"{current_salient_event}"
            )

        else:

            lines.append(
                "Current notable event: none"
            )

        # =================================================
        # ACTIVE INTERACTIONS
        # =================================================

        if active_interactions:

            lines.append(
                "Active interactions:"
            )

            for interaction in (
                active_interactions
            ):

                lines.append(
                    f"- {interaction}"
                )

        else:

            lines.append(
                "Active interactions: none"
            )

        # =================================================
        # RECENT ACTIONS
        # =================================================

        if recent_actions:

            lines.append(
                "Recent actions "
                "(oldest to newest):"
            )

            for action in (
                recent_actions
            ):

                lines.append(
                    f"- {action}"
                )

        else:

            lines.append(
                "Recent actions: none"
            )

        # =================================================
        # REPEATED ACTIONS
        # =================================================

        if repeated_actions:

            lines.append(
                "Repeated recent actions:"
            )

            for action in (
                repeated_actions
            ):

                lines.append(
                    f"- {action}"
                )

        else:

            lines.append(
                "Repeated recent actions: none"
            )

        # =================================================
        # SUPPORTING METADATA
        # =================================================

        lines.append(
            "Recent semantic event count: "
            f"{recent_event_count}"
        )

        if (
            context_age_seconds
            is not None
        ):

            lines.append(
                "Current context age: "
                f"{context_age_seconds:.1f} "
                "seconds"
            )

        if (
            confidence
            is not None
        ):

            lines.append(
                "Context information confidence: "
                f"{confidence:.2f}"
            )

        return "\n".join(
            lines
        )

    # =====================================================
    # EXTRACT TIME WINDOW
    # =====================================================

    def _extract_minutes(
        self,
        question: str,
    ):

        text = (
            question.lower()
        )

        # =================================================
        # HOURS
        # =================================================

        hour_match = (
            re.search(
                r"\b(\d+)\s*"
                r"(?:hour|hours|hr|hrs)\b",
                text,
            )
        )

        if hour_match:

            hours = int(
                hour_match.group(1)
            )

            return (
                hours * 60
            )

        # =================================================
        # MINUTES
        # =================================================

        minute_match = (
            re.search(
                r"\b(\d+)\s*"
                r"(?:minute|minutes|min|mins)\b",
                text,
            )
        )

        if minute_match:

            return int(
                minute_match.group(1)
            )

        return None

    # =====================================================
    # CURRENT SCENE FORMAT
    # =====================================================

    def _format_current_scene(
        self,
        scene,
    ):

        if not scene:

            return (
                "No current visual scene "
                "has been established."
            )

        return (
            f"Observed at: "
            f"{scene.get('timestamp', 'unknown')}\n"
            f"Observation: "
            f"{scene.get('observation', '')}"
        )

    # =====================================================
    # PREVIOUS SCENE FORMAT
    # =====================================================

    def _format_previous_scene(
        self,
        scene,
    ):

        if not scene:

            return (
                "No previous recent scene "
                "is available."
            )

        return (
            f"Observed at: "
            f"{scene.get('timestamp', 'unknown')}\n"
            f"Observation: "
            f"{scene.get('observation', '')}"
        )

    # =====================================================
    # WORKING MEMORY FORMAT
    # =====================================================

    def _format_working_memory(
        self,
        events,
    ):

        if not events:

            return (
                "No recent chronological "
                "events are available."
            )

        lines = []

        for event in events:

            timestamp = (
                event.get(
                    "timestamp",
                    "unknown",
                )
            )

            event_type = (
                event.get(
                    "event_type",
                    "UNKNOWN",
                )
            )

            observation = (
                event.get(
                    "observation"
                )
            )

            line = (
                f"- {timestamp} "
                f"[{event_type}]"
            )

            if observation:

                line += (
                    f": {observation}"
                )

            lines.append(
                line
            )

        return "\n".join(
            lines
        )

    # =====================================================
    # SEMANTIC MEMORY FORMAT
    # =====================================================

    def _format_semantic_memories(
        self,
        memories,
        include_similarity: bool = False,
    ):

        if not memories:

            return (
                "No relevant memories "
                "were found."
            )

        lines = []

        for memory in memories:

            first_seen = (
                memory.get(
                    "first_seen"
                )
                or
                memory.get(
                    "timestamp"
                )
                or
                "unknown"
            )

            last_observed = (
                memory.get(
                    "last_observed"
                )
                or
                memory.get(
                    "last_confirmed"
                )
                or
                first_seen
            )

            observation = (
                memory.get(
                    "observation",
                    "",
                )
            )

            line = (
                f"- First seen: "
                f"{first_seen}\n"
                f"  Last observed: "
                f"{last_observed}\n"
                f"  Observation: "
                f"{observation}"
            )

            if include_similarity:

                similarity = (
                    memory.get(
                        "similarity"
                    )
                )

                if (
                    similarity
                    is not None
                ):

                    line += (
                        "\n  Relevance score: "
                        f"{similarity:.3f}"
                    )

            lines.append(
                line
            )

        return "\n".join(
            lines
        )