from pathlib import Path

import pytest

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"
VERSION_DIRS = sorted(d for d in CASES_DIR.glob("*/*/*") if (d / "case.json").is_file())


@pytest.fixture(params=VERSION_DIRS, ids=lambda d: f"{d.parent.name}/{d.name}")
def version_dir(request: pytest.FixtureRequest) -> Path:
    return request.param
