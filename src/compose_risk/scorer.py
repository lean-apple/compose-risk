"""Inspect scorer: parses the reviewer's reply as a `ReviewVerdict` and scores it against the stored case.

A refusal counts in its own `refused` metric and stays out of the accuracy metrics, so a model is judged on
the answers it gives, with its refusal rate next to them.
"""

from inspect_ai.scorer import CORRECT, INCORRECT, Score, Scorer, Target, accuracy, scorer
from inspect_ai.solver import TaskState
from pydantic import ValidationError

from compose_risk.case import VulnerableCase, parse_case
from compose_risk.verdict import ReviewVerdict, score

# NaN leaves a sample out of a metric: a fixed version has no root cause to locate, and a refusal has no verdict.
NOT_APPLICABLE = float("nan")
REFUSED = "content_filter"


def _mark(correct: bool | None) -> str | float:
    if correct is None:
        return NOT_APPLICABLE
    return CORRECT if correct else INCORRECT


@scorer(metrics={"verdict_correct": [accuracy()], "root_cause_layer_correct": [accuracy()], "refused": [accuracy()]})
def verdict_scorer() -> Scorer:
    async def score_sample(state: TaskState, target: Target) -> Score:
        case = parse_case(state.metadata["expected"])
        if state.output.stop_reason == REFUSED:
            return Score(
                value={"verdict_correct": NOT_APPLICABLE, "root_cause_layer_correct": NOT_APPLICABLE, "refused": 1.0},
                answer="",
                explanation="the model refused to answer",
            )
        answer = state.output.completion
        try:
            verdict = ReviewVerdict.model_validate_json(answer)
        except ValidationError as e:
            layer = INCORRECT if isinstance(case, VulnerableCase) else NOT_APPLICABLE
            return Score(
                value={"verdict_correct": INCORRECT, "root_cause_layer_correct": layer, "refused": 0.0},
                answer=answer,
                explanation=f"the reply is not a valid verdict: {e}",
            )
        scores = score(verdict, case)
        return Score(
            value={
                "verdict_correct": _mark(scores.verdict_correct),
                "root_cause_layer_correct": _mark(scores.root_cause_layer_correct),
                "refused": 0.0,
            },
            answer=verdict.verdict,
            explanation=verdict.explanation,
            metadata={"verdict": verdict.model_dump()},
        )

    return score_sample
