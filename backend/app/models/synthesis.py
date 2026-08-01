from dataclasses import dataclass, field

@dataclass
class Synthesis:
    summary:str
    key_findings:list[str]=field(default_factory=list)
    limitations:list[str]=field(default_factory=list)
    future_work:list[str]=field(default_factory=list)
