"""
groq_problem_gen.py — Part 2

Standalone module wrapping the Groq coding-problem generator, ready to be
imported directly into gemini.py. This is the exact same function validated
in Part 1 (test_groq_problem_gen.py), just packaged for reuse instead of
being a throwaway script.

Usage from gemini.py:
    from groq_problem_gen import generate_coding_problem
    problem = generate_coding_problem("candidate seemed confident about FastAPI routing")
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

_groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

GROQ_MODEL = "openai/gpt-oss-120b"
# Note: llama-3.3-70b-versatile was deprecated by Groq (~Aug 16, 2026 shutdown).
# gpt-oss-120b is the current recommended general-purpose replacement.

SYSTEM_PROMPT = """You are generating a single coding problem for a live technical interview,
based on a short summary of what the candidate has just been discussing with the interviewer.

Your problem must:
- Be directly relevant to the summary given — grounded in the specific technology/topic just discussed, not generic.
- Be solvable by writing a short function or small script in 5-15 minutes — this is a quick
  in-interview exercise, not a take-home assignment or a full LeetCode-hard problem.
- Match the candidate's demonstrated skill level from the summary. If the summary indicates they
  seemed confident/strong on a topic, it's fine to ask something that requires real depth. If the
  summary indicates they seemed unsure, partial, or shaky, favor a more foundational question on
  that same topic rather than jumping to an advanced pattern (e.g. don't ask someone unsure about
  psycopg2 basics to implement a connection pool — ask them to write a basic query function instead).
- Be self-contained — a candidate should be able to start coding from the description alone,
  with no need for external context they don't already have.

Respond ONLY with a JSON object in exactly this format, no other text:
{
  "title": "Short problem title, a few words",
  "description": "The full problem statement, written as you'd say it to a candidate. 2-5 sentences.",
  "language": "python | javascript | etc — infer from the summary",
  "starter_code": "A small starter code snippet (function signature, class stub, or similar) to give the candidate a starting point. Keep it minimal.",
  "difficulty": "easy | medium"
}
"""


def generate_coding_problem(conversation_summary: str) -> dict:
    """
    Takes a short summary of recent interview conversation (ideally including
    a read on the candidate's demonstrated confidence, not just topics named)
    and returns a structured coding problem dict:
        {title, description, language, starter_code, difficulty}

    Raises on failure (bad JSON, API error) — caller (gemini.py) is
    responsible for deciding what to do if problem generation fails
    (e.g. tell the candidate something went wrong and skip the coding round).
    """
    completion = _groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Conversation summary: {conversation_summary}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.8,
        max_completion_tokens=1200,
        reasoning_effort="low",
    )
    raw = completion.choices[0].message.content
    return json.loads(raw)


if __name__ == "__main__":
    # Quick smoke test — run this file directly to sanity-check the import
    # works and a single call succeeds, without running the full test suite.
    test = generate_coding_problem(
        "Candidate is a Python backend developer, seemed confident about FastAPI routing."
    )
    print(json.dumps(test, indent=2))