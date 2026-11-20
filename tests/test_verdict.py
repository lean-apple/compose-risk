from pathlib import Path

from compose_risk.case import VulnerableCase, find_version_dirs, load_case
from compose_risk.verdict import ReviewVerdict, score

CASES = [load_case(d) for d in find_version_dirs()]


def _verdict(verdict: str, layer: str = "") -> ReviewVerdict:
    return ReviewVerdict(verdict=verdict, root_cause_layer=layer, propagation_path=[], explanation="")


def _root_layer(case) -> str:
    return case.root_cause.layer if isinstance(case, VulnerableCase) else ""


def test_expected_answer_scores_correct(version_dir: Path):
    case = load_case(version_dir)
    scores = score(_verdict(case.expected_verdict, _root_layer(case)), case)
    assert scores.verdict_correct and scores.root_cause_layer_correct is not False


def test_wrong_layer_is_not_credited():
    case = next(c for c in CASES if isinstance(c, VulnerableCase))
    scores = score(_verdict("exploitable", "0-target"), case)
    assert scores.verdict_correct and scores.root_cause_layer_correct is False


def test_constant_reviewers_do_not_score_perfectly():
    for constant in ("exploitable", "not_exploitable"):
        assert not all(score(_verdict(constant, _root_layer(c)), c).verdict_correct for c in CASES)
