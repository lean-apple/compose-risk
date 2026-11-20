"""Builds what the reviewer reads for one version of a case: its layer contracts, with comments stripped."""

import shutil
from pathlib import Path

from tree_sitter_language_pack import get_parser

_PARSER = get_parser("solidity")


class ParseError(Exception):
    pass


def _comment_spans(source: bytes) -> list[tuple[int, int]]:
    """Byte ranges of every comment in Solidity source, found by parsing it."""
    tree = _PARSER.parse(source)
    if tree.root_node.has_error:
        raise ParseError("source does not parse as Solidity")
    spans, stack = [], [tree.root_node]
    while stack:
        node = stack.pop()
        if node.type == "comment":
            spans.append((node.start_byte, node.end_byte))
        else:
            stack.extend(node.children)
    return sorted(spans)


def strip_comments(source: str) -> str:
    """Removes comments from Solidity source; string literals are left intact."""
    data = source.encode()
    out, pos = [], 0
    for start, end in _comment_spans(data):
        out.append(data[pos:start])
        # Keeps the comment's line breaks, or one space, so the tokens around it stay apart.
        out.append(b"\n" * data[start:end].count(b"\n") or b" ")
        pos = end
    out.append(data[pos:])
    text = "\n".join(line.rstrip() for line in b"".join(out).decode().split("\n"))
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip() + "\n"


def comment_count(source: str) -> int:
    """Counts the comments in Solidity source; text inside string literals is not a comment."""
    return len(_comment_spans(source.encode()))


def prepare_version(version_dir: Path, out_dir: Path) -> Path:
    """Writes `out_dir/layers/` with every layer contract of `version_dir`, comments stripped.

    Only `layers/` is copied: the exploit and `case.json` hold the answer. An existing `out_dir` is replaced.
    """
    if out_dir.exists():
        shutil.rmtree(out_dir)
    layers = version_dir / "layers"
    for source in sorted(layers.rglob("*.sol")):
        target = out_dir / "layers" / source.relative_to(layers)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(strip_comments(source.read_text()))
    return out_dir
