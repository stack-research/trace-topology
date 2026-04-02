from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum


class BondType(StrEnum):
    COVALENT = "covalent"
    HYDROGEN = "hydrogen"
    VANDERWAALS = "vanderwaals"


class FindingType(StrEnum):
    CYCLE = "cycle"
    DANGLING = "dangling"
    UNSUPPORTED_TERMINAL = "unsupported_terminal"
    CONTRADICTION = "contradiction"
    ENTROPY_DIVERGENCE = "entropy_divergence"
    BOND_IMBALANCE = "bond_imbalance"


@dataclass(slots=True)
class Step:
    id: str
    text: str
    start_char: int
    end_char: int
    step_type: str = "claim"
    summary: str = ""


@dataclass(slots=True)
class Bond:
    source: str
    target: str
    type: BondType
    confidence: float = 0.5
    reason: str = ""


@dataclass(slots=True)
class TraceGraph:
    transcript_id: str
    steps: list[Step] = field(default_factory=list)
    bonds: list[Bond] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "transcript_id": self.transcript_id,
            "steps": [asdict(step) for step in self.steps],
            "bonds": [
                {
                    "source": b.source,
                    "target": b.target,
                    "type": b.type.value,
                    "confidence": b.confidence,
                    "reason": b.reason,
                }
                for b in self.bonds
            ],
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class Finding:
    type: FindingType
    steps_involved: list[str]
    description: str
    severity: str = "moderate"
    score: float = 0.5

    def to_dict(self) -> dict:
        data = asdict(self)
        data["type"] = self.type.value
        return data


@dataclass(slots=True)
class AnalysisReport:
    graph: TraceGraph
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "graph": self.graph.to_dict(),
            "findings": [finding.to_dict() for finding in self.findings],
            "stats": self.stats,
        }
