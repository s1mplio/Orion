from app.evaluation.run_retrieval_evaluation import (
    build_europa_corpus,
)


def print_chunk(
    chunk,
):
    print()
    print("=" * 80)

    print(
        "CHUNK ID:",
        chunk.chunk_id,
    )

    print(
        "PAGE:",
        chunk.page_start,
    )

    print(
        "SECTION:",
        chunk.section,
    )

    print("-" * 80)

    print(
        chunk.text
    )

    print("=" * 80)


def search_chunks(
    chunks,
    keywords,
):
    """
    Find chunks containing at least one supplied keyword.
    """

    matches = []

    for chunk in chunks:

        text = chunk.text.lower()

        if any(
            keyword.lower() in text
            for keyword in keywords
        ):
            matches.append(
                chunk
            )

    return matches


def show_category(
    name,
    chunks,
    keywords,
):
    print()
    print()
    print("#" * 80)

    print(
        f"GROUND-TRUTH CATEGORY: {name}"
    )

    print(
        "KEYWORDS:",
        ", ".join(keywords),
    )

    print("#" * 80)

    matches = search_chunks(
        chunks=chunks,
        keywords=keywords,
    )

    print(
        f"\nCandidate chunks found: {len(matches)}"
    )

    for chunk in matches:
        print_chunk(
            chunk
        )


def main():

    print()
    print(
        "Building the exact same Europa corpus "
        "used by the benchmark..."
    )

    (
        vector_store,
        retriever,
        chunks,
    ) = build_europa_corpus()

    print()
    print("=" * 80)

    print(
        "TOTAL CHUNKS:",
        len(chunks),
    )

    print("=" * 80)

    # =====================================================
    # 1. HABITABILITY
    # =====================================================

    show_category(
        name="EUROPA HABITABILITY",

        chunks=chunks,

        keywords=[
            "ingredients that may allow life",
            "habitability",
            "habitable",
            "bioessential",
            "liquid water",
            "redox",
            "chemical energy",
        ],
    )

    # =====================================================
    # 2. SUBSURFACE OCEAN
    # =====================================================

    show_category(
        name="SUBSURFACE OCEAN",

        chunks=chunks,

        keywords=[
            "subsurface ocean",
            "global saltwater ocean",
            "global ocean",
            "induced magnetic",
            "magnetometer",
            "ocean beneath",
        ],
    )

    # =====================================================
    # 3. SURFACE -> OCEAN EXCHANGE
    # =====================================================

    show_category(
        name="SURFACE TO OCEAN EXCHANGE",

        chunks=chunks,

        keywords=[
            "downward transport",
            "downward cycling",
            "chaos terrain",
            "chaos regions",
            "surface material",
            "subduction",
            "recycling",
        ],
    )

    # =====================================================
    # 4. ENERGY FOR LIFE
    # =====================================================

    show_category(
        name="CHEMICAL ENERGY FOR LIFE",

        chunks=chunks,

        keywords=[
            "chemical energy",
            "redox",
            "oxidant",
            "oxidants",
            "reductant",
            "reductants",
            "seafloor",
            "radiolysis",
        ],
    )

    # =====================================================
    # 5. EUROPA CLIPPER
    # =====================================================

    show_category(
        name="EUROPA CLIPPER SCIENCE",

        chunks=chunks,

        keywords=[
            "europa clipper",
            "clipper",
            "instrument",
            "instruments",
            "habitability",
            "reconnaissance",
        ],
    )


if __name__ == "__main__":
    main()