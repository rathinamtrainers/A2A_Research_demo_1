"""
Code Agent — Sandboxed Python code execution via Gemini code_execution tool.

Demonstrates:
  F8  — API Key authentication (X-API-Key header)
  F12 — Gemini built-in code_execution tool (BuiltInCodeExecutor)
  F17 — Safety guardrails blocking dangerous code patterns
  F20 — Cloud Run deployment
"""

from __future__ import annotations

from dotenv import load_dotenv
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.agents import LlmAgent
from google.adk.code_executors import BuiltInCodeExecutor
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from shared.callbacks import (
    guardrail_callback_before_tool,
    logging_callback_after_tool,
    logging_callback_before_tool,
)
from shared.config import settings

load_dotenv()

# ── Agent Card (F1) ───────────────────────────────────────────────────────────

_code_skill = AgentSkill(
    id="code_execution",
    name="Python Code Execution",
    description=(
        "Generates and executes Python code in a sandboxed environment. "
        "Returns code, stdout, stderr, and any generated files."
    ),
    tags=["code", "execution", "python"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_debug_skill = AgentSkill(
    id="code_debug",
    name="Code Debugging",
    description="Analyses Python code for bugs and suggests fixes.",
    tags=["code", "debug", "python"],
    input_modes=["text/plain"],
    output_modes=["text/plain"],
)

_AGENT_CARD = AgentCard(
    name="code_agent",
    description="Executes Python code safely in a Gemini-managed sandbox.",
    url=settings.CODE_AGENT_URL,
    version="1.0.0",
    skills=[_code_skill, _debug_skill],
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    # F8: API Key auth required (X-API-Key header)
)

# ── LLM Agent with Gemini code_execution (F12) ────────────────────────────────
# ``BuiltInCodeExecutor`` enables Gemini's native sandboxed Python execution.
# The code executor is passed to the LlmAgent as ``code_executor``.

_SYSTEM_INSTRUCTION = """
You are a code execution assistant. When asked to run code:
1. Write clean, correct Python code to solve the problem.
2. Execute it using the code execution tool.
3. Return the output along with a clear explanation.

SAFETY RULES (enforced by guardrail callbacks):
- Never use os.system, subprocess, or shutil.rmtree.
- Never use exec() or eval() on user-provided strings.
- Never open files outside the sandbox working directory.
"""

root_agent = LlmAgent(
    model=settings.GEMINI_MODEL,
    name="code_agent",
    description="Executes Python code in a sandboxed environment.",
    instruction=_SYSTEM_INSTRUCTION,
    code_executor=BuiltInCodeExecutor(),  # F12 — Gemini built-in code execution
    before_tool_callback=guardrail_callback_before_tool,  # F17 — Safety guardrail
    after_tool_callback=logging_callback_after_tool,
)

# ── FastAPI A2A app with API Key middleware (F8) ──────────────────────────────

app = to_a2a(root_agent, port=8003, agent_card=_AGENT_CARD)


async def _api_key_middleware(request: Request, call_next):
    """
    Middleware that enforces X-API-Key authentication (F8).

    The ``/.well-known/agent.json`` discovery endpoint is always public.
    All other endpoints require a valid ``X-API-Key`` header.
    """
    # Allow discovery endpoint without auth
    if request.url.path == "/.well-known/agent.json":
        return await call_next(request)

    api_key = request.headers.get("X-API-Key", "")
    if not api_key or api_key != settings.CODE_AGENT_API_KEY:
        return JSONResponse(
            {"error": "Invalid or missing API key"},
            status_code=403,
        )
    return await call_next(request)


app.add_middleware(BaseHTTPMiddleware, dispatch=_api_key_middleware)
