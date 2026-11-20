from pathlib import Path

from compose_risk.prepare import comment_count, prepare_version, strip_comments


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
