"""Claude Code LLM provider — routes evolver calls through a Claude Code
subscription (OAuth) instead of the Anthropic API.

Backed by the `claude-agent-sdk` Python package, which spawns the local
`claude` CLI as a subprocess. The user must have run `claude` once to
complete the OAuth flow — the SDK reads those stored credentials.

Use by setting `EvolveConfig.evolver_model="claude-code:<model-id>"`, e.g.
`claude-code:claude-opus-4-7`. The `create_default_llm` router in
`agent_evolve/algorithms/adaptive_skill/tools.py` handles dispatch.

Notes:
- Usage tokens are not reported by the SDK; returned as 0.
- The adaptive-skill evolver's preferred bash-tool path (engine.py:160)
  is Bedrock-only. With this provider, the engine falls through to the
  plain `complete()` path at engine.py:175-181, so `complete_with_tools`
  here just delegates to `complete`.
"""

from __future__ import annotations

from typing import Any

from .base import LLMMessage, LLMProvider, LLMResponse


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

    def _run(self, system: str | None, user: str) -> str:
        import asyncio

        async def _go() -> str:
            opts = self._ClaudeAgentOptions(
                model=self.model,
                system_prompt=system,
                permission_mode="bypassPermissions",
                allowed_tools=[],  # evolver fallback path doesn't need tools
            )
            chunks: list[str] = []
            async for msg in self._query(prompt=user, options=opts):
                for block in getattr(msg, "content", []) or []:
                    text = getattr(block, "text", None)
                    if text:
                        chunks.append(text)
            return "".join(chunks)

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
        text = self._run(system, user)
        return LLMResponse(
            content=text,
            usage={"input_tokens": 0, "output_tokens": 0},
            raw=None,
        )

    def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        max_tokens: int = 4096,
        **kwargs: Any,
    ) -> LLMResponse:
        return self.complete(messages, max_tokens=max_tokens, **kwargs)
