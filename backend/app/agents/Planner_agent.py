





class planner_agent:
    def __init__(self,llm):
        self.llm=llm



    def run(self,state):
        prompt = f"""
        You are ORION's Planner Agent.

        Break the following scientific research question into 5 focused research sub-questions.

        Research Question:
        {state.question}

        Return only a numbered list.
        """
        response=self.llm.generate(prompt)
        sub_questions=[]
        
        for line in response.split('\n'):
            line=line.strip()

            if line:
                if line[0].isdigit():
                    question=line.split(".",1)[1].strip()
                    sub_questions.append(question)


        state.sub_questions=sub_questions
        