"""
Chat completions via Groq (OpenAI-compatible API) or Google Gemini.
Configured with LLM_PROVIDER and the corresponding API key in config / .env.
"""

from __future__ import annotations

import json
from typing import Any

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


def _resolved_model() -> str:
    from shared.config.config import LLM_MODEL, LLM_PROVIDER

    explicit = (LLM_MODEL or "").strip()
    if explicit:
        return explicit
    if LLM_PROVIDER == "gemini":
        return "gemini-2.0-flash"
    return "llama-3.3-70b-versatile"


def _chat_groq_json(system: str, user: str, temperature: float) -> dict[str, Any]:
    from openai import OpenAI

    from shared.config.config import GROQ_API_KEY

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set (LLM_PROVIDER=groq).")
    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    model = _resolved_model()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RuntimeError("Groq returned empty content.")
    return json.loads(raw)


def _chat_groq_text(system: str, user: str, temperature: float) -> str:
    from openai import OpenAI

    from shared.config.config import GROQ_API_KEY

    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set (LLM_PROVIDER=groq).")
    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)
    model = _resolved_model()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RuntimeError("Groq returned empty content.")
    return raw.strip()


def _chat_gemini_json(system: str, user: str, temperature: float) -> dict[str, Any]:
    import google.generativeai as genai

    from shared.config.config import GEMINI_API_KEY

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set (LLM_PROVIDER=gemini).")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        _resolved_model(),
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    raw = response.text
    if not raw:
        raise RuntimeError("Gemini returned empty content.")
    return json.loads(raw)


def _chat_gemini_text(system: str, user: str, temperature: float) -> str:
    import google.generativeai as genai

    from shared.config.config import GEMINI_API_KEY

    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY (or GOOGLE_API_KEY) is not set (LLM_PROVIDER=gemini).")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        _resolved_model(),
        system_instruction=system,
    )
    response = model.generate_content(
        user,
        generation_config=genai.GenerationConfig(temperature=temperature),
    )
    raw = response.text
    if not raw:
        raise RuntimeError("Gemini returned empty content.")
    return raw.strip()


def chat_json(*, system: str, user: str, temperature: float = 0.7) -> dict[str, Any]:
    """Single-turn chat that must return a JSON object (parsed to dict)."""
    from shared.config.config import LLM_PROVIDER

    if LLM_PROVIDER == "groq":
        return _chat_groq_json(system, user, temperature)
    if LLM_PROVIDER == "gemini":
        return _chat_gemini_json(system, user, temperature)
    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={LLM_PROVIDER!r}. Use 'groq' or 'gemini'."
    )


def chat_text(*, system: str, user: str, temperature: float = 0.7) -> str:
    """Single-turn chat returning plain text."""
    from shared.config.config import LLM_PROVIDER

    if LLM_PROVIDER == "groq":
        return _chat_groq_text(system, user, temperature)
    if LLM_PROVIDER == "gemini":
        return _chat_gemini_text(system, user, temperature)
    raise RuntimeError(
        f"Unsupported LLM_PROVIDER={LLM_PROVIDER!r}. Use 'groq' or 'gemini'."
    )
