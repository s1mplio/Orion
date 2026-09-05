from typing import List, Optional


class Paper:

    def __init__(
        self,
        title: str,
        authors: List[str],
        abstract: str,
        year: Optional[int],
        url: str,
        citation_count: int,
        doi: Optional[str] = None,
        landing_page_url: Optional[str] = None,
        pdf_url: Optional[str] = None,
        is_open_access: bool = False,
        open_access_status: Optional[str] = None,
        source_name: Optional[str] = None,
    ):

        # =================================================
        # BASIC PAPER INFORMATION
        # =================================================

        self.title = title

        self.authors = authors

        self.abstract = abstract

        self.year = year

        # OpenAlex work URL / ID.
        #
        # Keeping the old field name "url" preserves
        # compatibility with the existing pipeline.

        self.url = url

        self.citation_count = citation_count

        # =================================================
        # RESEARCH V2 METADATA
        # =================================================

        self.doi = doi

        self.landing_page_url = landing_page_url

        self.pdf_url = pdf_url

        self.is_open_access = is_open_access

        self.open_access_status = open_access_status

        self.source_name = source_name

        # =================================================
        # FULL-TEXT STATE
        #
        # These will be populated later by the
        # FullTextAcquisitionService.
        # =================================================

        self.full_text = None

        self.full_text_source = None

        self.full_text_available = False

    # =====================================================
    # DEBUG / SERIALIZATION
    # =====================================================

    def to_dict(
        self,
    ):

        return {
            "title": self.title,
            "authors": self.authors,
            "abstract": self.abstract,
            "year": self.year,
            "url": self.url,
            "citation_count": self.citation_count,
            "doi": self.doi,
            "landing_page_url": (
                self.landing_page_url
            ),
            "pdf_url": self.pdf_url,
            "is_open_access": (
                self.is_open_access
            ),
            "open_access_status": (
                self.open_access_status
            ),
            "source_name": self.source_name,
            "full_text_available": (
                self.full_text_available
            ),
            "full_text_source": (
                self.full_text_source
            ),
        }

    def __repr__(
        self,
    ):

        return (
            f"Paper("
            f"title={self.title!r}, "
            f"year={self.year!r}, "
            f"citations={self.citation_count}, "
            f"open_access={self.is_open_access}, "
            f"pdf_available={bool(self.pdf_url)}"
            f")"
        )