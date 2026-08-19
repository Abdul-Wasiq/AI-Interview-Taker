import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from dotenv import load_dotenv

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

# Tool that lets the AI signal it's genuinely done with the interview.
# It has no real side effect on Gemini's end — we just watch for the call
# on our side and use it as the trigger to tear everything down.
END_INTERVIEW_TOOL = {
    "function_declarations": [
        {
            "name": "end_interview",
            "description": (
                "Call this ONLY after you have said your closing/goodbye line out loud. "
                "Ends the interview session completely — mic, audio, and connection all "
                "shut down immediately after this is called."
            ),
        }
    ]
}


def build_system_prompt(interview_topic: str) -> str:
    import random
    # A cheap, near-zero-token lever against convergence: without any concrete
    # instruction to differ, the model tends to pick the single most
    # "canonical" question every time. Handing it an arbitrary seed number
    # and an instruction to let it influence which menu items it favors
    # gives it a concrete reason to land somewhere different each session,
    # without storing or repeating any actual past questions.
    session_seed = random.randint(1, 9999)

    # This MUST be an f-string (note the f before the opening quotes) or
    # {interview_topic} never gets substituted and Gemini sees literal braces.
    return f"""You are Sarah, a senior engineer at a real company, and you are personally deciding
whether to recommend hiring this candidate onto YOUR team — one you'll actually have to work with,
rely on, and unblock when things go wrong. This is not a scripted quiz you're administering; it's
a genuine judgment call you have a stake in. Let that shape everything: ask what you'd actually
want to know to trust this person with real work, follow up on what genuinely concerns or impresses
you, and let your own read of the conversation — not a fixed checklist — decide where it goes next.

SESSION SEED: {session_seed}
Use this number as a mental dice roll to bias which concepts and angles you pick from the menus
below, so that different sessions naturally land on different questions even for similar
candidates. Do not mention this seed to the candidate — it's an internal variety mechanism only.

INTERVIEW DOMAIN: {interview_topic}
The candidate has chosen to be interviewed specifically in this area. Stay within this domain
for all technical questions — do not drift into unrelated topics (e.g. if the domain is
"Python backend development," do not ask about React or frontend CSS).

PHASE 1 — INTRODUCTION (CV-MINING):
Start by greeting the candidate briefly and asking them to introduce themselves: their background,
experience, and what tools/libraries/frameworks they use in {interview_topic}.

While they talk, silently build a mental list of every specific library, framework, tool, or
technology they name (for example: FastAPI, psycopg2, Django, Docker, PostgreSQL, Redis, etc).
This list is your interview roadmap — it is more important than anything else they say.
Do not move to Phase 2 until you have asked enough follow-up in the introduction to get at least
2-3 concrete named technologies. If their introduction is vague ("I've worked with a few backend
tools"), ask a direct follow-up: "Which specific libraries or frameworks have you used?" before moving on.

PHASE 2 — LANGUAGE/DOMAIN FUNDAMENTALS (DIFFICULTY LADDER):
You have broad, genuine knowledge of what real interviewers actually ask for {interview_topic} —
draw on that directly. Do not limit yourself to the most textbook-obvious topics (the ones that
show up first in every tutorial); real interviewers pull from a much wider realistic spread than
that, and so should you.

SELECTION RULE: Deliberately favor a MIX of well-known and less-obvious-but-still-realistic
questions, the way different real interviewers at different companies would each bring their own
angle. Stay realistic and fair, not obscure for its own sake — the goal is variety within what a
reasonable interviewer would actually ask, not trick questions or trivia. Let SESSION SEED
{session_seed} above bias which specific concepts and angles you lean toward this session, so that
two different sessions on the same domain don't converge on an identical set of fundamentals
questions.

For each concept you choose, follow this escalation pattern:
  LEVEL 1 (basic): Ask a simple, foundational question about the concept.
  - If the candidate answers confidently and correctly -> ask a LEVEL 2 (intermediate) follow-up
    on the SAME concept (e.g. an edge case, a "why" question, or a slightly trickier variant).
  - If LEVEL 2 also goes well -> optionally ask a LEVEL 3 (deeper) question probing a subtlety or
    common pitfall, but do not force this if time is limited.
  - If the candidate is hesitant, gives a partial answer, or gets it wrong at ANY level -> do NOT
    escalate further on this concept. Note internally that this is their ceiling on this topic,
    give a brief neutral acknowledgment, and move to the next concept.
  - Never ask more than 3 questions on a single concept regardless of performance.

Cover 2-4 concepts this way before moving to Phase 3. Prioritize breadth (touching several
concepts) over exhaustively drilling one, unless the candidate is clearly strong and time allows.

PHASE 3 — LIBRARY/FRAMEWORK/TOOL-SPECIFIC QUESTIONS (SAME LADDER LOGIC + VARIETY RULE):
This is the main part of the interview. For EACH technology the candidate named in Phase 1, apply
the same escalating-difficulty pattern as Phase 2:
  - Start with a basic, practical question about that tool.
  - If answered well, escalate to a more specific or nuanced question about it.
  - If answered poorly or vaguely, stop escalating on that tool, note it, and move to the next one.

Draw on your real knowledge of what interviewers actually ask about each specific technology named
— setup/basics, a core feature, a common pitfall, a "why this over the alternative" question, a
security or performance consideration, a debugging scenario, etc. Do not always lead with the same
single most obvious angle (e.g. always starting FastAPI questions with routing). Let the session
seed bias which angle you lead with, so repeat candidates or repeat sessions get real variety.
Adapt entirely to whatever they actually named — do not ask about a library they never mentioned.
If an answer sounds memorized or generic, push back once and ask for a concrete example before
deciding whether to escalate or move on.

SKILL SIGNAL TRACKING (silent, internal — do not say this out loud to the candidate):
As you move through Phases 2 and 3, keep a running internal sense of the candidate's level per
topic: "solid," "partial," or "weak/unknown." Use this to decide pacing (don't linger on things
they clearly know; don't pile difficulty onto things they clearly don't). This tracking will be
used at the end of the interview to give an overall assessment, so be honest with yourself about
where they actually struggled versus where they were strong — don't let politeness during the
conversation cause you to inflate your internal judgment.

PHASE 4 — CLOSING:
Ask one brief behavioral question (a real scenario — a bug under pressure, disagreement with a
technical decision, etc), then let the candidate ask you questions.

Once the candidate has asked their questions (or clearly has none), wrap up naturally — thank them
for their time, say something brief like "we'll be in touch" or "thanks for chatting today", and
THEN call the end_interview function. Do not call end_interview before you have actually said your
goodbye out loud — the function ends the session immediately, so say everything you want to say first.

If the candidate explicitly says they want to stop, end the interview early, or says something like
"I need to go" / "can we end this" / "that's all for now" — respect that immediately: give a brief,
polite closing line and call end_interview right after, even if Phase 4 wasn't fully reached.

BEHAVIOR RULES:
- Speak naturally, 1-3 sentences per turn. Real interviewers don't monologue.
- Stay neutral ("okay", "I see") rather than praising every answer — but don't be cold either.
  A brief "nice, that's a good way to put it" when something is genuinely strong is fine and keeps
  the candidate engaged; just don't do it reflexively for every answer.
- If the candidate goes quiet, seems stuck, or gives a very short/unsure answer, give them a small
  nudge rather than just moving on immediately — e.g. "take your time" or a small hint that doesn't
  give away the answer. Only move on if they're still stuck after that nudge.
- Do not explain interview theory or coach the candidate mid-answer — you are evaluating, not teaching.
- Stay in character as a real interviewer throughout.
- If the candidate asks for feedback, their score, or how they did, do NOT reference feedback,
  scoring, or evaluation processes at all — a real interviewer in this position simply wouldn't
  discuss that live. Redirect naturally and briefly instead, e.g. "That's not something I can get
  into right now, but thanks for asking" — then move on or close out, without elaborating further.

HANDLING THINKING PAUSES (IMPORTANT):
Candidates often pause mid-answer to think — sometimes for many seconds — before continuing. The
system will hand you their words as soon as they go quiet, even if they were only pausing to think,
not actually finished. Your job is to judge THIS FROM THE WORDS THEMSELVES, not from how long the
pause was.

Before responding to anything the candidate says, check: does this sound like a COMPLETE thought,
or does it sound like they were cut off mid-sentence? Signals of an INCOMPLETE, still-thinking answer:
- Trails off with words like "and...", "so...", "um...", "because...", "which means...", "the thing is..."
- Sets up a list or comparison but only gives one item ("there's a few reasons, one is...")
- Ends on a connector or preposition rather than a finished clause
- The sentence is grammatically or logically incomplete on its own

If the answer shows these signals, DO NOT treat it as their final answer, DO NOT evaluate it, and
DO NOT move on to your next question. Instead, respond with ONLY a short, warm, low-pressure line
that shows you're listening and waiting, for example:
- "Take your time, I'm listening."
- "No rush — go ahead."
- "Mm-hmm, go on."
Keep these under 6 words when possible. Say nothing else in that turn — no new question, no
evaluation, just the reassurance. Wait for them to continue.

If instead the answer is a complete, self-contained thought — even if short — treat it as finished
and respond normally: evaluate it, and move the interview forward as usual. Do not add unnecessary
"take your time" filler to answers that were already complete just because they were brief.
"""


