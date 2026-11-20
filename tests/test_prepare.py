from pathlib import Path

import pytest

from compose_risk.prepare import ParseError, comment_count, prepare_version, strip_comments


def test_strips_line_and_block_comments():
    source = "contract A {\n    // note\n    uint x; /* inline */ uint y;\n}\n"
    assert strip_comments(source) == "contract A {\n\n    uint x;   uint y;\n}\n"


def test_keeps_comment_markers_inside_strings():
    source = 'contract A {\n    string s = "a // b /* c */";\n}\n'
    assert strip_comments(source) == source


def test_string_ending_in_escaped_backslash():
    source = 'contract A {\n    string s = "\\\\"; // gone\n}\n'
    assert strip_comments(source) == 'contract A {\n    string s = "\\\\";\n}\n'


def test_line_comment_ending_in_backslash_does_not_swallow_code():
    source = "contract A {\n    // ends with \\\n    uint x;\n}\n"
    assert "uint x;" in strip_comments(source)


def test_prepared_versions_have_no_comments(version_dir: Path, tmp_path: Path):
    out = prepare_version(version_dir, tmp_path / "out")
    files = sorted((out / "layers").rglob("*.sol"))
    assert files, "no layer contracts were prepared"
    assert all(comment_count(f.read_text()) == 0 for f in files)
    assert not (out / "case.json").exists() and not (out / "exploit").exists()


@pytest.mark.parametrize("relation", ["equal", "ancestor", "inside"])
@pytest.mark.parametrize("alias", ["none", "source", "output"])
def test_rejects_output_overlapping_source(tmp_path: Path, relation: str, alias: str) -> None:
    version = tmp_path / "case" / "version"
    source = version / "layers" / "A.sol"
    source.parent.mkdir(parents=True)
    source.write_text("contract A {}\n")
    answer = version / "case.json"
    answer.write_text('{"answer": "preserve me"}')
    out = {"equal": version, "ancestor": version.parent, "inside": version / "layers"}[relation]
    link = tmp_path / "alias"
    if alias == "source":
        link.symlink_to(version, target_is_directory=True)
        version = link
    elif alias == "output":
        link.symlink_to(out, target_is_directory=True)
        out = link

    with pytest.raises(ValueError, match="must not overlap"):
        prepare_version(version, out)

    assert source.read_text() == "contract A {}\n"
    assert answer.read_text() == '{"answer": "preserve me"}'


def _write(root: Path, files: dict[str, str]) -> None:
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)


@pytest.mark.parametrize(
    ("files", "error", "message"),
    [
        pytest.param({}, FileNotFoundError, "no Solidity contracts", id="missing_version"),
        pytest.param({"layers": "a file"}, FileNotFoundError, "no Solidity contracts", id="layers_file"),
        pytest.param(
            {"layers/README.md": "no contracts"}, FileNotFoundError, "no Solidity contracts", id="no_contracts"
        ),
        pytest.param(
            {"layers/A.sol": "contract A {}", "layers/B.sol": "contract B {"},
            ParseError,
            r"B\.sol: source does not parse",
            id="invalid",
        ),
    ],
)
def test_invalid_source_preserves_output(
    tmp_path: Path, files: dict[str, str], error: type[Exception], message: str
) -> None:
    version = tmp_path / "version"
    _write(version, files)
    out = tmp_path / "out"
    _write(out, {"previous.txt": "preserve me"})

    with pytest.raises(error, match=message):
        prepare_version(version, out)

    assert [p.name for p in out.iterdir()] == ["previous.txt"]
    assert (out / "previous.txt").read_text() == "preserve me"


def test_valid_source_replaces_existing_output(tmp_path: Path) -> None:
    version = tmp_path / "version"
    _write(version, {"layers/nested/A.sol": "// comment\ncontract A {}\n"})
    out = tmp_path / "out"
    _write(out, {"previous.txt": "obsolete"})

    assert prepare_version(version, out) == out

    assert not (out / "previous.txt").exists()
    assert (out / "layers" / "nested" / "A.sol").read_text() == "contract A {}\n"
