import json
import shutil
from pathlib import Path

import pytest

from compose_risk.case import CaseError, load_case


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
