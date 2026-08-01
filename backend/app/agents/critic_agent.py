import json

from app.models.critic_results import CriticResult


class CriticAgent:
    def __init__(self,llm):
        self.llm=llm
    
    def run(self,state):
        batch_size=5

        batch_results=[]

        for i in range(0,len(state.evidence),batch_size):
            batch=state.evidence[i:i+batch_size]

            evidence_text=""
            
            for evidence in batch:
                evidence_text+=f"""
                             Paper:
                            {evidence.paper_title}

                            Findings:
                            {evidence.findings}

                            Methods:
                            {evidence.methods}

                            Limitations:
                            {evidence.limitations}

                            Relevance:
                            {evidence.relevance}

                            ------------------------
                            """ 
            prompt = f"""
            You are an expert scientific reviewer.

            Below is evidence extracted from multiple research papers.

            {evidence_text}

                    Analyze the evidence across all papers.

                    Compare the findings.

                    Identify:

                    1. Agreements supported by multiple papers.
                    2. Contradictions between papers.
                    3. Important research gaps.
                    4. Overall confidence in the current evidence.

                    If no contradictions exist, return an empty list.

                    Return ONLY valid JSON.

            {{
                "agreements": [],
                "contradictions": [],
                "research_gaps": [],
                "confidence": ""
            }}
            """ 
            response=self.llm.generate(prompt)
            try:
                data=json.loads(response)
            except json.JSONDecodeError:
                print("INVALID JSON CRITCIC RESPONSE")
                print(response)
                continue

 
            critic=CriticResult(
                agreements=data.get("agreements", []),
                contradictions=data.get("contradictions", []),
                research_gaps=data.get("research_gaps", []),
                confidence=data.get("confidence", "")
            )
            batch_results.append(critic)
        
        if not batch_results:
          print("No valid batch results generated.")
          return
        summary_text=""
        for result in batch_results:
                summary_text += f"""
                                Agreements:
                                {result.agreements}

                                Contradictions:
                                {result.contradictions}

                                Research Gaps:
                                {result.research_gaps}

                                Confidence:
                                {result.confidence}

                                ------------------------
                                """
        final_prompt = f"""
                        You are an expert scientific reviewer.

                        Below are summaries from multiple batches of research papers.

                        {summary_text}

                        Combine all of these summaries into ONE final scientific review.

                        Identify:

                        1. Agreements
                        2. Contradictions
                        3. Research gaps
                        4. Overall confidence

                        Return ONLY valid JSON.

                        {{
                            "agreements": [],
                            "contradictions": [],
                            "research_gaps": [],
                            "confidence": ""
                        }}
                        """
        print("Number of batch results:", len(batch_results))
        print("Final prompt length:", len(final_prompt))
        response=self.llm.generate(final_prompt)
        try:
             data=json.loads(response)
        except json.JSONDecodeError:
             print("INVALID CRITIC RESPONSE")
             print(response)
             return 
        final_critic = CriticResult(
             agreements=data.get("agreements", []),
             contradictions=data.get("contradictions", []),
             research_gaps=data.get("research_gaps", []),
             confidence=data.get("confidence", "")
            )
             

        state.critic_results = final_critic
        print("\n========== FINAL CRITIC ==========")

        print("Agreements:")
        for item in state.critic_results.agreements:
            print("-", item)

        print("\nContradictions:")
        for item in state.critic_results.contradictions:
            print("-", item)

        print("\nResearch Gaps:")
        for item in state.critic_results.research_gaps:
            print("-", item)

        print("\nConfidence:")
        print(state.critic_results.confidence)