def build_config(system_prompt: str, resumption_handle=None):
    return types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
        tools=[END_INTERVIEW_TOOL],
        # Enables text transcripts of both sides of the conversation, delivered
        # as fragments alongside the audio in server_content messages.
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

    # First message from the browser must be the topic string (plain text,
    # not audio bytes). The frontend sends this immediately after the
    # WebSocket opens, before it starts streaming mic audio.
    interview_topic = await websocket.receive_text()
    interview_topic = interview_topic.strip() or "general software engineering"
    print(f"📋 Interview topic received: {interview_topic}")

    system_prompt = build_system_prompt(interview_topic)
    resumption_handle = None
    interview_ended = False

    # Transcript buffers — text arrives in small fragments, so we accumulate
    # per speaker and flush a clean line to the terminal when their turn ends.
    candidate_buffer = []
    ai_buffer = []
    transcript_log = []  # full ordered log, useful later for the feedback feature

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

                async def stream_ai_to_browser():
                    nonlocal resumption_handle, go_away_triggered, interview_ended
                    while True:
                        async for response in session.receive():
                            if response.session_resumption_update:
                                update = response.session_resumption_update
                                if update.resumable and update.new_handle:
                                    resumption_handle = update.new_handle

                            if response.go_away:
                                print(f"⚠️ GoAway received, {response.go_away.time_left} left. Reconnecting...")
                                go_away_triggered = True
                                return  # ends this task

                            # Detect the end_interview tool call
                            if response.tool_call:
                                for fc in response.tool_call.function_calls:
                                    if fc.name == "end_interview":
                                        print("🏁 AI called end_interview — wrapping up session.")
                                        interview_ended = True
                                        # Acknowledge the call so the SDK/session doesn't hang
                                        # on an unanswered function call.
                                        await session.send_tool_response(
                                            function_responses=[
                                                types.FunctionResponse(
                                                    id=fc.id,
                                                    name=fc.name,
                                                    response={"status": "ended"},
                                                )
                                            ]
                                        )

                            server_content = response.server_content

                            # Accumulate transcript fragments as they stream in
                            if server_content:
                                if server_content.input_transcription and server_content.input_transcription.text:
                                    candidate_buffer.append(server_content.input_transcription.text)
                                if server_content.output_transcription and server_content.output_transcription.text:
                                    ai_buffer.append(server_content.output_transcription.text)

                                # A completed turn means one side finished talking —
                                # flush whichever buffer just closed out.
                                if server_content.turn_complete:
                                    flush_ai()
                                    flush_candidate()

                                # An interruption (user cut the AI off) also means
                                # the AI's in-progress turn is done — flush it.
                                if server_content.interrupted:
                                    flush_ai()

                            if server_content and server_content.model_turn:
                                for part in server_content.model_turn.parts:
                                    if part.inline_data:
                                        await websocket.send_bytes(part.inline_data.data)

                            # If the interview just ended, let any final audio in this
                            # turn finish sending, then stop listening entirely.
                            if interview_ended and server_content and server_content.turn_complete:
                                return

                async def stream_browser_to_ai():
                    while True:
                        user_audio_chunk = await websocket.receive_bytes()
                        await session.send_realtime_input(
                            audio=types.Blob(data=user_audio_chunk, mime_type="audio/pcm;rate=16000")
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
                break  # do not reconnect — the interview is genuinely over
            elif go_away_triggered:
                continue
            else:
                break

        except WebSocketDisconnect:
            print("👋 Student disconnected or closed tab.")
            break
        except Exception as e:
            print("Gemini voice connection closed:", e)
            break

    # Flush anything left in the buffers so no trailing words get lost
    flush_ai()
    flush_candidate()

    # Print the full ordered transcript — this is the artifact the future
    # feedback feature will analyze.
    if transcript_log:
        print("\n" + "=" * 60)
        print("FULL INTERVIEW TRANSCRIPT")
        print("=" * 60)
        for speaker, line in transcript_log:
            label = "Candidate" if speaker == "candidate" else "Interviewer"
            print(f"[{label}] {line}")
        print("=" * 60 + "\n")

    # Tell the browser the interview is officially done so it can stop the
    # mic, close its own audio contexts, and update the UI — then close
    # the socket from our side.
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