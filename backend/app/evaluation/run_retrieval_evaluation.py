from dataclasses import dataclass
from pathlib import Path

from app.evaluation.retrieval_evaluator import (
    RetrievalEvaluator,
)

from app.evaluation.retrieval_test_cases import (
    RETRIEVAL_TEST_CASES,
)

from app.services.paper_parser_service import (
    PaperParserService,
)

from app.services.paper_chunking_service import (
    PaperChunkingService,
)

from app.services.research_vector_store import (
    ResearchVectorStore,
)

from app.services.research_retriever import (
    ResearchRetriever,
)

from app.services.research_reranker import (
    ResearchReranker,
)

from app.models.paper import Paper


# =========================================================
# METRIC CONTAINER
# =========================================================


@dataclass
class SystemMetrics:
    precision: float = 0.0
    recall: float = 0.0
    mrr: float = 0.0
    ndcg: float = 0.0
    evaluated_queries: int = 0


# =========================================================
# RETRIEVAL BENCHMARK
# =========================================================


class RetrievalBenchmark:
    """
    Compare three retrieval systems:

    1. Raw FAISS dense retrieval
    2. Filtered ResearchRetriever
    3. Filtered ResearchRetriever + Cross-Encoder

    All systems use the same:

    - corpus
    - evaluation queries
    - manually-labelled ground truth
    - final K
    """

    def __init__(
        self,
        vector_store: ResearchVectorStore,
        retriever: ResearchRetriever,
        reranker: ResearchReranker,
        k: int = 5,
        reranker_candidate_count: int = 10,
    ):
        self.vector_store = vector_store
        self.retriever = retriever
        self.reranker = reranker

        self.k = k

        self.reranker_candidate_count = (
            reranker_candidate_count
        )

        self.evaluator = RetrievalEvaluator()

    def run(self):

        raw_metrics = SystemMetrics()

        filtered_metrics = SystemMetrics()

        reranked_metrics = SystemMetrics()

        print()
        print(
            "========================================"
        )
        print(
            "ORION RESEARCH RETRIEVAL BENCHMARK"
        )
        print(
            "========================================"
        )

        print(
            f"Final K: {self.k}"
        )

        print(
            "Reranker candidate pool:",
            self.reranker_candidate_count,
        )

        # =================================================
        # EVALUATION LOOP
        # =================================================

        for test_case in RETRIEVAL_TEST_CASES:

            relevant = set(
                test_case.relevant_chunk_ids
            )

            if not relevant:

                print(
                    f"\n[SKIP] {test_case.name}"
                )

                print(
                    "       No ground-truth chunks labelled."
                )

                continue

            print()
            print(
                "----------------------------------------"
            )

            print(
                f"TEST CASE: {test_case.name}"
            )

            print(
                "----------------------------------------"
            )

            print(
                f"QUESTION: {test_case.query}"
            )

            print(
                f"GROUND TRUTH: {len(relevant)} chunk(s)"
            )

            # =================================================
            # SYSTEM 1
            # RAW FAISS
            # =================================================

            raw_results = (
                self.vector_store.search(
                    query=test_case.query,
                    top_k=self.k,
                )
            )

            raw_ids = [
                result.chunk_id
                for result in raw_results
            ]

            raw = self.evaluator.evaluate(
                retrieved_chunk_ids=raw_ids,
                relevant_chunk_ids=relevant,
                k=self.k,
            )

            self._accumulate(
                raw_metrics,
                raw,
            )

            # =================================================
            # SYSTEM 2
            # FILTERED RETRIEVER
            # =================================================

            filtered_results = (
                self.retriever.retrieve(
                    query=test_case.query,
                    top_k=self.k,
                )
            )

            filtered_ids = [
                result.chunk_id
                for result in filtered_results
            ]

            filtered = self.evaluator.evaluate(
                retrieved_chunk_ids=filtered_ids,
                relevant_chunk_ids=relevant,
                k=self.k,
            )

            self._accumulate(
                filtered_metrics,
                filtered,
            )

            # =================================================
            # SYSTEM 3
            # FILTERED RETRIEVER + CROSS-ENCODER
            #
            # IMPORTANT:
            #
            # Do NOT rerank only the final Top-K.
            #
            # First retrieve a larger filtered candidate pool.
            # Then let the cross-encoder choose the final Top-K.
            # =================================================

            reranker_candidates = (
                self.retriever.retrieve(
                    query=test_case.query,
                    top_k=(
                        self.reranker_candidate_count
                    ),
                )
            )

            reranked_results = (
                self.reranker.rerank(
                    query=test_case.query,
                    candidates=reranker_candidates,
                    top_k=self.k,
                )
            )

            reranked_ids = [
                result.chunk_id
                for result in reranked_results
            ]

            reranked = self.evaluator.evaluate(
                retrieved_chunk_ids=reranked_ids,
                relevant_chunk_ids=relevant,
                k=self.k,
            )

            self._accumulate(
                reranked_metrics,
                reranked,
            )

            # =================================================
            # PRINT PER-QUERY METRICS
            # =================================================

            print()
            print(
                "RAW FAISS"
            )

            self._print_metrics(
                raw
            )

            print()
            print(
                "FILTERED RETRIEVER"
            )

            self._print_metrics(
                filtered
            )

            print()
            print(
                "FILTERED + CROSS-ENCODER"
            )

            self._print_metrics(
                reranked
            )

            # =================================================
            # PRINT RAW RESULTS
            # =================================================

            print()
            print(
                "RAW RETRIEVED CHUNKS"
            )

            for rank, result in enumerate(
                raw_results,
                start=1,
            ):

                marker = (
                    "RELEVANT"
                    if result.chunk_id in relevant
                    else "-"
                )

                print(
                    f"{rank}. "
                    f"{result.chunk_id} "
                    f"[{marker}] "
                    f"score={result.score:.4f}"
                )

                print(
                    f"   section={result.section} "
                    f"page={result.page_start}"
                )

            # =================================================
            # PRINT FILTERED RESULTS
            # =================================================

            print()
            print(
                "FILTERED RETRIEVED CHUNKS"
            )

            for rank, result in enumerate(
                filtered_results,
                start=1,
            ):

                marker = (
                    "RELEVANT"
                    if result.chunk_id in relevant
                    else "-"
                )

                print(
                    f"{rank}. "
                    f"{result.chunk_id} "
                    f"[{marker}] "
                    f"score={result.score:.4f}"
                )

                print(
                    f"   section={result.section} "
                    f"page={result.page_start}"
                )

            # =================================================
            # PRINT RERANKED RESULTS
            # =================================================

            print()
            print(
                "RERANKED RETRIEVED CHUNKS"
            )

            for result in reranked_results:

                marker = (
                    "RELEVANT"
                    if result.chunk_id in relevant
                    else "-"
                )

                print(
                    f"{result.retrieval_rank}. "
                    f"{result.chunk_id} "
                    f"[{marker}]"
                )

                print(
                    "   "
                    f"old_rank="
                    f"{result.original_retrieval_rank} "
                    f"faiss_rank="
                    f"{result.faiss_rank}"
                )

                print(
                    "   "
                    f"vector_score="
                    f"{result.vector_score:.4f} "
                    f"reranker_score="
                    f"{result.reranker_score:.4f}"
                )

                print(
                    f"   section={result.section} "
                    f"page={result.page_start}"
                )

        # =====================================================
        # FINAL BENCHMARK
        # =====================================================

        print()
        print()
        print(
            "========================================"
        )

        print(
            "FINAL BENCHMARK"
        )

        print(
            "========================================"
        )

        if raw_metrics.evaluated_queries == 0:

            print(
                "No labelled test cases were found."
            )

            print(
                "Add relevant_chunk_ids to "
                "retrieval_test_cases.py first."
            )

            return

        raw_average = self._average(
            raw_metrics
        )

        filtered_average = self._average(
            filtered_metrics
        )

        reranked_average = self._average(
            reranked_metrics
        )

        print(
            f"\nEvaluated queries: "
            f"{raw_metrics.evaluated_queries}"
        )

        print(
            f"K: {self.k}"
        )

        print(
            "Reranker candidates:",
            self.reranker_candidate_count,
        )

        print()

        print(
            "SYSTEM                         "
            "P@K     R@K     MRR     nDCG"
        )

        print(
            "---------------------------------------------------------"
        )

        print(
            "Raw FAISS                      "
            f"{raw_average.precision:.3f}   "
            f"{raw_average.recall:.3f}   "
            f"{raw_average.mrr:.3f}   "
            f"{raw_average.ndcg:.3f}"
        )

        print(
            "Filtered Retriever             "
            f"{filtered_average.precision:.3f}   "
            f"{filtered_average.recall:.3f}   "
            f"{filtered_average.mrr:.3f}   "
            f"{filtered_average.ndcg:.3f}"
        )

        print(
            "Filtered + Cross-Encoder       "
            f"{reranked_average.precision:.3f}   "
            f"{reranked_average.recall:.3f}   "
            f"{reranked_average.mrr:.3f}   "
            f"{reranked_average.ndcg:.3f}"
        )

        print(
            "========================================"
        )

    # =====================================================
    # HELPERS
    # =====================================================

    def _accumulate(
        self,
        accumulator,
        metrics,
    ):

        accumulator.precision += (
            metrics.precision_at_k
        )

        accumulator.recall += (
            metrics.recall_at_k
        )

        accumulator.mrr += (
            metrics.reciprocal_rank
        )

        accumulator.ndcg += (
            metrics.ndcg_at_k
        )

        accumulator.evaluated_queries += 1

    def _average(
        self,
        metrics: SystemMetrics,
    ) -> SystemMetrics:

        count = (
            metrics.evaluated_queries
        )

        if count == 0:
            return SystemMetrics()

        return SystemMetrics(
            precision=(
                metrics.precision / count
            ),

            recall=(
                metrics.recall / count
            ),

            mrr=(
                metrics.mrr / count
            ),

            ndcg=(
                metrics.ndcg / count
            ),

            evaluated_queries=count,
        )

    def _print_metrics(
        self,
        metrics,
    ):

        print(
            f"  Precision@{self.k}: "
            f"{metrics.precision_at_k:.3f}"
        )

        print(
            f"  Recall@{self.k}:    "
            f"{metrics.recall_at_k:.3f}"
        )

        print(
            f"  MRR:                "
            f"{metrics.reciprocal_rank:.3f}"
        )

        print(
            f"  nDCG@{self.k}:       "
            f"{metrics.ndcg_at_k:.3f}"
        )


