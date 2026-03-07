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
# 2- The API is hitting token limited Exceed:
thats the bad thing, 
## Solution:
I will use more than one API(it can be 5,6 or any n numbers depending on users) lets say there are 500 active users that are using,
what will I do is that I will make a loop of these APIs, if one API hit limit exceed then next API and when that one then next API and so on until it completes the full cycle and move to first API and obviously its limit has been reset 
I have observed the tokens and thats what I got:  

## 📊 Token Usage Observed (per turn)

| Turn | Total Tokens |
|------|-------------|
| 1    | 2,708       |
| 2    | 2,902       |
| 3    | 3,128       |
| 4    | 3,273       |
| 5    | 3,391       |
| 6    | 3,564       |
| 7    | 3,740       |
| n    | n + ~200 (grows each turn because history is added) |

> **Why does it grow?** Because every turn sends the full conversation history as context to the AI. More turns = bigger prompt = more tokens.

---

### 🧮 Key Formula (DSA — Circular Queue)

```python
newIndex = (currentIndex + 1) % len(apis)
```

This ensures the index never goes out of bounds and wraps back to 0 after the last key.

---

### 📐 How Many Keys Do You Need?

```
1 full interview  ≈ 75,000 tokens
1 key limit       = 100,000 tokens/day
= ~1 interview per key per day

So:
Users per day = Keys needed
100 active users = ~100 keys
```

> Keys reset every 24 hours. By the time all keys are cycled through, the first one has already reset.

---

### ⚙️ Rotation Conditions

| Condition | Header | Threshold |
|-----------|--------|-----------|
| Low tokens | `x-ratelimit-remaining-tokens` | `< 5000` |
| Low requests | `x-ratelimit-remaining-requests` | `< 50` |
| Emergency | `response.status_code` | `== 429` |

---

#### Overview:
CheckRotate(response) -> if hit limit then -> rotateAPI(currIndx) by getting getCurrAPI()
```
checkandRotate(response)
  │
  ├── remainingTokens < 5000?  ──Yes──► getCurrAPI()
  │                                          │
  ├── remainingRequests < 50?  ──Yes──►  rotateAPI(currIndx)
  │                                          │
  └── status_code == 429?      ──Yes──►  saves new index to api_data.json
  │
  No
  │
  continue normally

apis = [API1, API2, API3 ... APIN]
         │
         └── newIndex = (currentIndex + 1) % len(apis)

API1 ──limit──► API2 ──limit──► API3 ──limit──► back to API1 ♻️
```
