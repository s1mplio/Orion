import json

from app.models.experiment import Experiment


class ExperimentAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

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

Accepted Hypothesis

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Design ONE realistic scientific experiment to test this hypothesis.

Return ONLY valid JSON.

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

        response = self.llm.generate(prompt)

        try:
            data = json.loads(response)

        except json.JSONDecodeError:
            print("INVALID EXPERIMENT RESPONSE")
            print(response)
            return

        experiment = Experiment(
            title=data.get("title", ""),
            objective=data.get("objective", ""),
            methodology=data.get("methodology", []),
            required_data=data.get("required_data", []),
            expected_outcomes=data.get("expected_outcomes", []),
            evaluation_metrics=data.get("evaluation_metrics", []),
            limitations=data.get("limitations", [])
        )

        state.experiment = experiment

        print("\n========== EXPERIMENT ==========")

        print("\nTitle:")
        print(experiment.title)

        print("\nObjective:")
        print(experiment.objective)

        print("\nMethodology:")
        for item in experiment.methodology:
            print("-", item)

        print("\nRequired Data:")
        for item in experiment.required_data:
            print("-", item)

        print("\nExpected Outcomes:")
        for item in experiment.expected_outcomes:
            print("-", item)

        print("\nEvaluation Metrics:")
        for item in experiment.evaluation_metrics:
            print("-", item)

        print("\nLimitations:")
        for item in experiment.limitations:
            print("-", item)