# =========================================================
# FIND EUROPA PDF
# =========================================================


def find_europa_pdf() -> Path:
    """
    Find the cached Europa Clipper PDF.

    Avoid hard-coding the generated cache filename.
    """

    research_folder = Path(
        r"C:\Orion\backend\data\research_papers"
    )

    if not research_folder.exists():

        raise RuntimeError(
            "Research paper folder does not exist:\n"
            f"{research_folder}"
        )

    pdf_files = list(
        research_folder.glob(
            "*.pdf"
        )
    )

    if not pdf_files:

        raise RuntimeError(
            "No PDF files were found in:\n"
            f"{research_folder}"
        )

    # Prefer Europa / Clipper PDF.

    for pdf_file in pdf_files:

        filename = (
            pdf_file.name.lower()
        )

        if (
            "europa" in filename
            or "clipper" in filename
        ):
            return pdf_file

    # If exactly one exists, use it.

    if len(pdf_files) == 1:
        return pdf_files[0]

    print()
    print(
        "Available PDFs:"
    )

    for pdf_file in pdf_files:

        print(
            "-",
            pdf_file.name,
        )

    raise RuntimeError(
        "Could not automatically determine "
        "which PDF is the Europa Clipper paper."
    )


# =========================================================
# BUILD EUROPA CORPUS
# =========================================================


