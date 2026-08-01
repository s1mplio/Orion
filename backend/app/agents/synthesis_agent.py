import json
from app.models.synthesis import Synthesis

class SynthesisAgent:
    def __init__(self,llm):
        self.llm=llm
    
    def run(self,state):
                prompt = f"""
                You are an expert scientific writer.

                Research Question:
                {state.question}

                Below is the final scientific review generated after analyzing multiple research papers.

                Agreements:
                {state.critic_results.agreements}

                Contradictions:
                {state.critic_results.contradictions}

                Research Gaps:
                {state.critic_results.research_gaps}

                Confidence:
                {state.critic_results.confidence}

                Using ONLY the information above, write a scientific synthesis.

                Return ONLY valid JSON.

                {{
                    "summary": "",
                    "key_findings": [],
                    "limitations": [],
                    "future_work": []
                }}
                """
                response=self.llm.generate(prompt)
                try:
                    data=json.loads(response)
                except json.JSONDecodeError:
                      print("INVALID SYNTHESIS")
                      print(response)
                      return
                
                synthesis=Synthesis(
                      summary=data.get("summary", ""),
                      key_findings=data.get("key_findings", []),
                      limitations=data.get("limitations", []),
                      future_work=data.get("future_work", [])

                )
                state.synthesis=synthesis
                print("\n========== SYNTHESIS ==========")

                print("\nSummary:")
                print(state.synthesis.summary)

                print("\nKey Findings:")
                for finding in state.synthesis.key_findings:
                    print("-", finding)

                print("\nLimitations:")
                for limitation in state.synthesis.limitations:
                    print("-", limitation)

                print("\nFuture Work:")
                for work in state.synthesis.future_work:
                    print("-", work)