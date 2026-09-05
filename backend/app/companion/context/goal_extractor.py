import json
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class GoalExtractionResult:
    """
    Result extracted locally from the single conversational
    LLM response.

    The extractor itself performs NO LLM calls.
    """

    answer: str

    has_goal: bool = False

    description: Optional[str] = None

    relevant_objects: Optional[List[str]] = None

    instruction: Optional[str] = None

    error: Optional[str] = None


class GoalExtractor:
    """
    Orion Automatic Goal Capture V1.

    IMPORTANT:

    This class does NOT infer goals.

    The conversational LLM is instructed to include a
    structured goal block only when the USER explicitly
    expresses a future goal, reminder, task or instruction.

    This class only:

        1. finds the structured block,
        2. parses JSON,
        3. validates it,
        4. returns the conversational answer separately.

    No additional LLM call is made.
    """

    START_MARKER = "<ORION_GOAL>"
    END_MARKER = "</ORION_GOAL>"

    def parse(
        self,
        raw_response: str,
    ) -> GoalExtractionResult:

        if not raw_response:

            return GoalExtractionResult(
                answer="",
                error="empty_response",
            )

        raw_response = str(
            raw_response
        ).strip()

        if not raw_response:

            return GoalExtractionResult(
                answer="",
                error="empty_response",
            )

        # =================================================
        # FIND OPTIONAL GOAL BLOCK
        # =================================================

        pattern = (
            re.escape(
                self.START_MARKER
            )
            +
            r"(.*?)"
            +
            re.escape(
                self.END_MARKER
            )
        )

        match = re.search(
            pattern,
            raw_response,
            flags=re.DOTALL | re.IGNORECASE,
        )

        # =================================================
        # NORMAL CONVERSATIONAL RESPONSE
        # =================================================

        if match is None:

            return GoalExtractionResult(
                answer=raw_response,
                has_goal=False,
            )

        # =================================================
        # REMOVE INTERNAL BLOCK FROM USER-FACING ANSWER
        # =================================================

        answer = (
            raw_response[
                :match.start()
            ]
            +
            raw_response[
                match.end():
            ]
        ).strip()

        goal_text = (
            match.group(1)
            .strip()
        )

        if not goal_text:

            return GoalExtractionResult(
                answer=answer,
                has_goal=False,
                error="empty_goal_block",
            )

        # =================================================
        # LOCAL JSON CLEANUP
        # =================================================

        goal_text = (
            self._clean_json_text(
                goal_text
            )
        )

        # =================================================
        # PARSE JSON
        # =================================================

        try:

            payload = json.loads(
                goal_text
            )

        except Exception as exc:

            print(
                "GOAL_EXTRACTION_PARSE_ERROR:",
                repr(exc),
            )

            return GoalExtractionResult(
                answer=answer,
                has_goal=False,
                error="invalid_goal_json",
            )

        if not isinstance(
            payload,
            dict,
        ):

            return GoalExtractionResult(
                answer=answer,
                has_goal=False,
                error="goal_payload_not_object",
            )

        # =================================================
        # EXPLICIT GOAL FLAG
        # =================================================

        has_goal = bool(
            payload.get(
                "has_goal",
                False,
            )
        )

        if not has_goal:

            return GoalExtractionResult(
                answer=answer,
                has_goal=False,
            )

        # =================================================
        # VALIDATE FIELDS
        # =================================================

        description = (
            self._clean_text(
                payload.get(
                    "description"
                )
            )
        )

        instruction = (
            self._clean_text(
                payload.get(
                    "instruction"
                )
            )
        )

        relevant_objects = (
            self._clean_objects(
                payload.get(
                    "relevant_objects"
                )
            )
        )

        # We require an explicit description.
        #
        # This prevents malformed model output from
        # creating meaningless goals.

        if not description:

            return GoalExtractionResult(
                answer=answer,
                has_goal=False,
                error="goal_missing_description",
            )

        # =================================================
        # SUCCESS
        # =================================================

        return GoalExtractionResult(
            answer=answer,
            has_goal=True,
            description=description,
            relevant_objects=relevant_objects,
            instruction=instruction,
        )

    # =====================================================
    # JSON CLEANUP
    # =====================================================

    def _clean_json_text(
        self,
        text: str,
    ) -> str:

        value = str(
            text
        ).strip()

        # Models occasionally wrap JSON in a fenced block.
        # Remove formatting only.
        #
        # We do NOT semantically repair the goal.

        if value.startswith("```"):

            value = re.sub(
                r"^```(?:json)?\s*",
                "",
                value,
                flags=re.IGNORECASE,
            )

            value = re.sub(
                r"\s*```$",
                "",
                value,
            )

        return value.strip()

    # =====================================================
    # TEXT VALIDATION
    # =====================================================

    def _clean_text(
        self,
        value: Any,
    ) -> Optional[str]:

        if value is None:

            return None

        text = str(
            value
        ).strip()

        if not text:

            return None

        if text.lower() in {
            "none",
            "null",
            "unknown",
        }:

            return None

        return text

    # =====================================================
    # OBJECT VALIDATION
    # =====================================================

    def _clean_objects(
        self,
        value: Any,
    ) -> List[str]:

        if not isinstance(
            value,
            list,
        ):

            return []

        output = []

        for item in value:

            text = (
                self._clean_text(
                    item
                )
            )

            if not text:

                continue

            normalized = (
                text.lower()
            )

            if normalized not in output:

                output.append(
                    normalized
                )

        return output