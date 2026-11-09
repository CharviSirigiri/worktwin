"""One call path for every agent: Google ADK by default, Gemini API directly as a fallback.

Every agent (twin, coordinator, narrator) is an ADK LlmAgent. We pass the
conversation so far in the prompt, so each call is stateless and easy to retry.
In mock mode nothing here is called; the agents use their template writers.
"""
from __future__ import annotations

import inspect
import json
import logging
import re
import uuid

from . import config

log = logging.getLogger("worktwin.llm")


def is_mock() -> bool:
    return config.MOCK_LLM


def _safe_name(name: str) -> str:
    n = re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "agent"
    return n if n[0].isalpha() else f"a_{n}"


async def _run_adk(agent_name: str, system: str, prompt: str, want_json: bool) -> str:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    gen_config = types.GenerateContentConfig(
        temperature=0.7,
        response_mime_type="application/json" if want_json else None,
    )
    # instruction is a function so ADK does not treat {braces} in prompts as state variables
    agent = LlmAgent(
        name=_safe_name(agent_name),
        model=config.GEMINI_MODEL,
        instruction=lambda _ctx: system,
        generate_content_config=gen_config,
    )
    runner = InMemoryRunner(agent=agent, app_name="worktwin")
    session = runner.session_service.create_session(app_name="worktwin", user_id="worktwin")
    if inspect.isawaitable(session):
        session = await session
    message = types.Content(role="user", parts=[types.Part(text=prompt)])
    text = ""
    async for event in runner.run_async(user_id="worktwin", session_id=session.id, new_message=message):
        if event.is_final_response() and event.content and event.content.parts:
            text = "".join(p.text or "" for p in event.content.parts)
    return text.strip()


async def _run_genai(system: str, prompt: str, want_json: bool) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    resp = await client.aio.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7,
            response_mime_type="application/json" if want_json else None,
        ),
    )
    return (resp.text or "").strip()


async def generate(agent_name: str, system: str, prompt: str, want_json: bool = False) -> str:
    """Run one agent turn. Tries ADK first (unless AGENT_RUNTIME=genai), then the plain Gemini API."""
    if config.AGENT_RUNTIME == "adk":
        try:
            return await _run_adk(agent_name, system, prompt, want_json)
        except Exception as e:  # noqa: BLE001 - fall back rather than break the demo
            log.warning("ADK call failed for %s (%s); falling back to Gemini API", agent_name, e)
    return await _run_genai(system, prompt, want_json)


def parse_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply (handles ```json fences)."""
    if not text:
        return None
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        v = json.loads(text)
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        v = json.loads(text[start : end + 1])
        return v if isinstance(v, dict) else None
    except json.JSONDecodeError:
        return None


def new_id() -> str:
    return uuid.uuid4().hex[:10]
