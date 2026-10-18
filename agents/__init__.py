"""Bulwark Multi-Agent Risk Guardian package."""
from .llm_client import AgentMessage, BaseLLMClient, GeminiLLMClient, StubLLMClient, ToolCall
from .orchestrator import Orchestrator
from .roles import (
    ANALYST_SYSTEM_PROMPT,
    ANALYST_TOOLS,
    EXECUTOR_SYSTEM_PROMPT,
    EXECUTOR_TOOLS,
    GUARDIAN_SYSTEM_PROMPT,
    GUARDIAN_TOOLS,
    ROLE_ALLOWLIST,
)
from .validator import build_fallback_verdict_template, validate_citations

__all__ = [
    "Orchestrator",
    "AgentMessage",
    "BaseLLMClient",
    "GeminiLLMClient",
    "StubLLMClient",
    "ToolCall",
    "ANALYST_SYSTEM_PROMPT",
    "GUARDIAN_SYSTEM_PROMPT",
    "EXECUTOR_SYSTEM_PROMPT",
    "ANALYST_TOOLS",
    "GUARDIAN_TOOLS",
    "EXECUTOR_TOOLS",
    "ROLE_ALLOWLIST",
    "validate_citations",
    "build_fallback_verdict_template",
]
