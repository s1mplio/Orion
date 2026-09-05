from app.evaluation.run_retrieval_evaluation import (
    find_europa_pdf,
)

from app.evaluation.retrieval_evaluator import (
    RetrievalEvaluator,
)

from app.evaluation.retrieval_test_cases import (
    RETRIEVAL_TEST_CASES,
)

from app.evaluation.chunking_test_cases import (
    CROSS_PAGE_TEST_CASES,
)

from app.models.paper import Paper

from app.services.paper_parser_service import (
    PaperParserService,
)

from app.services.paper_chunking_service import (
    PaperChunkingService,
)

from app.services.section_aware_chunking_service import (
    SectionAwareChunkingService,
)

from app.services.research_vector_store import (
    ResearchVectorStore,
)

from app.services.research_retriever import (
    ResearchRetriever,
)


K = 5


# =========================================================
# PAPER
# =========================================================


def build_paper():

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

    return paper


# =========================================================
# PARSE ONCE
# =========================================================


def parse_paper():

    paper = (
        build_paper()
    )

    parser = (
        PaperParserService()
    )

    parsed_paper = parser.parse(
        paper
    )

    if parsed_paper is None:

        raise RuntimeError(
            "Paper parsing failed."
        )

    return parsed_paper


# =========================================================
# BUILD RETRIEVER
# =========================================================


def build_retriever(
    chunks,
):

    vector_store = (
        ResearchVectorStore()
    )

    vector_store.add_chunks(
        chunks
    )

    retriever = (
        ResearchRetriever(
            vector_store=vector_store
        )
    )

    return retriever


# =========================================================
# EVALUATE ONE SYSTEM
# =========================================================


def evaluate_system(
    system_name,
    retriever,
    test_cases,
):

    evaluator = (
        RetrievalEvaluator()
    )

    precision_scores = []
    recall_scores = []
    reciprocal_rank_scores = []
    ndcg_scores = []

    print()
    print("=" * 80)

    print(
        system_name
    )

    print("=" * 80)

    for test_case in test_cases:

        results = (
            retriever.retrieve(
                query=test_case.query,
                top_k=K,
            )
        )

        retrieved_ids = [
            result.chunk_id
            for result in results
        ]

        relevant_ids = set(
            test_case.relevant_chunk_ids
        )

        metrics = (
            evaluator.evaluate(
                retrieved_chunk_ids=(
                    retrieved_ids
                ),

                relevant_chunk_ids=(
                    relevant_ids
                ),

                k=K,
            )
        )

        precision_scores.append(
            metrics.precision_at_k
        )

        recall_scores.append(
            metrics.recall_at_k
        )

        reciprocal_rank_scores.append(
            metrics.reciprocal_rank
        )

        ndcg_scores.append(
            metrics.ndcg_at_k
        )

        print()
        print(
            "QUERY:",
            test_case.name,
        )

        print(
            "Question:",
            test_case.query,
        )

        print()

        print(
            "Relevant IDs:"
        )

        for chunk_id in (
            test_case.relevant_chunk_ids
        ):

            print(
                "  ",
                chunk_id,
            )

        print()
        print(
            "Retrieved:"
        )

        for result in results:

            relevant_marker = (
                "RELEVANT"
                if (
                    result.chunk_id
                    in relevant_ids
                )
                else "-"
            )

            print(
                f"  Rank {result.retrieval_rank}: "
                f"{result.chunk_id} "
                f"| score={result.score:.4f} "
                f"| section={result.section} "
                f"| pages="
                f"{result.page_start}-"
                f"{result.page_end} "
                f"| {relevant_marker}"
            )

        print()

        print(
            f"P@{K}:",
            f"{metrics.precision_at_k:.3f}",
        )

        print(
            f"R@{K}:",
            f"{metrics.recall_at_k:.3f}",
        )

        print(
            "MRR:",
            f"{metrics.reciprocal_rank:.3f}",
        )

        print(
            f"nDCG@{K}:",
            f"{metrics.ndcg_at_k:.3f}",
        )

    query_count = len(
        test_cases
    )

    if query_count == 0:

        raise RuntimeError(
            "No evaluation test cases."
        )

    averages = {

        "precision": (
            sum(precision_scores)
            / query_count
        ),

        "recall": (
            sum(recall_scores)
            / query_count
        ),

        "mrr": (
            sum(
                reciprocal_rank_scores
            )
            / query_count
        ),

        "ndcg": (
            sum(ndcg_scores)
            / query_count
        ),
    }

    return averages


