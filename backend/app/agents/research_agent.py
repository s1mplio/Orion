from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from dotenv import load_dotenv

from app.models.paper import Paper

load_dotenv()


class ResearchAgent:

    def __init__(self):
        self.base_url = "https://api.openalex.org/works"

    def search_papers(self, query):

        query = query.replace("?", "")

        params = {
            "search": query,
            "per-page": 5
        }

        response = requests.get(
            self.base_url,
            params=params,
            timeout=20
        )

        if response.status_code != 200:
            print(f"Search failed for: {query}")
            return []

        data = response.json()

        paper_objects = []

        for paper_data in data.get("results", []):

            title = paper_data.get("display_name", "")

            year = paper_data.get("publication_year")

            citation_count = paper_data.get("cited_by_count", 0)

            url = paper_data.get("id", "")

            authors = []

            for author in paper_data.get("authorships", []):
                authors.append(
                    author["author"]["display_name"]
                )

            abstract = self.reconstruct_abstract(
                paper_data.get("abstract_inverted_index")
            )

            paper_objects.append(

                Paper(
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    year=year,
                    url=url,
                    citation_count=citation_count
                )

            )

        return paper_objects

    def run(self, state):

        print("\n========== PARALLEL PAPER SEARCH ==========\n")

        unique_papers = {}

        with ThreadPoolExecutor(max_workers=5) as executor:

            futures = {

                executor.submit(
                    self.search_papers,
                    question
                ): question

                for question in state.sub_questions

            }

            for future in as_completed(futures):

                question = futures[future]

                try:

                    papers = future.result()

                    print(
                        f"Finished: {question} ({len(papers)} papers)"
                    )

                    for paper in papers:

                        unique_papers[paper.url] = paper

                except Exception as e:

                    print(
                        f"Error searching '{question}': {e}"
                    )

        state.papers = list(unique_papers.values())

        print("\n===================================")
        print(f"Total Unique Papers: {len(state.papers)}")
        print("===================================\n")

    def reconstruct_abstract(self, inverted_index):

        if not inverted_index:
            return ""

        words = []

        for word, positions in inverted_index.items():

            for position in positions:

                words.append((position, word))

        words.sort()

        return " ".join(word for position, word in words)