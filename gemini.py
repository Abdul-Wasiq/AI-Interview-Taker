import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from dotenv import load_dotenv
from Problem_Task import generate_coding_problem
from bucket_sampler import BucketSampler

load_dotenv()

app = FastAPI()

# Loaded once at startup — cheap, in-memory, reused across every session.
# If a language/role isn't in the buckets (e.g. Rust, Embedded), the sampler's
# has_language()/has_role() checks below fall back to the original
# "let Gemini use its own knowledge" behavior — nothing about that path changes.
bucket_sampler = BucketSampler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if (GEMINI_API_KEY):
    print("working")
else:
    print("Not working")

client = genai.Client()

MODEL = "gemini-3.1-flash-live-preview"

# ---- Interviewer voices ----
# Same 30 prebuilt voices used by generate_voices.py, in the same order,
# so the "has_sample" flag below lines up with whatever's in audio/ so far.
VOICES = [
    # Male voices
    "Charon", "Puck", "Fenrir", "Orus", "Achird", "Algenib", "Algieba", "Alnilam",
    "Enceladus", "Iapetus", "Rasalgethi", "Sadachbia", "Sadaltager", "Schedar",
    "Umbriel", "Zubenelgenubi",
    # Female voices
    "Kore", "Aoede", "Achernar", "Autonoe", "Callirrhoe", "Despina", "Erinome",
    "Gacrux", "Laomedeia", "Leda", "Pulcherrima", "Sulafat", "Vindemiatrix", "Zephyr",
]
VOICE_GENDER = {**{v: "male" for v in VOICES[:16]}, **{v: "female" for v in VOICES[16:]}}
DEFAULT_VOICE = "Charon"

AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
# Serves whatever's already in audio/ (from generate_voices.py) at /audio/<Name>.wav
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# ---- Interviewer profile pictures ----
# Filenames on disk don't follow one consistent pattern (mixed casing, some with
# a "Voice" suffix, some without) — so map each voice to its exact real filename
# rather than guessing. Update this dict if a filename ever changes.
PROFILE_DIR = "profiles_pictures"
os.makedirs(PROFILE_DIR, exist_ok=True)
app.mount("/profile-pictures", StaticFiles(directory=PROFILE_DIR), name="profile_pictures")

PROFILE_PICTURE_FILES = {
    "Charon": "charon.jpg",
    "Puck": "puck.jpg",
    "Fenrir": "fenrir.jpg",
    "Orus": "OrusVoice.jpg",
    "Achird": "AchirdVoice.jpg",
    "Algenib": "AlgenibVoice.jpg",
    "Algieba": "Algieba.jpg",
    "Alnilam": "AlnilamVoice.jpg",
    "Enceladus": "EnceladusVoice.jpg",
    "Iapetus": "IapetusVoice.jpg",
    "Rasalgethi": "RasalgethiVoice.jpg",
    "Sadachbia": "SadachbiaVoice.jpg",
    "Sadaltager": "SadaltagerVoice.jpg",
    "Schedar": "SchedarVoice.jpg",
    "Umbriel": "UmbrielVoice.jpg",
    "Zubenelgenubi": "ZubenelgenubiVoice.jpg",
    "Kore": "KoreVoice.jpg",
    "Aoede": "AoedeVoice.jpg",
    "Achernar": "AchernarVoice.jpg",
    "Autonoe": "AutonoeVoice.jpg",
    "Callirrhoe": "CallirrhoeVoice.jpg",
    "Despina": "DespinaVoice.jpg",
    "Erinome": "ErinomeVoice.jpg",
    "Gacrux": "GacruxVoice.jpg",
    "Laomedeia": "LaomedeiaVoice.jpg",
    "Leda": "LedaVoice.jpg",
    "Pulcherrima": "PulcherrimaVoice.jpg",
    "Sulafat": "SulafatVoice.jpg",
    "Vindemiatrix": "VindemiatrixVoice.jpg",
    "Zephyr": "ZephyrVoice.jpg",
}


