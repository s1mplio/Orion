from dataclasses import  dataclass

@dataclass
class HypothesisReview:
    strengths:list[str]
    weaknesses:list[str]
    supported_by_evidence:bool
    confidence:str
    recommendation:str