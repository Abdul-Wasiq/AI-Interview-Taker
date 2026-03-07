# Bug Fixes

## Saving Question and Answer Two Times
- **Reported:** 2/27/2026
- **Solved:** 2/28/2026
- Fixed by extracting `saveJudgement` into a separate function.

## Asking Questions from Same Category
- **Reported:** 2/28/2026
- `moveToNextCategory` was never being called.

## Repetitive Acknowledgment ("Oh nice!")
- **Reported:** 2/28/2026
- Acknowledgment phrase repeating after every answer — feels unnatural.
- Fixed it by fixing prompt in content 3/1/2026

---

# Features & Improvements

## 🔴 Priority 1 — End of Interview Feedback Report
After all categories are complete, generate a structured feedback report showing strong areas, weak areas, and recommended topics to study. This is the screen users will screenshot and share.

## 🔴 Priority 2 — Vary Acknowledgment Phrases
"Oh nice!" is being said 7–8 times in a row. Responses should feel like a real human — mix up phrasing naturally so the conversation doesn't feel robotic.

## Interview Adapts to Candidate's Introduction
If the user mentions "I work with Django", ask Django-related questions. Don't ask about FastAPI or unrelated tools. Currently the introduction is ignored entirely.

## Motivational Response After Weak Answers
Before moving to the next category after weak answers, say something encouraging — e.g., *"Database schema is something most developers learn on the job, don't worry about it."* This is the difference between a user coming back or never opening the app again.

## Proper Interview Ending
Right now the interview loops forever with no finish. Add a closing message like a real interviewer would — wrap up the session naturally.

## Gradual Difficulty Scaling Per Category
Start with beginner questions, move to medium if answers are strong. Never jump to hard questions early. If the user struggles, ease off rather than pushing harder.

## Track User Progress Across Sessions
Show users how they improved compared to their last interview — e.g., *"Last time you struggled with databases, this time you did better!"* This is the strongest reason to come back.

## User Profile Before Interview Starts
Ask experience level, technologies used, and the role they're applying for. Personalize every interview based on this — a React developer and a Python developer should get completely different interviews.

## use introduction like a data to use to ask questions