@app.get("/api/voices")
def list_voices():
    """All 30 prebuilt voices, flagged with whether a local preview .wav and a
    profile picture exist yet. A voice can still be selected for the real
    interview even without a sample — the sample/picture are local-only extras,
    unrelated to the Live API's own voice support."""
    voices = []
    for v in VOICES:
        filename = PROFILE_PICTURE_FILES.get(v)
        has_picture = bool(filename) and os.path.exists(os.path.join(PROFILE_DIR, filename))
        voices.append({
            "name": v,
            "gender": VOICE_GENDER.get(v, "male"),
            "has_sample": os.path.exists(os.path.join(AUDIO_DIR, f"{v}.wav")),
            "profile_picture": f"/profile-pictures/{filename}" if has_picture else None,
        })
    return voices

END_INTERVIEW_TOOL = {
    "function_declarations": [
        {
            "name": "end_interview",
            "description": (
                "Call this ONLY after you have said your closing/goodbye line out loud. "
                "Ends the interview session completely."
            ),
        }
    ]
}

OPEN_CODE_CHALLENGE_TOOL = {
    "function_declarations": [
        {
            "name": "open_code_challenge",
            "description": (
                "CRITICAL: Call this tool IMMEDIATELY after evaluating the candidate's theoretical answer, "
                "with NO spoken narration beforehand — do not say 'I'm opening the compiler' or anything "
                "similar before calling it, since the popup does not exist yet at that moment and saying so "
                "causes a confusing desync for the candidate. Call the tool FIRST, silently. You will "
                "receive an instruction telling you what to say once it is actually visible."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "context_summary": {
                        "type": "string",
                        "description": (
                            "A short summary (1-2 sentences) of what the candidate was just "
                            "discussing AND your read of their demonstrated confidence on that "
                            "topic. Used to generate a coding problem."
                        ),
                    }
                },
                "required": ["context_summary"],
            },
        }
    ]
}

