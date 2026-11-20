from pathlib import Path
from typing import Literal

import pytest

from compose_risk.case import Case, VulnerableCase, find_version_dirs, load_case
from compose_risk.verdict import ReviewVerdict, layer_name, score


@pytest.fixture(scope="module")
def cases() -> list[Case]:
    return [load_case(d) for d in find_version_dirs()]


def _verdict(verdict: Literal["exploitable", "not_exploitable"], layer: str = "") -> ReviewVerdict:
    return ReviewVerdict(verdict=verdict, root_cause_layer=layer, propagation_path=[], explanation="")


def _root_layer(case: Case) -> str:
    return case.root_cause.layer if isinstance(case, VulnerableCase) else ""


def test_expected_answer_scores_correct(version_dir: Path) -> None:
    case = load_case(version_dir)
    scores = score(_verdict(case.expected_verdict, _root_layer(case)), case)
    assert scores.verdict_correct and scores.root_cause_layer_correct is not False


def test_wrong_layer_is_not_credited(version_dir: Path) -> None:
    case = load_case(version_dir)
    if not isinstance(case, VulnerableCase):
        pytest.skip("a fixed version has no root cause")
    other = next(d.name for d in sorted((version_dir / "layers").iterdir()) if d.name != case.root_cause.layer)
    scores = score(_verdict("exploitable", other), case)
    assert scores.verdict_correct and scores.root_cause_layer_correct is False


def test_constant_reviewers_do_not_score_perfectly(cases: list[Case]) -> None:
    for constant in ("exploitable", "not_exploitable"):
        assert not all(score(_verdict(constant, _root_layer(c)), c).verdict_correct for c in cases)


@pytest.mark.parametrize(
    "answer", ["2-upstream", " 2-upstream ", "2-upstream/", "layers/2-upstream", "layers/2-upstream/EndpointConfig.sol"]
)
def test_layer_name_reads_the_folder(answer: str) -> None:
    assert layer_name(answer) == "2-upstream"
