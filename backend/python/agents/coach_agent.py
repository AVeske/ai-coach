import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = """You are a concise strength coach. 
Use the provided rubric and metrics. 
Be precise, practical, and avoid medical claims. 
Prefer bullet points (max 5)."""

async def get_feedback(exercise: str, metrics: dict, rubric_text: str) -> str:
    # shrink JSON for the model if huge: include only top-level summary + first few reps
    reps = metrics.get("reps", [])[:6]
    summary = metrics.get("summary", {})
    compact = {"summary": summary, "reps": reps}

    user = f"""
Exercise: {exercise}

RUBRIC (YAML):
{rubric_text}

METRICS (JSON):
{compact}

Write feedback:
- If 0 reps detected: suggest camera framing & reattempt.
- Else: highlight overall summary and call out specific rep numbers that need work (e.g., shallow, hip_twist).
- Use the rubric cues to pick phrasing.
"""
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",  # or a cheaper compatible model
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()
