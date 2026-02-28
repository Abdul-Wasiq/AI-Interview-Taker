# Brain.py Overview

## User-Defined Functions

### `loadInterview()`
Loads all interview questions from `interview_structure.json`

### `userAnswer()`
Handles user input during the interview

### `greeting()`
Greets the user, asks initial questions, and saves the greeting + answer via `saveData()`

### `resetInterview()`
When user types `"Start"`, clears the entire past conversation and resets the session

### `saveData()`
Saves conversation history (role + content) and stores any judgement if provided

### `askQuestion()`
The core function that:
- Fetches interviewer identity from `interview_structure.json`
- Passes current phase, conversation history, last question and last answer into a Groq API prompt
- Allows the AI to track what has been covered, stay in character, and decide what to ask next
- and in last ask question and get answer and then save in save Data.

### `askQuestion()`
- Step:01 (clear answers.json when start function clicked)
- Step:02 (if (answers.json is clear then greet and save in answers.json))
- Step:03 (else ask an other question but on the basis of previous questions)
- Step: 3.0 (dont ask same questions)
- Step: 3.1 (Question limit per category(max 3-4))
- moveToNextCategory logic — actually move to next category when true
- End condition — stop when all categories done