def build_system_prompt(language: str, role: str, difficulty_level: str) -> str:
    import random
    session_seed = random.randint(1, 9999)

    # --- Coin flip for Phase 1: sometimes go deep on architecture, sometimes don't ---
    # Matches real interviewer variance — some go deep, most don't.
    deep_dive_intro = random.random() < 0.15

    # --- Bucket lookup: known language/role use the sampler; unknown ("Other")
    #     falls back EXACTLY to the original "use your intelligence" behavior. ---
    use_buckets = bucket_sampler.has_language(language) and bucket_sampler.has_role(role)

    interview_topic = f"{language} — {role}".strip(" —")

    if use_buckets:
        fundamentals_topics = bucket_sampler.sample_fundamentals(language, k=2)
        extended_topics = bucket_sampler.sample_extended(role, k=2)
        design_scenarios = bucket_sampler.sample_system_design(role, difficulty_level, k=1)
        behavioral_questions = bucket_sampler.sample_behavioral(k=1)

        fundamentals_block = (
            "PRE-SELECTED FUNDAMENTALS TOPICS (ask about these, drill deeper based on answer quality, "
            "attack from any angle — do NOT just ask a textbook definition):\n"
            + "\n".join(f"- {t}" for t in fundamentals_topics)
        )
        extended_block = (
            "PRE-SELECTED EXTENDED TECHNICAL TOPICS:\n"
            + "\n".join(f"- {t}" for t in extended_topics)
        )
        if design_scenarios:
            scenario = design_scenarios[0]
            design_block = (
                f"PRE-SELECTED SYSTEM DESIGN SCENARIO: \"{scenario['name']}\"\n"
                f"Open with: \"{scenario['seed_prompt']}\" — then drill deeper with follow-up "
                f"constraints (scale, latency, failure handling) based on their answers."
            )
        else:
            design_block = "SYSTEM DESIGN: No pre-selected scenario available — use your judgment for this role."
        behavioral_block = (
            "PRE-SELECTED BEHAVIORAL QUESTION(S) — ask these, do not invent your own:\n"
            + "\n".join(f"- {q}" for q in behavioral_questions)
        )
    else:
        # Original behavior, unchanged: unsupported language/role (e.g. Rust, Embedded)
        # relies fully on Gemini's own knowledge, exactly as the app already worked.
        fundamentals_block = (
            "No pre-selected fundamentals topics exist for this domain yet. "
            "Use your own knowledge of real interview questions for this language."
        )
        extended_block = (
            "No pre-selected extended topics exist for this domain yet. "
            "Use your own knowledge of what's commonly asked for this role."
        )
        design_block = (
            "No pre-selected system design scenario exists for this domain yet. "
            "Use your own judgment to pick a realistic, commonly-asked scenario for this role."
        )
        behavioral_block = (
            "Using the SESSION SEED, randomly select ONE behavioral category from your knowledge "
            "of tech interviews (e.g., handling tight deadlines, strengths/weaknesses, teamwork "
            "conflicts, dealing with critical feedback, or curiosity/learning new things)."
        )

    intro_instruction = (
        "Greet the candidate briefly. Ask them to introduce themselves AND describe a recent "
        "project they are proud of. When they explain the project, ask exactly ONE follow-up "
        "question about the challenges they faced or their specific contribution to it.\n"
        + (
            "This session, go DEEPER than usual: after their first follow-up answer, ask ONE "
            "more probing question specifically about the architecture or technical decisions "
            "behind that project before moving on."
            if deep_dive_intro else
            "Keep this brief — one follow-up question is enough before moving to Phase 2."
        )
    )

    return f"""You are Sarah, a senior engineer at a real company interviewing a candidate.
You are directly controlling a live technical interview environment.

SESSION SEED: {session_seed}

CANDIDATE LANGUAGE: {language}
CANDIDATE ROLE: {role}
INTERVIEW DOMAIN: {interview_topic}
Stay strictly within this domain for all technical questions.

INTERVIEW DIFFICULTY LEVEL: {difficulty_level}
Calibrate your entire personality, expectations, and question complexity to this level:
- IF "Beginner": Be highly encouraging, forgiving, and patient. Focus heavily on textbook fundamentals.
- IF "Intermediate": Act like a standard Senior Engineer. Focus on real-world edge cases.
- IF "Hard": Act like a Staff Engineer doing a rigorous technical bar-raiser. Challenge them aggressively.

CRITICAL PACING RULE (THE ONE-QUESTION LIMIT):
You MUST ask EXACTLY ONE question per turn. 
NEVER ask two questions in a row. 
Once you ask a question, YOU MUST IMMEDIATELY STOP SPEAKING and wait for the candidate to answer.

TOTAL INTERVIEW LENGTH TARGET: 15-20 minutes. Keep every phase tight — this is a mock interview
for someone with a short attention span, not a full hour-long loop. Do not over-linger on any topic.

PHASE 1 — INTRODUCTION & PROJECT DEEP-DIVE:
{intro_instruction}
Silently list the technologies they name during this discussion.

PHASE 2 — CORE THEORY / FUNDAMENTALS:
{fundamentals_block}
For EACH topic above, follow this rhythm:
- Ask exactly ONE theoretical question about it. STOP SPEAKING.
- Listen to their answer. If shallow, drill one layer deeper on the SAME topic. If strong, move on.
Once you've covered the topics above, transition to Phase 3.

PHASE 3 — LIVE CODING / EXTENDED TECHNICAL PIPELINE (TURN-BY-TURN SEQUENCE):
{extended_block}
For EACH extended topic above, follow this STRICT rhythm:
- TURN A (You): Ask exactly ONE theoretical question about it. STOP SPEAKING.
- TURN B (Candidate): Answers your question theoretically.
- TURN C (You): Acknowledge their answer briefly — say something like "Okay, that's right, but I want you to show me practically." IN THIS EXACT SAME TURN, YOU MUST EXECUTE THE `open_code_challenge` TOOL. Do not wait for the candidate to ask for it.

REMEMBER: Use your judgment on how many of the above topics get a full practical coding round vs.
just a verbal discussion, based on time remaining and how quickly they're solving problems.

CRITICAL RULE - COMPILER MODE:
When the compiler opens, you enter COMPILER MODE:
1. NEVER ask a new interview question.
2. NEVER read the coding problem out loud. NEVER speak code out loud. NEVER solve the problem for the candidate. Just observe.
3. If the candidate stops writing and seems finished, you MUST explicitly tell them: "Please click the Submit button on your screen so I can review it."
4. You are strictly forbidden from moving to the next phase until you receive the exact system prompt: "[The candidate has just clicked SUBMIT]".

PHASE 4 — SYSTEM / ROLE DESIGN:
{design_block}
This is a verbal/conceptual discussion — the candidate talks through components and tradeoffs.
Do NOT expect code. Ask probing follow-ups about scale, failure handling, and tradeoffs.
IMPORTANT: When you transition into this phase, explicitly tell the candidate up front that this
part is a verbal/whiteboard-style discussion with NO compiler or coding involved — say something
like "For this next part, we'll just talk it through — no coding needed here." This is necessary
because the candidate just went through several rounds where every answer was followed by a coding
challenge, so without this heads-up they will reasonably expect a compiler to open again and get
confused when it doesn't.

PHASE 5 — BEHAVIORAL & CULTURAL FIT:
{behavioral_block}
Ask exactly ONE question at a time from the above. Listen to their answer, and briefly acknowledge it.

PHASE 6 — CLOSING:
Let the candidate ask you questions about the role or company. Wrap up naturally, and THEN call the `end_interview` function. 

ACTIVE LISTENING & THINKING PAUSES:
- If the candidate speaks gibberish, gets confused, or says "I don't understand", YOU MUST STOP and clarify.
- If a candidate trails off mid-sentence ("and...", "so...", "um..."), DO NOT treat it as their final answer. Respond with ONLY a short line (e.g., "Take your time, I'm listening.") and wait.
- NEVER repeat a sentence or instruction you have already said earlier in this session, even reworded.
  If you already told them the compiler is loading, already asked them to confirm they see it, or
  already said "go ahead and get started" — do NOT say any version of that again. If they seem stuck
  or confused, say something NEW and brief instead of restating what you already said.
- If the candidate mentions a compiler, asks if you can see them, or seems confused about whether a
  coding window should be open DURING A VERBAL-ONLY PHASE (like System Design or Behavioral), clearly
  and confidently tell them: "No compiler for this one — this part is just a conversation." Do not
  proceed as if nothing happened; directly address their confusion first, then continue the question.
"""

