import requests
import json
import os
from dotenv import load_dotenv

load_dotenv()
apis = apis = [os.getenv("api1"), os.getenv("api2"), os.getenv("api3"), os.getenv("api4"), os.getenv("api5"), os.getenv("api6"),os.getenv("api7"),os.getenv("api8"),os.getenv("api9"),os.getenv("api10")]
# 01 get Current API logic
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
        
        # Response from API(which will be linked to judgeInterview)
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
            # FAILED!! now rotate api
            print(f"[DEV_BACKEND]: API{currIndx+1} failed ({resInJSON.get('error', {}).get('message', 'unknown error')}), rotating...")
            rotateAPI(currIndx)
    # if not success nor failure then it means all APIs has limit exceed
    raise Exception("All APIs exhausted. Try again later.")

def judgeInterview():
    with open('answers.json', 'r') as file:
        answerData = json.load(file)

    categoryRes = answerData["categoryResults"]

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Content-Type": "application/json",
        "Authorization": ""  # DONT TRY TO FILL IT -> makeRequest() will fill this in
    }
    exampleJSON = """
    {
        "overallScore": 72,
        "levelAssessment": "Solid Junior",
        "badge": "Backend Fundamentals ✓",
        "improvement": "+11 from last attempt",
        "strongAreas": [
            {"topic": "Authentication", "reason": "Real JWT example with bcrypt"}
        ],
        "weakAreas": [
            {"topic": "System Design", "reason": "Too vague, no concrete numbers"}
        ],
        "redFlags": [
            {"moment": "Question 6", "reason": "Said I don't know with no attempt"}
        ],
        "improvementTips": [
            "Study load balancing with real numbers"
        ],
        "breakdown": [
            {"question": "How did you handle auth?", "color": "green", "reason": "Solid"}
        ]
    }
    """
    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""The Interview is over...
                        Return ONLY JSON format:
                        {exampleJSON}
                        Here is the interview data: {categoryRes}"""
        }]
    }

    resInJSON = makeRequest(url, headers, data)
    rawContent = resInJSON["choices"][0]["message"]["content"]
    rawContent = rawContent.replace("```json", "").replace("```", "").strip()
    parsedResponse = json.loads(rawContent)
    
    result = {
    "overallScore":     parsedResponse.get("overallScore", 0),
    "levelAssessment":  parsedResponse.get("levelAssessment", "Unknown"),
    "badge":            parsedResponse.get("badge", ""),
    "improvement":      parsedResponse.get("improvement", "First attempt"),
    "strongAreas":      parsedResponse.get("strongAreas", []),
    "weakAreas":        parsedResponse.get("weakAreas", []),
    "redFlags":         parsedResponse.get("redFlags", []),
    "improvementTips":  parsedResponse.get("improvementTips", []),
    "breakdown":        parsedResponse.get("breakdown", []),
    }

    with open("result.json", "w") as f:
        json.dump(result, f, indent=4)

    print("Result saved to result.json")
    
judgeInterview()