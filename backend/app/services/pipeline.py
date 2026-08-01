from app.services.llm_service import llm

from app.agents.Planner_agent import planner_agent
from app.agents.research_agent import ResearchAgent
from app.agents.evidence_extraction_agent import EvidenceExtractionAgent
from app.agents.critic_agent import CriticAgent
from app.agents.synthesis_agent import SynthesisAgent
from app.agents.hypothesis_agent import HypothesisAgent
from app.agents.hypothesis_critic_agent import HypothesisCriticAgent
from app.agents.experiment_agent import ExperimentAgent
from app.agents.finalReport_agent import FinalReportAgent

from app.models.research_state import ResearchState


def run_pipeline(question: str, job_id=None, job_manager=None):

    

    planner = planner_agent(llm)
    research_agent = ResearchAgent()
    evidence_agent = EvidenceExtractionAgent(llm)
    critic_agent = CriticAgent(llm)
    synthesis_agent = SynthesisAgent(llm)
    hypothesis_agent = HypothesisAgent(llm)
    hypothesis_critic_agent = HypothesisCriticAgent(llm)
    experiment_agent = ExperimentAgent(llm)
    final_report_agent = FinalReportAgent(llm)

    state = ResearchState(question)

    print("\nPIPELINE CREATED")
    print("Question:", state.question)
    print("State ID:", id(state))

    def update(step: str, progress: int):
        if job_manager is not None and job_id is not None:
            job_manager.update_progress(job_id, step, progress)

  
    # Planning
   

    update("Planning Research", 5)
    planner.run(state)

   
    # Literature Search
    

    update("Searching Scientific Papers", 15)
    research_agent.run(state)

  
    # Evidence Extraction
    

    update("Extracting Evidence", 35)
    evidence_agent.run(state)

  
    # Critic Analysis
   
    update("Analyzing Evidence", 50)
    critic_agent.run(state)

    
    # Scientific Synthesis
  

    update("Generating Scientific Synthesis", 65)
    synthesis_agent.run(state)

  
    # Hypothesis Generation
    

    MAX_REVISIONS = 3
    accepted = False

    for attempt in range(MAX_REVISIONS):

        update(f"Generating Hypothesis (Attempt {attempt + 1})", 75)

        print(f"\n========== HYPOTHESIS ATTEMPT {attempt + 1} ==========")

        hypothesis_agent.run(state)

        if state.hypothesis is None:
            print("Hypothesis generation failed.")
            break

        update("Reviewing Hypothesis", 85)

        hypothesis_critic_agent.run(state)

        if state.hypothesis_review is None:
            print("Hypothesis review failed.")
            break

        recommendation = (
            state.hypothesis_review.recommendation
            .strip()
            .lower()
        )

        if recommendation == "accept":
            print("\nHypothesis Accepted.")
            accepted = True
            break

        elif recommendation == "reject":
            print("\nHypothesis Rejected.")
            break

        elif recommendation == "revise":
            print("\nReviewer requested revision...")

        else:
            print(f"\nUnknown recommendation: {recommendation}")
            break

    
    # Experiment Design
    

    if accepted:

        update("Designing Experiments", 92)
        experiment_agent.run(state)

    
        # Final Report
        

        update("Writing Final Report", 97)
        final_report_agent.run(state)

    else:
        print("\nSkipping Experiment Generation.")

    
    # Finished
    

    update("Research Complete", 100)

    return state