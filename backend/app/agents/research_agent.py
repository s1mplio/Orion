from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from dotenv import load_dotenv

from app.models.paper import Paper


load_dotenv()


class ResearchAgent:

    def __init__(self):
        """
        Research V2 - Paper Discovery Agent

        Responsibility:
        - Search OpenAlex
        - Retrieve candidate scientific papers
        - Extract useful metadata
        - Reconstruct abstracts
        - Deduplicate papers

        This agent DOES NOT download PDFs.
        Full-text acquisition will be handled separately.
        """

        self.base_url = "https://api.openalex.org/works"

        # Number of candidate papers retrieved
        # for each research sub-question.
        self.papers_per_query = 10

        # HTTP request timeout in seconds.
        self.request_timeout = 20

    # =====================================================
    # SEARCH OPENALEX
    # =====================================================

    def search_papers(self, query):
        """
        Search OpenAlex for papers related to one
        research query/sub-question.

        Returns:
            List[Paper]
        """

        if not query:
            return []

        query = query.replace("?", "").strip()

        if not query:
            return []

        params = {
            "search": query,
            "per-page": self.papers_per_query,
        }

        try:

            response = requests.get(
                self.base_url,
                params=params,
                timeout=self.request_timeout,
            )

        except requests.RequestException as exc:

            print(
                f"OpenAlex request failed "
                f"for '{query}': {exc}"
            )

            return []

        # -------------------------------------------------
        # HTTP VALIDATION
        # -------------------------------------------------

        if response.status_code != 200:

            print(
                f"OpenAlex search failed "
                f"for: {query}"
            )

            print(
                "Status:",
                response.status_code,
            )

            return []

        # -------------------------------------------------
        # JSON VALIDATION
        # -------------------------------------------------

        try:

            data = response.json()

        except ValueError:

            print(
                f"OpenAlex returned invalid JSON "
                f"for: {query}"
            )

            return []

        # -------------------------------------------------
        # CONVERT RESULTS INTO PAPER OBJECTS
        # -------------------------------------------------

        paper_objects = []

        for paper_data in data.get("results", []):

            try:

                paper = self._build_paper(
                    paper_data
                )

                if paper is not None:
                    paper_objects.append(
                        paper
                    )

            except Exception as exc:

                print(
                    "Failed to parse OpenAlex paper:",
                    exc,
                )

        return paper_objects

    # =====================================================
    # BUILD PAPER OBJECT
    # =====================================================

    def _build_paper(self, paper_data):
        """
        Convert one OpenAlex result into our internal
        Paper object.
        """

        if not isinstance(paper_data, dict):
            return None

        # =================================================
        # TITLE
        # =================================================

        title = (
            paper_data.get("display_name")
            or ""
        ).strip()

        if not title:
            return None

        # =================================================
        # PUBLICATION YEAR
        # =================================================

        year = paper_data.get(
            "publication_year"
        )

        # =================================================
        # CITATION COUNT
        # =================================================

        citation_count = (
            paper_data.get(
                "cited_by_count",
                0,
            )
            or 0
        )

        # =================================================
        # OPENALEX ID
        # =================================================

        openalex_id = (
            paper_data.get("id")
            or ""
        )

        # =================================================
        # AUTHORS
        # =================================================

        authors = []

        for authorship in (
            paper_data.get(
                "authorships",
                [],
            )
            or []
        ):

            if not isinstance(
                authorship,
                dict,
            ):
                continue

            author_data = (
                authorship.get("author")
                or {}
            )

            name = (
                author_data.get(
                    "display_name"
                )
                or ""
            ).strip()

            if name:
                authors.append(name)

        # =================================================
        # ABSTRACT
        # =================================================
        #
        # OpenAlex stores many abstracts as an inverted
        # index rather than normal text.
        #
        # Example:
        #
        # {
        #     "Europa": [0, 5],
        #     "ocean": [1],
        #     ...
        # }
        #
        # reconstruct_abstract() restores normal text.
        # =================================================

        abstract = self.reconstruct_abstract(
            paper_data.get(
                "abstract_inverted_index"
            )
        )

        # =================================================
        # DOI
        # =================================================

        doi = paper_data.get("doi")

        # =================================================
        # OPEN ACCESS INFORMATION
        # =================================================

        open_access = (
            paper_data.get(
                "open_access"
            )
            or {}
        )

        is_open_access = bool(
            open_access.get(
                "is_oa",
                False,
            )
        )

        open_access_status = (
            open_access.get(
                "oa_status"
            )
        )

        # =================================================
        # BEST FULL-TEXT LOCATION
        # =================================================
        #
        # Prefer best_oa_location.
        #
        # If OpenAlex does not provide one, fall back to
        # primary_location.
        # =================================================

        best_location = (
            paper_data.get(
                "best_oa_location"
            )
            or
            paper_data.get(
                "primary_location"
            )
            or {}
        )

        landing_page_url = (
            best_location.get(
                "landing_page_url"
            )
        )

        pdf_url = (
            best_location.get(
                "pdf_url"
            )
        )

        # =================================================
        # SOURCE / JOURNAL
        # =================================================

        source = (
            best_location.get(
                "source"
            )
            or {}
        )

        source_name = (
            source.get(
                "display_name"
            )
        )

        # =================================================
        # CREATE INTERNAL PAPER OBJECT
        # =================================================

        return Paper(
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            url=openalex_id,
            citation_count=citation_count,
            doi=doi,
            landing_page_url=landing_page_url,
            pdf_url=pdf_url,
            is_open_access=is_open_access,
            open_access_status=open_access_status,
            source_name=source_name,
        )

    # =====================================================
    # PARALLEL PAPER DISCOVERY
    # =====================================================

    def run(self, state):
        """
        Search papers for every sub-question generated
        by the Planner Agent.

        Searches run concurrently because the OpenAlex
        requests are independent network operations.
        """

        print(
            "\n========== "
            "RESEARCH V2 PAPER DISCOVERY "
            "==========\n"
        )

        unique_papers = {}

        # -------------------------------------------------
        # SAFETY CHECK
        # -------------------------------------------------

        sub_questions = getattr(
            state,
            "sub_questions",
            [],
        )

        if not sub_questions:

            print(
                "No research sub-questions "
                "were provided."
            )

            state.papers = []

            return

        # -------------------------------------------------
        # PARALLEL OPENALEX SEARCH
        # -------------------------------------------------

        with ThreadPoolExecutor(
            max_workers=5
        ) as executor:

            futures = {
                executor.submit(
                    self.search_papers,
                    question,
                ): question

                for question
                in sub_questions
            }

            for future in as_completed(
                futures
            ):

                question = futures[future]

                try:

                    papers = future.result()

                    print(
                        f"Finished: "
                        f"{question} "
                        f"({len(papers)} papers)"
                    )

                    # -------------------------------------
                    # DEDUPLICATION
                    # -------------------------------------
                    #
                    # The same scientific paper can appear
                    # for several sub-questions.
                    #
                    # OpenAlex ID is our preferred stable
                    # identifier.
                    # -------------------------------------

                    for paper in papers:

                        key = (
                            paper.url
                            or paper.doi
                            or paper.title.lower()
                        )

                        unique_papers[
                            key
                        ] = paper

                except Exception as exc:

                    print(
                        f"Error searching "
                        f"'{question}': "
                        f"{exc}"
                    )

        # -------------------------------------------------
        # SAVE RESULTS INTO RESEARCH STATE
        # -------------------------------------------------

        state.papers = list(
            unique_papers.values()
        )

        # =================================================
        # DISCOVERY STATISTICS
        # =================================================

        total = len(
            state.papers
        )

        open_access_count = sum(
            1
            for paper in state.papers
            if paper.is_open_access
        )

        direct_pdf_count = sum(
            1
            for paper in state.papers
            if paper.pdf_url
        )

        abstract_count = sum(
            1
            for paper in state.papers
            if paper.abstract
        )

        # =================================================
        # SUMMARY
        # =================================================

        print(
            "\n==================================="
        )

        print(
            "RESEARCH V2 DISCOVERY SUMMARY"
        )

        print(
            "==================================="
        )

        print(
            "Total Unique Papers:",
            total,
        )

        print(
            "Open Access:",
            open_access_count,
        )

        print(
            "Direct PDF URLs:",
            direct_pdf_count,
        )

        print(
            "Abstract Available:",
            abstract_count,
        )

        print(
            "===================================\n"
        )

        # =================================================
        # DEBUG PAPER METADATA
        # =================================================

        for index, paper in enumerate(
            state.papers,
            start=1,
        ):

            print(
                f"[{index}] "
                f"{paper.title}"
            )

            print(
                "    Year:",
                paper.year,
            )

            print(
                "    Citations:",
                paper.citation_count,
            )

            print(
                "    OA:",
                paper.is_open_access,
            )

            print(
                "    OA status:",
                paper.open_access_status,
            )

            print(
                "    Source:",
                paper.source_name,
            )

            print(
                "    DOI:",
                paper.doi,
            )

            print(
                "    PDF:",
                (
                    paper.pdf_url
                    if paper.pdf_url
                    else "Not directly available"
                ),
            )

            print()

    # =====================================================
    # ABSTRACT RECONSTRUCTION
    # =====================================================

    def reconstruct_abstract(
        self,
        inverted_index,
    ):
        """
        Reconstruct normal abstract text from the
        OpenAlex abstract inverted index.
        """

        if not inverted_index:
            return ""

        words = []

        for word, positions in (
            inverted_index.items()
        ):

            for position in positions:

                words.append(
                    (
                        position,
                        word,
                    )
                )

        # Restore original word order.
        words.sort(
            key=lambda item: item[0]
        )

        return " ".join(
            word
            for _, word in words
        )