def build_playground_system_prompt(language: str, role: str, difficulty_level: str) -> str:
    """
    PLAYGROUND — merged from what used to be two separate, overlapping modes
    ("Technical Round" and "Playground"). Both were really the same mechanism
    — repeated [theory question -> live coding] rounds — differing only in:
    (a) Technical Round hard-capped at 5-6 rounds vs Playground's open-ended
    "as many as you want", and (b) Technical Round was evaluative/rigorous
    vs Playground's warm/no-judgment tone.

    Both differences are now just DIFFICULTY, reusing the same three-tier
    scheme already established for the full Real Interview:
    - Round count is ALWAYS open-ended now — never cap it, exactly like the
      old Playground — the candidate decides when to stop after each round.
    - Tone/rigor scales with difficulty_level: "Beginner" feels like the old
      warm Playground, "Hard" feels like the old rigorous Technical Round,
      "Intermediate" sits between. Topic depth uses the real weighted bucket
      pool (like Technical Round did) rather than Playground's old
      knowledge-only approach, since real topics make practice more useful
      regardless of how gently or rigorously they're delivered.
    """
    import random
    session_seed = random.randint(1, 9999)

    use_buckets = bucket_sampler.has_language(language) and bucket_sampler.has_role(role)
    interview_topic = f"{language} — {role}".strip(" —")

    if use_buckets:
        # Wide pool (not the Real Interview's k=2) since this mode can run
        # for many open-ended rounds without repeating a topic.
        fundamentals_topics = bucket_sampler.sample_fundamentals(language, k=4)
        extended_topics = bucket_sampler.sample_extended(role, k=4)
        all_topics = fundamentals_topics + extended_topics
        topics_block = (
            "PRE-SELECTED TOPIC POOL (one topic per round, do not repeat a topic within this "
            "session — if you run out, draw on your own knowledge for further rounds):\n"
            + "\n".join(f"- {t}" for t in all_topics)
        )
    else:
        topics_block = (
            "No pre-selected topics exist for this domain yet. Use your own knowledge of "
            "real, commonly-asked practical interview topics for this language/role, and "
            "don't repeat the same topic across rounds."
        )

    tone_block = {
        "Beginner": (
            "Warm, casual, encouraging - like a friendly mentor, not an evaluator. There is no "
            "passing or failing here. If they get something wrong or don't know it, respond "
            "supportively (\"no worries, that one trips up a lot of people - here's the idea...\") "
            "and move on gently. Never make them feel bad. A little genuine enthusiasm when they "
            "do something well goes a long way. Keep questions at a textbook/fundamentals level."
        ),
        "Intermediate": (
            "Like a normal senior engineer running a practice screen - friendly but honest. Give "
            "real, specific feedback (what was right, what to improve), not just encouragement. "
            "Ask real-world questions with some edge-case thinking, not pure textbook recall."
        ),
        "Hard": (
            "Like a Staff Engineer bar-raiser. Be respectful but rigorous - do not soften feedback, "
            "push on edge cases and tradeoffs, and expect real depth. This tier is for someone "
            "deliberately practicing under pressure, not looking for reassurance."
        ),
    }.get(difficulty_level, "Standard, honest, constructive feedback.")

    return f"""You are Sarah, a senior engineer running a focused, repeatable technical practice
session. This is PLAYGROUND MODE - an open-ended sequence of [theory question -> live coding]
rounds the candidate can repeat for as long as they want, at the difficulty level they chose.

SESSION SEED: {session_seed}

CANDIDATE LANGUAGE: {language}
CANDIDATE ROLE OR AREA OF INTEREST: {role}
INTERVIEW DOMAIN: {interview_topic}
Stay strictly within this domain.

DIFFICULTY LEVEL: {difficulty_level}
TONE FOR THIS SESSION: {tone_block}

CRITICAL PACING RULE (ONE-QUESTION LIMIT):
Ask EXACTLY ONE question per turn. Once you ask a question, STOP SPEAKING and wait for the answer.

STRUCTURE:

PHASE 1 - BRIEF INTRO:
Greet the candidate briefly, matching the tone above. Ask them to introduce themselves in one or
two sentences and confirm the language/role they're focusing on today. No project deep-dive - this
mode is about the practice rounds themselves. Move on quickly.

PHASE 2 - OPEN-ENDED PRACTICE ROUNDS (repeat for as long as the candidate wants):
{topics_block}
For EACH round, follow this rhythm:
- TURN A (You): Ask exactly ONE question about the round's topic, calibrated to the difficulty
  level above. STOP SPEAKING.
- TURN B (Candidate): Answers.
- TURN C (You): Acknowledge briefly, matching the tone above, then IMMEDIATELY AND SILENTLY call
  the `open_code_challenge` tool - do NOT say "I'm opening the compiler" or narrate the action
  before calling it, since the popup does not exist yet at that moment. Call the tool first,
  silently; you will receive an instruction telling you what to say once it is actually visible.
- Once the candidate submits, give feedback on their code matching the tone above.
- Then ask if they'd like to try another round or wrap up here. NEVER assume - always ask. If they
  want another, pick a new, unused topic from the pool and repeat this rhythm. There is no fixed
  number of rounds - keep going for as long as the candidate wants.

CRITICAL RULE - COMPILER MODE:
When the compiler opens, you enter COMPILER MODE:
1. NEVER ask a new question. NEVER read the problem out loud. NEVER solve it for the candidate.
2. If the candidate says they can't see the compiler, reassure them it's loading and to give it a
   moment - do NOT repeat your entire previous message, just briefly acknowledge and wait.
3. If they seem finished, remind them (matching the tone above) to hit Submit when ready.
4. Do not move on until you receive the exact system message: "[The candidate has just clicked SUBMIT]".

PHASE 3 - CLOSING:
Whenever the candidate decides to wrap up, give a brief closing note matching the tone above, then
call `end_interview`.

ACTIVE LISTENING:
- If the candidate speaks gibberish, gets confused, or says "I don't understand", STOP and clarify
  (matching the tone above - supportive at Beginner, direct at Hard).
- If a candidate trails off mid-sentence, do NOT treat it as final - say something brief and wait.
- NEVER repeat a sentence or instruction you've already said earlier in this session, even reworded.
"""


