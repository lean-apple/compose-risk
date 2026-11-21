"""The claude-code provider, run against a fake `claude` script that records how it was called."""

import asyncio
import json
import math
import stat
import sys
from pathlib import Path
from typing import Any

import pytest
from inspect_ai import eval
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser, GenerateConfig

from compose_risk.providers.claude_code import (
    ClaudeCodeAPI,
    ClaudeCodeError,
    TransientError,
    UnsupportedSettingError,
    cli_effort,
)
from compose_risk.task import compose_risk
from compose_risk.verdict import ReviewVerdict

VERDICT = ReviewVerdict(
    verdict="exploitable", root_cause_layer="2-upstream", propagation_path=[], explanation="fake claude"
).model_dump()

SUCCESS = {
    "subtype": "success",
    "is_error": False,
    "structured_output": VERDICT,
    "usage": {"input_tokens": 10, "output_tokens": 5},
    "modelUsage": {"claude-sonnet-5-5": {}},
    "total_cost_usd": 0.01,
}

# Records its arguments, environment and stdin next to itself, then behaves as `reply.json` says.
FAKE_CLAUDE = f"""#!{sys.executable}
import json, os, sys, time
from pathlib import Path
from typing import Any
here = Path(__file__).parent
reply = json.loads((here / "reply.json").read_text())
calls = here / "calls.jsonl"
with calls.open("a") as f:
    f.write(json.dumps({{"argv": sys.argv[1:], "env": sorted(os.environ), "stdin": sys.stdin.read()}}) + "\\n")
time.sleep(reply.get("sleep", 0))
sys.stdout.write(reply["stdout"] if "stdout" in reply else json.dumps(reply["result"]))
sys.exit(reply.get("exit", 0))
"""


def _fake_claude(tmp_path: Path, reply: dict[str, object]) -> Path:
    script = tmp_path / "claude"
    script.write_text(FAKE_CLAUDE)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (tmp_path / "reply.json").write_text(json.dumps(reply))
    return script


def _calls(tmp_path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text().splitlines()]


def test_runs_the_eval_through_an_isolated_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "must-not-leak")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "passed-through")
    script = _fake_claude(tmp_path, {"result": SUCCESS})

    [log] = eval(
        compose_risk(cases="kelpdao-aave-2026"),
        model="claude-code/sonnet",
        model_args={"executable": str(script)},
        log_dir=str(tmp_path / "logs"),
        display="none",
    )

    assert log.status == "success" and log.results is not None, log.error
    accuracy = {s.name: s.metrics["accuracy"].value for s in log.results.scores}
    assert accuracy == {"verdict_correct": 0.5, "root_cause_layer_correct": 1.0, "refused": 0.0}
    calls = _calls(tmp_path)
    assert len(calls) == 2
    for call in calls:
        argv = call["argv"]
        for flag in (
            "-p",
            "--safe-mode",
            "--strict-mcp-config",
            "--disable-slash-commands",
            "--no-session-persistence",
        ):
            assert flag in argv
        assert argv[argv.index("--tools") + 1] == ""
        assert argv[argv.index("--model") + 1] == "sonnet"
        assert "--json-schema" in argv and "--system-prompt" in argv
        assert "ANTHROPIC_API_KEY" not in call["env"] and "CLAUDE_CODE_OAUTH_TOKEN" in call["env"]
        assert "<threat_model>" in str(call["stdin"])


def _generate(script: Path, timeout: float = 30) -> object:
    api = ClaudeCodeAPI("sonnet", executable=str(script), timeout=timeout)
    messages: list[ChatMessage] = [ChatMessageSystem(content="system"), ChatMessageUser(content="review this")]
    return asyncio.run(api.generate(messages, [], "none", GenerateConfig()))


