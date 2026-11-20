import json
import shutil
from pathlib import Path

import pytest

from compose_risk.case import CaseError, find_version_dirs, load_case


def test_every_case_loads(version_dir: Path):
    load_case(version_dir)


def test_id_must_match_folder(version_dir: Path, tmp_path: Path):
    copy = tmp_path / "other-name" / version_dir.name
    shutil.copytree(version_dir, copy)
    with pytest.raises(CaseError, match="expected the case folder name"):
        load_case(copy)


def test_named_files_must_exist(version_dir: Path, tmp_path: Path):
    copy = tmp_path / version_dir.parent.name / version_dir.name
    shutil.copytree(version_dir, copy)
    data = json.loads((copy / "case.json").read_text())
    data["exploit_check"] = "exploit/Missing.t.sol"
    (copy / "case.json").write_text(json.dumps(data))
    with pytest.raises(CaseError, match="does not exist"):
        load_case(copy)


def test_finds_every_version(tmp_path: Path):
    for version in ("solidity/a/vulnerable", "solidity/a/fixed", "solidity/b/vulnerable"):
        (tmp_path / version).mkdir(parents=True)
    (tmp_path / "solidity" / "not-a-case").mkdir()
    found = [str(d.relative_to(tmp_path)) for d in find_version_dirs(tmp_path)]
    assert found == ["solidity/a/vulnerable", "solidity/a/fixed", "solidity/b/vulnerable"]
