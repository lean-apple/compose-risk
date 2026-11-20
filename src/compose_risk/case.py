"""Schema of `case.json`, the expected answer for one version of a case."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

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


class CaseError(Exception):
    pass


def load_case(version_dir: Path) -> Case:
    """Reads `<case>/<variant>/case.json`, validates it, and checks that every file it names exists."""
    case = _CASE.validate_json((version_dir / "case.json").read_bytes())
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
