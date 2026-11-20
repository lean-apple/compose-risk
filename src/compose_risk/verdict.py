"""The reviewer's structured answer, and how it is scored against `case.json`."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict

from compose_risk.case import Case, FixedCase


class ReviewVerdict(BaseModel):
    """What a reviewer must return for one version of a case."""

    model_config = ConfigDict(extra="forbid")

    verdict: Literal["exploitable", "not_exploitable"]
    # A plain string, empty when not exploitable: the Anthropic API rejects the anyOf a nullable field produces.
    root_cause_layer: str
    propagation_path: list[str]
    explanation: str


@dataclass(frozen=True)
class Scores:
    verdict_correct: bool
    # None for a fixed version, which has no root cause to locate.
    root_cause_layer_correct: bool | None


def layer_name(answer: str) -> str:
    """The layer folder an answer names, so `" layers/2-upstream/EndpointConfig.sol"` reads as `2-upstream`."""
    return answer.strip().removeprefix("layers/").split("/")[0].strip()


def score(verdict: ReviewVerdict, case: Case) -> Scores:
    """A vulnerable version must be flagged with the right layer; a fixed version must be left alone."""
    verdict_correct = verdict.verdict == case.expected_verdict
    if isinstance(case, FixedCase):
        return Scores(verdict_correct=verdict_correct, root_cause_layer_correct=None)
    layer_correct = verdict_correct and layer_name(verdict.root_cause_layer) == case.root_cause.layer
    return Scores(verdict_correct=verdict_correct, root_cause_layer_correct=layer_correct)
