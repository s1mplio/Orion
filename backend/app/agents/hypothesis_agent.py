import json

from app.models.hypothesis import Hypothesis


class HypothesisAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        print("\n========== HYPOTHESIS GENERATION ==========")

        # -------------------------------------------------
        # Basic safety check
        # -------------------------------------------------

        if state.synthesis is None:
            print("[HYPOTHESIS] No synthesis available.")
            return

        feedback = ""

        # -------------------------------------------------
        # Revision mode
        # -------------------------------------------------

        if (
            state.hypothesis_review is not None
            and state.hypothesis is not None
        ):
            feedback = f"""
Previous Hypothesis

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Reviewer Feedback

Strengths:
{state.hypothesis_review.strengths}

Weaknesses:
{state.hypothesis_review.weaknesses}

Recommendation:
{state.hypothesis_review.recommendation}

Generate an improved hypothesis that addresses the
reviewer feedback while remaining grounded in the
scientific synthesis.
"""

        # -------------------------------------------------
        # Prompt
        # -------------------------------------------------

        prompt = f"""
You are an expert scientific researcher.

Research Question:
{state.question}

Scientific Synthesis

Summary:
{state.synthesis.summary}

Key Findings:
{state.synthesis.key_findings}

Limitations:
{state.synthesis.limitations}

Future Work:
{state.synthesis.future_work}

{feedback}

Generate ONE scientifically plausible and testable
hypothesis.

The hypothesis must:

1. Follow from the supplied scientific synthesis.
2. Be specific and testable.
3. Avoid introducing unsupported scientific claims.
4. Clearly describe the proposed scientific relationship
   or mechanism.
5. Respect the limitations and uncertainty in the
   evidence.
6. Be suitable for later experimental validation.

Explain why the hypothesis follows from the available
evidence.

List the assumptions required for the hypothesis.

Return ONLY valid JSON.

Do not use markdown.
Do not use ```json fences.
Do not include any text before or after the JSON.

Use exactly this structure:

{{
    "hypothesis": "",
    "reasoning": "",
    "assumptions": []
}}
"""

        # -------------------------------------------------
        # LLM call
        # -------------------------------------------------

        response = self.llm.generate(prompt)

        if response is None:
            print("[HYPOTHESIS] LLM returned no response.")
            return

        # -------------------------------------------------
        # Parse JSON safely
        # -------------------------------------------------

        data = self._parse_json(response)

        if data is None:
            print("[HYPOTHESIS] INVALID HYPOTHESIS RESPONSE")
            print("\nRaw response:")
            print(response)
            return

        # -------------------------------------------------
        # Validate fields
        # -------------------------------------------------

        hypothesis_text = str(
            data.get("hypothesis", "")
        ).strip()

        reasoning = str(
            data.get("reasoning", "")
        ).strip()

        assumptions = data.get(
            "assumptions",
            []
        )

        if not hypothesis_text:
            print("[HYPOTHESIS] Empty hypothesis returned.")
            return

        if not reasoning:
            print("[HYPOTHESIS] Empty reasoning returned.")
            return

        if not isinstance(assumptions, list):
            assumptions = [str(assumptions)]

        assumptions = [
            str(item).strip()
            for item in assumptions
            if str(item).strip()
        ]

        # -------------------------------------------------
        # Create hypothesis
        # -------------------------------------------------

        hypothesis = Hypothesis(
            hypothesis=hypothesis_text,
            reasoning=reasoning,
            assumptions=assumptions
        )

        state.hypothesis = hypothesis

        # -------------------------------------------------
        # Save history
        # -------------------------------------------------

        if hasattr(state, "hypothesis_history"):
            state.hypothesis_history.append(
                hypothesis
            )

        # -------------------------------------------------
        # Print result
        # -------------------------------------------------

        print("\n========== HYPOTHESIS ==========")

        print("\nHypothesis:")
        print(state.hypothesis.hypothesis)

        print("\nReasoning:")
        print(state.hypothesis.reasoning)

        print("\nAssumptions:")

        if state.hypothesis.assumptions:
            for assumption in state.hypothesis.assumptions:
                print("-", assumption)
        else:
            print("- None")

    # =====================================================
    # JSON PARSER
    # =====================================================

    def _parse_json(self, response):

        cleaned = str(response).strip()

        # Remove common markdown fences
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]

        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        # -------------------------------------------------
        # First attempt
        # -------------------------------------------------

        try:
            data = json.loads(cleaned)

            if isinstance(data, dict):
                return data

        except json.JSONDecodeError:
            pass

        # -------------------------------------------------
        # Second attempt:
        # extract JSON object if model added extra text
        # -------------------------------------------------

        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")

        if (
            first_brace != -1
            and last_brace != -1
            and last_brace > first_brace
        ):
            possible_json = cleaned[
                first_brace:last_brace + 1
            ]

            try:
                data = json.loads(
                    possible_json
                )

                if isinstance(data, dict):
                    return data

            except json.JSONDecodeError:
                pass

        return None