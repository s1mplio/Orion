from app.agents.llm_json import (
    ensure_str_list,
    parse_llm_json,
)


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

        experiment = state.experiments

        hypothesis_section = self._format_hypothesis(
            state
        )

        experiment_section = self._format_experiment(
            experiment
        )

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


HYPOTHESIS

{hypothesis_section}


PROPOSED EXPERIMENT

{experiment_section}


Write a concise scientific report that contains:

1. Research question
2. Scientific synthesis
3. Key findings
4. Hypothesis and its review status
5. Hypothesis reasoning
6. Proposed experiment (leave experiment fields empty
   when no experiment is provided above)
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

        state.final_report = self._normalize_report(
            data,
            state,
        )

        data = state.final_report

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
    # PROMPT SECTIONS
    # =====================================================

    def _format_hypothesis(
        self,
        state,
    ):
        hypothesis = state.hypothesis

        if hypothesis is None:
            return (
                "No hypothesis could be generated "
                "from the available evidence."
            )

        review = state.hypothesis_review

        status = (
            review.recommendation
            if review is not None
            else "Not reviewed"
        )

        return "\n\n".join([
            f"Review status: {status}",
            f"Hypothesis:\n{hypothesis.hypothesis}",
            f"Reasoning:\n{hypothesis.reasoning}",
            f"Assumptions:\n{hypothesis.assumptions}",
        ])

    def _format_experiment(
        self,
        experiment,
    ):
        if experiment is None:
            return (
                "No experiment was designed because the "
                "hypothesis was not accepted by review."
            )

        return "\n\n".join([
            f"Title:\n{experiment.title}",
            f"Objective:\n{experiment.objective}",
            f"Methodology:\n{experiment.methodology}",
            f"Required Data:\n{experiment.required_data}",
            f"Expected Outcomes:\n{experiment.expected_outcomes}",
            f"Evaluation Metrics:\n{experiment.evaluation_metrics}",
            f"Limitations:\n{experiment.limitations}",
        ])

    # =====================================================
    # REPORT NORMALIZATION
    # =====================================================

    def _normalize_report(
        self,
        data,
        state,
    ):
        text_fields = (
            "research_question",
            "summary",
            "hypothesis",
            "hypothesis_reasoning",
            "experiment_title",
            "experiment_objective",
        )

        list_fields = (
            "key_findings",
            "experiment_methodology",
            "expected_outcomes",
            "limitations",
            "future_work",
        )

        report = {}

        for field in text_fields:
            value = data.get(field)

            if isinstance(value, (list, tuple)):
                value = " ".join(
                    ensure_str_list(value)
                )

            report[field] = str(
                value or ""
            ).strip()

        for field in list_fields:
            report[field] = ensure_str_list(
                data.get(field)
            )

        if not report["research_question"]:
            report["research_question"] = state.question

        return report

    # =====================================================
    # JSON PARSER
    # =====================================================

    def _parse_json(
        self,
        response
    ):
        return parse_llm_json(
            response
        )
