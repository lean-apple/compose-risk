import json
import shutil
from pathlib import Path

import pytest

from compose_risk.case import CaseError, check_pair, find_case_dirs, find_version_dirs, load_case


def test_every_case_loads(version_dir: Path) -> None:
    load_case(version_dir)


def test_id_must_match_folder(version_dir: Path, tmp_path: Path) -> None:
    copy = tmp_path / "other-name" / version_dir.name
    shutil.copytree(version_dir, copy)
    with pytest.raises(CaseError, match="expected the case folder name"):
        load_case(copy)


def test_named_files_must_exist(version_dir: Path, tmp_path: Path) -> None:
    copy = tmp_path / version_dir.parent.name / version_dir.name
    shutil.copytree(version_dir, copy)
    data = json.loads((copy / "case.json").read_text())
    data["exploit_check"] = "exploit/Missing.t.sol"
    (copy / "case.json").write_text(json.dumps(data))
    with pytest.raises(CaseError, match="does not exist"):
        load_case(copy)


def test_finds_every_version(tmp_path: Path) -> None:
    for version in ("solidity/a/vulnerable", "solidity/a/fixed", "solidity/b/vulnerable"):
        (tmp_path / version).mkdir(parents=True)
    (tmp_path / "solidity" / "not-a-case").mkdir()
    found = [str(d.relative_to(tmp_path)) for d in find_version_dirs(tmp_path)]
    assert found == ["solidity/a/vulnerable", "solidity/a/fixed", "solidity/b/vulnerable"]


@pytest.fixture(params=find_case_dirs(), ids=lambda d: d.name)
def case_dir(request: pytest.FixtureRequest) -> Path:
    path: Path = request.param
    return path


def test_every_case_is_a_controlled_pair(case_dir: Path) -> None:
    check_pair(case_dir)


def _copy(case_dir: Path, tmp_path: Path) -> Path:
    copy = tmp_path / case_dir.name
    shutil.copytree(case_dir, copy)
    return copy


def test_pair_rejects_a_second_changed_contract(case_dir: Path, tmp_path: Path) -> None:
    copy = _copy(case_dir, tmp_path)
    contract = next((copy / "fixed" / "layers").rglob("*.sol"))
    contract.write_text(contract.read_text() + "\n// drift\n")
    with pytest.raises(CaseError, match="expected only"):
        check_pair(copy)


def test_pair_rejects_different_threat_models(case_dir: Path, tmp_path: Path) -> None:
    copy = _copy(case_dir, tmp_path)
    path = copy / "fixed" / "case.json"
    data = json.loads(path.read_text())
    data["threat_model"]["property"] += " Changed."
    path.write_text(json.dumps(data))
    with pytest.raises(CaseError, match="threat models differ"):
        check_pair(copy)


def test_pair_rejects_a_missing_version(case_dir: Path, tmp_path: Path) -> None:
    copy = _copy(case_dir, tmp_path)
    shutil.rmtree(copy / "vulnerable")
    with pytest.raises(CaseError, match="missing vulnerable/"):
        check_pair(copy)


def test_invalid_case_json_is_a_case_error(version_dir: Path, tmp_path: Path) -> None:
    copy = tmp_path / version_dir.parent.name / version_dir.name
    shutil.copytree(version_dir, copy)
    (copy / "case.json").write_text('{"variant": "fixed"}')
    with pytest.raises(CaseError, match="case.json"):
        load_case(copy)
    (copy / "case.json").unlink()
    with pytest.raises(CaseError, match="case.json"):
        load_case(copy)
