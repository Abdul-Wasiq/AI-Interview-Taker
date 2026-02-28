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

# getting all interview questions from answers.json 
def loadInterview():
    try:
        with open('interview_structure.json', 'r') as file:
            questions = json.load(file)

        return questions
    except FileNotFoundError:
        return "Error: File Not Found"

# get user input(Function)
def userAnswer():
    getAnswer = input("Enter your answer: ")
    return getAnswer

# Greet and ask question, e:g "How are you?"
def greeting():
    allQuestions = loadInterview()
    greetingText = allQuestions["interviewer"]["opening_greeting"]
    print(f"\nInterviewer: {greetingText}\n")  
    answer = userAnswer()                        
    saveData(greetingText, answer)               

# reset Interview
def resetInterview():
    freshState = {
        "conversationHistory": [],
        "categoryResults": [],
        "currentPhase": "phase1_introduction",
        "currentCategoryIndex": 0,
        "currentQuestionIndex": 0
    }
    with open('answers.json', 'w') as file:
        json.dump(freshState, file, indent=2)

def saveData(question, answer, judgment=None):
    with open('answers.json', 'r') as file:
        data = json.load(file)

    # Append to conversation history
    data["conversationHistory"].append({"role": "assistant", "content": question})
    data["conversationHistory"].append({"role": "user", "content": answer})

    # Save judgment if provided
    if judgment:
        data["categoryResults"].append({
            "question": question,
            "answer": answer,
            "judgment": judgment,
            "phase": data["currentPhase"]
        })

    with open('answers.json', 'w') as file:
        json.dump(data, file, indent=2)

def askQuestion():

    with open('interview_structure.json', 'r') as file:
        data = json.load(file)

    identity = data["interviewer"]
    name = identity["name"]
    title = identity["title"]
    experience = identity["experience_years"]
    personality = identity["personality_trait"]

    with open('answers.json', 'r') as file:
        data = json.load(file)

    currentPhase = data["currentPhase"]  
    currentCategoryIndex = data["currentCategoryIndex"]
    currentQuestionIndex = data["currentQuestionIndex"]
    conversationHistory = data["conversationHistory"]
    lastQuestion = conversationHistory[-2]["content"]  # last assistant message
    lastAnswer = conversationHistory[-1]["content"]     # last user message


    data = {
    "model": "llama-3.3-70b-versatile",
    "messages": [{
        "role": "user",
        "content": f"""You are {name}, a {title} with {experience} years experience. Your personality is {personality}.

        Current category: {currentPhase}
        Conversation history: {conversationHistory}

        Last question asked: {lastQuestion}
        Candidate answer: {lastAnswer}

        Your job:
        1. Judge the last answer: excellent/good/weak/wrong
        2. Decide next question based on judgment
        3. Return ONLY this JSON, nothing else:
        {{
            "judgment": "good",
            "nextQuestion": "your next question here",
            "moveToNextCategory": false
        }}"""}] 
    }
    response = requests.post(url, headers=headers, json=data) 
    resInJSON = response.json()
    rawContent = resInJSON["choices"][0]["message"]["content"] 
    rawContent = rawContent.replace("```json", "").replace("```", "").strip() # remove backticks and pure JSON remains
    
    print(rawContent)

    parsedResponse = json.loads(rawContent)
    judgment  = parsedResponse["judgment"]
    nextQuestion = parsedResponse["nextQuestion"]
    moveToNextCategory = parsedResponse["moveToNextCategory"]

    # saveData(lastQuestion, lastAnswer, judgment)
    print(f"\n Interviewer: {nextQuestion}")
    answer = userAnswer()

    saveData(nextQuestion, answer)


def start():
    # Step:01 (clear answers.json when start function clicked)
    # Step:02 (if (answers.json is clear then greet and save in answers.json))
    # Step:03 (else ask an other question but on the basis of previous questions)
    # Step: 3.0 (dont ask same questions)

    # STEP #01
    with open('answers.json', 'r') as file:
        data = json.load(file)

    data["currentPhase"] = "opening_greeting"
    data["currentCategoryIndex"] = 0
    data["currentQuestionIndex"] = 0
    data["conversationHistory"] = []
    data["categoryResults"] = []

    with open('answers.json', 'w') as file:
        json.dump(data, file, indent=2)

    greeting()

    while True:
        askQuestion()

    

start()  
          
