import json
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ClaimEvaluation:
    claim: str
    chunk_id: str

    faithfulness: float
    citation_correctness: float

    explanation: str


@dataclass
class GenerationMetrics:
    faithfulness: float
    answer_relevance: float
    context_relevance: float
    citation_correctness: float

    evaluated_claims: int
    claim_evaluations: List[ClaimEvaluation]


class GenerationEvaluator:
    """
    Orion Research V2 generation / grounding evaluator.

    Measures:

    1. Faithfulness
       Is the generated scientific claim supported by
       the cited retrieved passage?

    2. Answer relevance
       Does the generated evidence help answer the
       research sub-question?

    3. Context relevance
       Are the retrieved passages useful for answering
       the research sub-question?

    4. Citation correctness
       Does the cited chunk actually support the claim
       associated with that citation?

    This evaluator is intentionally separate from the
    production EvidenceExtractionAgent.
    """

    def __init__(
        self,
        llm,
    ):
        self.llm = llm

    # =====================================================
    # PUBLIC API
    # =====================================================

    def evaluate(
        self,
        evidence,
        chunk_lookup,
    ) -> GenerationMetrics:

        print()
        print("=" * 80)
        print("GENERATION / GROUNDING EVALUATION")
        print("=" * 80)

        print(
            "Query:",
            evidence.query,
        )

        print(
            "Source type:",
            evidence.source_type,
        )

        # -------------------------------------------------
        # Claim-level grounding
        # -------------------------------------------------

        claim_evaluations = (
            self._evaluate_claims(
                evidence=evidence,
                chunk_lookup=chunk_lookup,
            )
        )

        # -------------------------------------------------
        # Answer relevance
        # -------------------------------------------------

        answer_relevance = (
            self._evaluate_answer_relevance(
                evidence
            )
        )

        # -------------------------------------------------
        # Context relevance
        # -------------------------------------------------

        context_relevance = (
            self._evaluate_context_relevance(
                evidence=evidence,
                chunk_lookup=chunk_lookup,
            )
        )

        # -------------------------------------------------
        # Aggregate claim metrics
        # -------------------------------------------------

        if claim_evaluations:

            faithfulness = sum(
                item.faithfulness
                for item in claim_evaluations
            ) / len(
                claim_evaluations
            )

            citation_correctness = sum(
                item.citation_correctness
                for item in claim_evaluations
            ) / len(
                claim_evaluations
            )

        else:

            faithfulness = 0.0
            citation_correctness = 0.0

        return GenerationMetrics(
            faithfulness=self._clamp(
                faithfulness
            ),

            answer_relevance=self._clamp(
                answer_relevance
            ),

            context_relevance=self._clamp(
                context_relevance
            ),

            citation_correctness=self._clamp(
                citation_correctness
            ),

            evaluated_claims=len(
                claim_evaluations
            ),

            claim_evaluations=(
                claim_evaluations
            ),
        )

    # =====================================================
    # CLAIM EVALUATION
    # =====================================================

    def _evaluate_claims(
        self,
        evidence,
        chunk_lookup,
    ) -> List[ClaimEvaluation]:

        evaluations = []

        findings = list(
            evidence.findings or []
        )

        cited_ids = list(
            evidence.cited_chunk_ids or []
        )

        if not findings:

            return evaluations

        # -------------------------------------------------
        # Current Evidence model stores findings and cited
        # chunk IDs separately.
        #
        # We therefore evaluate each finding against ALL
        # cited chunks and ask the judge to identify the
        # strongest supporting citation.
        #
        # This avoids incorrectly assuming:
        #
        # finding[0] -> cited_chunk_ids[0]
        # finding[1] -> cited_chunk_ids[1]
        #
        # because that mapping is not currently preserved.
        # -------------------------------------------------

        cited_chunks = []

        for chunk_id in cited_ids:

            chunk = (
                chunk_lookup.get(
                    chunk_id
                )
            )

            if chunk is not None:

                cited_chunks.append(
                    chunk
                )

        if not cited_chunks:

            print(
                "[GEN EVAL] No cited chunks available."
            )

            return evaluations

        context = (
            self._format_chunks(
                cited_chunks
            )
        )

        for index, claim in enumerate(
            findings,
            start=1,
        ):

            print()
            print(
                f"[GEN EVAL] Evaluating claim "
                f"{index}/{len(findings)}"
            )

            print(
                "[GEN EVAL] Claim:",
                claim,
            )

            result = (
                self._judge_claim(
                    query=evidence.query,
                    claim=claim,
                    context=context,
                )
            )

            if result is None:

                print(
                    "[GEN EVAL] Claim judge failed."
                )

                evaluations.append(
                    ClaimEvaluation(
                        claim=claim,
                        chunk_id="",
                        faithfulness=0.0,
                        citation_correctness=0.0,
                        explanation=(
                            "Evaluation failed."
                        ),
                    )
                )

                continue

            best_chunk_id = str(
                result.get(
                    "best_chunk_id",
                    "",
                )
            ).strip()

            valid_ids = {
                chunk.chunk_id
                for chunk in cited_chunks
            }

            # Judge cannot invent a citation.
            if (
                best_chunk_id
                not in valid_ids
            ):

                best_chunk_id = ""

            faithfulness = (
                self._safe_score(
                    result.get(
                        "faithfulness",
                        0.0,
                    )
                )
            )

            citation_correctness = (
                self._safe_score(
                    result.get(
                        "citation_correctness",
                        0.0,
                    )
                )
            )

            explanation = str(
                result.get(
                    "explanation",
                    "",
                )
            ).strip()

            evaluation = (
                ClaimEvaluation(
                    claim=claim,
                    chunk_id=best_chunk_id,
                    faithfulness=faithfulness,
                    citation_correctness=(
                        citation_correctness
                    ),
                    explanation=explanation,
                )
            )

            evaluations.append(
                evaluation
            )

            print(
                "[GEN EVAL] Best chunk:",
                best_chunk_id or "NONE",
            )

            print(
                "[GEN EVAL] Faithfulness:",
                f"{faithfulness:.3f}",
            )

            print(
                "[GEN EVAL] Citation correctness:",
                f"{citation_correctness:.3f}",
            )

        return evaluations

    # =====================================================
    # CLAIM JUDGE
    # =====================================================

    def _judge_claim(
        self,
        query,
        claim,
        context,
    ):

        prompt = f"""
You are evaluating the grounding quality of a scientific
retrieval-augmented generation system.

You must judge ONLY using the cited passages below.

RESEARCH QUESTION:
{query}

GENERATED CLAIM:
{claim}

CITED PASSAGES:

{context}

Evaluate two things.

FAITHFULNESS:
How strongly is the generated claim supported by the
information contained in the cited passages?

Score:
1.0 = directly and completely supported
0.75 = mostly supported with minor unsupported detail
0.5 = partially supported
0.25 = weakly supported
0.0 = unsupported or contradicted

CITATION CORRECTNESS:
Does the best cited passage actually provide evidence
for this generated claim?

Score:
1.0 = citation directly supports the claim
0.75 = citation substantially supports it
0.5 = citation provides partial support
0.25 = citation is only loosely related
0.0 = citation does not support it

Select the CHUNK_ID that provides the strongest support.

Do not use outside scientific knowledge.

Do not reward a claim merely because it sounds
scientifically plausible.

Return ONLY valid JSON.

Use exactly:

{{
    "faithfulness": 0.0,
    "citation_correctness": 0.0,
    "best_chunk_id": "",
    "explanation": ""
}}
"""

        response = (
            self.llm.generate(
                prompt
            )
        )

        return (
            self._parse_json(
                response
            )
        )

    # =====================================================
    # ANSWER RELEVANCE
    # =====================================================

    def _evaluate_answer_relevance(
        self,
        evidence,
    ) -> float:

        findings_text = "\n".join(
            f"- {finding}"
            for finding in (
                evidence.findings or []
            )
        )

        prompt = f"""
You are evaluating a scientific research assistant.

RESEARCH QUESTION:
{evidence.query}

GENERATED EVIDENCE:
{findings_text}

RELEVANCE EXPLANATION:
{evidence.relevance}

Evaluate how directly the generated evidence helps answer
the research question.

Score:
1.0 = directly answers the question
0.75 = highly relevant but incomplete
0.5 = partially relevant
0.25 = mostly tangential
0.0 = irrelevant

Do not evaluate factual correctness here.
Evaluate only relevance to the question.

Return ONLY valid JSON.

Use exactly:

{{
    "answer_relevance": 0.0,
    "explanation": ""
}}
"""

        response = (
            self.llm.generate(
                prompt
            )
        )

        data = (
            self._parse_json(
                response
            )
        )

        if data is None:

            return 0.0

        return (
            self._safe_score(
                data.get(
                    "answer_relevance",
                    0.0,
                )
            )
        )

    # =====================================================
    # CONTEXT RELEVANCE
    # =====================================================

    def _evaluate_context_relevance(
        self,
        evidence,
        chunk_lookup,
    ) -> float:

        chunks = []

        for metadata in (
            evidence.retrieved_chunks or []
        ):

            chunk_id = (
                metadata.get(
                    "chunk_id"
                )
            )

            if not chunk_id:

                continue

            chunk = (
                chunk_lookup.get(
                    chunk_id
                )
            )

            if chunk is not None:

                chunks.append(
                    chunk
                )

        if not chunks:

            return 0.0

        context = (
            self._format_chunks(
                chunks
            )
        )

        prompt = f"""
You are evaluating the retrieval context of a scientific
RAG system.

RESEARCH QUESTION:
{evidence.query}

RETRIEVED PASSAGES:

{context}

Evaluate how useful the retrieved passages are as a set
for answering the research question.

Consider:

- direct relevance
- useful scientific evidence
- amount of irrelevant material
- whether the context contains enough information to
  address the question

Score:
1.0 = highly relevant context with strong evidence
0.75 = mostly relevant with some unnecessary material
0.5 = mixed useful and irrelevant context
0.25 = weakly useful context
0.0 = irrelevant context

Do NOT evaluate the generated answer.
Evaluate only the retrieved context.

Do not use outside knowledge.

Return ONLY valid JSON.

Use exactly:

{{
    "context_relevance": 0.0,
    "explanation": ""
}}
"""

        response = (
            self.llm.generate(
                prompt
            )
        )

        data = (
            self._parse_json(
                response
            )
        )

        if data is None:

            return 0.0

        return (
            self._safe_score(
                data.get(
                    "context_relevance",
                    0.0,
                )
            )
        )

    # =====================================================
    # CHUNK FORMATTING
    # =====================================================

    def _format_chunks(
        self,
        chunks,
    ) -> str:

        blocks = []

        for chunk in chunks:

            blocks.append(
                (
                    f"[CHUNK_ID: "
                    f"{chunk.chunk_id}]\n"
                    f"Paper: "
                    f"{chunk.title}\n"
                    f"DOI: "
                    f"{chunk.doi or 'Unknown'}\n"
                    f"Section: "
                    f"{chunk.section}\n"
                    f"Pages: "
                    f"{chunk.page_start}-"
                    f"{chunk.page_end}\n"
                    f"Text:\n"
                    f"{chunk.text}"
                )
            )

        return "\n\n".join(
            blocks
        )

    # =====================================================
    # JSON PARSING
    # =====================================================

    def _parse_json(
        self,
        response,
    ) -> Optional[dict]:

        if response is None:

            return None

        cleaned = str(
            response
        ).strip()

        if cleaned.startswith(
            "```json"
        ):

            cleaned = (
                cleaned[7:]
            )

        elif cleaned.startswith(
            "```"
        ):

            cleaned = (
                cleaned[3:]
            )

        if cleaned.endswith(
            "```"
        ):

            cleaned = (
                cleaned[:-3]
            )

        cleaned = (
            cleaned.strip()
        )

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

    # =====================================================
    # SCORE HELPERS
    # =====================================================

    def _safe_score(
        self,
        value,
    ) -> float:

        try:

            score = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):

            return 0.0

        return (
            self._clamp(
                score
            )
        )

    @staticmethod
    def _clamp(
        score,
    ) -> float:

        return max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )