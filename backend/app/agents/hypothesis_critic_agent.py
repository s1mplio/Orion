import json

from app.models.hypothesis_review import HypothesisReview


class HypothesisCriticAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        prompt = f"""
You are a scientific reviewer.

Question:
{state.question}

Summary:
{state.synthesis.summary}

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Review the hypothesis.

Return ONLY JSON:

{{
    "strengths": [],
    "weaknesses": [],
    "supported_by_evidence": true,
    "confidence": "High | Moderate | Low",
    "recommendation": "Accept | Revise | Reject"
}}

Rules:
- Accept if the hypothesis is supported by the evidence and is testable.
- Revise only if major improvements are needed.
- Reject only if it contradicts the evidence or is not scientifically plausible.
"""

        response = self.llm.generate(prompt)

        try:
            data = json.loads(response)

        except json.JSONDecodeError:
            print("INVALID HYPOTHESIS REVIEW")
            print(response)
            return

        review = HypothesisReview(
            strengths=data.get("strengths", []),
            weaknesses=data.get("weaknesses", []),
            supported_by_evidence=data.get("supported_by_evidence", False),
            confidence=data.get("confidence", ""),
            recommendation=data.get("recommendation", "")
        )

        state.hypothesis_review = review
        state.hypothesis_review_history.append(review)

        print("\n========== HYPOTHESIS REVIEW ==========")

        print("\nStrengths:")
        for item in review.strengths:
            print("-", item)

        print("\nWeaknesses:")
        for item in review.weaknesses:
            print("-", item)

        print("\nSupported by Evidence:")
        print(review.supported_by_evidence)

        print("\nConfidence:")
        print(review.confidence)

        print("\nRecommendation:")
        print(review.recommendation)