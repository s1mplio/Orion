from app.evaluation.run_retrieval_evaluation import (
    find_europa_pdf,
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


def main():

    print()
    print("=" * 70)
    print("RESEARCH V2 - CHUNKING EXPERIMENT")
    print("=" * 70)

    # =====================================================
    # PAPER
    # =====================================================

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

    # =====================================================
    # PARSE
    # =====================================================

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

    # =====================================================
    # BASELINE
    # =====================================================

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

    # =====================================================
    # EXPERIMENTAL
    # =====================================================

    experimental_chunker = (
        SectionAwareChunkingService(
            chunk_size_words=350,
            overlap_words=60,
            minimum_chunk_words=40,
        )
    )

    experimental_chunks = (
        experimental_chunker.chunk(
            parsed_paper
        )
    )

    # =====================================================
    # SUMMARY
    # =====================================================

    print()
    print("=" * 70)
    print("CHUNKING COMPARISON")
    print("=" * 70)

    print(
        "Baseline chunks:",
        len(baseline_chunks),
    )

    print(
        "Experimental chunks:",
        len(experimental_chunks),
    )

    baseline_cross_page = sum(
        1
        for chunk in baseline_chunks
        if chunk.page_start != chunk.page_end
    )

    experimental_cross_page = sum(
        1
        for chunk in experimental_chunks
        if chunk.page_start != chunk.page_end
    )

    print(
        "Baseline cross-page chunks:",
        baseline_cross_page,
    )

    print(
        "Experimental cross-page chunks:",
        experimental_cross_page,
    )

    print()
    print("=" * 70)
    print("EXPERIMENTAL CHUNKS")
    print("=" * 70)

    for chunk in experimental_chunks:

        print()

        print(
            "ID:",
            chunk.chunk_id,
        )

        print(
            "SECTION:",
            chunk.section,
        )

        print(
            "PAGES:",
            f"{chunk.page_start}-{chunk.page_end}",
        )

        print(
            "WORDS:",
            chunk.word_count,
        )

        print(
            "TEXT:",
            chunk.text[:500],
        )


if __name__ == "__main__":
    main()