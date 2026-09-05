from app.companion.memory.memory_manager import (
    MemoryManager,
)

from app.companion.memory.working_memory import (
    WorkingMemory,
)

from app.companion.memory.scene_intelligence import (
    SceneIntelligence,
)

from app.companion.context.context_reasoner import (
    ContextReasoner,
)

from app.companion.context.temporal_world_state import (
    TemporalWorldState,
)

from app.companion.context.goal_context import (
    GoalContext,
)

from app.companion.context.goal_progress import (
    GoalProgressReasoner,
)

from app.companion.proactive.proactive_policy import (
    ProactivePolicy,
)

from app.companion.proactive.goal_candidate_generator import (
    GoalCandidateGenerator,
)

from app.companion.proactive.proactive_message_service import (
    ProactiveMessageService,
)


# =========================================================
# LONG-TERM MEMORY
# =========================================================

memory_manager = MemoryManager()


# =========================================================
# SHORT-TERM WORKING MEMORY
# =========================================================

working_memory = WorkingMemory(
    max_events=50,
    retention_minutes=10,
)


# =========================================================
# SCENE INTELLIGENCE
# =========================================================

scene_intelligence = SceneIntelligence(
    working_memory=working_memory,
)


# =========================================================
# CONTEXT REASONER V1
# =========================================================

context_reasoner = ContextReasoner(
    working_memory=working_memory,
    recent_event_limit=20,
)


# =========================================================
# TEMPORAL WORLD STATE V1
# =========================================================

temporal_world_state = TemporalWorldState(
    working_memory=working_memory,
    recent_event_limit=40,
    recent_interaction_limit=10,
)


# =========================================================
# GOAL CONTEXT V1
# =========================================================

goal_context = GoalContext(
    max_goals=50,
)


# =========================================================
# GOAL PROGRESS / RELEVANCE V1
# =========================================================

goal_progress_reasoner = GoalProgressReasoner(
    context_reasoner=context_reasoner,
    temporal_world_state=temporal_world_state,
    goal_context=goal_context,
)


# =========================================================
# VISUAL PROACTIVE POLICY V1
#
# Produces candidates from:
#     interactions
#     repeated actions
#     salient events
# =========================================================

proactive_policy = ProactivePolicy(
    context_reasoner=context_reasoner,
    cooldown_seconds=20.0,
)


# =========================================================
# GOAL-DRIVEN CANDIDATE GENERATOR V1
#
# Produces candidates from GoalProgress evidence.
#
# It does NOT decide to speak.
# =========================================================

goal_candidate_generator = GoalCandidateGenerator(
    goal_progress_reasoner=goal_progress_reasoner,
    cooldown_seconds=20.0,
    minimum_relevance_score=0.5,
    minimum_confidence=0.5,
)


# =========================================================
# PROACTIVE MESSAGE GENERATION V1
# =========================================================

proactive_message_service = ProactiveMessageService()