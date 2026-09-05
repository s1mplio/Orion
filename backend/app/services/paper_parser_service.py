from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import re

from pypdf import PdfReader

from app.models.paper import Paper


# =========================================================
# PARSED PAGE
# =========================================================

@dataclass
class ParsedPage:
    """
    Text extracted from one PDF page.

    page_number is 1-based so that it matches the page
    numbering a user naturally expects when reading a PDF.
    """

    page_number: int
    text: str

    @property
    def character_count(self) -> int:
        return len(self.text)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


# =========================================================
# PARSED PAPER
# =========================================================

@dataclass
class ParsedPaper:
    """
    Structured representation of one parsed scientific
    paper.

    This object becomes the input to the chunking stage.
    """

    title: str
    openalex_id: Optional[str]
    doi: Optional[str]
    source_name: Optional[str]
    local_pdf_path: str

    pages: List[ParsedPage] = field(
        default_factory=list
    )

    total_pages: int = 0
    pages_with_text: int = 0
    total_characters: int = 0
    total_words: int = 0

    @property
    def full_text(self) -> str:
        """
        Combine all extracted page text.

        We preserve page boundaries here so that the
        original document structure is not completely lost.
        """

        return "\n\n".join(
            page.text
            for page in self.pages
            if page.text
        )


# =========================================================
# PAPER PARSER SERVICE
# =========================================================

