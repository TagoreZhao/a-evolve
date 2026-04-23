"""Claude Code LLM provider — routes evolver calls through a Claude Code
subscription (OAuth) instead of the Anthropic API.

Backed by the `claude-agent-sdk` Python package, which spawns the local
`claude` CLI as a subprocess. The user must have run `claude` once to
complete the OAuth flow — the SDK reads those stored credentials.

Use by setting `EvolveConfig.evolver_model="claude-code:<model-id>"`, e.g.
`claude-code:claude-opus-4-7`. The `create_default_llm` router in
`agent_evolve/algorithms/adaptive_skill/tools.py` handles dispatch.

Tool access:
- ``converse_loop`` enables the SDK's built-in file tools (Bash, Read, Write,
  Edit, Glob, Grep) scoped to ``cwd`` so the evolver can actually mutate the
  workspace. ``tools``/``tool_executor`` kwargs are ignored here — the SDK
  has no API for registering custom tool executors.
- ``complete`` and ``complete_with_tools`` run tool-less and are used for
  callers that only need plain generation.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .base import LLMMessage, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_SDK_TOOLS = ["Bash", "Read", "Write", "Edit", "Glob", "Grep"]


def _normalize_usage(raw: Any) -> dict[str, int]:
    """Best-effort extraction of token counts from a ResultMessage.usage dict."""
    if not isinstance(raw, dict):
        return {"input_tokens": 0, "output_tokens": 0}
    input_tokens = int(raw.get("input_tokens") or raw.get("inputTokens") or 0)
    output_tokens = int(raw.get("output_tokens") or raw.get("outputTokens") or 0)
    out = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    for k in ("cache_creation_input_tokens", "cache_read_input_tokens"):
        if k in raw:
            try:
                out[k] = int(raw[k])
            except (TypeError, ValueError):
                pass
    return out


class ClaudeCodeProvider(LLMProvider):
    def __init__(self, model: str = "claude-opus-4-7"):
        try:
            from claude_agent_sdk import query, ClaudeAgentOptions
        except ImportError as e:
            raise ImportError(
                "pip install claude-agent-sdk  (then run `claude` once to "
                "complete the OAuth flow so the SDK can use your subscription)"
            ) from e

        self._query = query
        self._ClaudeAgentOptions = ClaudeAgentOptions
        self.model = model

    def _run(
        self,
        system: str | None,
        user: str,
        cwd: str | Path | None = None,
        allowed_tools: list[str] | None = None,
    ) -> tuple[str, dict[str, int], int]:
        """Run a query, return (text, usage, n_tool_uses)."""
        import asyncio

        opts_kwargs: dict[str, Any] = dict(
            model=self.model,
            system_prompt=system,
            permission_mode="bypassPermissions",
            allowed_tools=list(allowed_tools or []),
        )
        if cwd is not None:
            opts_kwargs["cwd"] = str(cwd)
        opts = self._ClaudeAgentOptions(**opts_kwargs)

        async def _go() -> tuple[str, dict[str, int], int]:
            chunks: list[str] = []
            usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
            n_tool_uses = 0
            async for msg in self._query(prompt=user, options=opts):
                cls_name = type(msg).__name__
                for block in getattr(msg, "content", []) or []:
                    block_cls = type(block).__name__
                    text = getattr(block, "text", None)
                    if text:
                        chunks.append(text)
                    if block_cls == "ToolUseBlock":
                        n_tool_uses += 1
                if cls_name == "ResultMessage":
                    raw_usage = getattr(msg, "usage", None)
                    if raw_usage:
                        usage = _normalize_usage(raw_usage)
            return "".join(chunks), usage, n_tool_uses

        return asyncio.run(_go())

    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> LLMResponse:
        system = next((m.content for m in messages if m.role == "system"), None)
        user = "\n\n".join(m.content for m in messages if m.role != "system")
        text, usage, _ = self._run(system, user)
        return LLMResponse(content=text, usage=usage, raw=None)

    def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        return self.complete(messages, max_tokens=max_tokens, **kwargs)

    def converse_loop(
        self,
        system_prompt: str | None,
        user_message: str,
        tools: list[dict[str, Any]] | None = None,
        tool_executor: dict[str, Any] | None = None,
        cwd: str | Path | None = None,
        max_tokens: int = 4096,
        max_turns: int = 20,
    ) -> LLMResponse:
        """Run a tool-using conversation via the Claude Code SDK.

        Enables the SDK's built-in file tools (Bash, Read, Write, Edit, Glob,
        Grep) scoped to ``cwd``. The SDK handles the tool-use loop internally,
        so there is no explicit turn loop on this side.

        ``tools`` and ``tool_executor`` are accepted for interface parity with
        BedrockProvider but are ignored — the SDK has no API for registering
        custom tool executors. A debug log line is emitted if they are set.
        """
        if tools or tool_executor:
            logger.debug(
                "ClaudeCodeProvider.converse_loop ignoring custom tools=%s "
                "tool_executor=%s; using SDK built-ins %s scoped to cwd=%s",
                [t.get("name") for t in (tools or [])],
                list((tool_executor or {}).keys()),
                _SDK_TOOLS,
                cwd,
            )
        text, usage, n_tool_uses = self._run(
            system=system_prompt,
            user=user_message,
            cwd=cwd,
            allowed_tools=_SDK_TOOLS,
        )
        if n_tool_uses:
            logger.info(
                "ClaudeCodeProvider.converse_loop: %d tool use(s) inside cwd=%s",
                n_tool_uses, cwd,
            )
        usage = dict(usage)
        usage["tool_uses"] = n_tool_uses
        return LLMResponse(content=text, usage=usage, raw=None)
