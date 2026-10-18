"""LLM client abstractions for Bulwark agents.

Supports:
1. GeminiLLMClient: Real Google Gemini API calls via official `google-genai` SDK.
2. StubLLMClient: Deterministic, offline mock client for unit testing.
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("bulwark.llm")


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    call_id: str = "call_default"


@dataclass
class AgentMessage:
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None


class BaseLLMClient(ABC):
    @abstractmethod
    def generate(
        self,
        messages: list[AgentMessage],
        tools: list[dict] | None = None,
        system_instruction: str = "",
    ) -> AgentMessage:
        """Generate response from LLM."""
        pass


class GeminiLLMClient(BaseLLMClient):
    """Real Google Gemini API client."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY must be set in environment or passed to GeminiLLMClient.")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        from google import genai
        self.client = genai.Client(api_key=self.api_key)

    def generate(
        self,
        messages: list[AgentMessage],
        tools: list[dict] | None = None,
        system_instruction: str = "",
    ) -> AgentMessage:
        from google.genai import types

        # Prepare contents
        contents = []
        for m in messages:
            if m.role == "user":
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=m.content)]))
            elif m.role == "assistant":
                parts = []
                if m.content:
                    parts.append(types.Part.from_text(text=m.content))
                for tc in m.tool_calls:
                    parts.append(types.Part.from_function_call(name=tc.name, args=tc.args))
                contents.append(types.Content(role="model", parts=parts))
            elif m.role == "tool":
                try:
                    res_dict = json.loads(m.content) if isinstance(m.content, str) else m.content
                except Exception:
                    res_dict = {"output": m.content}
                parts = [types.Part.from_function_response(name=m.tool_call_id or "tool", response=res_dict)]
                contents.append(types.Content(role="user", parts=parts))

        # Format tools if provided
        function_declarations = []
        for t in tools or []:
            function_declarations.append(
                types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters"),
                )
            )

        config = types.GenerateContentConfig(
            system_instruction=system_instruction or None,
            temperature=0.0,  # Deterministic output
            tools=[types.Tool(function_declarations=function_declarations)] if function_declarations else None,
        )

        try:
            resp = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            )
        except Exception as e:
            logger.warning(f"Gemini API call failed ({e}), attempting fallback model 'gemini-1.5-flash'...")
            resp = self.client.models.generate_content(
                model="gemini-1.5-flash",
                contents=contents,
                config=config,
            )

        tool_calls: list[ToolCall] = []
        text_content = ""

        if resp.candidates and resp.candidates[0].content and resp.candidates[0].content.parts:
            for part in resp.candidates[0].content.parts:
                if part.text:
                    text_content += part.text
                if part.function_call:
                    fc = part.function_call
                    tool_calls.append(ToolCall(name=fc.name, args=dict(fc.args or {}), call_id=fc.name))

        return AgentMessage(role="assistant", content=text_content, tool_calls=tool_calls)


class StubLLMClient(BaseLLMClient):
    """Deterministic stub client for testing without external API calls."""

    def __init__(self, responses: list[AgentMessage] | None = None, script_fn: Callable | None = None):
        self.responses = list(responses or [])
        self.script_fn = script_fn
        self.call_history: list[list[AgentMessage]] = []

    def generate(
        self,
        messages: list[AgentMessage],
        tools: list[dict] | None = None,
        system_instruction: str = "",
    ) -> AgentMessage:
        self.call_history.append(messages)
        if self.script_fn:
            return self.script_fn(messages, tools, system_instruction)
        if self.responses:
            return self.responses.pop(0)
        # Default fallback
        return AgentMessage(role="assistant", content="Deterministic stub response.")
