"""Inspect model provider that answers through the local Claude Code CLI (`claude -p`).

Each generate call runs one isolated, tool-free `claude -p` process in a fresh empty directory, so the
model sees only the messages Inspect sends. Use it as `--model claude-code/<model>`, where `<model>`
(`opus`, `sonnet`, `haiku` or a full model name) is passed to `claude --model`.
"""

import asyncio
import json
import os
import re
import shutil
import signal
import tempfile
from typing import Any

import anyio
from inspect_ai.model import (
    ChatMessage,
    ChatMessageSystem,
    ChatMessageUser,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
    ModelUsage,
    modelapi,
)
from inspect_ai.tool import ToolChoice, ToolInfo

DEFAULT_TIMEOUT = 900.0
DEFAULT_MAX_CONNECTIONS = 2

# Only what the CLI needs to find itself and the signed-in account; API keys and other secrets stay out.
# `CLAUDE_CODE_OAUTH_TOKEN` signs in a machine with no saved login, such as a CI runner.
_ENV_KEYS = (
    "HOME",
    "PATH",
    "USER",
    "LOGNAME",
    "SHELL",
    "LANG",
    "LC_ALL",
    "TMPDIR",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_OAUTH_TOKEN",
)

# Settings Inspect applies itself around the call, so the CLI never needs to see them.
_APPLIED_BY_INSPECT = frozenset(
    {"max_connections", "adaptive_connections", "max_retries", "timeout", "attempt_timeout", "cache"}
)
# Settings this provider forwards to the CLI.
_FORWARDED = frozenset({"effort", "reasoning_effort", "response_schema"})
# `claude --effort` levels; Inspect's `reasoning_effort` also allows "none" and "minimal", which have no equivalent.
_CLI_EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})


class ClaudeCodeError(Exception):
    """`claude -p` failed, timed out, or returned an error result."""


class TransientError(ClaudeCodeError):
    """`claude -p` timed out or could not reach the API, such as after sleep or a network drop; Inspect retries it."""


class UnsupportedSettingError(ClaudeCodeError):
    """A generation setting was requested that `claude -p` cannot apply."""


def _retryable_api_error(message: str) -> bool:
    """Recognize temporary API/transport failures; unknown errors must fail rather than retry forever."""
    detail = message.removeprefix("API Error:").strip()
    status = re.match(r"(\d{3})\b", detail)
    if status:
        code = int(status[1])
        return code in {408, 409, 429} or 500 <= code < 600
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error", payload)
        return isinstance(error, dict) and error.get("type") in {"rate_limit_error", "overloaded_error", "api_error"}
    return bool(
        re.fullmatch(
            r"(?:ENOTFOUND|EAI_AGAIN|ECONNRESET|ECONNREFUSED|ETIMEDOUT|EPIPE|Connection error\.?|Request timed out\.?)",
            detail,
        )
    )


def cli_effort(config: GenerateConfig) -> str | None:
    """The `claude --effort` level for `config`, or None to leave the CLI default.

    Raises `UnsupportedSettingError` for any generation setting the CLI cannot apply, so a run never
    records a setting that was not used.
    """
    unsupported = sorted(set(config.model_dump(exclude_none=True)) - _APPLIED_BY_INSPECT - _FORWARDED)
    if unsupported:
        raise UnsupportedSettingError(f"claude-code cannot apply: {', '.join(unsupported)}")
    efforts = {e for e in (config.effort, config.reasoning_effort) if e is not None}
    if len(efforts) > 1:
        raise UnsupportedSettingError(f"conflicting effort and reasoning_effort: {sorted(efforts)}")
    effort = next(iter(efforts), None)
    if effort is not None and effort not in _CLI_EFFORTS:
        raise UnsupportedSettingError(f"claude --effort has no level {effort!r}")
    return effort


def claude_command(
    executable: str, model: str, system_prompt: str, json_schema: dict[str, Any] | None, effort: str | None
) -> list[str]:
    """The isolated `claude -p` invocation: no tools, customizations, MCP servers, commands or saved session."""
    command = [
        executable,
        "-p",
        "--safe-mode",
        "--tools",
        "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--no-session-persistence",
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--output-format",
        "json",
    ]
    if effort is not None:
        command += ["--effort", effort]
    if json_schema is not None:
        command += ["--json-schema", json.dumps(json_schema)]
    return command


