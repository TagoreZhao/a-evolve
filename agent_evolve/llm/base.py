"""LLM provider abstraction."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    usage: dict[str, int] = field(default_factory=dict)
    raw: Any = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers.

    Used by the Evolver engine to power the evolution LLM agent.
    """

    @abstractmethod
    def complete(
        self,
        messages: list[LLMMessage],
        max_tokens: int = 4096,
        temperature: float = 0.0,
        **kwargs,
    ) -> LLMResponse:
        """Send a completion request to the LLM."""

    @abstractmethod
    def complete_with_tools(
        self,
        messages: list[LLMMessage],
        tools: list[dict[str, Any]],
        max_tokens: int = 4096,
        **kwargs,
    ) -> LLMResponse:
        """Send a completion request with tool definitions."""

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
        """Run a multi-turn conversation with file-edit tools available.

        Evolution engines call this so the LLM can read/write workspace files.
        Providers that route through a custom tool API (Bedrock) use
        ``tools``/``tool_executor``. Providers that expose their own built-in
        file tools (Claude Code) use ``cwd`` to scope those tools to the
        workspace. Providers that support neither raise NotImplementedError;
        the engine falls back to a tool-less complete() with a warning.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not implement converse_loop; "
            "the caller should fall back to complete() or use a provider that supports tools."
        )
