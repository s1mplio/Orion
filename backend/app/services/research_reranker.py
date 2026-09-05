from dataclasses import dataclass
from typing import List, Optional

from sentence_transformers import CrossEncoder

from app.services.research_retriever import (
    RetrievedEvidence,
)


@dataclass
class RerankedEvidence:
    """
    One evidence chunk after cross-encoder reranking.

    retrieval_rank:
        Final rank after reranking.

    original_retrieval_rank:
        Rank produced by the filtered retriever.

    faiss_rank:
        Original FAISS rank.

    vector_score:
        Dense retrieval similarity score.

    reranker_score:
        Cross-encoder relevance score.
    """

    retrieval_rank: int

    original_retrieval_rank: int

    faiss_rank: int

    vector_score: float

    reranker_score: float

    chunk_id: str

    paper_id: Optional[str]

    title: str

    doi: Optional[str]

    section: str

    page_start: int

    page_end: int

    text: str

    word_count: int


class ResearchReranker:
    """
    Research V2 - Cross-Encoder Reranker

    The reranker does NOT replace FAISS.

    Pipeline:

        query
          ↓
        FAISS
          ↓
        filtered candidates
          ↓
        CrossEncoder
          ↓
        reordered evidence

    The cross-encoder sees the query and chunk together,
    allowing more precise relevance scoring than embedding
    similarity alone.
    """

    def __init__(
        self,
        model_name: str = (
            "cross-encoder/"
            "ms-marco-MiniLM-L-6-v2"
        ),
    ):
        self.model_name = model_name

        print(
            "[RERANKER] Loading model:",
            self.model_name,
        )

        self.model = CrossEncoder(
            self.model_name
        )

        print(
            "[RERANKER] Model loaded."
        )

    def rerank(
        self,
        query: str,
        candidates: List[RetrievedEvidence],
        top_k: int = 5,
    ) -> List[RerankedEvidence]:
        """
        Rerank retrieved evidence using a cross-encoder.
        """

        if top_k <= 0:
            raise ValueError(
                "top_k must be greater than 0"
            )

        if not candidates:
            return []

        # -------------------------------------------------
        # Query-document pairs
        # -------------------------------------------------

        pairs = [
            [
                query,
                candidate.text,
            ]
            for candidate in candidates
        ]

        # -------------------------------------------------
        # Cross-encoder inference
        # -------------------------------------------------

        scores = self.model.predict(
            pairs,
            show_progress_bar=False,
        )

        # -------------------------------------------------
        # Combine candidates with scores
        # -------------------------------------------------

        scored_candidates = list(
            zip(
                candidates,
                scores,
            )
        )

        # Highest cross-encoder score first.
        scored_candidates.sort(
            key=lambda item: float(item[1]),
            reverse=True,
        )

        # -------------------------------------------------
        # Keep final Top-K
        # -------------------------------------------------

        selected = scored_candidates[
            :top_k
        ]

        results = []

        for final_rank, (
            candidate,
            reranker_score,
        ) in enumerate(
            selected,
            start=1,
        ):

            result = RerankedEvidence(
                retrieval_rank=final_rank,

                original_retrieval_rank=(
                    candidate.retrieval_rank
                ),

                faiss_rank=(
                    candidate.faiss_rank
                ),

                vector_score=float(
                    candidate.score
                ),

                reranker_score=float(
                    reranker_score
                ),

                chunk_id=(
                    candidate.chunk_id
                ),

                paper_id=(
                    candidate.paper_id
                ),

                title=(
                    candidate.title
                ),

                doi=(
                    candidate.doi
                ),

                section=(
                    candidate.section
                ),

                page_start=(
                    candidate.page_start
                ),

                page_end=(
                    candidate.page_end
                ),

                text=(
                    candidate.text
                ),

                word_count=(
                    candidate.word_count
                ),
            )

            results.append(
                result
            )

        return results