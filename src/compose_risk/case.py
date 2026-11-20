"""Schema of `case.json`, the expected answer for one version of a case."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

CASES_DIR = Path(__file__).resolve().parents[2] / "cases"
VARIANTS = ("vulnerable", "fixed")

# Shared attacker vocabulary, so cases from different protocols state the same baseline the same way.
BASELINE_POWERS = {
    "permissionless": "Can call any public or external function, deploy contracts, and order its own transactions.",
}
CAPITAL = {
    "none": "Has no capital beyond gas.",
    "own_funds": "Can use its own funds but cannot borrow within a transaction.",
    "flash_loans": "Can borrow any amount within a single transaction through flash loans.",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LayerFile(_Strict):
    layer: str
    file: str
    detail: str


class LayerContract(_Strict):
    assumes: str | None = None
    guarantees: str | None = None


class Attacker(_Strict):
    """A shared baseline and capital level, plus what this case adds or forbids."""

    baseline: Literal["permissionless"]
    capital: Literal["none", "own_funds", "flash_loans"]
    extra_powers: list[str]
    limits: list[str]


class ThreatModel(_Strict):
    """The assumptions a verdict is judged under: "not exploitable" means against this attacker only."""

    attacker: Attacker
    trusted: list[str]
    honest_parties: list[str]
    environment: list[str]
    excluded: list[str]
    property: str


class VulnerableCase(_Strict):
    id: str
    variant: Literal["vulnerable"]
    expected_verdict: Literal["exploitable"]
    threat_model: ThreatModel
    incident_date: str
    propagation_type: Literal["composition"]
    vuln_type: str
    vuln_contract: str
    vuln_function: str
    root_cause: LayerFile
    assumptions_and_guarantees: dict[str, LayerContract]
    propagation_path: list[str]
    code_hops_from_root_cause: int
    exploit_check: str
    expected_reviewer_finding: str
    simplifications: list[str]


class FixedCase(_Strict):
    id: str
    variant: Literal["fixed"]
    expected_verdict: Literal["not_exploitable"]
    threat_model: ThreatModel
    difference: LayerFile
    exploit_check: str
    expected_reviewer_finding: str


Case = VulnerableCase | FixedCase

_CASE: TypeAdapter[Case] = TypeAdapter(Annotated[Case, Field(discriminator="variant")])


class CaseError(ValueError):
    """A case folder or its `case.json` is invalid; the message names the case."""


def find_case_dirs(root: Path = CASES_DIR) -> list[Path]:
    """Every case folder, `<root>/<ecosystem>/<case>/`, that holds at least one version."""
    return sorted(d for d in root.glob("*/*") if any((d / variant).is_dir() for variant in VARIANTS))


def find_version_dirs(root: Path = CASES_DIR) -> list[Path]:
    """Every version folder, `<root>/<ecosystem>/<case>/<variant>/`."""
    return [d / variant for d in find_case_dirs(root) for variant in VARIANTS if (d / variant).is_dir()]


def load_case(version_dir: Path) -> Case:
    """Reads `<case>/<variant>/case.json`, validates it, and checks that every file it names exists.

    Raises `CaseError` for every problem with the case, including a missing or invalid `case.json`.
    """
    path = version_dir / "case.json"
    try:
        case = _CASE.validate_json(path.read_bytes())
    except (OSError, ValidationError) as e:
        raise CaseError(f"{path}: {e}") from e
    name = version_dir.parent.name
    if case.id != name:
        raise CaseError(f"{name}: id is {case.id!r}, expected the case folder name")
    if case.variant != version_dir.name:
        raise CaseError(f"{name}: variant is {case.variant!r}, expected the version folder name")
    named = case.root_cause if isinstance(case, VulnerableCase) else case.difference
    for rel in (Path("layers") / named.layer / named.file, Path(case.exploit_check)):
        if not (version_dir / rel).is_file():
            raise CaseError(f"{name}/{case.variant}: {rel} does not exist")
    return case


def _contracts(version_dir: Path) -> dict[Path, bytes]:
    layers = version_dir / "layers"
    return {p.relative_to(layers): p.read_bytes() for p in sorted(layers.rglob("*.sol"))}


def check_pair(case_dir: Path) -> tuple[VulnerableCase, FixedCase]:
    """Checks that a case's two versions form a controlled pair, and returns them.

    Both versions must load, share the same threat model, and hold the same contract files, identical except
    the one `fixed/case.json` declares in `difference`. A reviewer that judges them differently is then
    reacting to that file.
    """
    name = case_dir.name
    missing = [variant for variant in VARIANTS if not (case_dir / variant).is_dir()]
    if missing:
        raise CaseError(f"{name}: missing {', '.join(missing)}/")
    vulnerable, fixed = load_case(case_dir / "vulnerable"), load_case(case_dir / "fixed")
    # `load_case` matched each variant to its folder name.
    assert isinstance(vulnerable, VulnerableCase) and isinstance(fixed, FixedCase)
    if vulnerable.threat_model != fixed.threat_model:
        raise CaseError(f"{name}: the versions' threat models differ")

    before, after = _contracts(case_dir / "vulnerable"), _contracts(case_dir / "fixed")
    if before.keys() != after.keys():
        only = sorted(str(p) for p in before.keys() ^ after.keys())
        raise CaseError(f"{name}: contract files differ between versions: {', '.join(only)}")
    declared = Path(fixed.difference.layer) / fixed.difference.file
    changed = sorted(p for p in before if before[p] != after[p])
    if changed != [declared]:
        found = ", ".join(str(p) for p in changed) or "no difference"
        raise CaseError(f"{name}: expected only {declared} to differ, found {found}")
    return vulnerable, fixed