class PaperParserService:
    """
    Research V2 - Scientific PDF Parser

    Responsibility:
    - Read locally acquired PDFs
    - Extract text page-by-page
    - Perform conservative text cleanup
    - Preserve page provenance
    - Return structured ParsedPaper objects

    This service DOES NOT:
    - Download papers
    - Chunk papers
    - Create embeddings
    - Retrieve evidence
    - Call an LLM
    """

    def __init__(
        self,
        minimum_page_characters: int = 20,
    ):
        self.minimum_page_characters = (
            minimum_page_characters
        )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def parse(
        self,
        paper: Paper,
    ) -> Optional[ParsedPaper]:
        """
        Parse one acquired Paper.

        Returns:
            ParsedPaper on success.
            None if the document cannot be parsed.
        """

        local_pdf_path = getattr(
            paper,
            "local_pdf_path",
            None,
        )

        # -------------------------------------------------
        # ACQUISITION CHECK
        # -------------------------------------------------

        if not getattr(
            paper,
            "full_text_available",
            False,
        ):

            print(
                f"[PARSER] Full text unavailable: "
                f"{paper.title}"
            )

            return None

        if not local_pdf_path:

            print(
                f"[PARSER] Missing local PDF path: "
                f"{paper.title}"
            )

            return None

        path = Path(
            local_pdf_path
        )

        if not path.exists():

            print(
                f"[PARSER] PDF does not exist: "
                f"{path}"
            )

            return None

        if not path.is_file():

            print(
                f"[PARSER] PDF path is not a file: "
                f"{path}"
            )

            return None

        # -------------------------------------------------
        # OPEN PDF
        # -------------------------------------------------

        try:

            reader = PdfReader(
                str(path)
            )

        except Exception as exc:

            print(
                f"[PARSER] Failed to open PDF: "
                f"{paper.title}"
            )

            print(
                f"         {exc}"
            )

            return None

        total_pages = len(
            reader.pages
        )

        if total_pages == 0:

            print(
                f"[PARSER] PDF contains no pages: "
                f"{paper.title}"
            )

            return None

        print(
            f"\n[PARSER] Parsing: "
            f"{paper.title}"
        )

        print(
            f"[PARSER] PDF pages: "
            f"{total_pages}"
        )

        parsed_pages = []

        pages_with_text = 0
        total_characters = 0
        total_words = 0

        # =================================================
        # PAGE-BY-PAGE EXTRACTION
        # =================================================

        for index, pdf_page in enumerate(
            reader.pages,
            start=1,
        ):

            try:

                raw_text = (
                    pdf_page.extract_text()
                    or ""
                )

            except Exception as exc:

                print(
                    f"[PARSER] Page {index} "
                    f"extraction failed: {exc}"
                )

                raw_text = ""

            cleaned_text = (
                self._clean_text(
                    raw_text
                )
            )

            # ---------------------------------------------
            # VERY SMALL PAGE OUTPUT
            # ---------------------------------------------
            #
            # Some PDFs contain pages that are effectively
            # image-only or contain tiny fragments.
            #
            # We keep the page record for provenance but
            # don't count tiny fragments as meaningful
            # extracted text.
            # ---------------------------------------------

            meaningful_text = (
                len(cleaned_text)
                >= self.minimum_page_characters
            )

            if meaningful_text:

                pages_with_text += 1

                total_characters += len(
                    cleaned_text
                )

                total_words += len(
                    cleaned_text.split()
                )

            parsed_pages.append(
                ParsedPage(
                    page_number=index,
                    text=(
                        cleaned_text
                        if meaningful_text
                        else ""
                    ),
                )
            )

        # =================================================
        # VALIDATE EXTRACTION
        # =================================================

        if pages_with_text == 0:

            print(
                f"[PARSER] No usable text extracted: "
                f"{paper.title}"
            )

            print(
                "[PARSER] The document may be "
                "image-based/scanned."
            )

            return None

        # =================================================
        # CREATE PARSED PAPER
        # =================================================

        parsed_paper = ParsedPaper(
            title=paper.title,

            openalex_id=getattr(
                paper,
                "url",
                None,
            ),

            doi=getattr(
                paper,
                "doi",
                None,
            ),

            source_name=getattr(
                paper,
                "source_name",
                None,
            ),

            local_pdf_path=str(
                path.resolve()
            ),

            pages=parsed_pages,

            total_pages=total_pages,

            pages_with_text=(
                pages_with_text
            ),

            total_characters=(
                total_characters
            ),

            total_words=(
                total_words
            ),
        )

        # -------------------------------------------------
        # Store parsed text on Paper as well.
        #
        # This gives later components a convenient fallback,
        # while ParsedPaper remains our structured version.
        # -------------------------------------------------

        paper.full_text = (
            parsed_paper.full_text
        )

        print(
            "[PARSER] Extraction complete."
        )

        print(
            f"[PARSER] Pages with text: "
            f"{pages_with_text}/{total_pages}"
        )

        print(
            f"[PARSER] Characters: "
            f"{total_characters}"
        )

        print(
            f"[PARSER] Words: "
            f"{total_words}"
        )

        return parsed_paper

    # =====================================================
    # BATCH PARSING
    # =====================================================

    def parse_many(
        self,
        papers,
    ) -> List[ParsedPaper]:
        """
        Parse multiple acquired papers.

        Failed documents are skipped rather than crashing
        the complete research run.
        """

        papers = list(
            papers or []
        )

        parsed_papers = []

        print(
            "\n========== "
            "SCIENTIFIC PAPER PARSING "
            "==========\n"
        )

        for index, paper in enumerate(
            papers,
            start=1,
        ):

            print(
                f"[{index}/{len(papers)}]"
            )

            parsed = self.parse(
                paper
            )

            if parsed is not None:

                parsed_papers.append(
                    parsed
                )

        print(
            "\n==================================="
        )

        print(
            "PAPER PARSING SUMMARY"
        )

        print(
            "==================================="
        )

        print(
            "Attempted:",
            len(papers),
        )

        print(
            "Parsed:",
            len(parsed_papers),
        )

        print(
            "Failed:",
            (
                len(papers)
                - len(parsed_papers)
            ),
        )

        print(
            "===================================\n"
        )

        return parsed_papers

    # =====================================================
    # TEXT CLEANING
    # =====================================================

    def _clean_text(
        self,
        text: str,
    ) -> str:
        """
        Conservative PDF text cleanup.

        Scientific PDFs have layout artifacts such as:

            habita-
            bility

        or excessive spaces/newlines.

        We clean obvious extraction noise without making
        aggressive assumptions about document structure.
        """

        if not text:

            return ""

        # Normalize line endings.
        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        # -------------------------------------------------
        # JOIN WORDS SPLIT BY PDF LINE WRAPPING
        #
        # Example:
        #
        # habita-
        # bility
        #
        # becomes:
        #
        # habitability
        # -------------------------------------------------

        text = re.sub(
            r"([A-Za-z])-\n([A-Za-z])",
            r"\1\2",
            text,
        )

        # -------------------------------------------------
        # NORMALIZE TABS
        # -------------------------------------------------

        text = text.replace(
            "\t",
            " ",
        )

        # -------------------------------------------------
        # NORMALIZE MULTIPLE SPACES
        # -------------------------------------------------

        text = re.sub(
            r"[ ]{2,}",
            " ",
            text,
        )

        # -------------------------------------------------
        # NORMALIZE NEWLINES
        #
        # Keep paragraph boundaries where possible while
        # removing excessive blank lines.
        # -------------------------------------------------

        text = re.sub(
            r"\n[ ]+\n",
            "\n\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        # Remove leading/trailing whitespace per line.
        lines = [
            line.strip()
            for line in text.splitlines()
        ]

        text = "\n".join(
            lines
        )

        return text.strip()