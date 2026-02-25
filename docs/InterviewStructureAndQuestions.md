## Overview

A user provides a rough, messy description of what kind of interview they want to prepare for, and the system generates a complete, structured interview with a realistic interviewer persona, phased question sets, and difficulty progression — all saved as a JSON file.

---

## How It Works (High-Level Flow)

```
User Input (raw, messy text)
        ↓
  cleanPrompt()        ← Refines the input into a structured prompt
        ↓
  getResponse()        ← Uses the refined prompt to generate interview data
        ↓
interview_structure.json ← Final output saved to disk
```

---
