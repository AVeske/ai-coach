# backend/python/agents/coach_agent.py
from __future__ import annotations
import os
from typing import Dict, Any
from openai import AsyncOpenAI
from dotenv import load_dotenv, find_dotenv

_SYSTEM = (
    "You are AI Coach. Be concise, specific, and actionable. "
    "Prioritize BAD reps and give concrete cues the lifter can use next set."
)

_client: AsyncOpenAI | None = None

def _load_env_once() -> None:
    here = os.path.dirname(__file__)
    local_env = os.path.join(here, "..", ".env")
    if os.path.exists(local_env):
        load_dotenv(local_env, override=False)
    else:
        load_dotenv(find_dotenv(), override=False)

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _load_env_once()
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _client = AsyncOpenAI(api_key=key)
    return _client

def _model_name() -> str:
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini")

def _summ(metrics: Dict[str, Any]) -> str:
    s = metrics.get("summary", {}) or {}
    parts = [
        f"total={s.get('total_reps',0)}",
        f"good={s.get('good_reps',0)}",
        f"bad={s.get('bad_reps',0)}",
    ]
    for k, v in s.items():
        if k.endswith("_reps") and k not in ("total_reps","good_reps","bad_reps"):
            parts.append(f"{k}={int(v or 0)}")
    return ", ".join(parts)

def _tempo_hint(metrics: Dict[str, Any]) -> str:
    s = metrics.get("summary", {}) or {}
    tf = int(s.get("too_fast_reps", 0) or 0)
    ts = int(s.get("too_slow_reps", 0) or 0)
    bad = int(s.get("bad_reps", 0) or 0)
    if bad <= 0:
        return ""
    if bad and tf >= 2 and (tf / bad) >= 0.33:
        return "Tempo note: Many bad reps were too fast. Aim ~2–3s down, 1s up."
    if bad and ts >= 2 and (ts / bad) >= 0.33:
        return "Tempo note: Several reps were too slow. Keep a steady 2–3s down, 1s up."
    return ""

async def get_feedback(exercise_id: str, metrics: Dict[str, Any], rubric_text: str) -> str:
    client = _get_client()
    s = metrics.get("summary", {}) or {}
    counts = [(k, int(v or 0)) for k, v in s.items()
              if k.endswith("_reps") and k not in ("total_reps","good_reps","bad_reps")]
    counts.sort(key=lambda kv: kv[1], reverse=True)
    top_errors = [k for k, v in counts if v > 0][:2]

    tempo_note = _tempo_hint(metrics)
    tn = f"\n{tempo_note}" if tempo_note else ""

    user = f"""
Exercise: {exercise_id}
Metrics: {_summ(metrics)}
Top error categories: {', '.join(top_errors) if top_errors else 'none'}
Rubric (YAML):
{rubric_text}
{tn}

Write feedback:
1) One-sentence verdict (mention good/bad counts).
2) Bullet list: Fix the top 2 error categories with 2–3 precise cues each.
3) One short cue for the next set (memorable).
4) If a tempo note was provided, include it as a final sentence.
<120 words. No emojis. Avoid generic tips; tie to the metrics/terms above.
""".strip()

    resp = await client.chat.completions.create(
        model=_model_name(),
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
