from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import hashlib

import requests

from app.models.paper import Paper


class FullTextAcquisitionService:
    """
    Research V2 - Full Text Acquisition

    Responsibility:
    - Receive Paper objects discovered by ResearchAgent
    - Download legally available open-access PDFs
    - Validate that the response is actually a PDF
    - Cache PDFs locally
    - Record acquisition metadata on the Paper object

    This service DOES NOT:
    - Parse PDF text
    - Chunk documents
    - Create embeddings
    - Perform vector retrieval
    """

    def __init__(
        self,
        cache_dir: str = "data/research_papers",
        request_timeout: int = 30,
    ):
        self.cache_dir = Path(cache_dir)

        self.request_timeout = request_timeout

        self.cache_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "OrionResearch/2.0 "
                    "(scientific research assistant)"
                ),
                "Accept": (
                    "application/pdf,"
                    "application/octet-stream;q=0.9,"
                    "*/*;q=0.8"
                ),
            }
        )

    # =====================================================
    # PUBLIC API
    # =====================================================

    def acquire(
        self,
        paper: Paper,
    ) -> bool:
        """
        Attempt to acquire the full-text PDF for one paper.

        Returns:
            True  -> PDF successfully acquired or cached
            False -> full text could not be acquired
        """

        self._reset_acquisition_state(
            paper
        )

        # -------------------------------------------------
        # We currently acquire only papers where OpenAlex
        # provides a direct PDF URL.
        #
        # Additional resolvers can be added later without
        # changing the rest of the RAG pipeline.
        # -------------------------------------------------

        pdf_url = getattr(
            paper,
            "pdf_url",
            None,
        )

        if not pdf_url:

            print(
                f"[FULL TEXT] No direct PDF: "
                f"{paper.title}"
            )

            return False

        # -------------------------------------------------
        # CHECK CACHE FIRST
        # -------------------------------------------------

        local_path = (
            self._build_cache_path(
                paper
            )
        )

        if self._is_valid_cached_pdf(
            local_path
        ):
            self._mark_success(
                paper=paper,
                local_path=local_path,
                source_url=pdf_url,
            )

            print(
                f"[FULL TEXT] Cache hit: "
                f"{paper.title}"
            )

            return True

        # -------------------------------------------------
        # DOWNLOAD
        # -------------------------------------------------

        print(
            f"[FULL TEXT] Downloading: "
            f"{paper.title}"
        )

        try:

            response = self.session.get(
                pdf_url,
                timeout=self.request_timeout,
                allow_redirects=True,
            )

        except requests.RequestException as exc:

            print(
                f"[FULL TEXT] Request failed: "
                f"{paper.title}"
            )

            print(
                f"            {exc}"
            )

            return False

        # -------------------------------------------------
        # HTTP VALIDATION
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                f"[FULL TEXT] HTTP "
                f"{response.status_code}: "
                f"{paper.title}"
            )

            return False

        content = response.content

        # -------------------------------------------------
        # DOCUMENT VALIDATION
        # -------------------------------------------------

        if not self._looks_like_pdf(
            content
        ):
            content_type = (
                response.headers.get(
                    "Content-Type",
                    ""
                )
            )

            print(
                f"[FULL TEXT] Response was "
                f"not a valid PDF: "
                f"{paper.title}"
            )

            print(
                f"            Content-Type: "
                f"{content_type}"
            )

            return False

        # -------------------------------------------------
        # SAVE ATOMICALLY
        # -------------------------------------------------

        try:

            self._save_pdf(
                local_path=local_path,
                content=content,
            )

        except OSError as exc:

            print(
                f"[FULL TEXT] Failed to save: "
                f"{paper.title}"
            )

            print(
                f"            {exc}"
            )

            return False

        # -------------------------------------------------
        # FINAL VALIDATION
        # -------------------------------------------------

        if not self._is_valid_cached_pdf(
            local_path
        ):
            print(
                f"[FULL TEXT] Saved file failed "
                f"validation: {paper.title}"
            )

            try:
                local_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            return False

        self._mark_success(
            paper=paper,
            local_path=local_path,
            source_url=response.url,
        )

        print(
            f"[FULL TEXT] Acquired: "
            f"{paper.title}"
        )

        print(
            f"            Saved: "
            f"{local_path}"
        )

        return True

    # =====================================================
    # BATCH ACQUISITION
    # =====================================================

    def acquire_many(
        self,
        papers,
        limit: Optional[int] = None,
    ):
        """
        Acquire full text for multiple Paper objects.

        Returns only successfully acquired papers.

        `limit` is useful during development so we don't
        download an unnecessarily large corpus.
        """

        papers = list(
            papers or []
        )

        if limit is not None:
            papers = papers[:limit]

        acquired = []

        print(
            "\n========== "
            "FULL-TEXT ACQUISITION "
            "==========\n"
        )

        for index, paper in enumerate(
            papers,
            start=1,
        ):

            print(
                f"[{index}/{len(papers)}]"
            )

            if self.acquire(
                paper
            ):
                acquired.append(
                    paper
                )

        print(
            "\n==================================="
        )

        print(
            "FULL-TEXT ACQUISITION SUMMARY"
        )

        print(
            "==================================="
        )

        print(
            "Attempted:",
            len(papers),
        )

        print(
            "Acquired:",
            len(acquired),
        )

        print(
            "Unavailable/Failed:",
            (
                len(papers)
                - len(acquired)
            ),
        )

        print(
            "===================================\n"
        )

        return acquired

    # =====================================================
    # PAPER STATE
    # =====================================================

    def _reset_acquisition_state(
        self,
        paper: Paper,
    ):
        paper.full_text_available = False

        paper.full_text_source = None

        # We are intentionally NOT putting the actual
        # extracted paper text here yet.
        #
        # Step 3 will parse the cached PDF.
        paper.full_text = None

        # Added dynamically for now.
        # We can promote this into Paper permanently
        # once this component passes validation.
        paper.local_pdf_path = None

    def _mark_success(
        self,
        paper: Paper,
        local_path: Path,
        source_url: str,
    ):
        paper.full_text_available = True

        paper.full_text_source = (
            source_url
        )

        paper.local_pdf_path = str(
            local_path.resolve()
        )

    # =====================================================
    # CACHE PATH
    # =====================================================

    def _build_cache_path(
        self,
        paper: Paper,
    ) -> Path:
        """
        Build a deterministic filename.

        We don't use the paper title directly because
        scientific titles can contain characters invalid
        in Windows filenames.
        """

        stable_identifier = (
            getattr(
                paper,
                "url",
                None,
            )
            or getattr(
                paper,
                "doi",
                None,
            )
            or getattr(
                paper,
                "title",
                "paper",
            )
        )

        identifier_hash = hashlib.sha256(
            stable_identifier.encode(
                "utf-8",
                errors="ignore",
            )
        ).hexdigest()[:16]

        title_slug = (
            self._safe_title(
                getattr(
                    paper,
                    "title",
                    "paper",
                )
            )
        )

        filename = (
            f"{title_slug}_"
            f"{identifier_hash}.pdf"
        )

        return (
            self.cache_dir
            / filename
        )

    def _safe_title(
        self,
        title: str,
    ) -> str:

        cleaned = []

        for character in title:

            if (
                character.isalnum()
                or character in (
                    "-",
                    "_",
                    " ",
                )
            ):
                cleaned.append(
                    character
                )

            else:
                cleaned.append(
                    " "
                )

        slug = "".join(
            cleaned
        )

        slug = "_".join(
            slug.split()
        )

        if not slug:
            slug = "paper"

        # Avoid excessively long Windows paths.
        return slug[:80]

    # =====================================================
    # PDF VALIDATION
    # =====================================================

    def _looks_like_pdf(
        self,
        content: bytes,
    ) -> bool:
        """
        Validate using the PDF file signature.

        A real PDF should begin with:
            %PDF-

        This is more reliable than trusting Content-Type,
        because some servers return incorrect headers.
        """

        if not content:
            return False

        if len(content) < 5:
            return False

        return content.startswith(
            b"%PDF-"
        )

    def _is_valid_cached_pdf(
        self,
        path: Path,
    ) -> bool:

        if not path.exists():
            return False

        if not path.is_file():
            return False

        try:

            # Reject obviously broken/empty files.
            if path.stat().st_size < 100:
                return False

            with path.open(
                "rb"
            ) as file:
                signature = file.read(
                    5
                )

            return (
                signature == b"%PDF-"
            )

        except OSError:

            return False

    # =====================================================
    # SAVE PDF
    # =====================================================

    def _save_pdf(
        self,
        local_path: Path,
        content: bytes,
    ):
        """
        Atomic-ish local write.

        Write to a temporary file first and rename only
        after the complete response has been written.
        """

        temp_path = (
            local_path.with_suffix(
                ".tmp"
            )
        )

        try:

            with temp_path.open(
                "wb"
            ) as file:

                file.write(
                    content
                )

                file.flush()

            temp_path.replace(
                local_path
            )

        finally:

            if temp_path.exists():

                try:
                    temp_path.unlink()
                except OSError:
                    pass