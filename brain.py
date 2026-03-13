import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()


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

apis = [os.getenv("api1"), os.getenv("api2"), os.getenv("api3"), os.getenv("api4"), os.getenv("api5"), os.getenv("api6"),os.getenv("api7"),os.getenv("api8"),os.getenv("api9"),os.getenv("api10")]

def getCurrAPI():
    with open('api_data.json', 'r') as file:
        data = json.load(file)

    return data['index']

def rotateAPI(currIndx):
    newIndx = (currIndx + 1) % len(apis)
    with open('api_data.json', 'w') as file:
        json.dump({"api": f"api{newIndx+1}", "index": newIndx}, file)
    print(f"[DEV_BACKEND]: ROTATE! NOW USING API{newIndx + 1}")

def makeRequest(url, headers, data):
    """Make request, auto-rotate if rate limited, retry up to 10 times"""
    for attempt in range(len(apis)):
        currIndx = getCurrAPI()
        brainAPI = apis[currIndx]
        
        headers["Authorization"] = f"Bearer {brainAPI}"
        
        response = requests.post(url, headers=headers, json=data)
        resInJSON = response.json()
        
        if "choices" in resInJSON:
            # Success! Also check if tokens are getting low for NEXT call
            remainingTokens = int(response.headers.get("x-ratelimit-remaining-tokens", 99999))
            if remainingTokens < 5000:
                print(f"[DEV_BACKEND]: API{currIndx+1} low on tokens, rotating for next call...")
                rotateAPI(currIndx)
            return resInJSON
        else:
            print(f"[DEV_BACKEND]: API{currIndx+1} failed ({resInJSON.get('error', {}).get('message', 'unknown error')}), rotating...")
            rotateAPI(currIndx)
    
    raise Exception("All APIs exhausted. Try again later.")

def askQuestion(questionCount):
    
    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": ""
    }

    structure = loadInterview()
    with open ('user_background.json', 'r') as file:
        user_input = json.load(file)
    prompt = user_input["userPrompt"]
    level = user_input["level"]

    
    with open('answers.json', 'r') as file:
        answersData = json.load(file)
    
    # last 6 questions and answers
    conversationHistory = answersData["conversationHistory"][-16:]
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
        }}
                QUESTION TRACKING:
        - You have asked {questionCount} out of 9 questions
        - Questions remaining: {9 - questionCount}
        - DISTRIBUTE questions across phases:
        * phase1_introduction: questions 1-2
        * phase2_core: questions 3-8
        * phase3_closing: question 9
        - YOU MUST cover all phases — do not spend too many questions on one topic
        """
        }]
    }

    resInJSON = makeRequest(url, headers, data) # same as requests.post()
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

    if (parsedResponse.get("end") == True):
        print(f"\nInterviewer: {parsedResponse['acknowledgment']} \n")
        return True

def closeInterview():
    url = "https://api.groq.com/openai/v1/chat/completions"

    structure = loadInterview()
    with open('answers.json', 'r') as file: 
        answersData = json.load(file)

    conversationHistory = answersData["conversationHistory"][-10:]
    lastQuestion = conversationHistory[-2]["content"]
    lastAnswer = conversationHistory[-1]["content"]

    name = structure["interviewer"]["name"]
    title = structure["interviewer"]["title"]
    experience = structure["interviewer"]["experience_years"]
    personality = structure["interviewer"].get("personality_trait") or structure["interviewer"].get("personality") or "professional"

    headers = {
        "Content-Type": "application/json",
        "Authorization": ""
    }

    # Step 1: React to the last answer, wrap up warmly, and ask if they have any questions
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""You are {name}, a {title} with {experience} years of experience. Your personality: {personality}.

The interview questions are now done. The candidate just answered your last question.

Last question you asked: "{lastQuestion}"
Candidate's answer: "{lastAnswer}"

Your job now:
1. React briefly and naturally to their last answer (1-2 sentences max)
2. Thank them warmly for coming in and for their time — sound genuine, not scripted
3. Then ask: "Before we wrap up, do you have any questions for me — about the role, the team, or the company?"

Sound like a real human. Be warm and direct.
Return ONLY plain text. No JSON, no markdown. Just what you would say out loud.
"""
        }]
    }

    resInJSON = makeRequest(url, headers, data)
    transitionText = resInJSON["choices"][0]["message"]["content"].strip()
    print(f"\nInterviewer: {transitionText}\n")

    # Step 2: Candidate asks their question(s)
    candidateQuestions = input("Enter your answer: ")
    saveData(transitionText, candidateQuestions)

    # Step 3: AI answers the candidate's questions and closes the interview
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""You are {name}, a {title} with {experience} years of experience. Your personality: {personality}.

The candidate just asked you their closing questions:
"{candidateQuestions}"

Your job:
1. Answer their question(s) naturally and helpfully — 2-3 sentences per question max. If they said they have no questions (e.g. "no", "I'm good", "nothing"), acknowledge that warmly and skip answering.
2. Close the interview warmly and professionally.
3. End with exactly this sentence: "You will receive an email with your results in about 5 minutes. Best of luck!"

Sound like a real human wrapping up — not a robot. Be warm, direct, and genuine.
Return ONLY plain text. No JSON, no markdown. Just what you would say out loud.
"""
        }]
    }

    resInJSON = makeRequest(url, headers, data)
    closingText = resInJSON["choices"][0]["message"]["content"].strip()
    print(f"\nInterviewer: {closingText}\n")


def start():
    freshState = {
        "conversationHistory": [],
        "categoryResults": []
    }
    with open('answers.json', 'w') as file:
        json.dump(freshState, file, indent=2)

    greeting()

    for questionCount in range(1, 10):
        print(questionCount)
        askQuestion(questionCount)

    closeInterview()


start()
