# AI Interview Agent

Conducts a personalized, multi-turn technical interview based on a candidate's
actual progress through the 31-day AI Cohort, then produces structured feedback.
Implements the single endpoint required by the technical spec: `POST /api/interview`.

## How it works

- **`curriculum.json`** — the full 31-day curriculum (provided data), used to ground
  every question in real learning objectives/tools rather than generic trivia.
- **`planner.py`** — deterministically builds each candidate's interview plan
  *before* any LLM call happens. This guarantees the spec's hard minimums
  (≥8 questions, ≥4 distinct curriculum days) regardless of what the LLM decides —
  the LLM only controls *phrasing* and *whether one follow-up is warranted*, not
  whether the minimums are met. Topics are chosen from what the candidate actually
  passed, weighted toward the challenge's core topics (RAG, vector search, prompting,
  agentic AI, MCP, deployment), and 1–3 "probe" questions are woven in on topics the
  candidate skipped/failed/never attempted, framed gently. Difficulty is calibrated
  per topic using their attempt count (passed first try → pushed deeper; passed after
  many attempts → verified more carefully).
- **`llm.py`** — thin Anthropic Messages API wrapper. Model: `claude-sonnet-5`.
- **`main.py`** — the FastAPI app and the actual conversational state machine
  (in-memory session store, per the challenge's "no persistent accounts" scope).

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # required — get one at console.anthropic.com
uvicorn main:app --reload --port 8000
```

## Using it

**1. Start an interview** (send the full candidate object, no `message`):

```bash
curl -X POST http://localhost:8000/api/interview \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "abc-123",
    "candidate": { "member": {...}, "missions": [...], "signals": {...} }
  }'
```

**2. Continue the conversation** — send the candidate's latest reply each turn:

```bash
curl -X POST http://localhost:8000/api/interview \
  -H "Content-Type: application/json" \
  -d '{ "sessionId": "abc-123", "message": "I used cosine similarity because..." }'
```

Repeat until the response has `"done": true`, at which point it also includes the
`feedback` object (`summary`, `strengths`, `gaps`, `next`), matching the spec exactly.

## Testing without burning API calls

`planner.py`'s plan-building logic (the part that guarantees the spec minimums) is
pure Python with no LLM dependency, so it's fully unit-testable on its own — see the
`build_plan()` function. The conversational state machine in `main.py` is also
LLM-call-agnostic in its control flow (advance/follow-up/finish), so it can be
exercised with a mocked `llm.call_json` for fast iteration.

## Notes on design decisions

- **Why deterministic planning, not full LLM autonomy?** An LLM deciding topic
  selection *and* the stopping condition risks under- or over-shooting the spec's
  hard minimums, especially for very low-completion candidates. Splitting the
  concerns — Python guarantees the contract, the LLM handles the human part
  (phrasing, adaptivity, follow-ups) — makes the minimums a hard guarantee instead
  of a hopeful prompt instruction.
- **Why cap follow-ups at one per topic?** Keeps interview length predictable and
  prevents the LLM from getting stuck probing a single topic indefinitely.
- **Sessions are in-memory and cleared on completion** — matches the challenge's
  explicit "out of scope: persistent user accounts, long-term conversation history."
