import os
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from dotenv import load_dotenv
from Problem_Task import generate_coding_problem

load_dotenv()

app = FastAPI()

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
                "CRITICAL: Call this tool IMMEDIATELY after evaluating the candidate's theoretical answer. "
                "You MUST execute this tool to physically open the compiler. Do not wait for the candidate to ask for it. "
                "Execute it in the exact same turn that you say you are opening it."
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

def build_system_prompt(interview_topic: str, difficulty_level: str) -> str:
    import random
    session_seed = random.randint(1, 9999)

    return f"""You are Sarah, a senior engineer at a real company interviewing a candidate.
You are directly controlling a live technical interview environment.

SESSION SEED: {session_seed}
Use this seed to bias the topics and behavioral questions you choose so different sessions are unique.

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

PHASE 1 — INTRODUCTION & PROJECT DEEP-DIVE:
Greet the candidate briefly. Ask them to introduce themselves AND describe a recent project they are proud of.
When they explain the project, ask exactly ONE follow-up question about the challenges they faced or their specific contribution to it.
Silently list the technologies they name during this discussion. Do not move to Phase 2 until you have 2-3 specific technologies.

PHASE 2 — THE 80/20 PRACTICAL PIPELINE (TURN-BY-TURN SEQUENCE):
For EACH technology or concept from your mental list, follow this STRICT rhythm:
- TURN A (You): Ask exactly ONE theoretical question. STOP SPEAKING.
- TURN B (Candidate): Answers your question theoretically.
- TURN C (You): Acknowledge their answer briefly. IN THIS EXACT SAME TURN, YOU MUST EXECUTE THE `open_code_challenge` TOOL. Do not wait for the candidate to ask for it. Say "Let's test that in practice," and trigger the tool immediately.

REMEMBER: Use your intelligence to determine how many coding questions are needed to properly evaluate the candidate, just like a real company would. Typically, this means choosing between 2 to 4 practical problems based on how quickly they solve them.

CRITICAL RULE - COMPILER MODE:
When the compiler opens, you enter COMPILER MODE:
1. NEVER ask a new interview question.
2. NEVER read the coding problem out loud. NEVER speak Python code out loud. NEVER solve the problem for the candidate. Just observe.
3. If the candidate stops writing and seems finished, you MUST explicitly tell them: "Please click the Submit button on your screen so I can review it."
4. You are strictly forbidden from moving to the next phase until you receive the exact system prompt: "[The candidate has just clicked SUBMIT]".

PHASE 3 — BEHAVIORAL & CULTURAL FIT:
After going through 2-3 practical coding exercises, you must assess their soft skills. 
Using the SESSION SEED, randomly select ONE behavioral category from your infinite knowledge of tech interviews (e.g., handling tight deadlines, strengths/weaknesses, teamwork conflicts, dealing with critical feedback, or curiosity/learning new things).
Ask exactly ONE scenario-based or reflection question from that category. Listen to their answer, and briefly acknowledge it.

PHASE 4 — CLOSING:
After the behavioral question, let the candidate ask you questions about the role or company. Wrap up naturally, and THEN call the `end_interview` function. 

ACTIVE LISTENING & THINKING PAUSES:
- If the candidate speaks gibberish, gets confused, or says "I don't understand", YOU MUST STOP and clarify.
- If a candidate trails off mid-sentence ("and...", "so...", "um..."), DO NOT treat it as their final answer. Respond with ONLY a short line (e.g., "Take your time, I'm listening.") and wait.
"""

def build_config(system_prompt: str, resumption_handle=None):
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
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon")
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
        interview_topic = init_data.get("topic", "general software engineering").strip()
        difficulty_level = init_data.get("difficulty", "Intermediate").strip()
    except json.JSONDecodeError:
        interview_topic = init_message.strip() or "general software engineering"
        difficulty_level = "Intermediate"

    print(f"📋 Topic: {interview_topic} | Level: {difficulty_level}")

    system_prompt = build_system_prompt(interview_topic, difficulty_level)
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
                model=MODEL, config=build_config(system_prompt, resumption_handle)
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

                                        # Changed from a dialogue script to a strict internal state directive
                                        setup_instruction = (
                                            "[INTERNAL SYSTEM DIRECTIVE]: Tool executed successfully. The compiler is loading. "
                                            "ACTION REQUIRED: Stop speaking immediately. Do NOT ask a question. Wait silently."
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

                                        await websocket.send_text(json.dumps({
                                            "type": "code_challenge_loading"
                                        }))

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