def test_cli_refusals_are_excluded_from_accuracy(tmp_path: Path) -> None:
    script = _fake_claude(
        tmp_path,
        {"result": {"subtype": "success", "is_error": False, "stop_reason": "refusal", "result": "I cannot help."}},
    )
    [log] = eval(
        compose_risk(cases="kelpdao-aave-2026"),
        model="claude-code/sonnet",
        model_args={"executable": str(script)},
        log_dir=str(tmp_path / "logs"),
        display="none",
    )
    assert log.status == "success" and log.results is not None, log.error
    assert log.samples is not None and len(log.samples) == 2
    for sample in log.samples:
        assert sample.output.stop_reason == "content_filter"
        assert sample.output.completion == "I cannot help."
    accuracy = {s.name: s.metrics["accuracy"].value for s in log.results.scores}
    assert accuracy["refused"] == 1.0
    assert math.isnan(accuracy["verdict_correct"]) and math.isnan(accuracy["root_cause_layer_correct"])


@pytest.mark.parametrize(
    ("reply", "message"),
    [
        ({"result": {}, "exit": 1}, "exited with 1"),
        ({"stdout": "not json"}, "did not print JSON"),
        ({"result": {"subtype": "error_max_turns", "is_error": True}}, "returned an error"),
        ({"result": SUCCESS, "sleep": 5}, "timed out"),
    ],
)
def test_cli_failures_raise(tmp_path: Path, reply: dict[str, object], message: str) -> None:
    script = _fake_claude(tmp_path, reply)
    with pytest.raises(ClaudeCodeError, match=message):
        _generate(script, timeout=1)


def test_settings_the_cli_cannot_apply_are_rejected() -> None:
    assert cli_effort(GenerateConfig(effort="high")) == "high"
    with pytest.raises(UnsupportedSettingError, match="temperature"):
        cli_effort(GenerateConfig(temperature=0.5))
    with pytest.raises(UnsupportedSettingError, match="no level"):
        cli_effort(GenerateConfig(reasoning_effort="minimal"))


API_ERROR = {"subtype": "success", "is_error": True, "terminal_reason": "api_error", "result": "API Error: ENOTFOUND"}


@pytest.mark.parametrize(
    ("message", "transient"),
    [
        ('API Error: 400 {"error":{"type":"invalid_request_error"}}', False),
        ('API Error: 401 {"error":{"type":"authentication_error"}}', False),
        ("API Error: 403 permission denied", False),
        ("API Error: 404 model not found", False),
        ("API Error: 413 request too large", False),
        ("API Error: 400 invalid request mentioning ECONNRESET", False),
        ("API Error: 408 request timeout", True),
        ("API Error: 409 conflict", True),
        ("API Error: 429 rate limited", True),
        ("API Error: 500 internal server error", True),
        ("API Error: 503 service unavailable", True),
        ("API Error: 529 overloaded", True),
        ('API Error: {"error":{"type":"authentication_error"}}', False),
        ('API Error: {"error":{"type":"rate_limit_error"}}', True),
        ('API Error: {"error":{"type":"overloaded_error"}}', True),
        ('API Error: {"error":{"type":"api_error"}}', True),
        ("API Error: ENOTFOUND", True),
        ("API Error: ECONNRESET", True),
        ("API Error: Connection error.", True),
        ("API Error: Request timed out.", True),
        ("API Error: unknown failure", False),
    ],
)
@pytest.mark.parametrize("exit_code", [0, 1])
def test_api_errors_retry_only_known_transient_failures(
    tmp_path: Path, message: str, transient: bool, exit_code: int
) -> None:
    script = _fake_claude(tmp_path, {"result": {**API_ERROR, "result": message}, "exit": exit_code})
    with pytest.raises(ClaudeCodeError, match="could not complete the API call") as raised:
        _generate(script)
    assert ClaudeCodeAPI("sonnet", executable=str(script)).should_retry(raised.value) is transient


@pytest.mark.parametrize(
    ("reply", "transient"),
    [
        ({"result": API_ERROR, "exit": 1}, True),
        ({"result": SUCCESS, "sleep": 5}, True),
        ({"result": {}, "exit": 1}, False),
        ({"result": {"subtype": "error_max_turns", "is_error": True}}, False),
    ],
)
def test_only_transient_failures_are_retried(tmp_path: Path, reply: dict[str, object], transient: bool) -> None:
    script = _fake_claude(tmp_path, reply)
    with pytest.raises(ClaudeCodeError) as raised:
        _generate(script, timeout=1)
    assert isinstance(raised.value, TransientError) is transient
    assert ClaudeCodeAPI("sonnet", executable=str(script)).should_retry(raised.value) is transient
