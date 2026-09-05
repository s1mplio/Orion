from dataclasses import dataclass
from typing import List, Optional
import re

from app.services.research_vector_store import (
    ResearchVectorStore,
    ResearchSearchResult,
)


# =========================================================
# RETRIEVED EVIDENCE
# =========================================================

@dataclass
class RetrievedEvidence:
    """
    Final evidence returned by the retrieval layer.

    `retrieval_rank` is the rank after filtering and
    deduplication.

    `faiss_rank` preserves the original vector-search rank.
    """

    retrieval_rank: int
    faiss_rank: int

    score: float

    chunk_id: str
    paper_id: Optional[str]

    title: str
    doi: Optional[str]

    section: str

    page_start: int
    page_end: int

    text: str
    word_count: int


# =========================================================
# RESEARCH RETRIEVER
# =========================================================

class ResearchRetriever:
    """
    Research V2 - Evidence Retriever

    Responsibilities:
    - Retrieve a larger candidate pool from FAISS
    - Remove chunks unsuitable as direct evidence
    - Remove duplicate / near-duplicate candidates
    - Return the final Top-K evidence chunks

    This component DOES NOT:
    - Generate embeddings
    - Modify the FAISS index
    - Call an LLM
    - Rerank using a cross-encoder
    - Generate answers
    """

    EXCLUDED_SECTIONS = {
        "references",
        "acknowledgements",
        "acknowledgments",
    }

    def __init__(
        self,
        vector_store: ResearchVectorStore,
        candidate_multiplier: int = 4,
        duplicate_threshold: float = 0.85,
    ):
        if candidate_multiplier <= 0:
            raise ValueError(
                "candidate_multiplier must be greater than 0"
            )

        if not 0.0 <= duplicate_threshold <= 1.0:
            raise ValueError(
                "duplicate_threshold must be between 0 and 1"
            )

        self.vector_store = vector_store
        self.candidate_multiplier = candidate_multiplier
        self.duplicate_threshold = duplicate_threshold

    # =====================================================
    # PUBLIC API
    # =====================================================

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[RetrievedEvidence]:

        if not query:
            return []

        query = query.strip()

        if not query:
            return []

        if top_k <= 0:
            return []

        if self.vector_store.size == 0:

            print(
                "[RETRIEVER] Vector store is empty."
            )

            return []

        # -------------------------------------------------
        # CANDIDATE RETRIEVAL
        # -------------------------------------------------
        #
        # We intentionally retrieve more than final Top-K.
        #
        # Example:
        #
        # final top_k = 5
        # multiplier = 4
        #
        # FAISS candidates = 20
        #
        # This gives filtering and deduplication room to
        # remove poor candidates without leaving us with
        # fewer than five results.
        # -------------------------------------------------

        candidate_k = min(
            top_k * self.candidate_multiplier,
            self.vector_store.size,
        )

        print(
            f"\n[RETRIEVER] Query: {query}"
        )

        print(
            f"[RETRIEVER] Candidate pool: "
            f"{candidate_k}"
        )

        candidates = self.vector_store.search(
            query=query,
            top_k=candidate_k,
        )

        # -------------------------------------------------
        # FILTER UNSUITABLE SECTIONS
        # -------------------------------------------------

        filtered_candidates = []

        excluded_count = 0

        for candidate in candidates:

            if self._is_excluded_section(
                candidate.section
            ):

                excluded_count += 1
                continue

            if not candidate.text.strip():
                continue

            filtered_candidates.append(
                candidate
            )

        print(
            f"[RETRIEVER] Section-filtered: "
            f"{excluded_count}"
        )

        # -------------------------------------------------
        # DEDUPLICATION
        # -------------------------------------------------

        unique_candidates = []

        duplicate_count = 0

        for candidate in filtered_candidates:

            if self._is_duplicate(
                candidate,
                unique_candidates,
            ):

                duplicate_count += 1
                continue

            unique_candidates.append(
                candidate
            )

            # We already have enough final results.
            if len(unique_candidates) >= top_k:
                break

        print(
            f"[RETRIEVER] Duplicates removed: "
            f"{duplicate_count}"
        )

        # -------------------------------------------------
        # FINAL RESULT
        # -------------------------------------------------

        results = []

        for retrieval_rank, candidate in enumerate(
            unique_candidates[:top_k],
            start=1,
        ):

            results.append(
                RetrievedEvidence(
                    retrieval_rank=retrieval_rank,

                    faiss_rank=candidate.rank,

                    score=candidate.score,

                    chunk_id=candidate.chunk_id,

                    paper_id=candidate.paper_id,

                    title=candidate.title,

                    doi=candidate.doi,

                    section=candidate.section,

                    page_start=candidate.page_start,

                    page_end=candidate.page_end,

                    text=candidate.text,

                    word_count=candidate.word_count,
                )
            )

        print(
            f"[RETRIEVER] Final evidence: "
            f"{len(results)}"
        )

        return results

    # =====================================================
    # SECTION FILTER
    # =====================================================

    def _is_excluded_section(
        self,
        section: Optional[str],
    ) -> bool:

        if not section:
            return False

        normalized = (
            section
            .strip()
            .lower()
        )

        return (
            normalized
            in self.EXCLUDED_SECTIONS
        )

    # =====================================================
    # DEDUPLICATION
    # =====================================================

    def _is_duplicate(
        self,
        candidate: ResearchSearchResult,
        accepted: List[ResearchSearchResult],
    ) -> bool:
        """
        Detect near-duplicate chunks using token overlap.

        This is deliberately cheap and deterministic.

        We are NOT making another embedding or LLM call.
        """

        candidate_tokens = (
            self._normalized_tokens(
                candidate.text
            )
        )

        if not candidate_tokens:
            return False

        for existing in accepted:

            existing_tokens = (
                self._normalized_tokens(
                    existing.text
                )
            )

            if not existing_tokens:
                continue

            similarity = (
                self._jaccard_similarity(
                    candidate_tokens,
                    existing_tokens,
                )
            )

            if (
                similarity
                >= self.duplicate_threshold
            ):
                return True

        return False

    # =====================================================
    # TOKEN NORMALIZATION
    # =====================================================

    def _normalized_tokens(
        self,
        text: str,
    ):
        """
        Create a normalized token set for cheap duplicate
        detection.

        This is NOT the embedding tokenizer.
        """

        tokens = re.findall(
            r"\b[a-z0-9]+\b",
            text.lower(),
        )

        return set(
            tokens
        )

    # =====================================================
    # JACCARD SIMILARITY
    # =====================================================

    def _jaccard_similarity(
        self,
        tokens_a,
        tokens_b,
    ) -> float:

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = len(
            tokens_a.intersection(
                tokens_b
            )
        )

        union = len(
            tokens_a.union(
                tokens_b
            )
        )

        if union == 0:
            return 0.0

        return (
            intersection
            / union
        )