def build_config(system_prompt: str, resumption_handle=None, voice_name: str = DEFAULT_VOICE):
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
        tools=[{
            "function_declarations": (
                END_INTERVIEW_TOOL["function_declarations"]
                + OPEN_CODE_CHALLENGE_TOOL["function_declarations"]
            )
        }],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name)
            )
        ),
        session_resumption=types.SessionResumptionConfig(handle=resumption_handle),
        context_window_compression=types.ContextWindowCompressionConfig(
            sliding_window=types.SlidingWindow()
        ),
    )

@app.websocket("/media-stream")
async def handle_voice_interview(websocket: WebSocket):
    await websocket.accept()
    print("🎙️ Client connected to local server websocket!")

    init_message = await websocket.receive_text()
    try:
        init_data = json.loads(init_message)
        mode = init_data.get("mode", "real").strip().lower()
        language = init_data.get("language", "").strip()
        role = init_data.get("role", "").strip()
        difficulty_level = init_data.get("difficulty", "Intermediate").strip()
        voice = init_data.get("voice", DEFAULT_VOICE).strip()
    except json.JSONDecodeError:
        mode = "real"
        language = "general"
        role = "software engineering"
        difficulty_level = "Intermediate"
        voice = DEFAULT_VOICE

    if voice not in VOICES:
        print(f"⚠️ Unknown voice '{voice}' requested — falling back to {DEFAULT_VOICE}.")
        voice = DEFAULT_VOICE

    print(f"📋 Mode: {mode} | Language: {language} | Role: {role} | Level: {difficulty_level} | Voice: {voice}")

    if mode == "playground":
        system_prompt = build_playground_system_prompt(language, role, difficulty_level)
    else:
        system_prompt = build_system_prompt(language, role, difficulty_level)

    resumption_handle = None
    interview_ended = False
    needs_opening_trigger = True
    code_challenge_open = False

    candidate_buffer = []
    ai_buffer = []
    transcript_log = []

    def flush_candidate():
        if candidate_buffer:
            line = "".join(candidate_buffer).strip()
            if line:
                print(f"🧑 Candidate: {line}")
                transcript_log.append(("candidate", line))
            candidate_buffer.clear()

    def flush_ai():
        if ai_buffer:
            line = "".join(ai_buffer).strip()
            if line:
                print(f"🤖 Interviewer: {line}")
                transcript_log.append(("interviewer", line))
            ai_buffer.clear()

    while True:
        go_away_triggered = False
        try:
            async with client.aio.live.connect(
                model=MODEL, config=build_config(system_prompt, resumption_handle, voice)
            ) as session:
                print("⚡ Connected to Gemini Live!")

                if needs_opening_trigger:
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=(
                                "[SYSTEM: The candidate has just joined the call. Nothing has "
                                "been said yet. Begin the interview now: greet them warmly and "
                                "start Phase 1 as instructed in your system prompt.]"
                            ))],
                        ),
                        turn_complete=True,
                    )
                    needs_opening_trigger = False
                else:
                    # BUGFIX: after a reconnect (e.g. GoAway), explicitly restate whether the
                    # compiler is currently open or closed. Without this, Gemini has no reliable
                    # signal after reconnecting and candidates get told confusing/contradictory
                    # things about a compiler that isn't actually open (or vice versa).
                    state_reminder = (
                        "[INTERNAL SYSTEM DIRECTIVE — RECONNECTED]: Your connection was silently "
                        "refreshed. Continue the interview exactly where you left off — do NOT "
                        "greet the candidate again or restart any phase. "
                        + (
                            "The coding compiler IS CURRENTLY OPEN and visible to the candidate — "
                            "you are still in COMPILER MODE. Do not ask a new question; wait for "
                            "their submission."
                            if code_challenge_open else
                            "The coding compiler is CURRENTLY CLOSED — you are in a verbal/discussion "
                            "phase. If the candidate mentions a compiler or says they can't see it, "
                            "clarify that no coding exercise is open right now and continue the "
                            "verbal discussion."
                        )
                    )
                    await session.send_client_content(
                        turns=types.Content(
                            role="user",
                            parts=[types.Part(text=state_reminder)],
                        ),
                        turn_complete=True,
                    )

                async def stream_ai_to_browser():
                    nonlocal resumption_handle, go_away_triggered, interview_ended, code_challenge_open
                    while True:
                        async for response in session.receive():
                            if response.session_resumption_update:
                                update = response.session_resumption_update
                                if update.resumable and update.new_handle:
                                    resumption_handle = update.new_handle

                            if response.go_away:
                                print(f"⚠️ GoAway received, {response.go_away.time_left} left. Reconnecting...")
                                go_away_triggered = True
                                return

                            if response.tool_call:
                                for fc in response.tool_call.function_calls:
                                    if fc.name == "end_interview":
                                        print("🏁 AI called end_interview — wrapping up session.")
                                        interview_ended = True
                                        await session.send_tool_response(
                                            function_responses=[
                                                types.FunctionResponse(
                                                    id=fc.id,
                                                    name=fc.name,
                                                    response={"status": "ended"},
                                                )
                                            ]
                                        )

                                    elif fc.name == "open_code_challenge":
                                        context_summary = fc.args.get("context_summary", "")

                                        if code_challenge_open:
                                            print("🚫 open_code_challenge blocked — a challenge is already open and unsubmitted.")
                                            await session.send_tool_response(
                                                function_responses=[
                                                    types.FunctionResponse(
                                                        id=fc.id,
                                                        name=fc.name,
                                                        response={
                                                            "status": "blocked_challenge_already_open",
                                                            "instruction": (
                                                                "A coding challenge is still open. Remember COMPILER MODE rules. "
                                                                "Wait for the candidate to click submit or tell them to click submit."
                                                            ),
                                                        },
                                                    )
                                                ]
                                            )
                                            continue

                                        print(f"\n🧩 AI called open_code_challenge!")
                                        print(f"   context_summary: {context_summary}\n")

                                        code_challenge_open = True

                                        # BUGFIX: tell the browser to show the loading spinner FIRST,
                                        # before Gemini is told the tool succeeded. Previously the tool
                                        # response went out first, which let Gemini start narrating
                                        # ("opening the compiler now...") before the frontend had even
                                        # begun rendering the popup — causing the "I can't see the
                                        # compiler" desync during the Groq generation gap.
                                        await websocket.send_text(json.dumps({
                                            "type": "code_challenge_loading"
                                        }))

                                        # Changed from a dialogue script to a strict internal state directive
                                        setup_instruction = (
                                            "[INTERNAL SYSTEM DIRECTIVE]: Tool executed successfully. The compiler popup "
                                            "is now visibly loading on the candidate's screen. "
                                            "ACTION REQUIRED: Stop speaking immediately. Do NOT ask a question. Do NOT "
                                            "narrate that you are opening anything further — it is already open and loading. "
                                            "Wait silently until you receive the next system directive."
                                        )
                                        await session.send_tool_response(
                                            function_responses=[
                                                types.FunctionResponse(
                                                    id=fc.id,
                                                    name=fc.name,
                                                    response={
                                                        "status": "setting_up",
                                                        "instruction": setup_instruction,
                                                    },
                                                )
                                            ]
                                        )

                                        try:
                                            problem = await asyncio.to_thread(
                                                generate_coding_problem, context_summary
                                            )
                                            print("🧩 Groq generated problem:")
                                            print(f"   Title:      {problem.get('title')}")
                                            print(f"   Language:   {problem.get('language')}")
                                            print(f"   Difficulty: {problem.get('difficulty')}")
                                            print(f"   Description: {problem.get('description')}")
                                            print(f"   Starter code:\n{problem.get('starter_code')}\n")

                                            await websocket.send_text(json.dumps({
                                                "type": "code_challenge",
                                                "problem": problem,
                                            }))

                                            # Changed from a dialogue script to a strict internal state directive
                                            ready_instruction = (
                                                "[INTERNAL SYSTEM DIRECTIVE]: The problem generated by the system is now visible to the candidate. "
                                                "ACTION REQUIRED: Briefly ask the candidate to confirm they see the problem and remind them to think out loud. "
                                                "CRITICAL: Do NOT read the problem to them. Do NOT ask any new technical questions."
                                            )
                                            await session.send_client_content(
                                                turns=types.Content(
                                                    role="user",
                                                    parts=[types.Part(text=f"{ready_instruction}")],
                                                ),
                                                turn_complete=True,
                                            )
                                        except Exception as groq_error:
                                            print(f"⚠️ Groq problem generation failed: {groq_error}")
                                            code_challenge_open = False
                                            await websocket.send_text(json.dumps({
                                                "type": "code_challenge_failed"
                                            }))
                                            fail_instruction = (
                                                "[INTERNAL SYSTEM DIRECTIVE]: Problem generation failed. Apologize briefly, tell "
                                                "the candidate the coding exercise isn't available "
                                                "right now, and continue the interview verbally "
                                                "instead — ask your next practical question."
                                            )
                                            await session.send_client_content(
                                                turns=types.Content(
                                                    role="user",
                                                    parts=[types.Part(text=f"{fail_instruction}")],
                                                ),
                                                turn_complete=True,
                                            )

                            server_content = response.server_content

                            if server_content:
                                if server_content.input_transcription and server_content.input_transcription.text:
                                    candidate_buffer.append(server_content.input_transcription.text)
                                if server_content.output_transcription and server_content.output_transcription.text:
                                    frag = server_content.output_transcription.text
                                    
                                    if not ai_buffer or "".join(ai_buffer).strip() != frag.strip():
                                        if ai_buffer and not frag.startswith(" ") and not ai_buffer[-1].endswith(" "):
                                            ai_buffer.append(" " + frag)
                                        else:
                                            ai_buffer.append(frag)

                                if server_content.turn_complete:
                                    flush_ai()
                                    flush_candidate()

                                if server_content.interrupted:
                                    flush_ai()

                            if server_content and server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data:
                                        await websocket.send_bytes(part.inline_data.data)

                            if interview_ended and server_content and server_content.turn_complete:
                                return

                async def stream_browser_to_ai():
                    nonlocal code_challenge_open
                    while True:
                        message = await websocket.receive()

                        if "bytes" in message and message["bytes"] is not None:
                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=message["bytes"], mime_type="audio/pcm;rate=16000"
                                )
                            )

                        elif "text" in message and message["text"] is not None:
                            try:
                                payload = json.loads(message["text"])
                            except json.JSONDecodeError:
                                continue

                            if payload.get("type") == "code_submission":
                                submitted_code = payload.get("code", "")
                                print(f"\n📝 Candidate submitted code:\n{submitted_code}\n")

                                code_challenge_open = False

                                await session.send_client_content(
                                    turns=types.Content(
                                        role="user",
                                        parts=[types.Part(text=(
                                            "[SYSTEM: The candidate has just clicked SUBMIT on their code. "
                                            "They are officially done with this exercise. Here is their code:]\n\n"
                                            f"{submitted_code}\n\n"
                                            "[SYSTEM: You are no longer in Compiler Mode. Acknowledge the submission, "
                                            "briefly evaluate their code, and move on to the next topic.]"
                                        ))],
                                    ),
                                    turn_complete=True,
                                )

                ai_task = asyncio.create_task(stream_ai_to_browser())
                mic_task = asyncio.create_task(stream_browser_to_ai())

                done, pending = await asyncio.wait(
                    [ai_task, mic_task], return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                for task in done:
                    if task.exception():
                        raise task.exception()

            if interview_ended:
                break 
            elif go_away_triggered:
                continue
            else:
                break

        except WebSocketDisconnect:
            print("👋 Student disconnected or closed tab.")
            break
        except Exception as e:
            print(f"⚠️ Gemini voice connection dropped (Error: {e}). Auto-reconnecting in 1 second...")
            await asyncio.sleep(1)
            continue

    flush_ai()
    flush_candidate()

    if transcript_log:
        print("\n" + "=" * 60)
        print("FULL INTERVIEW TRANSCRIPT")
        print("=" * 60)
        for speaker, line in transcript_log:
            label = "Candidate" if speaker == "candidate" else "Interviewer"
            print(f"[{label}] {line}")
        print("=" * 60 + "\n")

    if interview_ended:
        try:
            await websocket.send_text("__INTERVIEW_ENDED__")
        except Exception:
            pass

    try:
        await websocket.close()
    except Exception:
        pass

    print("Session fully closed.")