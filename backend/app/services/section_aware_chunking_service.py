from dataclasses import dataclass
from typing import List, Optional

import hashlib
import re

from app.services.paper_parser_service import (
    ParsedPaper,
)

from app.services.paper_chunking_service import (
    PaperChunk,
)


@dataclass
class SectionWord:
    """
    One word together with the PDF page
    from which it originated.
    """

    word: str
    page_number: int


@dataclass
class SectionBuffer:
    """
    Continuous text belonging to one detected
    scientific-paper section.
    """

    section: str
    words: List[SectionWord]


class SectionAwareChunkingService:
    """
    Research V2 - Experimental Section-Aware Chunker

    Main difference from PaperChunkingService:

    Baseline:
        page
          -> section detection
          -> chunk
          -> stop at page boundary

    Experimental:
        pages
          -> detect sections
          -> construct continuous section streams
          -> chunk across page boundaries
          -> preserve page_start/page_end

    A chunk may therefore have:

        page_start = 1
        page_end   = 2

    when evidence naturally crosses a PDF page boundary.

    This service DOES NOT:

    - create embeddings
    - store vectors
    - retrieve evidence
    - call an LLM
    - modify ParsedPaper
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
                "overlap_words must be smaller than "
                "chunk_size_words"
            )

        if minimum_chunk_words <= 0:
            raise ValueError(
                "minimum_chunk_words must be greater than 0"
            )

        self.chunk_size_words = (
            chunk_size_words
        )

        self.overlap_words = (
            overlap_words
        )

        self.minimum_chunk_words = (
            minimum_chunk_words
        )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def chunk(
        self,
        parsed_paper: ParsedPaper,
    ) -> List[PaperChunk]:

        print()
        print(
            "[SECTION CHUNKER] Processing:",
            parsed_paper.title,
        )

        section_buffers = (
            self._build_section_buffers(
                parsed_paper
            )
        )

        chunks = []

        for section_buffer in section_buffers:

            section_chunks = (
                self._chunk_section(
                    parsed_paper=parsed_paper,
                    section_buffer=section_buffer,
                    starting_index=len(chunks),
                )
            )

            chunks.extend(
                section_chunks
            )

        cross_page_count = sum(
            1
            for chunk in chunks
            if chunk.page_start != chunk.page_end
        )

        detected_sections = sorted(
            {
                chunk.section
                for chunk in chunks
            }
        )

        print(
            "[SECTION CHUNKER] Section streams:",
            len(section_buffers),
        )

        print(
            "[SECTION CHUNKER] Total chunks:",
            len(chunks),
        )

        print(
            "[SECTION CHUNKER] Cross-page chunks:",
            cross_page_count,
        )

        print(
            "[SECTION CHUNKER] Sections:",
            detected_sections,
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

        print()
        print(
            "========== SECTION-AWARE CHUNKING =========="
        )

        for index, parsed_paper in enumerate(
            parsed_papers,
            start=1,
        ):

            print()
            print(
                f"[{index}/{len(parsed_papers)}]"
            )

            chunks = self.chunk(
                parsed_paper
            )

            all_chunks.extend(
                chunks
            )

        print()
        print(
            "============================================"
        )

        print(
            "SECTION-AWARE CHUNKING SUMMARY"
        )

        print(
            "============================================"
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
            "============================================"
        )

        return all_chunks

    # =====================================================
    # BUILD CONTINUOUS SECTION STREAMS
    # =====================================================

    def _build_section_buffers(
        self,
        parsed_paper: ParsedPaper,
    ) -> List[SectionBuffer]:
        """
        Read every page in order and create continuous
        section streams.

        The active section survives a page boundary.

        Example:

            Page 1:
                Introduction ...
                Methods ...

            Page 2:
                continuation of Methods ...

        The Methods text from pages 1 and 2 becomes one
        continuous section stream.
        """

        buffers = []

        active_section = "unknown"

        current_buffer = SectionBuffer(
            section=active_section,
            words=[],
        )

        for page in parsed_paper.pages:

            if not page.text:
                continue

            lines = (
                page.text.splitlines()
            )

            for line in lines:

                cleaned_line = (
                    line.strip()
                )

                if not cleaned_line:
                    continue

                detected_section = (
                    self._detect_section(
                        cleaned_line
                    )
                )

                # -----------------------------------------
                # New section heading
                # -----------------------------------------

                if detected_section:

                    if current_buffer.words:

                        buffers.append(
                            current_buffer
                        )

                    active_section = (
                        detected_section
                    )

                    current_buffer = (
                        SectionBuffer(
                            section=active_section,
                            words=[],
                        )
                    )

                    # Do not add the heading itself
                    # to the evidence text.

                    continue

                # -----------------------------------------
                # Normal text
                # -----------------------------------------

                words = (
                    cleaned_line.split()
                )

                for word in words:

                    current_buffer.words.append(
                        SectionWord(
                            word=word,
                            page_number=(
                                page.page_number
                            ),
                        )
                    )

        if current_buffer.words:

            buffers.append(
                current_buffer
            )

        return buffers

    # =====================================================
    # SECTION DETECTION
    # =====================================================

    def _detect_section(
        self,
        line: str,
    ) -> Optional[str]:

        if not line:
            return None

        normalized = (
            line.lower().strip()
        )

        # Remove common numeric heading prefixes:
        #
        # 1 Introduction
        # 1. Introduction
        # 2.1 Methods
        # 3.2.1 Results

        normalized = re.sub(
            r"^\d+(?:\.\d+)*\.?\s+",
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

    # =====================================================
    # CHUNK ONE CONTINUOUS SECTION
    # =====================================================

    def _chunk_section(
        self,
        parsed_paper: ParsedPaper,
        section_buffer: SectionBuffer,
        starting_index: int,
    ) -> List[PaperChunk]:

        words = (
            section_buffer.words
        )

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

            chunk_words = (
                words[start:end]
            )

            if (
                len(chunk_words)
                < self.minimum_chunk_words
                and start != 0
            ):
                break

            chunk_text = " ".join(
                item.word
                for item in chunk_words
            )

            page_numbers = [
                item.page_number
                for item in chunk_words
            ]

            page_start = min(
                page_numbers
            )

            page_end = max(
                page_numbers
            )

            chunk_number = (
                starting_index
                + local_index
            )

            chunk_id = (
                self._build_chunk_id(
                    parsed_paper=parsed_paper,
                    page_start=page_start,
                    page_end=page_end,
                    section=(
                        section_buffer.section
                    ),
                    chunk_number=chunk_number,
                    text=chunk_text,
                )
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

                    section=(
                        section_buffer.section
                    ),

                    page_start=page_start,

                    page_end=page_end,

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

    # =====================================================
    # CHUNK ID
    # =====================================================

    def _build_chunk_id(
        self,
        parsed_paper: ParsedPaper,
        page_start: int,
        page_end: int,
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
            f"{page_start}|"
            f"{page_end}|"
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

        if page_start == page_end:

            page_label = (
                f"p{page_start}"
            )

        else:

            page_label = (
                f"p{page_start}-{page_end}"
            )

        return (
            f"section_chunk_"
            f"{page_label}_"
            f"{digest}"
        )