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
# The API is hitting token limited Exceed:
thats the bad thing, 
## Solution:
I will use more than one API(it can be 5,6 or any n numbers depending on users) lets say there are 500 active users that are using,
what will I do is that I will make a loop of these APIs, if one API hit limit exceed then next API and when that one then next API and so on until it completes the full cycle and move to first API and obviously its limit has been reset 