def model_output(result: dict[str, Any], requested_model: str) -> ModelOutput:
    """Inspect output for a successful `claude -p` JSON result, keeping usage, cost and the resolved model."""
    structured = result.get("structured_output")
    content = json.dumps(structured) if structured is not None else result.get("result", "")
    # `modelUsage` is keyed by the concrete model that answered (e.g. claude-opus-5-5).
    models = sorted(result.get("modelUsage") or {})
    output = ModelOutput.from_content(model=",".join(models) or requested_model, content=content)
    usage = result.get("usage")
    if usage is not None:
        input_tokens = usage.get("input_tokens", 0)
        cache_write = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        output.usage = ModelUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + cache_write + cache_read + output_tokens,
            input_tokens_cache_write=cache_write,
            input_tokens_cache_read=cache_read,
            reasoning_tokens=(usage.get("output_tokens_details") or {}).get("thinking_tokens"),
            total_cost=result.get("total_cost_usd"),
        )
    output.metadata = {"requested_model": requested_model, "duration_ms": result.get("duration_ms")}
    return output


def _split(input: list[ChatMessage]) -> tuple[str, str]:
    """System prompt and user prompt of a single-turn conversation."""
    system = [m.text for m in input if isinstance(m, ChatMessageSystem)]
    user = [m.text for m in input if isinstance(m, ChatMessageUser)]
    if len(system) + len(user) != len(input) or not user:
        raise ClaudeCodeError("claude-code supports a single-turn conversation of system and user messages only")
    return "\n\n".join(system), "\n\n".join(user)


async def _terminate(process: asyncio.subprocess.Process) -> None:
    """Kills the CLI and everything it started, then waits for it, even while the caller is being cancelled."""
    if process.returncode is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    with anyio.CancelScope(shield=True):
        await process.wait()


@modelapi(name="claude-code")
class ClaudeCodeAPI(ModelAPI):
    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig | None = None,
        executable: str = "claude",
        timeout: float = DEFAULT_TIMEOUT,
        **model_args: Any,
    ) -> None:
        config = config or GenerateConfig()
        # Inspect's adaptive concurrency ignores max_connections() unless a limit is set explicitly.
        if config.max_connections is None:
            config.max_connections = DEFAULT_MAX_CONNECTIONS
        super().__init__(model_name, base_url, api_key, [], config)
        resolved = shutil.which(executable)
        if resolved is None:
            raise ClaudeCodeError(f"Claude Code CLI not found: {executable!r}")
        self.executable = resolved
        self.timeout = float(timeout)

    def max_connections(self) -> int:
        return DEFAULT_MAX_CONNECTIONS

    def should_retry(self, ex: Exception) -> bool:
        return isinstance(ex, TransientError)

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        if tools:
            raise ClaudeCodeError("claude-code does not support tools")
        effort = cli_effort(config)
        system_prompt, prompt = _split(input)
        schema = config.response_schema
        json_schema = schema.json_schema.model_dump(exclude_none=True, by_alias=True) if schema else None
        command = claude_command(self.executable, self.model_name, system_prompt, json_schema, effort)
        env = {k: os.environ[k] for k in _ENV_KEYS if k in os.environ}

        with tempfile.TemporaryDirectory(prefix="claude-code-") as workdir:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=workdir,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Its own process group, so cleanup reaches anything the CLI starts.
                start_new_session=True,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(prompt.encode()), self.timeout)
            except TimeoutError:
                await _terminate(process)
                raise TransientError(f"claude -p timed out after {self.timeout:.0f}s") from None
            except BaseException:
                # Cancellation or any other interruption: never leave the CLI running.
                await _terminate(process)
                raise

        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = None
        # The CLI exits non-zero on API errors too, with the reason in its JSON result.
        if isinstance(result, dict) and result.get("terminal_reason") == "api_error":
            message = str(result.get("result", ""))
            error_type = TransientError if _retryable_api_error(message) else ClaudeCodeError
            raise error_type(f"claude -p could not complete the API call: {message}")
        if process.returncode != 0:
            raise ClaudeCodeError(
                f"claude -p exited with {process.returncode}: {stderr.decode().strip() or stdout.decode().strip()}"
            )
        if not isinstance(result, dict):
            raise ClaudeCodeError(f"claude -p did not print JSON: {stdout.decode()[:500]}")
        if result.get("is_error") or result.get("subtype") != "success":
            raise ClaudeCodeError(f"claude -p returned an error: {result.get('subtype')}: {result.get('result')}")
        return model_output(result, self.model_name)
