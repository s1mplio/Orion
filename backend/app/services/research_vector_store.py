from dataclasses import dataclass
from typing import List, Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from app.services.paper_chunking_service import PaperChunk


# =========================================================
# SEARCH RESULT
# =========================================================

@dataclass
class ResearchSearchResult:
    """
    One semantic retrieval result from the research index.
    """

    rank: int
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
# RESEARCH VECTOR STORE
# =========================================================

class ResearchVectorStore:
    """
    Research V2 - Embedding + FAISS Vector Store

    Responsibilities:
    - Convert PaperChunk text into dense embeddings
    - Normalize embeddings
    - Store vectors in FAISS
    - Preserve mapping between FAISS vectors and PaperChunk
    - Perform semantic similarity search

    This component DOES NOT:
    - Download PDFs
    - Parse PDFs
    - Chunk papers
    - Call an LLM
    - Generate answers
    - Evaluate retrieval quality
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        print(
            f"[VECTOR STORE] Loading embedding model: "
            f"{model_name}"
        )

        self.model_name = model_name

        self.embedding_model = SentenceTransformer(
            model_name
        )

        self.embedding_dimension = (
            self.embedding_model.get_sentence_embedding_dimension()
        )

        if self.embedding_dimension is None:
            raise RuntimeError(
                "Could not determine embedding dimension."
            )

        # -------------------------------------------------
        # IndexFlatIP performs inner-product similarity.
        #
        # Because we normalize every embedding first,
        # inner product becomes cosine similarity.
        # -------------------------------------------------

        self.index = faiss.IndexFlatIP(
            self.embedding_dimension
        )

        # FAISS stores vectors, not our PaperChunk objects.
        #
        # Position 0 in this list corresponds to vector 0
        # in FAISS, position 1 to vector 1, etc.
        self.chunks: List[PaperChunk] = []

        print(
            f"[VECTOR STORE] Embedding dimension: "
            f"{self.embedding_dimension}"
        )

    # =====================================================
    # INDEXING
    # =====================================================

    def add_chunks(
        self,
        chunks: List[PaperChunk],
        batch_size: int = 32,
    ) -> int:

        chunks = [
            chunk
            for chunk in (chunks or [])
            if chunk.text
            and chunk.text.strip()
        ]

        if not chunks:

            print(
                "[VECTOR STORE] No chunks to index."
            )

            return 0

        print(
            f"\n[VECTOR STORE] Embedding "
            f"{len(chunks)} chunks..."
        )

        texts = [
            chunk.text
            for chunk in chunks
        ]

        embeddings = self.embedding_model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )

        embeddings = np.asarray(
            embeddings,
            dtype=np.float32,
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if embeddings.ndim != 2:

            raise ValueError(
                "Embedding output must be a 2D matrix."
            )

        if embeddings.shape[0] != len(chunks):

            raise ValueError(
                "Number of embeddings does not match "
                "number of chunks."
            )

        if (
            embeddings.shape[1]
            != self.embedding_dimension
        ):

            raise ValueError(
                "Embedding dimension mismatch."
            )

        # -------------------------------------------------
        # COSINE SIMILARITY PREPARATION
        # -------------------------------------------------

        faiss.normalize_L2(
            embeddings
        )

        # -------------------------------------------------
        # ADD TO FAISS
        # -------------------------------------------------

        self.index.add(
            embeddings
        )

        self.chunks.extend(
            chunks
        )

        print(
            f"[VECTOR STORE] Added: "
            f"{len(chunks)}"
        )

        print(
            f"[VECTOR STORE] Total indexed: "
            f"{self.index.ntotal}"
        )

        return len(chunks)

    # =====================================================
    # SEARCH
    # =====================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[ResearchSearchResult]:

        if not query:
            return []

        query = query.strip()

        if not query:
            return []

        if self.index.ntotal == 0:

            print(
                "[VECTOR STORE] Index is empty."
            )

            return []

        if top_k <= 0:
            return []

        # Never request more vectors than we actually have.
        actual_k = min(
            top_k,
            self.index.ntotal,
        )

        # -------------------------------------------------
        # QUERY EMBEDDING
        # -------------------------------------------------

        query_embedding = (
            self.embedding_model.encode(
                [query],
                convert_to_numpy=True,
            )
        )

        query_embedding = np.asarray(
            query_embedding,
            dtype=np.float32,
        )

        faiss.normalize_L2(
            query_embedding
        )

        # -------------------------------------------------
        # FAISS SEARCH
        # -------------------------------------------------

        scores, indices = self.index.search(
            query_embedding,
            actual_k,
        )

        results = []

        # scores and indices have shape:
        #
        # (number_of_queries, top_k)
        #
        # We supplied one query, so use row 0.
        for rank, (
            score,
            vector_index,
        ) in enumerate(
            zip(
                scores[0],
                indices[0],
            ),
            start=1,
        ):

            # FAISS may return -1 if no valid result exists.
            if vector_index < 0:
                continue

            if vector_index >= len(
                self.chunks
            ):
                continue

            chunk = self.chunks[
                vector_index
            ]

            results.append(
                ResearchSearchResult(
                    rank=rank,

                    score=float(
                        score
                    ),

                    chunk_id=(
                        chunk.chunk_id
                    ),

                    paper_id=(
                        chunk.paper_id
                    ),

                    title=(
                        chunk.title
                    ),

                    doi=(
                        chunk.doi
                    ),

                    section=(
                        chunk.section
                    ),

                    page_start=(
                        chunk.page_start
                    ),

                    page_end=(
                        chunk.page_end
                    ),

                    text=(
                        chunk.text
                    ),

                    word_count=(
                        chunk.word_count
                    ),
                )
            )

        return results

    # =====================================================
    # INDEX INFORMATION
    # =====================================================

    @property
    def size(self) -> int:
        return int(
            self.index.ntotal
        )

    def clear(self):
        """
        Clear all indexed vectors and metadata.
        """

        self.index = faiss.IndexFlatIP(
            self.embedding_dimension
        )

        self.chunks = []

        print(
            "[VECTOR STORE] Index cleared."
        )