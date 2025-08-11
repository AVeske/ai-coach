# agents/coach_agent.py
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in environment variables")

client = AsyncOpenAI(api_key=api_key)

async def get_feedback(exercise: str, keypoints: dict) -> str:
    prompt = f"""
    You are a gym form coach. The exercise is: {exercise}.
    Here are the extracted body keypoints (pose data):

    {keypoints}

    Give the user short, practical feedback in a gym-bro tone.
    """
    resp = await client.chat.completions.create(
        model="gpt-4o-mini",  # use nano later if released
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content.strip()
