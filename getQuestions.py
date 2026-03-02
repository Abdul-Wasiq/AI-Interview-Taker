import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

def cleanPrompt(userMessyPrompt):
    APIKey = os.getenv("groqAPI")
    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {APIKey}"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""
            You are a prompt engineer. A user wants to prepare for an interview.
            Their raw input is: "{userMessyPrompt}"

            Your job is to convert this into a clean, structured prompt that will be 
            sent to an AI question generator.

            The output prompt must:
            1. Identify the interview type (DSA, university admission, government job, big tech, etc.)
            2. Identify specific topics or subjects if mentioned
            3. Specify that questions must be CONCEPTUAL and VERBAL — meaning technically grounded 
            but discussion-based. No writing code, no MCQs. Questions should test understanding, 
            trade-offs, and reasoning — not syntax or implementation.
            4. Ask for 50-100 questions grouped by topic/category
            5. Specify that the output format must always be exactly:
            **Category Name**
            * Question 1
            * Question 2
            No other format is acceptable.
            6. If the interview type cannot be determined from the input, do not assume. 
            Instead return exactly: UNCLEAR_INTENT: Ask the user what type of interview 
            they are preparing for.

            Only return the refined prompt. Nothing else.
            """
}]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        prompt = response.json()
        return prompt["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error: {e}")
        return "Something went wrong"    


def getResponse(cleanUserPrompt):
    APIKey = os.getenv("groqAPI")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {APIKey}"
    }

    data = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{
            "role": "user",
            "content": f"""You are an expert interview structure designer and question generator.
            The interview context is:
            {cleanUserPrompt}

            Generate a realistic interviewer persona for this specific interview type.
            Make it feel like a real human being, not a generic AI interviewer.

            PERSONA DETAILS:
            - Full name (culturally appropriate to the company/institution location)
            - Exact job title
            - Years of experience (specific number)
            - Company or institution name
            - City they are interviewing from
            - One personality trait (warm, direct, formal, casual)

            - Interviewer greeting must be about the INTERVIEW, not small talk
            - Must reference the role or subject being interviewed for
            - Never mention weather, coffee, or unrelated personal things
            - Get to the point within 1-2 sentences
            - Then naturally invite candidate to introduce themselves

            Your job is to:
            1. Analyze the interview type (military, truck driver, DSA, React.js, 
            university admission, labour, air force — literally anything)
            2. Design a realistic phase structure FOR THAT SPECIFIC interview
            3. Generate questions for each phase

            IMPORTANT RULES:
            - For a truck driver interview: core questions = driving experience, 
            road safety, license, physical fitness, routes. NOT DSA.
            - For military/air force: core = discipline, physical, patriotism, 
            leadership, situational. NOT coding.
            - For React.js: core = component lifecycle, state management, hooks, 
            performance. NOT MongoDB.
            - For labour job: core = physical capability, work experience, 
            availability, tools knowledge. Keep language simple.
            - NEVER mix categories from different interview types
            - Phase 1 size depends on interview type:
            formal/technical → shorter intro
            admission/personality → longer intro
            - Difficulty progression within each category:
            1st-2nd → Beginner
            3rd-4th → Easy-Medium
            5th-6th → Medium
            7th+    → Medium-Hard
            - First question of Phase 1 must always be warm and confidence building
            - No coding tasks, no MCQs, discussion based only
            - Questions must be specific and technically sharp, not vague or essay-like
            - Avoid "tell me about" or "describe your journey" style in CORE phase
            - Good example: "Why is a hash table O(1) average but O(n) worst case?"
            - Bad example: "Can you describe a scenario where you would use a hash table?"
            - CORE questions should immediately reveal whether candidate truly understands
            - CRITICAL: Numbering MUST restart from 1 for every new category
            - Total questions: 50-100 depending on interview complexity
            - If interview is simple (labour, driver): 50-60 questions
            - If interview is complex (DSA, React, medical): 70-100 questions
            - Match question language complexity to the interview type

            YOU MUST RETURN ONLY VALID JSON. NO TEXT BEFORE OR AFTER. NO MARKDOWN. NO BACKTICKS.
            
            Return exactly this structure:
            {{
                "interviewer": {{
                    "name": "...",
                    "title": "...",
                    "experience_years": 10,
                    "company": "...",
                    "opening_greeting": "..."
                }},
                "phases": {{
                    "phase1_introduction": [
                        {{
                            "category": "Category Name",
                            "questions": [
                                {{"id": 1, "difficulty": "beginner", "question": "..."}}
                            ]
                        }}
                    ],
                    "phase2_core": [
                        {{
                            "category": "Category Name",
                            "questions": [
                                {{"id": 1, "difficulty": "beginner", "question": "..."}},
                                {{"id": 2, "difficulty": "easy-medium", "question": "..."}},
                                {{"id": 3, "difficulty": "medium", "question": "..."}},
                                {{"id": 4, "difficulty": "medium-hard", "question": "..."}}
                            ]
                        }}
                    ],
                    "phase3_closing": [
                        {{
                            "category": "Category Name",
                            "questions": [
                                {{"id": 1, "difficulty": "beginner", "question": "..."}}
                            ]
                        }}
                    ]
                }}
            }}
            """
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        resInJSON = response.json()
        rawContent = resInJSON["choices"][0]["message"]["content"] 
        rawContent = rawContent.replace("```json", "").replace("```", "").strip() # remove backticks and pure JSON remains

        interviewData = json.loads(rawContent) # convert String -> dictionary

        with open("interview_structure.json", "w") as f:
            json.dump(interviewData, f, indent=2)

        print("Done! Saved to interview_structure.json")
        print(response.elapsed.total_seconds(), "seconds")
    except Exception as e:
        print(f"Error: {e}")    




while True:
    userInput = input("Enter prompt: ")
    print("What level are you preparing for?")
    print("1. Internship")
    print("2. Junior Developer")
    print("3. Mid Level")
    print("4. Senior Developer")

    level = input("Enter 1-4: ")

    cleanUserPrompt = cleanPrompt(userInput)

    if "UNCLEAR_INTENT" in cleanUserPrompt:
        print("Please Enter Correct Input\n")
    else:
        getResponse(cleanUserPrompt)

        with open('user_background.json', 'w') as file:
            json.dump({"userPrompt": userInput,"level": level}, file, indent=2) 
        break