def build_europa_corpus():

    print()
    print(
        "Building Europa evaluation corpus..."
    )

    # =====================================================
    # CREATE PAPER
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

    # =====================================================
    # LOCAL PDF
    # =====================================================

    pdf_path = (
        find_europa_pdf()
    )

    print(
        "Using PDF:",
        pdf_path,
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
            "PaperParserService returned None."
        )

    print(
        "Parsed pages:",
        parsed_paper.total_pages,
    )

    print(
        "Pages with text:",
        parsed_paper.pages_with_text,
    )

    print(
        "Total words:",
        parsed_paper.total_words,
    )

    # =====================================================
    # CHUNK
    # =====================================================

    chunker = PaperChunkingService(
        chunk_size_words=350,
        overlap_words=60,
        minimum_chunk_words=40,
    )

    chunks = chunker.chunk(
        parsed_paper
    )

    if not chunks:

        raise RuntimeError(
            "No chunks were generated "
            "from the parsed paper."
        )

    print(
        "Generated chunks:",
        len(chunks),
    )

    # =====================================================
    # VERIFY GROUND TRUTH
    # =====================================================

    labelled_ids = set()

    for test_case in RETRIEVAL_TEST_CASES:

        labelled_ids.update(
            test_case.relevant_chunk_ids
        )

    existing_ids = {
        chunk.chunk_id
        for chunk in chunks
    }

    print()
    print(
        "Ground-truth chunk check:"
    )

    if not labelled_ids:

        print(
            "No labelled chunk IDs currently exist."
        )

    else:

        for chunk_id in sorted(
            labelled_ids
        ):

            if chunk_id in existing_ids:

                print(
                    f"[FOUND] {chunk_id}"
                )

            else:

                print(
                    f"[MISSING] {chunk_id}"
                )

    # =====================================================
    # VECTOR STORE
    # =====================================================

    print()
    print(
        "Building FAISS vector store..."
    )

    vector_store = (
        ResearchVectorStore()
    )

    vector_store.add_chunks(
        chunks
    )

    print(
        "Vector store size:",
        vector_store.size,
    )

    # =====================================================
    # FILTERED RETRIEVER
    # =====================================================

    retriever = (
        ResearchRetriever(
            vector_store
        )
    )

    return (
        vector_store,
        retriever,
        chunks,
    )


# =========================================================
# MAIN
# =========================================================


if __name__ == "__main__":

    (
        vector_store,
        retriever,
        chunks,
    ) = build_europa_corpus()

    # Load cross-encoder ONCE.
    #
    # It is then reused across all five benchmark queries.

    reranker = (
        ResearchReranker()
    )

    benchmark = RetrievalBenchmark(
        vector_store=vector_store,
        retriever=retriever,
        reranker=reranker,
        k=5,
        reranker_candidate_count=10,
    )

    benchmark.run()