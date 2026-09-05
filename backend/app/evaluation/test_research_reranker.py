from app.evaluation.run_retrieval_evaluation import (
    build_europa_corpus,
)

from app.services.research_reranker import (
    ResearchReranker,
)


def main():

    print()
    print("=" * 70)
    print("RESEARCH V2 - RERANKER TEST")
    print("=" * 70)

    # -----------------------------------------------------
    # Build the same frozen evaluation corpus
    # -----------------------------------------------------

    (
        vector_store,
        retriever,
        chunks,
    ) = build_europa_corpus()

    query = (
        "What evidence supports the existence "
        "of a subsurface ocean on Europa?"
    )

    print()
    print("QUERY:")
    print(query)

    # -----------------------------------------------------
    # IMPORTANT:
    #
    # We want MORE than the final Top-5 here.
    #
    # The reranker needs a candidate pool to reorder.
    # -----------------------------------------------------

    candidate_count = 10

    candidates = retriever.retrieve(
        query=query,
        top_k=candidate_count,
    )

    print()
    print("=" * 70)
    print("BEFORE RERANKING")
    print("=" * 70)

    for candidate in candidates:

        print()
        print(
            "Retrieval rank:",
            candidate.retrieval_rank,
        )

        print(
            "FAISS rank:",
            candidate.faiss_rank,
        )

        print(
            "Chunk:",
            candidate.chunk_id,
        )

        print(
            "Section:",
            candidate.section,
        )

        print(
            "Page:",
            candidate.page_start,
        )

        print(
            "Vector score:",
            round(
                candidate.score,
                4,
            ),
        )

        print(
            "Text:",
            candidate.text[:300]
            .replace(
                "\n",
                " ",
            ),
        )

    # -----------------------------------------------------
    # Load reranker
    # -----------------------------------------------------

    reranker = ResearchReranker()

    # -----------------------------------------------------
    # Rerank candidates
    # -----------------------------------------------------

    results = reranker.rerank(
        query=query,
        candidates=candidates,
        top_k=5,
    )

    print()
    print()
    print("=" * 70)
    print("AFTER RERANKING")
    print("=" * 70)

    for result in results:

        print()
        print(
            "Final rank:",
            result.retrieval_rank,
        )

        print(
            "Old retrieval rank:",
            result.original_retrieval_rank,
        )

        print(
            "FAISS rank:",
            result.faiss_rank,
        )

        print(
            "Chunk:",
            result.chunk_id,
        )

        print(
            "Section:",
            result.section,
        )

        print(
            "Page:",
            result.page_start,
        )

        print(
            "Vector score:",
            round(
                result.vector_score,
                4,
            ),
        )

        print(
            "Reranker score:",
            round(
                result.reranker_score,
                4,
            ),
        )

        print(
            "Text:",
            result.text[:300]
            .replace(
                "\n",
                " ",
            ),
        )


if __name__ == "__main__":
    main()