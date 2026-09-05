import json

from app.models.synthesis import Synthesis


class SynthesisAgent:
    """
    Research V2 synthesis agent.

    Converts the scientific critic output into a concise
    scientific synthesis while preserving evidence
    citations generated upstream.

    Existing Synthesis model fields are preserved so the
    hypothesis and report stages remain compatible.
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):
        print()
        print("=" * 70)
        print("SCIENTIFIC SYNTHESIS")
        print("=" * 70)

        if state.critic_results is None:
            print(
                "[SYNTHESIS] No critic results "
                "available."
            )
            return

        source_papers = getattr(
            state,
            "critic_source_papers",
            [],
        )

        source_text = (
            "\n".join(
                f"- {paper}"
                for paper in source_papers
            )
            if source_papers
            else "Not explicitly available"
        )

        prompt = f"""
You are an expert scientific writer.

Research Question:
{state.question}

Below is a scientific review generated from grounded
full-paper evidence.

SOURCE PAPERS:
{source_text}

Agreements:
{state.critic_results.agreements}

Contradictions:
{state.critic_results.contradictions}

Research Gaps:
{state.critic_results.research_gaps}

Confidence:
{state.critic_results.confidence}

Write ONE scientific synthesis using ONLY the information
above.

IMPORTANT RULES:

1. Do not introduce outside scientific knowledge.

2. Do not invent findings, papers, experiments or
   citations.

3. Preserve valid [chunk_id] citations when they are
   present in the critic output.

4. Do not claim agreement across multiple papers unless
   the critic explicitly supports that conclusion.

5. Clearly distinguish:
   - supported findings
   - uncertainty
   - limitations
   - research gaps

6. Research gaps are not established facts.

7. If the available evidence is limited to one source,
   avoid language such as:
   "multiple independent studies prove..."

8. The summary should directly address the user's
   research question.

Return ONLY valid JSON.

Use exactly:

{{
    "summary": "",
    "key_findings": [],
    "limitations": [],
    "future_work": []
}}
"""

        response = self.llm.generate(
            prompt
        )

        data = self._parse_json(
            response
        )

        if data is None:
            print(
                "[SYNTHESIS] Invalid JSON response."
            )

            print(response)
            return

        synthesis = Synthesis(
            summary=data.get(
                "summary",
                "",
            ),
            key_findings=data.get(
                "key_findings",
                [],
            ),
            limitations=data.get(
                "limitations",
                [],
            ),
            future_work=data.get(
                "future_work",
                [],
            ),
        )

        state.synthesis = (
            synthesis
        )

        print()
        print(
            "========== SYNTHESIS =========="
        )

        print()
        print("Summary:")
        print(
            state.synthesis.summary
        )

        print()
        print("Key Findings:")

        for finding in (
            state.synthesis.key_findings
        ):
            print(
                "-",
                finding,
            )

        print()
        print("Limitations:")

        for limitation in (
            state.synthesis.limitations
        ):
            print(
                "-",
                limitation,
            )

        print()
        print("Future Work:")

        for work in (
            state.synthesis.future_work
        ):
            print(
                "-",
                work,
            )

    # =====================================================
    # JSON PARSER
    # =====================================================

    def _parse_json(
        self,
        response,
    ):
        if response is None:
            return None

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

        try:
            data = json.loads(
                cleaned
            )

        except json.JSONDecodeError:
            return None

        if not isinstance(
            data,
            dict,
        ):
            return None

        return data