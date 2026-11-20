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


@pytest.mark.parametrize("ancestor", [False, True])
@pytest.mark.parametrize("alias", ["none", "source", "output"])
def test_rejects_output_containing_source(tmp_path: Path, ancestor: bool, alias: str) -> None:
    version = tmp_path / "case" / "version"
    layers = version / "layers"
    layers.mkdir(parents=True)
    source = layers / "A.sol"
    source.write_text("contract A {}\n")
    answer = version / "case.json"
    answer.write_text('{"answer": "preserve me"}')
    out = version.parent if ancestor else version
    link = tmp_path / "alias"
    if alias == "source":
        link.symlink_to(version, target_is_directory=True)
        version = link
    elif alias == "output":
        link.symlink_to(out, target_is_directory=True)
        out = link

    with pytest.raises(ValueError, match="must not equal or contain"):
        prepare_version(version, out)

    assert source.read_text() == "contract A {}\n"
    assert answer.read_text() == '{"answer": "preserve me"}'


@pytest.mark.parametrize(
    ("source_state", "error", "message"),
    [
        ("missing_version", NotADirectoryError, "source version directory"),
        ("version_file", NotADirectoryError, "source version directory"),
        ("missing_layers", NotADirectoryError, "source layers directory"),
        ("layers_file", NotADirectoryError, "source layers directory"),
        ("empty_layers", ValueError, "no Solidity contracts"),
        ("non_solidity", ValueError, "no Solidity contracts"),
        ("solidity_directory", ValueError, "no Solidity contracts"),
        ("invalid_solidity", ParseError, "does not parse"),
    ],
)
def test_invalid_source_preserves_output(
    tmp_path: Path, source_state: str, error: type[Exception], message: str
) -> None:
    version = tmp_path / "version"
    layers = version / "layers"
    if source_state == "version_file":
        version.write_text("not a directory")
    elif source_state != "missing_version":
        version.mkdir()
        if source_state == "layers_file":
            layers.write_text("not a directory")
        elif source_state != "missing_layers":
            layers.mkdir()
            if source_state == "non_solidity":
                (layers / "README.md").write_text("No contracts here")
            elif source_state == "solidity_directory":
                (layers / "A.sol").mkdir()
            elif source_state == "invalid_solidity":
                (layers / "A.sol").write_text("contract A {}")
                (layers / "B.sol").write_text("contract B {")
    out = tmp_path / "out"
    out.mkdir()
    previous = out / "previous.txt"
    previous.write_text("preserve me")

    with pytest.raises(error, match=message):
        prepare_version(version, out)

    assert previous.read_text() == "preserve me"
    assert list(out.iterdir()) == [previous]


def test_valid_source_replaces_existing_output(tmp_path: Path) -> None:
    version = tmp_path / "version"
    layers = version / "layers" / "nested"
    layers.mkdir(parents=True)
    (layers / "A.sol").write_text("// comment\ncontract A {}\n")
    out = tmp_path / "out"
    out.mkdir()
    previous = out / "previous.txt"
    previous.write_text("obsolete")

    assert prepare_version(version, out) == out

    assert not previous.exists()
    assert (out / "layers" / "nested" / "A.sol").read_text() == "contract A {}\n"
