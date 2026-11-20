from pathlib import Path

import pytest

from compose_risk.case import find_version_dirs


@pytest.fixture(params=find_version_dirs(), ids=lambda d: f"{d.parent.name}/{d.name}")
def version_dir(request: pytest.FixtureRequest) -> Path:
    return request.param
