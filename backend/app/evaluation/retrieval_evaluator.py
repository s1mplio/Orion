from dataclasses import dataclass
from typing import List, Set
import math


@dataclass
class RetrievalMetrics:
    """
    Metrics for one evaluation query.
    """

    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    ndcg_at_k: float

    retrieved_count: int
    relevant_count: int
    relevant_retrieved: int


class RetrievalEvaluator:
    """
    Research V2 - Retrieval Evaluator

    Measures:
    - Precision@K
    - Recall@K
    - Reciprocal Rank
    - nDCG@K

    Relevance is determined using manually labelled
    relevant chunk IDs.
    """

    def evaluate(
        self,
        retrieved_chunk_ids: List[str],
        relevant_chunk_ids: Set[str],
        k: int = 5,
    ) -> RetrievalMetrics:

        if k <= 0:
            raise ValueError(
                "k must be greater than 0"
            )

        retrieved = list(
            retrieved_chunk_ids[:k]
        )

        relevant = set(
            relevant_chunk_ids
        )

        # ================================================
        # PRECISION@K
        # ================================================

        relevant_retrieved = sum(
            1
            for chunk_id in retrieved
            if chunk_id in relevant
        )

        precision = (
            relevant_retrieved / k
        )

        # ================================================
        # RECALL@K
        # ================================================

        if relevant:

            recall = (
                relevant_retrieved
                / len(relevant)
            )

        else:

            recall = 0.0

        # ================================================
        # RECIPROCAL RANK
        # ================================================

        reciprocal_rank = 0.0

        for rank, chunk_id in enumerate(
            retrieved,
            start=1,
        ):

            if chunk_id in relevant:

                reciprocal_rank = (
                    1.0 / rank
                )

                break

        # ================================================
        # nDCG@K
        # ================================================

        dcg = 0.0

        for rank, chunk_id in enumerate(
            retrieved,
            start=1,
        ):

            relevance = (
                1
                if chunk_id in relevant
                else 0
            )

            if relevance:

                dcg += (
                    relevance
                    / math.log2(rank + 1)
                )

        ideal_relevant_count = min(
            len(relevant),
            k,
        )

        idcg = 0.0

        for rank in range(
            1,
            ideal_relevant_count + 1,
        ):

            idcg += (
                1.0
                / math.log2(rank + 1)
            )

        if idcg > 0:

            ndcg = (
                dcg / idcg
            )

        else:

            ndcg = 0.0

        return RetrievalMetrics(
            precision_at_k=precision,
            recall_at_k=recall,
            reciprocal_rank=reciprocal_rank,
            ndcg_at_k=ndcg,
            retrieved_count=len(retrieved),
            relevant_count=len(relevant),
            relevant_retrieved=relevant_retrieved,
        )