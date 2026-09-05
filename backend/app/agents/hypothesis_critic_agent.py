import json

from app.models.hypothesis_review import HypothesisReview


class HypothesisCriticAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        print("\n========== HYPOTHESIS CRITIC ==========")

        # -------------------------------------------------
        # Safety checks
        # -------------------------------------------------

        if state.synthesis is None:
            print(
                "[HYPOTHESIS CRITIC] "
                "No synthesis available."
            )
            return

        if state.hypothesis is None:
            print(
                "[HYPOTHESIS CRITIC] "
                "No hypothesis available."
            )
            return

        # -------------------------------------------------
        # Prompt
        # -------------------------------------------------

        prompt = f"""
You are an expert scientific reviewer.

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

PROPOSED HYPOTHESIS

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Evaluate the hypothesis using ONLY the scientific
synthesis supplied above.

Evaluate:

1. Whether the hypothesis follows from the evidence.

2. Whether the reasoning is scientifically coherent.

3. Whether the hypothesis is testable.

4. Whether important limitations or uncertainties
   have been ignored.

5. Whether the assumptions are reasonable given
   the supplied evidence.

Do NOT use outside knowledge.

Do NOT invent evidence.

RECOMMENDATION RULES

Accept:
The hypothesis is reasonably supported by the supplied
evidence, scientifically coherent and testable.

Revise:
The core hypothesis is plausible, but important changes
are required before it should be accepted.

Reject:
The hypothesis contradicts the supplied evidence,
is scientifically implausible based on the supplied
information, or cannot meaningfully be tested.

Return ONLY valid JSON.

Do not use markdown.
Do not use ```json fences.
Do not include text before or after the JSON.

Use exactly this structure:

{{
    "strengths": [],
    "weaknesses": [],
    "supported_by_evidence": true,
    "confidence": "High",
    "recommendation": "Accept"
}}

The "confidence" field MUST be exactly one of:

"High"
"Moderate"
"Low"

The "recommendation" field MUST be exactly one of:

"Accept"
"Revise"
"Reject"
"""

        # -------------------------------------------------
        # LLM call
        # -------------------------------------------------

        response = self.llm.generate(
            prompt
        )

        if response is None:
            print(
                "[HYPOTHESIS CRITIC] "
                "LLM returned no response."
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
                "[HYPOTHESIS CRITIC] "
                "INVALID HYPOTHESIS REVIEW"
            )

            print("\nRaw response:")
            print(response)

            return

        # -------------------------------------------------
        # Validate lists
        # -------------------------------------------------

        strengths = data.get(
            "strengths",
            []
        )

        weaknesses = data.get(
            "weaknesses",
            []
        )

        if not isinstance(
            strengths,
            list
        ):
            strengths = [
                str(strengths)
            ]

        if not isinstance(
            weaknesses,
            list
        ):
            weaknesses = [
                str(weaknesses)
            ]

        strengths = [
            str(item).strip()
            for item in strengths
            if str(item).strip()
        ]

        weaknesses = [
            str(item).strip()
            for item in weaknesses
            if str(item).strip()
        ]

        # -------------------------------------------------
        # Validate supported_by_evidence
        # -------------------------------------------------

        supported = data.get(
            "supported_by_evidence",
            False
        )

        if isinstance(
            supported,
            str
        ):
            supported = (
                supported.strip().lower()
                == "true"
            )

        else:
            supported = bool(
                supported
            )

        # -------------------------------------------------
        # Validate confidence
        # -------------------------------------------------

        confidence = str(
            data.get(
                "confidence",
                ""
            )
        ).strip()

        confidence_map = {
            "high": "High",
            "moderate": "Moderate",
            "low": "Low",
        }

        confidence = confidence_map.get(
            confidence.lower(),
            "Low"
        )

        # -------------------------------------------------
        # Validate recommendation
        # -------------------------------------------------

        recommendation = str(
            data.get(
                "recommendation",
                ""
            )
        ).strip()

        recommendation_map = {
            "accept": "Accept",
            "revise": "Revise",
            "reject": "Reject",
        }

        normalized_recommendation = (
            recommendation_map.get(
                recommendation.lower()
            )
        )

        if normalized_recommendation is None:

            print(
                "[HYPOTHESIS CRITIC] "
                "Invalid recommendation:"
            )

            print(
                recommendation
            )

            return

        # -------------------------------------------------
        # Create review
        # -------------------------------------------------

        review = HypothesisReview(
            strengths=strengths,
            weaknesses=weaknesses,
            supported_by_evidence=supported,
            confidence=confidence,
            recommendation=(
                normalized_recommendation
            )
        )

        state.hypothesis_review = review

        # -------------------------------------------------
        # Preserve review history
        # -------------------------------------------------

        if hasattr(
            state,
            "hypothesis_review_history"
        ):
            state.hypothesis_review_history.append(
                review
            )

        # -------------------------------------------------
        # Print result
        # -------------------------------------------------

        print(
            "\n========== HYPOTHESIS REVIEW =========="
        )

        print("\nStrengths:")

        if review.strengths:
            for item in review.strengths:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nWeaknesses:")

        if review.weaknesses:
            for item in review.weaknesses:
                print(
                    "-",
                    item
                )
        else:
            print("- None")

        print("\nSupported by Evidence:")
        print(
            review.supported_by_evidence
        )

        print("\nConfidence:")
        print(
            review.confidence
        )

        print("\nRecommendation:")
        print(
            review.recommendation
        )

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
        # Remove markdown JSON fences
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
        # Second attempt
        #
        # Handle:
        #
        # Here is the review:
        # { ... }
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