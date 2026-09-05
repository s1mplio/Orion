from dataclasses import dataclass
from typing import List, Optional
import re
import hashlib

from app.services.paper_parser_service import ParsedPaper


@dataclass
class PaperChunk:
    chunk_id: str
    paper_id: Optional[str]
    title: str
    doi: Optional[str]
    section: str
    page_start: int
    page_end: int
    text: str
    word_count: int


class PaperChunkingService:
    """
    Research V2 - Scientific Paper Chunking

    Responsibilities:
    - Accept ParsedPaper objects
    - Detect common scientific section headings
    - Split text into overlapping word-based chunks
    - Preserve paper/page/section provenance

    This service DOES NOT:
    - Create embeddings
    - Store vectors
    - Retrieve chunks
    - Call an LLM
    """

    SECTION_PATTERNS = [
        "abstract",
        "introduction",
        "background",
        "related work",
        "materials and methods",
        "materials & methods",
        "methods",
        "methodology",
        "experimental methods",
        "experimental setup",
        "results",
        "results and discussion",
        "discussion",
        "limitations",
        "conclusion",
        "conclusions",
        "future work",
        "acknowledgements",
        "acknowledgments",
        "references",
    ]

    def __init__(
        self,
        chunk_size_words: int = 350,
        overlap_words: int = 60,
        minimum_chunk_words: int = 40,
    ):
        if chunk_size_words <= 0:
            raise ValueError(
                "chunk_size_words must be greater than 0"
            )

        if overlap_words < 0:
            raise ValueError(
                "overlap_words cannot be negative"
            )

        if overlap_words >= chunk_size_words:
            raise ValueError(
                "overlap_words must be smaller than chunk_size_words"
            )

        self.chunk_size_words = chunk_size_words
        self.overlap_words = overlap_words
        self.minimum_chunk_words = minimum_chunk_words

    def chunk(
        self,
        parsed_paper: ParsedPaper,
    ) -> List[PaperChunk]:

        print(
            f"\n[CHUNKER] Processing: "
            f"{parsed_paper.title}"
        )

        chunks = []

        current_section = "unknown"

        for page in parsed_paper.pages:

            if not page.text:
                continue

            page_segments = self._split_page_by_sections(
                page.text,
                current_section,
            )

            for section_name, segment_text in page_segments:

                current_section = section_name

                segment_chunks = self._chunk_segment(
                    text=segment_text,
                    parsed_paper=parsed_paper,
                    section=section_name,
                    page_number=page.page_number,
                    starting_index=len(chunks),
                )

                chunks.extend(
                    segment_chunks
                )

        print(
            f"[CHUNKER] Total chunks: "
            f"{len(chunks)}"
        )

        return chunks

    def chunk_many(
        self,
        parsed_papers,
    ) -> List[PaperChunk]:

        parsed_papers = list(
            parsed_papers or []
        )

        all_chunks = []

        print(
            "\n========== PAPER CHUNKING ==========\n"
        )

        for index, parsed_paper in enumerate(
            parsed_papers,
            start=1,
        ):

            print(
                f"[{index}/{len(parsed_papers)}]"
            )

            chunks = self.chunk(
                parsed_paper
            )

            all_chunks.extend(
                chunks
            )

        print(
            "\n==================================="
        )

        print(
            "PAPER CHUNKING SUMMARY"
        )

        print(
            "==================================="
        )

        print(
            "Papers:",
            len(parsed_papers),
        )

        print(
            "Chunks:",
            len(all_chunks),
        )

        print(
            "===================================\n"
        )

        return all_chunks

    def _split_page_by_sections(
        self,
        text: str,
        current_section: str,
    ):
        lines = text.splitlines()

        segments = []

        active_section = current_section
        buffer = []

        for line in lines:

            cleaned_line = line.strip()

            detected_section = self._detect_section(
                cleaned_line
            )

            if detected_section:

                if buffer:

                    segment_text = "\n".join(
                        buffer
                    ).strip()

                    if segment_text:

                        segments.append(
                            (
                                active_section,
                                segment_text,
                            )
                        )

                active_section = detected_section

                buffer = []

                continue

            buffer.append(
                line
            )

        if buffer:

            segment_text = "\n".join(
                buffer
            ).strip()

            if segment_text:

                segments.append(
                    (
                        active_section,
                        segment_text,
                    )
                )

        return segments

    def _detect_section(
        self,
        line: str,
    ) -> Optional[str]:

        if not line:
            return None

        normalized = line.lower().strip()

        normalized = re.sub(
            r"^\d+(\.\d+)*[\.\s]+",
            "",
            normalized,
        )

        normalized = normalized.strip(
            " :-"
        )

        for section in self.SECTION_PATTERNS:

            if normalized == section:

                return section

        return None

    def _chunk_segment(
        self,
        text: str,
        parsed_paper: ParsedPaper,
        section: str,
        page_number: int,
        starting_index: int,
    ) -> List[PaperChunk]:

        words = text.split()

        if not words:
            return []

        chunks = []

        step = (
            self.chunk_size_words
            - self.overlap_words
        )

        start = 0
        local_index = 0

        while start < len(words):

            end = min(
                start + self.chunk_size_words,
                len(words),
            )

            chunk_words = words[
                start:end
            ]

            if (
                len(chunk_words)
                < self.minimum_chunk_words
                and start != 0
            ):
                break

            chunk_text = " ".join(
                chunk_words
            )

            chunk_number = (
                starting_index
                + local_index
            )

            chunk_id = self._build_chunk_id(
                parsed_paper=parsed_paper,
                page_number=page_number,
                section=section,
                chunk_number=chunk_number,
                text=chunk_text,
            )

            chunks.append(
                PaperChunk(
                    chunk_id=chunk_id,

                    paper_id=(
                        parsed_paper.openalex_id
                    ),

                    title=(
                        parsed_paper.title
                    ),

                    doi=(
                        parsed_paper.doi
                    ),

                    section=section,

                    page_start=page_number,

                    page_end=page_number,

                    text=chunk_text,

                    word_count=len(
                        chunk_words
                    ),
                )
            )

            local_index += 1

            if end >= len(words):
                break

            start += step

        return chunks

    def _build_chunk_id(
        self,
        parsed_paper: ParsedPaper,
        page_number: int,
        section: str,
        chunk_number: int,
        text: str,
    ) -> str:

        paper_identifier = (
            parsed_paper.openalex_id
            or parsed_paper.doi
            or parsed_paper.title
        )

        raw_identifier = (
            f"{paper_identifier}|"
            f"{page_number}|"
            f"{section}|"
            f"{chunk_number}|"
            f"{text[:100]}"
        )

        digest = hashlib.sha256(
            raw_identifier.encode(
                "utf-8",
                errors="ignore",
            )
        ).hexdigest()[:12]

        return (
            f"chunk_"
            f"p{page_number}_"
            f"{digest}"
        )