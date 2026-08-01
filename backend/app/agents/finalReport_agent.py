import json

from app.models.final_report import FinalReport


class FinalReportAgent:

    def __init__(self, llm):
        self.llm = llm

    def run(self, state):

        prompt = f"""
You are an expert scientific researcher.

Prepare a professional scientific research report.

Research Question:
{state.question}

Scientific Synthesis

Summary:
{state.synthesis.summary}

Key Findings:
{state.synthesis.key_findings}

Limitations:
{state.synthesis.limitations}

Future Work:
{state.synthesis.future_work}

Hypothesis

Hypothesis:
{state.hypothesis.hypothesis}

Reasoning:
{state.hypothesis.reasoning}

Assumptions:
{state.hypothesis.assumptions}

Hypothesis Review

Strengths:
{state.hypothesis_review.strengths}

Weaknesses:
{state.hypothesis_review.weaknesses}

Confidence:
{state.hypothesis_review.confidence}

Experiment

Title:
{state.experiment.title}

Objective:
{state.experiment.objective}

Methodology:
{state.experiment.methodology}

Required Data:
{state.experiment.required_data}

Expected Outcomes:
{state.experiment.expected_outcomes}

Evaluation Metrics:
{state.experiment.evaluation_metrics}

Experiment Limitations:
{state.experiment.limitations}

Generate a complete scientific report.

Return ONLY valid JSON.

{{
    "title": "",
    "executive_summary": "",
    "background": "",
    "evidence_summary": "",
    "hypothesis": "",
    "experiment_plan": "",
    "conclusion": "",
    "future_work": ""
}}
"""

        print("\n[Final Report] Generating report...")

        response = self.llm.generate(prompt)

        try:
            data = json.loads(response)

        except json.JSONDecodeError:
            print("INVALID FINAL REPORT")
            print(response)
            return

        report = FinalReport(
            title=data.get("title", ""),
            executive_summary=data.get("executive_summary", ""),
            background=data.get("background", ""),
            evidence_summary=data.get("evidence_summary", ""),
            hypothesis=data.get("hypothesis", ""),
            experiment_plan=data.get("experiment_plan", ""),
            conclusion=data.get("conclusion", ""),
            future_work=data.get("future_work", "")
        )

        state.final_report = report

        print("[Final Report] Completed.")

        print("\n========== FINAL REPORT ==========")

        print("\nTitle:")
        print(report.title)

        print("\nExecutive Summary:")
        print(report.executive_summary)

        print("\nBackground:")
        print(report.background)

        print("\nEvidence Summary:")
        print(report.evidence_summary)

        print("\nHypothesis:")
        print(report.hypothesis)

        print("\nExperiment Plan:")
        print(report.experiment_plan)

        print("\nConclusion:")
        print(report.conclusion)

        print("\nFuture Work:")
        print(report.future_work)