from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionOutcome(str, Enum):
    PROCEED = "proceed"
    CHALLENGE = "challenge"
    CONFIRM_RESIDENT = "confirm_resident"
    DENY = "deny"


@dataclass
class NoulAnswer:
    probability: float
    confidence: float
    raw_answer: bool

    def is_positive(self, threshold: float = 0.5) -> bool:
        return self.probability >= threshold


@dataclass
class ChoiceAnswer:
    choice: str
    confidence: float
    probabilities: Dict[str, float] = field(default_factory=dict)


@dataclass
class ScoreAnswer:
    score: float
    confidence: float


@dataclass
class GuardrailEvaluation:
    action: ActionOutcome
    reason: str
    latency_ms: float
    model_name: str
    injection_risk: NoulAnswer
    policy_category: ChoiceAnswer
    actuator_grounding: NoulAnswer
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "reason": self.reason,
            "latency_ms": round(self.latency_ms, 2),
            "model_name": self.model_name,
            "injection_risk": {
                "probability": round(self.injection_risk.probability, 3),
                "confidence": round(self.injection_risk.confidence, 3),
                "flagged": self.injection_risk.is_positive(0.65),
            },
            "policy_category": {
                "choice": self.policy_category.choice,
                "confidence": round(self.policy_category.confidence, 3),
                "probabilities": {k: round(v, 3) for k, v in self.policy_category.probabilities.items()},
            },
            "actuator_grounding": {
                "probability": round(self.actuator_grounding.probability, 3),
                "confidence": round(self.actuator_grounding.confidence, 3),
                "grounded": self.actuator_grounding.is_positive(0.60),
            },
            "metadata": self.metadata,
        }
