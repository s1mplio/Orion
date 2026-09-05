from app.services.llm_service import llm

from app.agents.evidence_extraction_agent import (
    EvidenceExtractionAgent,
)

from app.evaluation.generation_evaluator import (
    GenerationEvaluator,
)

from app.evaluation.test_full_paper_evidence import (
    build_test_state,
)

from app.services.paper_parser_service import (
    PaperParserService,
)

from app.services.paper_chunking_service import (
    PaperChunkingService,
)


def build_chunk_lookup(state):
    """
    Rebuild the same full-paper chunks so the evaluator
    can access the actual source text behind each chunk ID.
    """

    parser = PaperParserService()

    chunker = PaperChunkingService(
        chunk_size_words=350,
        overlap_words=60,
        minimum_chunk_words=40,
    )

    chunk_lookup = {}

    for paper in state.papers:

        parsed_paper = parser.parse(
            paper
        )

        if parsed_paper is None:
            continue

        chunks = chunker.chunk(
            parsed_paper
        )

        for chunk in chunks:
            chunk_lookup[
                chunk.chunk_id
            ] = chunk

    return chunk_lookup


def print_metrics(
    evidence,
    metrics,
):
    print()
    print("=" * 80)
    print(
        "EVALUATION RESULT"
    )
    print("=" * 80)

    print(
        "Query:",
        evidence.query,
    )

    print()

    print(
        f"Faithfulness:          "
        f"{metrics.faithfulness:.3f}"
    )

    print(
        f"Answer Relevance:      "
        f"{metrics.answer_relevance:.3f}"
    )

    print(
        f"Context Relevance:     "
        f"{metrics.context_relevance:.3f}"
    )

    print(
        f"Citation Correctness:  "
        f"{metrics.citation_correctness:.3f}"
    )

    print(
        f"Evaluated Claims:      "
        f"{metrics.evaluated_claims}"
    )

    print()
    print(
        "CLAIM-LEVEL RESULTS"
    )
    print("-" * 80)

    for index, claim_result in enumerate(
        metrics.claim_evaluations,
        start=1,
    ):
        print()
        print(
            f"Claim {index}:"
        )

        print(
            claim_result.claim
        )

        print(
            "Best supporting chunk:",
            (
                claim_result.chunk_id
                or "NONE"
            ),
        )

        print(
            "Faithfulness:",
            f"{claim_result.faithfulness:.3f}",
        )

        print(
            "Citation correctness:",
            f"{claim_result.citation_correctness:.3f}",
        )

        print(
            "Explanation:",
            claim_result.explanation,
        )


def print_final_benchmark(
    results,
):
    if not results:

        print(
            "No generation evaluation "
            "results available."
        )

        return

    count = len(
        results
    )

    average_faithfulness = (
        sum(
            metrics.faithfulness
            for _, metrics in results
        )
        / count
    )

    average_answer_relevance = (
        sum(
            metrics.answer_relevance
            for _, metrics in results
        )
        / count
    )

    average_context_relevance = (
        sum(
            metrics.context_relevance
            for _, metrics in results
        )
        / count
    )

    average_citation_correctness = (
        sum(
            metrics.citation_correctness
            for _, metrics in results
        )
        / count
    )

    print()
    print()
    print("=" * 80)
    print(
        "FINAL GENERATION BENCHMARK"
    )
    print("=" * 80)

    print(
        "Evaluated questions:",
        count,
    )

    print()

    print(
        f"{'METRIC':<30}"
        f"{'SCORE':>10}"
    )

    print("-" * 40)

    print(
        f"{'Faithfulness':<30}"
        f"{average_faithfulness:>10.3f}"
    )

    print(
        f"{'Answer Relevance':<30}"
        f"{average_answer_relevance:>10.3f}"
    )

    print(
        f"{'Context Relevance':<30}"
        f"{average_context_relevance:>10.3f}"
    )

    print(
        f"{'Citation Correctness':<30}"
        f"{average_citation_correctness:>10.3f}"
    )

    print("=" * 80)


def main():
    print()
    print("=" * 80)
    print(
        "ORION RESEARCH V2"
    )
    print(
        "GENERATION / GROUNDING BENCHMARK"
    )
    print("=" * 80)

    # -------------------------------------------------
    # Build the same isolated Europa test state
    # -------------------------------------------------

    state = build_test_state()

    # -------------------------------------------------
    # Run actual full-paper RAG evidence extraction
    # -------------------------------------------------

    evidence_agent = (
        EvidenceExtractionAgent(
            llm=llm,
            top_k=5,
        )
    )

    evidence_agent.run(
        state
    )

    if not state.evidence:

        print(
            "No evidence generated."
        )

        return

    # -------------------------------------------------
    # Build lookup:
    #
    # chunk_id -> actual PaperChunk
    # -------------------------------------------------

    print()
    print("=" * 80)
    print(
        "BUILDING EVALUATION CHUNK LOOKUP"
    )
    print("=" * 80)

    chunk_lookup = (
        build_chunk_lookup(
            state
        )
    )

    print(
        "Chunks available to evaluator:",
        len(chunk_lookup),
    )

    if not chunk_lookup:

        print(
            "Cannot evaluate generation "
            "without source chunks."
        )

        return

    # -------------------------------------------------
    # Generation evaluator
    # -------------------------------------------------

    evaluator = (
        GenerationEvaluator(
            llm=llm
        )
    )

    results = []

    for evidence in (
        state.evidence
    ):

        metrics = (
            evaluator.evaluate(
                evidence=evidence,
                chunk_lookup=chunk_lookup,
            )
        )

        results.append(
            (
                evidence,
                metrics,
            )
        )

        print_metrics(
            evidence=evidence,
            metrics=metrics,
        )

    # -------------------------------------------------
    # Final aggregate benchmark
    # -------------------------------------------------

    print_final_benchmark(
        results
    )


if __name__ == "__main__":
    main()