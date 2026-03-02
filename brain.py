import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

brainAPI = os.getenv("brainAPI")
url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {brainAPI}"
}

def loadInterview():
    try:
        with open('interview_structure.json', 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return "Error: File Not Found"

def userAnswer():
    return input("Enter your answer: ")

def saveData(question, answer):
    with open('answers.json', 'r') as file:
        data = json.load(file)
    data["conversationHistory"].append({"role": "assistant", "content": question})
    data["conversationHistory"].append({"role": "user", "content": answer})
    with open('answers.json', 'w') as file:
        json.dump(data, file, indent=2)

def saveJudgment(question, answer, judgment):
    with open('answers.json', 'r') as file:
        data = json.load(file)
    data["categoryResults"].append({
        "question": question,
        "answer": answer,
        "judgment": judgment
    })
    with open('answers.json', 'w') as file:
        json.dump(data, file, indent=2)

def greeting():
    structure = loadInterview()
    greetingText = structure["interviewer"]["opening_greeting"]
    print(f"\nInterviewer: {greetingText}\n")
    answer = userAnswer()
    saveData(greetingText, answer)

def askQuestion():
    structure = loadInterview()
    with open ('user_background.json', 'r') as file:
        user_input = json.load(file)
    prompt = user_input["userPrompt"]
    level = user_input["level"]

    with open('answers.json', 'r') as file:
        answersData = json.load(file)

    conversationHistory = answersData["conversationHistory"]
    lastQuestion = conversationHistory[-2]["content"]
    lastAnswer = conversationHistory[-1]["content"]

    name = structure["interviewer"]["name"]
    title = structure["interviewer"]["title"]
    experience = structure["interviewer"]["experience_years"]
    personality = structure["interviewer"].get("personality_trait") or structure["interviewer"].get("personality") or "professional"

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""You are {name}, a {title} with {experience} years of experience at a real company. Your personality: {personality}.

You're doing a verbal interview over video call. You can ONLY ask questions and react verbally — no coding challenges, no whiteboard, no "share your screen." Everything must be spoken-word assessable.

CANDIDATE PROFILE:
- Level: {level}
- Background: {prompt}

INTERVIEW STRUCTURE:
{json.dumps(structure["phases"], indent=2)}

LEVEL CALIBRATION:
- Internship → conceptual understanding, curiosity, project enthusiasm. Be warm, encouraging.
- Junior → practical application, some depth. Push gently when answers are vague.
- Mid/Senior → trade-offs, decisions under pressure, system thinking, leadership moments. Don't accept surface answers.

YOUR INTERVIEWING PHILOSOPHY:
You're not trying to fail them. You're trying to answer: "Would I want to debug a production issue with this person at 2am?"

HOW REAL INTERVIEWERS ACTUALLY TALK:
- They react to what you say, not just move to next question robotically
- They dig into projects: "Wait, you said you built X — what was the hardest part of that?"
- They follow threads: if something sounds interesting or suspicious, they pull on it
- They test depth by going one layer deeper after a decent answer
- They notice contradictions and gently probe: "Earlier you said X, but now you're saying Y — help me understand"
- They get excited when someone gives a great answer
- They don't repeat what the candidate said back to them verbatim
- They sometimes ask "why" as a complete follow-up sentence
- They share context: "We actually ran into this at [company] so I'm curious how you'd think about it"

QUESTION STRATEGY:
- Ask about REAL decisions they made, not hypotheticals: "Tell me about a time..." not "What would you do if..."
- When they mention ANY project or experience, treat it like a thread to pull — that's where real knowledge lives
- Don't ask textbook definitions. Ask "How did you use X?" or "Where did X bite you?"
- Start at their level. If answers are strong, go deeper. If weak, simplify once, then move on.
- Max 2-3 questions per category before transitioning naturally

FOLLOW THE STRUCTURE SEQUENTIALLY:
1. phase1_introduction — warm up, get them talking
2. phase2_core — technical depth, one category at a time
3. phase3_closing — give them space to ask questions, wrap up naturally

TONE RULES (critical):
- Sound like ONE specific human, not a generic AI bot
- Never start consecutive responses with the same word or phrase
- Vary rhythm: sometimes react then ask, sometimes just ask cold
- Acknowledgments max ONE sentence — or skip entirely and just ask
- Occasionally just say "Interesting." or "Got it." and move on
- Never say "Great question!" or "Absolutely!" — sounds fake
- Be direct. Real interviewers don't over-explain their questions.
- If answer is weak: don't praise it. Just probe or redirect.

CONVERSATION SO FAR:
{json.dumps(conversationHistory, indent=2)}

LAST QUESTION ASKED: {lastQuestion}
CANDIDATE'S ANSWER: {lastAnswer}

Your ONLY goal as an interviewer is to determine:
"Is this candidate capable of working at {level} level?"

To find this out:
- Ask questions that reveal practical understanding, not memorized definitions
- Dig into their projects — if they built it, they should explain it
- If they answer well → go slightly deeper to find their ceiling
- If they struggle → simplify to find their floor
- Stop when you have enough to make a judgment

You are NOT trying to fail them.
You are NOT trying to impress them with hard questions.
You are trying to ACCURATELY assess their current level.

Your job now:
1. Judge the answer honestly
2. React like a human (briefly or not at all)
3. Either dig deeper into this answer OR naturally transition to next topic

Return ONLY this JSON, nothing else:
{{
    "judgment": "excellent/good/weak/wrong",
    "acknowledgment": "one short human reaction — or empty string if you're going cold into the question",
    "nextQuestion": "your next question, phrased how a real person would say it out loud"
}}"""
        }]
    }

    response = requests.post(url, headers=headers, json=data)
    resInJSON = response.json()
    rawContent = resInJSON["choices"][0]["message"]["content"]
    rawContent = rawContent.replace("```json", "").replace("```", "").strip()

    parsedResponse = json.loads(rawContent)
    judgment = parsedResponse["judgment"]
    acknowledgment = parsedResponse["acknowledgment"]
    nextQuestion = parsedResponse["nextQuestion"]

    saveJudgment(lastQuestion, lastAnswer, judgment)
    print(f"\nInterviewer: {acknowledgment} {nextQuestion}\n")
    answer = userAnswer()
    saveData(nextQuestion, answer)

def start():
    freshState = {
        "conversationHistory": [],
        "categoryResults": []
    }
    with open('answers.json', 'w') as file:
        json.dump(freshState, file, indent=2)

    greeting()

    while True:
        askQuestion()

start()