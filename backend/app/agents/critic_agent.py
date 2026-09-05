import json

from app.models.critic_results import CriticResult


class CriticAgent:
    """
    Research V2 scientific critic.

    Reviews grounded Evidence objects produced by the
    full-paper RAG pipeline.

    Important:
    Evidence objects may be generated per sub-question,
    so multiple Evidence objects can originate from the
    same scientific paper.

    Therefore this agent reasons using actual source
    provenance rather than assuming:

        one Evidence object == one paper
    """

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):
        print()
        print("=" * 70)
        print("SCIENTIFIC CRITIC")
        print("=" * 70)

        if not state.evidence:
            print("[CRITIC] No evidence available.")
            return

        batch_size = 5
        batch_results = []

        unique_papers = self._collect_unique_papers(
            state.evidence
        )

        print(
            "[CRITIC] Evidence objects:",
            len(state.evidence),
        )

        print(
            "[CRITIC] Unique source papers:",
            len(unique_papers),
        )

        # =================================================
        # BATCH REVIEW
        # =================================================

        for batch_number, start in enumerate(
            range(
                0,
                len(state.evidence),
                batch_size,
            ),
            start=1,
        ):
            batch = state.evidence[
                start:start + batch_size
            ]

            evidence_text = (
                self._format_evidence_batch(
                    batch
                )
            )

            prompt = f"""
You are an expert scientific reviewer.

Research Question:
{state.question}

Below is grounded scientific evidence extracted by a
full-paper retrieval-augmented generation system.

IMPORTANT RULES:

1. Use ONLY the supplied evidence.

2. Evidence objects may correspond to different
   sub-questions from the SAME paper.

3. Do NOT call something an agreement between multiple
   papers unless the supporting evidence actually comes
   from at least two distinct papers.

4. Distinguish:
   - repeated evidence from the same paper
   - independent support from different papers

5. Preserve supporting CHUNK_ID citations inside your
   statements whenever possible.

6. Do not invent papers, citations, findings or
   contradictions.

7. A research gap should represent something unresolved
   or insufficiently supported by the supplied evidence.

8. Confidence should reflect the strength, diversity and
   consistency of the supplied evidence.

EVIDENCE:

{evidence_text}

Analyze the evidence.

Identify:

1. Agreements supported by the evidence.
2. Contradictions between sources.
3. Important research gaps.
4. Overall confidence in the evidence.

If no contradiction exists, return an empty list.

Return ONLY valid JSON.

Use exactly this structure:

{{
    "agreements": [],
    "contradictions": [],
    "research_gaps": [],
    "confidence": ""
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
                    "[CRITIC] Invalid JSON "
                    f"for batch {batch_number}"
                )

                print(response)
                continue

            critic = CriticResult(
                agreements=data.get(
                    "agreements",
                    [],
                ),
                contradictions=data.get(
                    "contradictions",
                    [],
                ),
                research_gaps=data.get(
                    "research_gaps",
                    [],
                ),
                confidence=data.get(
                    "confidence",
                    "",
                ),
            )

            batch_results.append(
                critic
            )

            print(
                "[CRITIC] Batch",
                batch_number,
                "reviewed successfully.",
            )

        if not batch_results:
            print(
                "[CRITIC] No valid batch "
                "results generated."
            )
            return

        # =================================================
        # FINAL CRITIC
        # =================================================

        summary_text = ""

        for index, result in enumerate(
            batch_results,
            start=1,
        ):
            summary_text += f"""
BATCH {index}

Agreements:
{result.agreements}

Contradictions:
{result.contradictions}

Research Gaps:
{result.research_gaps}

Confidence:
{result.confidence}

------------------------
"""

        final_prompt = f"""
You are an expert scientific reviewer.

Research Question:
{state.question}

You are combining reviews produced from batches of
grounded full-paper evidence.

Number of original evidence objects:
{len(state.evidence)}

Number of unique source papers:
{len(unique_papers)}

BATCH REVIEWS:

{summary_text}

Produce ONE final scientific review.

IMPORTANT:

- Do not claim independent confirmation from multiple
  papers unless the original evidence contained multiple
  distinct source papers.

- Preserve valid [chunk_id] citations already present in
  the batch reviews.

- Do not create new chunk IDs.

- Do not invent contradictions.

- Merge duplicate conclusions.

- Confidence must reflect evidence quality and source
  diversity.

Return ONLY valid JSON.

Use exactly:

