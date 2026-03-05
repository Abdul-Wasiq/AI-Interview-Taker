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
I have observed the tokens and thats what I got:  

Turn 1: 2,708<br>
Turn 2: 2,902<br>
Turn 3: 3,128<br>
Turn 4: 3,273<br>
Turn 5: 3,391<br>
Turn 6: 3,564<br>
Turn 7: 3,740
Turn n: n + 200(apprx)

Users per day = Keys needed  
Because 1 key resets every 24 hours  
So if 100 users come before reset = 100 keys needed  
