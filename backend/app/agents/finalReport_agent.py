import json


class FinalReportAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        print("\n========== FINAL REPORT GENERATION ==========")

        # -------------------------------------------------
        # Safety checks
        # -------------------------------------------------

        if state.synthesis is None:
            print(
                "[FINAL REPORT] No synthesis available."
            )
            return

        if state.hypothesis is None:
            print(
                "[FINAL REPORT] No hypothesis available."
            )
            return

        if state.experiments is None:
            print(
                "[FINAL REPORT] No experiment available."
            )
            return

        experiment = state.experiments

        # -------------------------------------------------
        # Prompt
        # -------------------------------------------------

        prompt = f"""
You are an expert scientific writer.

Create a final scientific research report using ONLY
the information provided below.

RESEARCH QUESTION

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


PROPOSED EXPERIMENT

Title:
{experiment.title}

Objective:
{experiment.objective}

Methodology:
{experiment.methodology}

Required Data:
{experiment.required_data}

Expected Outcomes:
{experiment.expected_outcomes}

Evaluation Metrics:
{experiment.evaluation_metrics}

Limitations:
{experiment.limitations}


Write a concise scientific report that contains:

1. Research question
2. Scientific synthesis
3. Key findings
4. Accepted hypothesis
5. Hypothesis reasoning
6. Proposed experiment
7. Expected outcomes
8. Limitations
9. Future research directions

Use ONLY the information supplied above.

Do not invent scientific evidence.

Do not introduce unsupported claims.

Return ONLY valid JSON.

Do not use markdown.
Do not use ```json fences.
Do not include text before or after the JSON.

Use exactly this structure:

{{
    "research_question": "",
    "summary": "",
    "key_findings": [],
    "hypothesis": "",
    "hypothesis_reasoning": "",
    "experiment_title": "",
    "experiment_objective": "",
    "experiment_methodology": [],
    "expected_outcomes": [],
    "limitations": [],
    "future_work": []
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
                "[FINAL REPORT] LLM returned no response."
            )
            return

        # -------------------------------------------------
        # Parse JSON safely
        # -------------------------------------------------

        data = self._parse_json(
            response
        )

        if data is None:
            print(
                "[FINAL REPORT] INVALID FINAL REPORT RESPONSE"
            )

            print("\nRaw response:")
            print(response)

            return

        # -------------------------------------------------
        # Store final report
        # -------------------------------------------------

        state.final_report = data

        # -------------------------------------------------
        # Print result
        # -------------------------------------------------

        print("\n========== FINAL REPORT ==========")

        print("\nResearch Question:")
        print(
            data.get(
                "research_question",
                state.question
            )
        )

        print("\nSummary:")
        print(
            data.get(
                "summary",
                ""
            )
        )

        print("\nKey Findings:")

        for item in self._ensure_list(
            data.get(
                "key_findings",
                []
            )
        ):
            print(
                "-",
                item
            )

        print("\nHypothesis:")
        print(
            data.get(
                "hypothesis",
                ""
            )
        )

        print("\nHypothesis Reasoning:")
        print(
            data.get(
                "hypothesis_reasoning",
                ""
            )
        )

        print("\nExperiment Title:")
        print(
            data.get(
                "experiment_title",
                ""
            )
        )

        print("\nExperiment Objective:")
        print(
            data.get(
                "experiment_objective",
                ""
            )
        )

        print("\nExperiment Methodology:")

        for item in self._ensure_list(
            data.get(
                "experiment_methodology",
                []
            )
        ):
            print(
                "-",
                item
            )

        print("\nExpected Outcomes:")

        for item in self._ensure_list(
            data.get(
                "expected_outcomes",
                []
            )
        ):
            print(
                "-",
                item
            )

        print("\nLimitations:")

        for item in self._ensure_list(
            data.get(
                "limitations",
                []
            )
        ):
            print(
                "-",
                item
            )

        print("\nFuture Work:")

        for item in self._ensure_list(
            data.get(
                "future_work",
                []
            )
        ):
            print(
                "-",
                item
            )

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
            return value

        return [
            value
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

        # First attempt
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

        # Second attempt:
        # extract JSON object if extra text exists

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