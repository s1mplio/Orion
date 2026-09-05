import json
import re


class planner_agent:
    MAX_SUB_QUESTIONS = 10

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):
        prompt = f"""
You are ORION's Planner Agent.

Your job is to decompose the scientific research question into the minimum
number of focused, non-overlapping research sub-questions needed to investigate
the topic properly.

Do NOT always generate the same number of sub-questions.

Use fewer sub-questions for simple or narrow questions.
Use more sub-questions for complex, interdisciplinary, or broad questions.

Guidelines:

- Simple question: usually 2-4 sub-questions
- Medium complexity question: usually 4-7 sub-questions
- Complex question: usually 6-10 sub-questions

These are guidelines, not strict targets.

The sub-questions together should cover the important scientific dimensions
needed to answer the original research question.

Avoid:
- duplicate questions
- strongly overlapping questions
- irrelevant questions
- overly broad questions
- unnecessary decomposition

Never generate more than {self.MAX_SUB_QUESTIONS} sub-questions.

Research Question:
{state.question}

Return ONLY valid JSON in this exact structure:

{{
    "complexity": "low | medium | high",
    "sub_questions": [
        "question 1",
        "question 2"
    ]
}}
"""

        response = self.llm.generate(prompt)

        parsed = self._parse_response(response)

        sub_questions = parsed.get(
            "sub_questions",
            []
        )

        cleaned_questions = []

        for question in sub_questions:
            if not isinstance(question, str):
                continue

            question = question.strip()

            if not question:
                continue

            if self._is_duplicate(
                question,
                cleaned_questions
            ):
                continue

            cleaned_questions.append(question)

            if (
                len(cleaned_questions)
                >= self.MAX_SUB_QUESTIONS
            ):
                break

        # Safety fallback:
        # If structured parsing failed completely,
        # try extracting a numbered list.
        if not cleaned_questions:
            cleaned_questions = (
                self._fallback_parse_numbered_list(
                    response
                )
            )

        # Final deterministic safety cap.
        state.sub_questions = (
            cleaned_questions[
                :self.MAX_SUB_QUESTIONS
            ]
        )

        return state

    def _parse_response(self, response):
        """
        Extract and parse JSON from the LLM response.

        Handles:
        - clean JSON
        - ```json ... ```
        - additional text surrounding JSON
        """

        if not response:
            return {}

        text = response.strip()

        # Remove Markdown code fences.
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            flags=re.IGNORECASE
        )

        text = re.sub(
            r"\s*```$",
            "",
            text
        )

        try:
            parsed = json.loads(text)

            if isinstance(parsed, dict):
                return parsed

        except json.JSONDecodeError:
            pass

        # Try to locate a JSON object inside extra text.
        start = text.find("{")
        end = text.rfind("}")

        if (
            start != -1
            and end != -1
            and end > start
        ):
            candidate = text[
                start:end + 1
            ]

            try:
                parsed = json.loads(candidate)

                if isinstance(parsed, dict):
                    return parsed

            except json.JSONDecodeError:
                pass

        return {}

    def _fallback_parse_numbered_list(
        self,
        response
    ):
        """
        Fallback parser in case the LLM ignores
        the requested JSON format.
        """

        questions = []

        if not response:
            return questions

        for line in response.splitlines():
            line = line.strip()

            if not line:
                continue

            match = re.match(
                r"^\d+[\.\)]\s*(.+)$",
                line
            )

            if not match:
                continue

            question = (
                match.group(1).strip()
            )

            if not question:
                continue

            if self._is_duplicate(
                question,
                questions
            ):
                continue

            questions.append(question)

            if (
                len(questions)
                >= self.MAX_SUB_QUESTIONS
            ):
                break

        return questions

    def _is_duplicate(
        self,
        question,
        existing_questions
    ):
        """
        Cheap deterministic duplicate check.

        This intentionally avoids another LLM call.
        """

        normalized_question = (
            self._normalize(question)
        )

        for existing in existing_questions:
            normalized_existing = (
                self._normalize(existing)
            )

            if (
                normalized_question
                == normalized_existing
            ):
                return True

        return False

    def _normalize(self, text):
        """
        Normalize text for basic exact
        duplicate detection.
        """

        text = text.lower()

        text = re.sub(
            r"[^a-z0-9\s]",
            "",
            text
        )

        text = re.sub(
            r"\s+",
            " ",
            text
        )

        return text.strip()