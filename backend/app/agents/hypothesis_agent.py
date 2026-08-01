import json

from app.models.hypothesis import Hypothesis


class HypothesisAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        feedback = ""

        if state.hypothesis_review is not None:
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

Generate an improved hypothesis that addresses all reviewer feedback.
"""

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

Generate ONE scientifically plausible, novel and testable hypothesis.

Explain why the hypothesis follows from the available evidence.

Return ONLY valid JSON.

{{
    "hypothesis": "",
    "reasoning": "",
    "assumptions": []
}}
"""

        response = self.llm.generate(prompt)

        try:
            data = json.loads(response)

        except json.JSONDecodeError:
            print("INVALID HYPOTHESIS RESPONSE")
            print(response)
            return

        hypothesis = Hypothesis(
            hypothesis=data.get("hypothesis", ""),
            reasoning=data.get("reasoning", ""),
            assumptions=data.get("assumptions", [])
        )

        state.hypothesis = hypothesis

        print("\n========== HYPOTHESIS ==========")

        print("\nHypothesis:")
        print(state.hypothesis.hypothesis)

        print("\nReasoning:")
        print(state.hypothesis.reasoning)

        print("\nAssumptions:")
        for assumption in state.hypothesis.assumptions:
            print("-", assumption)