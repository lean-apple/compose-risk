from pathlib import Path

from compose_risk.case import VulnerableCase, check_pair, load_case
from compose_risk.prepare import read_layers
from compose_risk.prompt import review_input

KELPDAO = Path(__file__).resolve().parent.parent / "cases" / "solidity" / "2026-04-18-kelpdao-aave"


def test_input_holds_every_layer_without_comments(version_dir: Path) -> None:
    case = load_case(version_dir)
    text = review_input(case.threat_model, read_layers(version_dir))
    for path in (version_dir / "layers").rglob("*.sol"):
        assert f'<file path="layers/{path.relative_to(version_dir / "layers").as_posix()}">' in text
    assert "//" not in text and "/*" not in text
    assert case.threat_model.property in text


def test_input_does_not_leak_the_answer(version_dir: Path) -> None:
    case = load_case(version_dir)
    text = review_input(case.threat_model, read_layers(version_dir))
    assert case.expected_reviewer_finding not in text
    if isinstance(case, VulnerableCase):
        assert case.root_cause.detail not in text


def test_versions_differ_only_in_code() -> None:
    vulnerable, fixed = check_pair(KELPDAO)
    before = review_input(vulnerable.threat_model, read_layers(KELPDAO / "vulnerable"))
    after = review_input(fixed.threat_model, read_layers(KELPDAO / "fixed"))
    changed = [a for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b]
    assert changed and all("VERIFIER" in line or "CONFIRMATIONS" in line for line in changed)
