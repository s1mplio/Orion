from app.evaluation.run_retrieval_evaluation import (
    find_europa_pdf,
)

from app.models.paper import Paper

from app.services.paper_parser_service import (
    PaperParserService,
)

from app.services.section_aware_chunking_service import (
    SectionAwareChunkingService,
)


# =========================================================
# QUESTIONS WE ARE EVALUATING
# =========================================================


EVALUATION_QUESTIONS = [

    (
        "EUROPA HABITABILITY",
        "What conditions could make Europa suitable for life?",
    ),

    (
        "SUBSURFACE OCEAN",
        "What evidence supports the existence "
        "of a subsurface ocean on Europa?",
    ),

    (
        "SURFACE TO OCEAN EXCHANGE",
        "How could material from Europa's "
        "surface reach its subsurface ocean?",
    ),

    (
        "CHEMICAL ENERGY",
        "What potential sources of chemical "
        "energy could support life on Europa?",
    ),

    (
        "EUROPA CLIPPER SCIENCE",
        "How will Europa Clipper investigate "
        "Europa's habitability?",
    ),
]


# =========================================================
# BUILD PAPER
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
# BUILD EXPERIMENTAL CHUNKS
# =========================================================


def build_experimental_chunks():

    paper = (
        build_paper()
    )

    parser = (
        PaperParserService()
    )

    parsed_paper = (
        parser.parse(
            paper
        )
    )

    if parsed_paper is None:

        raise RuntimeError(
            "Paper parsing failed."
        )

    chunker = (
        SectionAwareChunkingService(
            chunk_size_words=350,
            overlap_words=60,
            minimum_chunk_words=40,
        )
    )

    chunks = (
        chunker.chunk(
            parsed_paper
        )
    )

    if not chunks:

        raise RuntimeError(
            "No experimental chunks generated."
        )

    return chunks


# =========================================================
# PRINT QUESTIONS
# =========================================================


def print_questions():

    print()
    print("=" * 80)
    print("EVALUATION QUESTIONS")
    print("=" * 80)

    for index, (
        name,
        question,
    ) in enumerate(
        EVALUATION_QUESTIONS,
        start=1,
    ):

        print()

        print(
            f"{index}. {name}"
        )

        print(
            question
        )


# =========================================================
# PRINT COMPLETE CHUNKS
# =========================================================


def print_chunks(
    chunks,
):

    print()
    print("=" * 80)
    print("SECTION-AWARE CHUNKS")
    print("=" * 80)

    print(
        "Total chunks:",
        len(chunks),
    )

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        print()
        print()
        print("=" * 80)

        print(
            f"CHUNK {index}"
        )

        print("=" * 80)

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
            (
                f"{chunk.page_start}"
                if (
                    chunk.page_start
                    == chunk.page_end
                )
                else (
                    f"{chunk.page_start}"
                    f"-{chunk.page_end}"
                )
            ),
        )

        print(
            "WORDS:",
            chunk.word_count,
        )

        print()
        print(
            "FULL TEXT:"
        )

        print("-" * 80)

        print(
            chunk.text
        )

        print("-" * 80)


# =========================================================
# PRINT QUICK LABEL TEMPLATE
# =========================================================


def print_label_template():

    print()
    print()
    print("=" * 80)
    print("LABEL TEMPLATE")
    print("=" * 80)

    print()
    print(
        "After reading the chunks above, "
        "we will fill these:"
    )

    for name, question in (
        EVALUATION_QUESTIONS
    ):

        print()
        print(
            name
        )

        print(
            "Question:",
            question,
        )

        print(
            "Relevant chunk IDs:"
        )

        print(
            "[]"
        )


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
        "SECTION-AWARE CHUNK LABELLING"
    )

    print("=" * 80)

    chunks = (
        build_experimental_chunks()
    )

    print_questions()

    print_chunks(
        chunks
    )

    print_label_template()


if __name__ == "__main__":
    main()