import json
from typing import List

from app.models.evidence import Evidence

from app.services.full_text_acquisition_service import (
    FullTextAcquisitionService,
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


class EvidenceExtractionAgent:
    """
    Research V2 - Full-Paper Evidence Extraction Agent

    Pipeline:

        Candidate papers
            ↓
        Full-text acquisition
            ↓
        PDF parsing
            ↓
        Page-bounded chunking
            ↓
        Embeddings + FAISS
            ↓
        Filtered retrieval
            ↓
        Top-K evidence chunks
            ↓
        LLM evidence extraction

    The LLM no longer receives only paper abstracts.

    Abstracts are used only as a fallback when full-text
    retrieval is unavailable.
    """

    def __init__(
        self,
        llm,
        top_k: int = 5,
    ):
        self.llm = llm
        self.top_k = top_k

        # -------------------------------------------------
        # Research V2 services
        # -------------------------------------------------

        self.acquisition_service = (
            FullTextAcquisitionService()
        )

        self.parser_service = (
            PaperParserService()
        )

        # Step 9 winner:
        # keep page-bounded chunking.
        self.chunking_service = (
            PaperChunkingService(
                chunk_size_words=350,
                overlap_words=60,
                minimum_chunk_words=40,
            )
        )

    # =====================================================
    # PUBLIC ENTRY POINT
    # =====================================================

    def run(
        self,
        state,
    ):
        print()
        print("=" * 70)
        print("FULL-PAPER EVIDENCE EXTRACTION")
        print("=" * 70)

        if not state.papers:

            print(
                "No papers available for evidence extraction."
            )

            return

        # -------------------------------------------------
        # Build full-paper corpus once.
        # -------------------------------------------------

        chunks = (
            self._build_full_text_corpus(
                state.papers
            )
        )

        # -------------------------------------------------
        # Full-paper RAG path
        # -------------------------------------------------

        if chunks:

            print()
            print(
                "[EVIDENCE] Building research vector store..."
            )

            vector_store = (
                ResearchVectorStore()
            )

            vector_store.add_chunks(
                chunks
            )

            retriever = (
                ResearchRetriever(
                    vector_store=vector_store
                )
            )

            self._extract_from_retrieval(
                state=state,
                retriever=retriever,
            )

        # -------------------------------------------------
        # Fallback path
        # -------------------------------------------------

        else:

            print()
            print(
                "[EVIDENCE] No usable full-text chunks."
            )

            print(
                "[EVIDENCE] Falling back to abstracts."
            )

            self._extract_from_abstracts(
                state
            )

        print()
        print(
            "Total Evidence Objects:",
            len(state.evidence),
        )

    # =====================================================
    # BUILD FULL-TEXT CORPUS
    # =====================================================

    def _build_full_text_corpus(
        self,
        papers,
    ):
        """
        Acquire, parse and chunk all available papers.

        Failed or inaccessible papers are skipped.

        No paywall bypass is attempted.
        """

        all_chunks = []

        print()
        print(
            "[EVIDENCE] Preparing full-paper corpus..."
        )

        for index, paper in enumerate(
            papers,
            start=1,
        ):

            print()
            print("-" * 70)

            print(
                f"[EVIDENCE] Paper "
                f"{index}/{len(papers)}"
            )

            print(
                "[EVIDENCE] Title:",
                paper.title,
            )

            # ---------------------------------------------
            # Acquire full text
            # ---------------------------------------------

            try:

                acquired = (
                    self.acquisition_service.acquire(
                        paper
                    )
                )

            except Exception as error:

                print(
                    "[EVIDENCE] Acquisition error:",
                    error,
                )

                continue

            if not acquired:

                print(
                    "[EVIDENCE] Full text unavailable."
                )

                continue

            # ---------------------------------------------
            # Parse PDF
            # ---------------------------------------------

            try:

                parsed_paper = (
                    self.parser_service.parse(
                        paper
                    )
                )

            except Exception as error:

                print(
                    "[EVIDENCE] Parsing error:",
                    error,
                )

                continue

            if parsed_paper is None:

                print(
                    "[EVIDENCE] No usable parsed text."
                )

                continue

            # ---------------------------------------------
            # Chunk PDF
            # ---------------------------------------------

            try:

                paper_chunks = (
                    self.chunking_service.chunk(
                        parsed_paper
                    )
                )

            except Exception as error:

                print(
                    "[EVIDENCE] Chunking error:",
                    error,
                )

                continue

            if not paper_chunks:

                print(
                    "[EVIDENCE] No chunks generated."
                )

                continue

            all_chunks.extend(
                paper_chunks
            )

            print(
                "[EVIDENCE] Added chunks:",
                len(paper_chunks),
            )

        print()
        print(
            "[EVIDENCE] Full-paper corpus chunks:",
            len(all_chunks),
        )

        return all_chunks

    # =====================================================
    # RETRIEVAL-BASED EXTRACTION
    # =====================================================

    def _extract_from_retrieval(
        self,
        state,
        retriever,
    ):
        """
        Retrieve evidence for each research sub-question.

        If PlannerAgent produced no sub-questions,
        the original research question is used.
        """

        queries = list(
            state.sub_questions or []
        )

        if not queries:

            queries = [
                state.question
            ]

        print()
        print(
            "[EVIDENCE] Retrieval queries:",
            len(queries),
        )

        for query_index, query in enumerate(
            queries,
            start=1,
        ):

            print()
            print("=" * 70)

            print(
                f"[EVIDENCE] Query "
                f"{query_index}/{len(queries)}"
            )

            print(
                "[EVIDENCE] Question:",
                query,
            )

            try:

                retrieved = (
                    retriever.retrieve(
                        query=query,
                        top_k=self.top_k,
                    )
                )

            except Exception as error:

                print(
                    "[EVIDENCE] Retrieval failed:",
                    error,
                )

                continue

            if not retrieved:

                print(
                    "[EVIDENCE] No chunks retrieved."
                )

                continue

            self._print_retrieval_results(
                retrieved
            )

            prompt = (
                self._build_retrieval_prompt(
                    research_question=(
                        state.question
                    ),
                    sub_question=query,
                    retrieved=retrieved,
                )
            )

            response = (
                self.llm.generate(
                    prompt
                )
            )

            data = (
                self._parse_json_response(
                    response
                )
            )

            if data is None:

                print(
                    "[EVIDENCE] Failed to parse "
                    "LLM JSON."
                )

                print(
                    "[EVIDENCE] Raw response:"
                )

                print(
                    response
                )

                continue

            self._store_retrieved_evidence(
                state=state,
                query=query,
                data=data,
                retrieved=retrieved,
            )

    # =====================================================
    # PROMPT
    # =====================================================

    def _build_retrieval_prompt(
        self,
        research_question: str,
        sub_question: str,
        retrieved,
    ) -> str:

        context_blocks = []

        for result in retrieved:

            context_blocks.append(
                (
                    f"[CHUNK_ID: {result.chunk_id}]\n"
                    f"Paper: {result.title}\n"
                    f"DOI: {result.doi or 'Unknown'}\n"
                    f"Section: {result.section}\n"
                    f"Pages: "
                    f"{result.page_start}-"
                    f"{result.page_end}\n"
                    f"Retrieval Score: "
                    f"{result.score:.4f}\n"
                    f"Text:\n"
                    f"{result.text}"
                )
            )

        context = "\n\n".join(
            context_blocks
        )

        return f"""
You are an expert scientific research assistant.

Your job is to extract scientific evidence ONLY from the
retrieved full-paper passages provided below.

ORIGINAL RESEARCH QUESTION:
{research_question}

CURRENT SUB-QUESTION:
{sub_question}

RETRIEVED SCIENTIFIC PASSAGES:

{context}

INSTRUCTIONS:

1. Use ONLY information explicitly supported by the
   retrieved passages.

2. Do NOT use outside knowledge.

3. Do NOT invent findings, methods, limitations,
   citations, page numbers, or scientific claims.

4. Extract the strongest evidence relevant to the
   current sub-question.

5. Every finding must identify the CHUNK_ID that
   supports it.

6. If the retrieved passages do not contain enough
   information for methods or limitations, return
   an empty string for those fields.

7. Relevance should explain how the retrieved evidence
   helps answer the current sub-question.

Return ONLY valid JSON.

Do not include markdown.
Do not include explanations outside the JSON.

Use exactly this structure:

{{
    "findings": [
        {{
            "claim": "scientific finding",
            "chunk_id": "supporting chunk id"
        }}
    ],
    "methods": "",
    "limitations": "",
    "relevance": ""
}}
"""

    # =====================================================
    # STORE EVIDENCE
    # =====================================================

    def _store_retrieved_evidence(
        self,
        state,
        query,
        data,
        retrieved,
    ):
        """
        Preserve compatibility with the existing Evidence
        model while attaching RAG provenance dynamically.

        We are deliberately NOT changing Evidence yet,
        because downstream agents may depend on its
        current constructor.
        """

        findings_data = (
            data.get(
                "findings",
                [],
            )
        )

        if not isinstance(
            findings_data,
            list,
        ):

            findings_data = []

        valid_chunk_ids = {
            result.chunk_id
            for result in retrieved
        }

        findings = []

        cited_chunk_ids = []

        for item in findings_data:

            if isinstance(
                item,
                dict,
            ):

                claim = str(
                    item.get(
                        "claim",
                        "",
                    )
                ).strip()

                chunk_id = str(
                    item.get(
                        "chunk_id",
                        "",
                    )
                ).strip()

                if not claim:

                    continue

                # Reject hallucinated chunk IDs.
                if (
                    chunk_id
                    and chunk_id
                    not in valid_chunk_ids
                ):

                    print(
                        "[EVIDENCE] Ignoring "
                        "invalid chunk citation:",
                        chunk_id,
                    )

                    continue

                findings.append(
                    claim
                )

                if chunk_id:

                    cited_chunk_ids.append(
                        chunk_id
                    )

            elif isinstance(
                item,
                str,
            ):

                claim = (
                    item.strip()
                )

                if claim:

                    findings.append(
                        claim
                    )

        if not findings:

            print(
                "[EVIDENCE] No supported findings "
                "returned."
            )

            return

        # -------------------------------------------------
        # Determine primary paper for compatibility.
        # -------------------------------------------------

        primary_result = (
            retrieved[0]
        )

        evidence = Evidence(
            paper_title=(
                primary_result.title
            ),

            findings=findings,

            methods=str(
                data.get(
                    "methods",
                    "",
                )
            ).strip(),

            limitations=str(
                data.get(
                    "limitations",
                    "",
                )
            ).strip(),

            relevance=str(
                data.get(
                    "relevance",
                    "",
                )
            ).strip(),
        )

        # -------------------------------------------------
        # Attach Research V2 provenance without breaking
        # the existing Evidence constructor.
        # -------------------------------------------------

        evidence.query = (
            query
        )

        evidence.source_type = (
            "full_text_rag"
        )

        evidence.cited_chunk_ids = list(
            dict.fromkeys(
                cited_chunk_ids
            )
        )

        evidence.retrieved_chunks = [
            {
                "chunk_id": result.chunk_id,
                "paper_id": result.paper_id,
                "paper_title": result.title,
                "doi": result.doi,
                "section": result.section,
                "page_start": result.page_start,
                "page_end": result.page_end,
                "retrieval_score": (
                    result.score
                ),
            }
            for result in retrieved
        ]

        state.evidence.append(
            evidence
        )

        print()
        print(
            "[EVIDENCE] Evidence extracted successfully."
        )

        print(
            "[EVIDENCE] Findings:",
            evidence.findings,
        )

        print(
            "[EVIDENCE] Cited chunks:",
            evidence.cited_chunk_ids,
        )

        print(
            "[EVIDENCE] Methods:",
            evidence.methods,
        )

        print(
            "[EVIDENCE] Limitations:",
            evidence.limitations,
        )

        print(
            "[EVIDENCE] Relevance:",
            evidence.relevance,
        )

    # =====================================================
    # ABSTRACT FALLBACK
    # =====================================================

    def _extract_from_abstracts(
        self,
        state,
    ):
        """
        Compatibility fallback.

        Used only when the entire full-text corpus could
        not be created.
        """

        for paper in state.papers:

            abstract = (
                paper.abstract or ""
            ).strip()

            if not abstract:

                continue

            prompt = f"""
You are an expert scientific research assistant.

Full paper text was unavailable.

Use ONLY the following paper abstract.

Research question:
{state.question}

Title:
{paper.title}

Abstract:
{abstract}

Extract:

1. Key findings
2. Methods used
3. Limitations
4. Relevance to the research question

Do not use outside knowledge.

If information is not present in the abstract,
return an empty string or empty list.

Return ONLY valid JSON.

Do not include markdown.
Do not include explanations.

Use this structure:

{{
    "findings": [],
    "methods": "",
    "limitations": "",
    "relevance": ""
}}
"""

            response = (
                self.llm.generate(
                    prompt
                )
            )

            data = (
                self._parse_json_response(
                    response
                )
            )

            if data is None:

                print(
                    "[EVIDENCE] Abstract fallback "
                    "JSON parsing failed for:",
                    paper.title,
                )

                continue

            findings = (
                data.get(
                    "findings",
                    [],
                )
            )

            if not isinstance(
                findings,
                list,
            ):

                findings = []

            evidence = Evidence(
                paper_title=paper.title,

                findings=findings,

                methods=str(
                    data.get(
                        "methods",
                        "",
                    )
                ).strip(),

                limitations=str(
                    data.get(
                        "limitations",
                        "",
                    )
                ).strip(),

                relevance=str(
                    data.get(
                        "relevance",
                        "",
                    )
                ).strip(),
            )

            evidence.query = (
                state.question
            )

            evidence.source_type = (
                "abstract_fallback"
            )

            evidence.cited_chunk_ids = []

            evidence.retrieved_chunks = []

            state.evidence.append(
                evidence
            )

            print()
            print(
                "[EVIDENCE] Abstract fallback "
                "evidence extracted:"
            )

            print(
                paper.title
            )

    # =====================================================
    # JSON PARSING
    # =====================================================

    def _parse_json_response(
        self,
        response,
    ):
        """
        Conservative JSON parser.

        The prompt requests raw JSON, but this also handles
        accidental ```json wrappers without making another
        LLM call.
        """

        if response is None:

            return None

        cleaned = str(
            response
        ).strip()

        if cleaned.startswith(
            "```json"
        ):

            cleaned = (
                cleaned[7:]
            )

        elif cleaned.startswith(
            "```"
        ):

            cleaned = (
                cleaned[3:]
            )

        if cleaned.endswith(
            "```"
        ):

            cleaned = (
                cleaned[:-3]
            )

        cleaned = (
            cleaned.strip()
        )

        try:

            data = json.loads(
                cleaned
            )

        except json.JSONDecodeError:

            return None

        if not isinstance(
            data,
            dict,
        ):

            return None

        return data

    # =====================================================
    # DEBUG
    # =====================================================

    def _print_retrieval_results(
        self,
        retrieved,
    ):

        print()
        print(
            "[EVIDENCE] Retrieved full-paper evidence:"
        )

        for result in retrieved:

            print(
                f"  Rank "
                f"{result.retrieval_rank} | "
                f"{result.title} | "
                f"pages "
                f"{result.page_start}-"
                f"{result.page_end} | "
                f"section="
                f"{result.section} | "
                f"score="
                f"{result.score:.4f} | "
                f"{result.chunk_id}"
            )