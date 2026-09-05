from app.services.llm_service import llm

from app.agents.evidence_extraction_agent import (
    EvidenceExtractionAgent,
)

from app.models.paper import Paper
from app.models.research_state import ResearchState

from app.evaluation.run_retrieval_evaluation import (
    find_europa_pdf,
)


def build_test_state():

    state = ResearchState(
        "Can life survive beneath Europa's ice?"
    )

    # Use the same types of questions produced
    # by PlannerAgent in the real pipeline.
    state.sub_questions = [

        (
            "What conditions could make Europa "
            "suitable for life?"
        ),

        (
            "What evidence supports the existence "
            "of a subsurface ocean on Europa?"
        ),

        (
            "What potential sources of chemical "
            "energy could support life on Europa?"
        ),

    ]

    paper = Paper(
        title=(
            "NASA's Europa Clipper—a mission to "
            "a potentially habitable ocean world"
        ),

        authors=[],

        abstract="",

        year=2020,

        url=(
            "https://openalex.org/"
            "W3013411026"
        ),

        citation_count=0,

        doi=(
            "https://doi.org/"
            "10.1038/s41467-020-15160-9"
        ),

        landing_page_url=(
            "https://www.nature.com/articles/"
            "s41467-020-15160-9"
        ),

        pdf_url=(
            "https://www.nature.com/articles/"
            "s41467-020-15160-9.pdf"
        ),

        is_open_access=True,

        open_access_status="gold",

        source_name=(
            "Nature Communications"
        ),
    )

    # -------------------------------------------------
    # We already downloaded this PDF during Research V2.
    #
    # Giving the cached path makes this isolated test
    # deterministic and avoids depending on another
    # network download.
    # -------------------------------------------------

    pdf_path = (
        find_europa_pdf()
    )

    paper.full_text_available = True

    paper.full_text_source = (
        paper.pdf_url
    )

    paper.local_pdf_path = str(
        pdf_path.resolve()
    )

    state.papers.append(
        paper
    )

    return state


def print_evidence(
    state,
):

    print()
    print()
    print("=" * 80)

    print(
        "FINAL EVIDENCE OBJECTS"
    )

    print("=" * 80)

    print(
        "Evidence count:",
        len(state.evidence),
    )

    for index, evidence in enumerate(
        state.evidence,
        start=1,
    ):

        print()
        print("=" * 80)

        print(
            f"EVIDENCE {index}"
        )

        print("=" * 80)

        print(
            "Query:",
            evidence.query,
        )

        print(
            "Source type:",
            evidence.source_type,
        )

        print(
            "Paper:",
            evidence.paper_title,
        )

        print()

        print(
            "Findings:"
        )

        for finding_index, finding in enumerate(
            evidence.findings,
            start=1,
        ):

            print(
                f"  {finding_index}. "
                f"{finding}"
            )

        print()

        print(
            "Methods:",
            evidence.methods,
        )

        print()

        print(
            "Limitations:",
            evidence.limitations,
        )

        print()

        print(
            "Relevance:",
            evidence.relevance,
        )

        print()

        print(
            "Cited chunk IDs:"
        )

        for chunk_id in (
            evidence.cited_chunk_ids
        ):

            print(
                "  ",
                chunk_id,
            )

        print()

        print(
            "Retrieved provenance:"
        )

        for chunk in (
            evidence.retrieved_chunks
        ):

            print()

            print(
                "  Chunk:",
                chunk.get(
                    "chunk_id"
                ),
            )

            print(
                "  Paper:",
                chunk.get(
                    "paper_title"
                ),
            )

            print(
                "  DOI:",
                chunk.get(
                    "doi"
                ),
            )

            print(
                "  Section:",
                chunk.get(
                    "section"
                ),
            )

            print(
                "  Pages:",
                (
                    f"{chunk.get('page_start')}-"
                    f"{chunk.get('page_end')}"
                ),
            )

            score = (
                chunk.get(
                    "retrieval_score"
                )
            )

            if isinstance(
                score,
                (int, float),
            ):

                print(
                    "  Retrieval score:",
                    f"{score:.4f}",
                )

            else:

                print(
                    "  Retrieval score:",
                    score,
                )


def validate_evidence(
    state,
):

    print()
    print()
    print("=" * 80)

    print(
        "STEP 10 VALIDATION"
    )

    print("=" * 80)

    expected_count = len(
        state.sub_questions
    )

    actual_count = len(
        state.evidence
    )

    count_passed = (
        actual_count
        == expected_count
    )

    full_text_passed = (
        actual_count > 0
        and all(
            evidence.source_type
            == "full_text_rag"
            for evidence in state.evidence
        )
    )

    findings_passed = (
        actual_count > 0
        and all(
            len(
                evidence.findings
            ) > 0
            for evidence in state.evidence
        )
    )

    citations_passed = (
        actual_count > 0
        and all(
            len(
                evidence.cited_chunk_ids
            ) > 0
            for evidence in state.evidence
        )
    )

    provenance_passed = (
        actual_count > 0
        and all(
            len(
                evidence.retrieved_chunks
            ) > 0
            for evidence in state.evidence
        )
    )

    citation_integrity_passed = True

    for evidence in (
        state.evidence
    ):

        retrieved_ids = {
            chunk.get(
                "chunk_id"
            )
            for chunk in (
                evidence.retrieved_chunks
            )
        }

        for cited_id in (
            evidence.cited_chunk_ids
        ):

            if (
                cited_id
                not in retrieved_ids
            ):

                citation_integrity_passed = False

    checks = [

        (
            "One evidence object per query",
            count_passed,
        ),

        (
            "Full-paper RAG used",
            full_text_passed,
        ),

        (
            "Findings extracted",
            findings_passed,
        ),

        (
            "Chunk citations generated",
            citations_passed,
        ),

        (
            "Provenance preserved",
            provenance_passed,
        ),

        (
            "Citations belong to retrieved chunks",
            citation_integrity_passed,
        ),
    ]

    for name, passed in checks:

        status = (
            "PASS"
            if passed
            else "FAIL"
        )

        print(
            f"{name:<45}"
            f"{status}"
        )

    all_passed = all(
        passed
        for _, passed in checks
    )

    print()
    print("-" * 80)

    if all_passed:

        print(
            "STEP 10 RESULT: PASS"
        )

        print(
            "Full-paper RAG evidence extraction "
            "is working."
        )

    else:

        print(
            "STEP 10 RESULT: FAIL"
        )

        print(
            "Inspect the output above before "
            "integrating into the main pipeline."
        )

    print("-" * 80)

    return all_passed


def main():

    print()
    print("=" * 80)

    print(
        "ORION RESEARCH V2"
    )

    print(
        "FULL-PAPER RAG EVIDENCE TEST"
    )

    print("=" * 80)

    state = (
        build_test_state()
    )

    agent = (
        EvidenceExtractionAgent(
            llm=llm,
            top_k=5,
        )
    )

    agent.run(
        state
    )

    print_evidence(
        state
    )

    validate_evidence(
        state
    )


if __name__ == "__main__":
    main()