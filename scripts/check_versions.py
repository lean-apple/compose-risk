"""Checks that each case's two versions form a controlled pair.

For every case under `cases/<ecosystem>/<case>/`, `vulnerable/` and `fixed/` must name the same case,
expect `exploitable` and `not_exploitable`, share the same threat model, and hold the same contract
files, identical except the one `fixed/case.json` declares in `difference`. A reviewer that judges the
two versions differently is then reacting to that file.
"""

import json
import sys
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent.parent / "cases"


class VersionMismatch(Exception):
    pass


def _contracts(version_dir: Path) -> dict[Path, bytes]:
    layers = version_dir / "layers"
    return {p.relative_to(layers): p.read_bytes() for p in sorted(layers.rglob("*.sol"))}


def check_case(case_dir: Path) -> None:
    """Raises `VersionMismatch` if `case_dir`'s versions are not a controlled pair."""
    vulnerable = json.loads((case_dir / "vulnerable" / "case.json").read_text())
    fixed = json.loads((case_dir / "fixed" / "case.json").read_text())
    name = case_dir.name

    if vulnerable["id"] != name or fixed["id"] != name:
        raise VersionMismatch(f"{name}: case ids must both be {name!r}")
    if (vulnerable["variant"], fixed["variant"]) != ("vulnerable", "fixed"):
        raise VersionMismatch(f"{name}: variants must be 'vulnerable' and 'fixed'")
    if (vulnerable["expected_verdict"], fixed["expected_verdict"]) != ("exploitable", "not_exploitable"):
        raise VersionMismatch(f"{name}: verdicts must be 'exploitable' and 'not_exploitable'")
    if vulnerable["threat_model"] != fixed["threat_model"]:
        raise VersionMismatch(f"{name}: the versions' threat models differ")

    before, after = _contracts(case_dir / "vulnerable"), _contracts(case_dir / "fixed")
    if before.keys() != after.keys():
        only = sorted(str(p) for p in before.keys() ^ after.keys())
        raise VersionMismatch(f"{name}: contract files differ between versions: {', '.join(only)}")
    declared = Path(fixed["difference"]["layer"]) / fixed["difference"]["file"]
    changed = sorted(p for p in before if before[p] != after[p])
    if changed != [declared]:
        found = ", ".join(str(p) for p in changed) or "no difference"
        raise VersionMismatch(f"{name}: expected only {declared} to differ, found {found}")


def main() -> int:
    case_dirs = sorted(d for d in CASES_DIR.glob("*/*") if (d / "vulnerable").is_dir())
    failures = []
    for case_dir in case_dirs:
        try:
            check_case(case_dir)
        except VersionMismatch as e:
            failures.append(str(e))
    for failure in failures:
        print(failure, file=sys.stderr)
    print(f"checked {len(case_dirs)} case(s), {len(failures)} mismatch(es)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
