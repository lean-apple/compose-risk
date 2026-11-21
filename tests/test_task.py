import math
from pathlib import Path

import pytest
from inspect_ai import eval
from inspect_ai.model import ModelOutput, get_model

from compose_risk.task import compose_risk
from compose_risk.verdict import ReviewVerdict

EXPLOITABLE = ReviewVerdict(
    verdict="exploitable",
    root_cause_layer="2-upstream",
    propagation_path=["MessageEndpoint", "BridgedRestakeToken", "LendingPool"],
    explanation="mock reviewer",
).model_dump_json()


def _accuracy(reply: str, log_dir: Path, stop_reason: str = "stop") -> dict[str, float]:
    """Runs the KelpDAO pair against a mock model that always gives `reply`, and returns accuracy per score."""
    output = ModelOutput.from_content("mockllm", reply, stop_reason=stop_reason)  # type: ignore[arg-type]
    model = get_model("mockllm/model", custom_outputs=lambda *_: output)
    [log] = eval(compose_risk(cases="2026-04-18-kelpdao-aave"), model=model, log_dir=str(log_dir), display="none")
    assert log.status == "success" and log.results is not None, log.error
    assert {s.id for s in log.samples or []} == {"2026-04-18-kelpdao-aave/vulnerable", "2026-04-18-kelpdao-aave/fixed"}
    return {s.name: s.metrics["accuracy"].value for s in log.results.scores}


def test_a_constant_exploitable_verdict_gets_half_right(tmp_path: Path) -> None:
    accuracy = _accuracy(EXPLOITABLE, tmp_path)
    assert accuracy == {"verdict_correct": 0.5, "root_cause_layer_correct": 1.0, "refused": 0.0}


def test_an_unparseable_reply_is_wrong(tmp_path: Path) -> None:
    accuracy = _accuracy("not a verdict", tmp_path)
    assert accuracy == {"verdict_correct": 0.0, "root_cause_layer_correct": 0.0, "refused": 0.0}


def test_a_refusal_is_counted_apart(tmp_path: Path) -> None:
    accuracy = _accuracy("", tmp_path, stop_reason="content_filter")
    assert accuracy["refused"] == 1.0
    assert math.isnan(accuracy["verdict_correct"]) and math.isnan(accuracy["root_cause_layer_correct"])


def test_unknown_cases_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown case"):
        compose_risk(cases="no-such-case")


def test_cases_filter_takes_a_list_or_commas() -> None:
    ids = {"2026-04-18-kelpdao-aave/vulnerable", "2026-04-18-kelpdao-aave/fixed"}
    assert {str(s.id) for s in compose_risk(cases="2026-04-18-kelpdao-aave").dataset} == ids
    assert {str(s.id) for s in compose_risk(cases=["2026-04-18-kelpdao-aave"]).dataset} == ids
