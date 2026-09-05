from dataclasses import dataclass, field
from typing import List


@dataclass
class RetrievalTestCase:
    """
    One manually-labelled retrieval evaluation question.

    relevant_chunk_ids contains chunks that were manually
    inspected and judged to contain evidence that directly
    helps answer the query.

    These labels are ground truth for retrieval evaluation.
    """

    name: str
    query: str

    relevant_chunk_ids: List[str] = field(
        default_factory=list
    )


# =========================================================
# RETRIEVAL EVALUATION DATASET
# =========================================================

RETRIEVAL_TEST_CASES = [

    # =====================================================
    # 1. EUROPA HABITABILITY
    # =====================================================

    RetrievalTestCase(
        name="europa_habitability",

        query=(
            "What conditions could make Europa "
            "suitable for life?"
        ),

        relevant_chunk_ids=[
            "chunk_p1_654aa24ae2c4",
            "chunk_p1_a3fb4c76a18c",
            "chunk_p2_e4c4e01a1b42",
        ],
    ),

    # =====================================================
    # 2. SUBSURFACE OCEAN
    # =====================================================

    RetrievalTestCase(
        name="europa_subsurface_ocean",

        query=(
            "What evidence supports the existence "
            "of a subsurface ocean on Europa?"
        ),

        relevant_chunk_ids=[
            "chunk_p1_654aa24ae2c4",
        ],
    ),

    # =====================================================
    # 3. SURFACE -> OCEAN EXCHANGE
    # =====================================================

    RetrievalTestCase(
        name="europa_surface_ocean_exchange",

        query=(
            "How could material from Europa's "
            "surface reach its subsurface ocean?"
        ),

        relevant_chunk_ids=[
            "chunk_p1_a3fb4c76a18c",
            "chunk_p2_eee5ccc8b46a",
            "chunk_p2_e4c4e01a1b42",
        ],
    ),

    # =====================================================
    # 4. CHEMICAL ENERGY FOR LIFE
    # =====================================================

    RetrievalTestCase(
        name="europa_energy_for_life",

        query=(
            "What potential sources of chemical "
            "energy could support life on Europa?"
        ),

        relevant_chunk_ids=[
            "chunk_p1_654aa24ae2c4",
            "chunk_p1_a3fb4c76a18c",
        ],
    ),

    # =====================================================
    # 5. EUROPA CLIPPER SCIENCE
    # =====================================================

    RetrievalTestCase(
        name="europa_clipper_science",

        query=(
            "How will Europa Clipper investigate "
            "Europa's habitability?"
        ),

        relevant_chunk_ids=[
            "chunk_p1_654aa24ae2c4",
            "chunk_p2_e4c4e01a1b42",
            "chunk_p2_4372c25f7284",
            "chunk_p3_95642d822316",
        ],
    ),
]