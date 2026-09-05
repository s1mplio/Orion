from dataclasses import dataclass, field
from typing import List


@dataclass
class ChunkingTestCase:
    """
    Retrieval evaluation test case for the
    cross-page chunking experiment.

    These labels were manually inspected using
    the same scientific relevance criteria as
    the original page-bounded benchmark.
    """

    name: str

    query: str

    relevant_chunk_ids: List[str] = field(
        default_factory=list
    )


CROSS_PAGE_TEST_CASES = [

    ChunkingTestCase(
        name="europa_habitability",

        query=(
            "What conditions could make Europa "
            "suitable for life?"
        ),

        relevant_chunk_ids=[
            "section_chunk_p1_ebb9f65c6616",
            "section_chunk_p1-2_774a50a3a85d",
            "section_chunk_p2_368ad3bcf972",
        ],
    ),

    ChunkingTestCase(
        name="europa_subsurface_ocean",

        query=(
            "What evidence supports the existence "
            "of a subsurface ocean on Europa?"
        ),

        relevant_chunk_ids=[
            "section_chunk_p1_ebb9f65c6616",
        ],
    ),

    ChunkingTestCase(
        name="europa_surface_ocean_exchange",

        query=(
            "How could material from Europa's "
            "surface reach its subsurface ocean?"
        ),

        relevant_chunk_ids=[
            "section_chunk_p1-2_774a50a3a85d",
            "section_chunk_p2_368ad3bcf972",
        ],
    ),

    ChunkingTestCase(
        name="europa_energy_for_life",

        query=(
            "What potential sources of chemical "
            "energy could support life on Europa?"
        ),

        relevant_chunk_ids=[
            "section_chunk_p1_ebb9f65c6616",
            "section_chunk_p1-2_774a50a3a85d",
        ],
    ),

    ChunkingTestCase(
        name="europa_clipper_science",

        query=(
            "How will Europa Clipper investigate "
            "Europa's habitability?"
        ),

        relevant_chunk_ids=[
            "section_chunk_p1_ebb9f65c6616",
            "section_chunk_p2_18ded0b0117c",
            "section_chunk_p2-3_6da51e2540ac",
            "section_chunk_p3_ae0b60d4d11e",
        ],
    ),
]