import json

from app.models.evidence import Evidence

class EvidenceExtractionAgent:
    def __init__(self,llm):
        self.llm=llm

    def run(self,state):
        for paper in state.papers:
            prompt = f"""
                            You are an expert scientific research assistant.

                            Read the following research paper.

                            Title:
                            {paper.title}

                            Abstract:
                            {paper.abstract}

                            Extract:

                            1. Key findings
                            2. Methods used
                            3. Limitations
                            4. Relevance to the user's research question

                            Return ONLY valid JSON.

                            Do not include markdown.
                            Do not include explanations.
                            Do not include any text before or after the JSON.

                            Use this format:

                            {{
                                "findings": [],
                                "methods": "",
                                "limitations": "",
                                "relevance": ""
                            }}
                            """
            response=self.llm.generate(prompt)

            try:
                data=json.loads(response)

                evidence=Evidence(
                    paper_title=paper.title,
                    findings=data.get("findings",[]),
                    methods=data.get("methods", ""),
                    limitations=data.get("limitations", ""),
                    relevance=data.get("relevance", "")
                )
                state.evidence.append(evidence)

                print("=" * 70)
                print("Paper:", paper.title)
                print("Evidence Extracted Successfully")
                print("Findings:", evidence.findings)
                print("Methods:", evidence.methods)
                print("Limitations:", evidence.limitations)
                print("Relevance:", evidence.relevance)

            except json.JSONDecodeError:
                print("=" * 70)
                print(f"Failed to parse JSON for paper: {paper.title}")
                print("Raw Response:")
                print(response)

        print("\nTotal Evidence Objects:", len(state.evidence))
        