# =========================================================
# PRINT FINAL COMPARISON
# =========================================================


def print_final_comparison(
    baseline_metrics,
    cross_page_metrics,
    baseline_chunk_count,
    cross_page_chunk_count,
):

    print()
    print()
    print("=" * 80)

    print(
        "FINAL CHUNKING BENCHMARK"
    )

    print("=" * 80)

    print()

    print(
        "Evaluated queries:",
        len(RETRIEVAL_TEST_CASES),
    )

    print(
        "K:",
        K,
    )

    print(
        "Baseline chunks:",
        baseline_chunk_count,
    )

    print(
        "Cross-page chunks:",
        cross_page_chunk_count,
    )

    print()

    print(
        f"{'SYSTEM':<35}"
        f"{'P@K':>8}"
        f"{'R@K':>8}"
        f"{'MRR':>8}"
        f"{'nDCG':>8}"
    )

    print(
        "-" * 67
    )

    print(
        f"{'Page-Bounded + Filtered':<35}"
        f"{baseline_metrics['precision']:>8.3f}"
        f"{baseline_metrics['recall']:>8.3f}"
        f"{baseline_metrics['mrr']:>8.3f}"
        f"{baseline_metrics['ndcg']:>8.3f}"
    )

    print(
        f"{'Cross-Page + Filtered':<35}"
        f"{cross_page_metrics['precision']:>8.3f}"
        f"{cross_page_metrics['recall']:>8.3f}"
        f"{cross_page_metrics['mrr']:>8.3f}"
        f"{cross_page_metrics['ndcg']:>8.3f}"
    )

    print()
    print("=" * 80)


# =========================================================
# MAIN
# =========================================================


def main():

    print()
    print("=" * 80)

    print(
        "ORION RESEARCH V2"
    )

    print(
        "CHUNKING STRATEGY A/B EVALUATION"
    )

    print("=" * 80)

    # -----------------------------------------------------
    # Parse the PDF once.
    # -----------------------------------------------------

    parsed_paper = (
        parse_paper()
    )

    # -----------------------------------------------------
    # BASELINE CHUNKS
    # -----------------------------------------------------

    baseline_chunker = (
        PaperChunkingService(
            chunk_size_words=350,
            overlap_words=60,
            minimum_chunk_words=40,
        )
    )

    baseline_chunks = (
        baseline_chunker.chunk(
            parsed_paper
        )
    )

    # -----------------------------------------------------
    # CROSS-PAGE CHUNKS
    # -----------------------------------------------------

    cross_page_chunker = (
        SectionAwareChunkingService(
            chunk_size_words=350,
            overlap_words=60,
            minimum_chunk_words=40,
        )
    )

    cross_page_chunks = (
        cross_page_chunker.chunk(
            parsed_paper
        )
    )

    # -----------------------------------------------------
    # BUILD TWO COMPLETELY SEPARATE VECTOR STORES
    # -----------------------------------------------------

    print()
    print(
        "Building baseline vector store..."
    )

    baseline_retriever = (
        build_retriever(
            baseline_chunks
        )
    )

    print()
    print(
        "Building cross-page vector store..."
    )

    cross_page_retriever = (
        build_retriever(
            cross_page_chunks
        )
    )

    # -----------------------------------------------------
    # EVALUATE BASELINE
    # -----------------------------------------------------

    baseline_metrics = (
        evaluate_system(
            system_name=(
                "PAGE-BOUNDED + FILTERED"
            ),

            retriever=(
                baseline_retriever
            ),

            test_cases=(
                RETRIEVAL_TEST_CASES
            ),
        )
    )

    # -----------------------------------------------------
    # EVALUATE CROSS-PAGE
    # -----------------------------------------------------

    cross_page_metrics = (
        evaluate_system(
            system_name=(
                "CROSS-PAGE + FILTERED"
            ),

            retriever=(
                cross_page_retriever
            ),

            test_cases=(
                CROSS_PAGE_TEST_CASES
            ),
        )
    )

    # -----------------------------------------------------
    # FINAL TABLE
    # -----------------------------------------------------

    print_final_comparison(
        baseline_metrics=(
            baseline_metrics
        ),

        cross_page_metrics=(
            cross_page_metrics
        ),

        baseline_chunk_count=(
            len(baseline_chunks)
        ),

        cross_page_chunk_count=(
            len(cross_page_chunks)
        ),
    )


if __name__ == "__main__":
    main()