{{
    "agreements": [],
    "contradictions": [],
    "research_gaps": [],
    "confidence": ""
}}
"""

        print(
            "[CRITIC] Number of batch results:",
            len(batch_results),
        )

        response = self.llm.generate(
            final_prompt
        )

        data = self._parse_json(
            response
        )

        if data is None:
            print(
                "[CRITIC] Invalid final "
                "critic response."
            )

            print(response)
            return

        final_critic = CriticResult(
            agreements=data.get(
                "agreements",
                [],
            ),
            contradictions=data.get(
                "contradictions",
                [],
            ),
            research_gaps=data.get(
                "research_gaps",
                [],
            ),
            confidence=data.get(
                "confidence",
                "",
            ),
        )

        state.critic_results = (
            final_critic
        )

        # Research V2 diagnostic metadata.
        # Existing downstream agents remain compatible.
        state.critic_source_papers = (
            sorted(unique_papers)
        )

        print()
        print(
            "========== FINAL CRITIC =========="
        )

        print()
        print("Agreements:")

        for item in (
            state.critic_results.agreements
        ):
            print("-", item)

        print()
        print("Contradictions:")

        for item in (
            state.critic_results.contradictions
        ):
            print("-", item)

        print()
        print("Research Gaps:")

        for item in (
            state.critic_results.research_gaps
        ):
            print("-", item)

        print()
        print("Confidence:")
        print(
            state.critic_results.confidence
        )

    # =====================================================
    # EVIDENCE FORMATTING
    # =====================================================

    def _format_evidence_batch(
        self,
        batch,
    ):
        blocks = []

        for index, evidence in enumerate(
            batch,
            start=1,
        ):
            source_papers = (
                self._evidence_source_papers(
                    evidence
                )
            )

            provenance = (
                self._format_provenance(
                    evidence
                )
            )

            findings = "\n".join(
                f"- {finding}"
                for finding in (
                    evidence.findings or []
                )
            )

            cited_ids = ", ".join(
                evidence.cited_chunk_ids
                or []
            )

            if not cited_ids:
                cited_ids = "None"

            if not source_papers:
                source_text = (
                    evidence.paper_title
                    or "Unknown"
                )
            else:
                source_text = ", ".join(
                    sorted(source_papers)
                )

            blocks.append(
                f"""
EVIDENCE OBJECT {index}

Sub-question:
{getattr(evidence, "query", None)}

Source type:
{getattr(evidence, "source_type", "unknown")}

Source papers:
{source_text}

Findings:
{findings}

Methods:
{evidence.methods}

Limitations:
{evidence.limitations}

Relevance:
{evidence.relevance}

Cited chunk IDs:
{cited_ids}

Retrieved provenance:
{provenance}

------------------------
"""
            )

        return "\n".join(
            blocks
        )

    def _format_provenance(
        self,
        evidence,
    ):
        retrieved = getattr(
            evidence,
            "retrieved_chunks",
            [],
        ) or []

        if not retrieved:
            return "No provenance available."

        lines = []

        for item in retrieved:
            chunk_id = item.get(
                "chunk_id",
                "Unknown",
            )

            paper_title = item.get(
                "paper_title",
                "Unknown",
            )

            doi = item.get(
                "doi",
                "Unknown",
            )

            section = item.get(
                "section",
                "unknown",
            )

            page_start = item.get(
                "page_start",
                "?",
            )

            page_end = item.get(
                "page_end",
                "?",
            )

            lines.append(
                (
                    f"- [{chunk_id}] "
                    f"Paper: {paper_title} | "
                    f"DOI: {doi} | "
                    f"Section: {section} | "
                    f"Pages: {page_start}-{page_end}"
                )
            )

        return "\n".join(
            lines
        )

    # =====================================================
    # SOURCE TRACKING
    # =====================================================

    def _collect_unique_papers(
        self,
        evidence_objects,
    ):
        papers = set()

        for evidence in evidence_objects:
            papers.update(
                self._evidence_source_papers(
                    evidence
                )
            )

        return papers

    def _evidence_source_papers(
        self,
        evidence,
    ):
        papers = set()

        retrieved = getattr(
            evidence,
            "retrieved_chunks",
            [],
        ) or []

        cited_ids = set(
            getattr(
                evidence,
                "cited_chunk_ids",
                [],
            ) or []
        )

        # Prefer papers actually cited by
        # generated findings.
        for item in retrieved:
            chunk_id = item.get(
                "chunk_id"
            )

            if (
                cited_ids
                and chunk_id not in cited_ids
            ):
                continue

            title = item.get(
                "paper_title"
            )

            if title:
                papers.add(
                    title
                )

        # Fallback for Research V1 or evidence
        # without provenance.
        if (
            not papers
            and evidence.paper_title
        ):
            papers.add(
                evidence.paper_title
            )

        return papers

    # =====================================================
    # JSON PARSING
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