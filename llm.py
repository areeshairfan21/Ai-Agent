"""
Thin wrapper around the Groq API (using the official groq SDK). Groq is free
to use (no credit card, generous free-tier rate limits) and is explicitly one
of the LLM providers taught in this cohort's own curriculum (Day 11), so it's
a natural, cost-free fit here.

Model: openai/gpt-oss-120b — a strong open-weight model served at very high
speed on Groq's hardware, with native JSON mode support (needed for our
strict-JSON control-flow contract between turns).
"""

import json
import os
import re
from groq import Groq

MODEL = "openai/gpt-oss-120b"

_client = None


def get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at console.groq.com, then "
                "export it before starting the server, e.g. `set GROQ_API_KEY=gsk_...` "
                "(Windows) or `export GROQ_API_KEY=gsk_...` (Mac/Linux)."
            )
        _client = Groq(api_key=api_key)
    return _client


def _extract_json(text: str) -> dict:
    """Defensive parsing in case the model wraps JSON in code fences or adds stray text."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)


def call_json(system_prompt: str, user_prompt: str, max_tokens: int = 700, temperature: float = 0.4) -> dict:
    client = get_client()
    resp = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    text = resp.choices[0].message.content
    try:
        return _extract_json(text)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return {"reply": (text or "").strip() or "Let's continue.", "followup": False, "advance": True}