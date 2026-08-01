from dataclasses import field,dataclass

@dataclass
class Hypothesis:
    hypothesis:str
    reasoning:str
    assumptions:list[str]=field(default_factory=list)