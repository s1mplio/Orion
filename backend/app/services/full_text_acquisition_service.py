from pathlib import Path
from typing import Optional
from urllib.parse import quote
import hashlib

import requests

from app.models.paper import Paper
from app.services.research_settings import (
    MAX_PDF_MB,
    UNPAYWALL_EMAIL,
)


# backend/data/research_papers, independent of the working
# directory the server was started from.
DEFAULT_CACHE_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "research_papers"
)


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
        cache_dir=DEFAULT_CACHE_DIR,
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

        local_path = (
            self._build_cache_path(
                paper
            )
        )

        # -------------------------------------------------
        # CHECK CACHE FIRST
        # -------------------------------------------------

        if self._is_valid_cached_pdf(
            local_path
        ):
            self._mark_success(
                paper=paper,
                local_path=local_path,
                source_url=paper.pdf_url or "cache",
            )

            print(
                f"[FULL TEXT] Cache hit: "
                f"{paper.title}"
            )

            return True

        # -------------------------------------------------
        # TRY EVERY KNOWN OPEN-ACCESS COPY
        # -------------------------------------------------
        #
        # Only legally open copies are tried: OpenAlex
        # locations, arXiv, PubMed Central, Semantic Scholar
        # and Unpaywall. No paywall bypass is attempted.
        # -------------------------------------------------

        tried = set()

        for source_name, url in self._candidate_urls(paper):

            if not url or url in tried:
                continue

            tried.add(url)

            content, final_url = self._download_pdf(
                url,
                paper.title,
            )

            if content is None:
                continue

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

            if not self._is_valid_cached_pdf(
                local_path
            ):
                local_path.unlink(
                    missing_ok=True
                )
                continue

            self._mark_success(
                paper=paper,
                local_path=local_path,
                source_url=final_url,
            )

            print(
                f"[FULL TEXT] Acquired via {source_name}: "
                f"{paper.title}"
            )

            return True

        print(
            f"[FULL TEXT] No open full text found "
            f"({len(tried)} sources tried): "
            f"{paper.title}"
        )

        return False

    # =====================================================
    # FULL-TEXT SOURCES
    # =====================================================

    def _candidate_urls(
        self,
        paper: Paper,
    ):
        """
        Yield (source name, PDF URL) pairs, cheapest first.

        API-based resolvers run lazily, only when every
        direct link has already failed.
        """

        if paper.pdf_url:
            yield "OpenAlex", paper.pdf_url

        for url in getattr(paper, "pdf_candidates", None) or []:
            yield "OpenAlex location", url

        arxiv_id = getattr(paper, "arxiv_id", None)

        if arxiv_id:
            yield "arXiv", f"https://arxiv.org/pdf/{arxiv_id}"

        pmcid = getattr(paper, "pmcid", None)

        if pmcid:
            yield (
                "PubMed Central",
                "https://europepmc.org/backend/ptpmcrender.fcgi"
                f"?accid={pmcid}&blobtype=pdf",
            )

        doi = self._bare_doi(paper.doi)

        if not doi:
            return

        for url in self._semantic_scholar_pdfs(doi):
            yield "Semantic Scholar", url

        for url in self._unpaywall_pdfs(doi):
            yield "Unpaywall", url

    def _bare_doi(
        self,
        doi,
    ):
        if not doi:
            return None

        doi = str(doi).strip()

        for prefix in (
            "https://doi.org/",
            "http://doi.org/",
            "doi:",
        ):
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix):]

        return doi or None

    def _get_json(
        self,
        url,
        params=None,
    ):
        try:
            response = self.session.get(
                url,
                params=params,
                timeout=self.request_timeout,
                headers={"Accept": "application/json"},
            )

        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        try:
            return response.json()
        except ValueError:
            return None

    def _semantic_scholar_pdfs(
        self,
        doi,
    ):
        data = self._get_json(
            "https://api.semanticscholar.org/graph/v1/paper/DOI:"
            + quote(doi, safe="/"),
            params={"fields": "openAccessPdf"},
        )

        url = ((data or {}).get("openAccessPdf") or {}).get("url")

        return [url] if url else []

    def _unpaywall_pdfs(
        self,
        doi,
    ):
        if not UNPAYWALL_EMAIL:
            return []

        data = self._get_json(
            "https://api.unpaywall.org/v2/" + quote(doi, safe="/"),
            params={"email": UNPAYWALL_EMAIL},
        )

        urls = []

        for location in (data or {}).get("oa_locations") or []:
            url = (location or {}).get("url_for_pdf")

            if url and url not in urls:
                urls.append(url)

        return urls

    # =====================================================
    # DOWNLOAD
    # =====================================================

    def _download_pdf(
        self,
        url,
        title,
    ):
        """
        Download one URL. Returns (bytes, final URL) for a
        real PDF within the size limit, else (None, None).
        """

        max_bytes = MAX_PDF_MB * 1024 * 1024

        try:
            with self.session.get(
                url,
                timeout=self.request_timeout,
                allow_redirects=True,
                stream=True,
            ) as response:

                if response.status_code != 200:
                    print(
                        f"[FULL TEXT] HTTP {response.status_code} "
                        f"from {url}"
                    )
                    return None, None

                declared = response.headers.get("Content-Length")

                if (
                    declared
                    and declared.isdigit()
                    and int(declared) > max_bytes
                ):
                    print(
                        f"[FULL TEXT] Skipping PDF over "
                        f"{MAX_PDF_MB} MB: {title}"
                    )
                    return None, None

                chunks = []
                size = 0

                for chunk in response.iter_content(chunk_size=65536):
                    size += len(chunk)

                    if size > max_bytes:
                        print(
                            f"[FULL TEXT] Skipping PDF over "
                            f"{MAX_PDF_MB} MB: {title}"
                        )
                        return None, None

                    chunks.append(chunk)

                final_url = response.url

        except requests.RequestException as exc:
            print(
                f"[FULL TEXT] Request failed for {url}: {exc}"
            )
            return None, None

        content = b"".join(chunks)

        # Often an HTML landing or login page instead.
        if not self._looks_like_pdf(content):
            return None, None

        return content, final_url

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