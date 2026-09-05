import json

from app.models.experiment import Experiment


class ExperimentAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        print("\n========== EXPERIMENT GENERATION ==========")

        # -------------------------------------------------
        # Safety checks
        # -------------------------------------------------

        if state.synthesis is None:
            print(
                "[EXPERIMENT] No synthesis available."
            )
            return

        if state.hypothesis is None:
            print(
                "[EXPERIMENT] No accepted hypothesis available."
            )
            return

        # -------------------------------------------------
        # Prompt
        # -------------------------------------------------

        prompt = f"""
You are an expert scientific researcher.

Research Question:
{state.question}

SCIENTIFIC SYNTHESIS

Summary:
{state.synthesis.summary}

Key Findings:
{state.synthesis.key_findings}

Limitations:
{state.synthesis.limitations}

Future Work:
{state.synthesis.future_work}

ACCEPTED HYPOTHESIS

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Design ONE realistic scientific experiment to test
the accepted hypothesis.

The experiment should:

1. Directly test the proposed hypothesis.

2. Be scientifically plausible.

3. Clearly describe the methodology.

4. Identify the data or observations required.

5. Explain the possible expected outcomes.

6. Define measurable evaluation metrics.

7. Acknowledge important experimental limitations.

Use ONLY the scientific information supplied above.

Do not introduce unsupported scientific claims.

Return ONLY valid JSON.

Do not use markdown.
Do not use ```json fences.
Do not include text before or after the JSON.

Use exactly this structure:

{{
    "title": "",
    "objective": "",
    "methodology": [],
    "required_data": [],
    "expected_outcomes": [],
    "evaluation_metrics": [],
    "limitations": []
}}
"""

        # -------------------------------------------------
        # LLM call
        # -------------------------------------------------

        response = self.llm.generate(
            prompt
        )

        if response is None:
            print(
                "[EXPERIMENT] LLM returned no response."
            )
            return

        # -------------------------------------------------
        # Parse JSON
        # -------------------------------------------------

        data = self._parse_json(
            response
        )

        if data is None:
            print(
                "[EXPERIMENT] INVALID EXPERIMENT RESPONSE"
            )

            print("\nRaw response:")
            print(response)

            return

        # -------------------------------------------------
        # Normalize fields
        # -------------------------------------------------

        title = str(
            data.get(
                "title",
                ""
            )
        ).strip()

        objective = str(
            data.get(
                "objective",
                ""
            )
        ).strip()

        methodology = self._ensure_list(
            data.get(
                "methodology",
                []
            )
        )

        required_data = self._ensure_list(
            data.get(
                "required_data",
                []
            )
        )

        expected_outcomes = self._ensure_list(
            data.get(
                "expected_outcomes",
                []
            )
        )

        evaluation_metrics = self._ensure_list(
            data.get(
                "evaluation_metrics",
                []
            )
        )

        limitations = self._ensure_list(
            data.get(
                "limitations",
                []
            )
        )

        # -------------------------------------------------
        # Basic validation
        # -------------------------------------------------

        if not title:
            print(
                "[EXPERIMENT] Empty title returned."
            )
            return

        if not objective:
            print(
                "[EXPERIMENT] Empty objective returned."
            )
            return

        # -------------------------------------------------
        # Create experiment
        # -------------------------------------------------

        experiment = Experiment(
            title=title,
            objective=objective,
            methodology=methodology,
            required_data=required_data,
            expected_outcomes=expected_outcomes,
            evaluation_metrics=evaluation_metrics,
            limitations=limitations
        )

        # IMPORTANT:
        # ResearchState uses `experiments`,
        # not `experiment`.
        state.experiments = experiment

        # -------------------------------------------------
        # Print result
        # -------------------------------------------------

        print("\n========== EXPERIMENT ==========")

        print("\nTitle:")
        print(
            experiment.title
        )

        print("\nObjective:")
        print(
            experiment.objective
        )

        print("\nMethodology:")

        if experiment.methodology:
            for item in experiment.methodology:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nRequired Data:")

        if experiment.required_data:
            for item in experiment.required_data:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nExpected Outcomes:")

        if experiment.expected_outcomes:
            for item in experiment.expected_outcomes:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nEvaluation Metrics:")

        if experiment.evaluation_metrics:
            for item in experiment.evaluation_metrics:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nLimitations:")

        if experiment.limitations:
            for item in experiment.limitations:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

    # =====================================================
    # LIST NORMALIZATION
    # =====================================================

    def _ensure_list(
        self,
        value
    ):

        if value is None:
            return []

        if isinstance(
            value,
            list
        ):
            return [
                str(item).strip()
                for item in value
                if str(item).strip()
            ]

        return [
            str(value).strip()
        ]

    # =====================================================
    # JSON PARSER
    # =====================================================

    def _parse_json(
        self,
        response
    ):

        cleaned = str(
            response
        ).strip()

        # -------------------------------------------------
        # Remove markdown fences
        # -------------------------------------------------

        if cleaned.startswith(
            "```json"
        ):
            cleaned = cleaned[7:]

        elif cleaned.startswith(
            "```"
        ):
            cleaned = cleaned[3:]

        if cleaned.endswith(
            "```"
        ):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        # -------------------------------------------------
        # First attempt
        # -------------------------------------------------

        try:

            data = json.loads(
                cleaned
            )

            if isinstance(
                data,
                dict
            ):
                return data

        except json.JSONDecodeError:
            pass

        # -------------------------------------------------
        # Second attempt:
        # extract JSON if model added extra text
        # -------------------------------------------------

        first_brace = cleaned.find(
            "{"
        )

        last_brace = cleaned.rfind(
            "}"
        )

        if (
            first_brace != -1
            and last_brace != -1
            and last_brace > first_brace
        ):

            possible_json = cleaned[
                first_brace:
                last_brace + 1
            ]

            try:

                data = json.loads(
                    possible_json
                )

                if isinstance(
                    data,
                    dict
                ):
                    return data

            except json.JSONDecodeError:
                pass

        return None