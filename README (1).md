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
- **`llm.py`** — thin Groq API wrapper (free, no credit card). Model: `openai/gpt-oss-120b`.
- **`main.py`** — the FastAPI app and the actual conversational state machine
  (in-memory session store, per the challenge's "no persistent accounts" scope).
  Follow-ups are grounded in the full back-and-forth on the *current topic only*
  (not just the last few messages), and the LLM is instructed to reference
  something specific the candidate said rather than asking generic "tell me
  more" — up to 2 genuine follow-ups per topic, enforced as a hard cap in code
  so the interview can't get stuck.
- **`interview_ui.html`** — a small standalone browser chat UI. Open it directly
  in a browser (double-click it, no server needed for the UI itself), upload
  your `candidates.json`, pick a candidate from the dropdown, and chat with the
  agent like a normal messaging app. It talks to your locally running backend
  at `localhost:8000`.
- **`run_interview.py`** — a terminal-based alternative to the browser UI, for
  quick testing without opening a browser.

## Setup

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_...   # required — free, get one at console.groq.com
uvicorn main:app --reload --port 8000
```

On Windows (Command Prompt), use `set GROQ_API_KEY=gsk_...` instead of `export`.

## Using it

**Option A — the browser UI (recommended):**

1. Start the backend server (see Setup above) and leave it running.
2. Double-click `interview_ui.html` to open it in your browser (or drag it into a browser window). No web server needed for this file — it's a plain local file that talks to your running backend.
3. Upload your `candidates.json`, pick a candidate from the dropdown, click "Start interview," and chat normally — type an answer, press Enter, repeat.
4. When the interview ends, structured feedback (summary/strengths/gaps/next) renders right there in the page.

**Option B — the terminal client:**

```bash
python run_interview.py
```
Lists your real candidates from `candidates.json`, lets you pick one by number, then runs the interview as a plain back-and-forth in the terminal.

**Option C — raw HTTP (for automated testing / grading):**

Start (send the full candidate object, no `message`):
```bash
curl -X POST http://localhost:8000/api/interview \
  -H "Content-Type: application/json" \
  -d '{ "sessionId": "abc-123", "candidate": { "member": {...}, "missions": [...], "signals": {...} } }'
```
Continue (send the candidate's latest reply each turn):
```bash
curl -X POST http://localhost:8000/api/interview \
  -H "Content-Type: application/json" \
  -d '{ "sessionId": "abc-123", "message": "I used cosine similarity because..." }'
```
Repeat until the response has `"done": true`, at which point it also includes the `feedback` object, matching the spec exactly.

**Option D — the desktop app (simplest, no browser or separate server needed):**

```bash
python interview_gui.py
```

A real window opens directly — no `uvicorn`, no browser, no localhost address to think about. It talks to the same interview logic directly (not over HTTP), so this one command is genuinely everything: pick a candidate, chat, click "View results" at the end to see real bar-chart visualizations (Strengths vs Gaps, Topics Covered by Module) built with matplotlib. Still needs `GROQ_API_KEY` set first, same as always. `candidates.json` should be in the same folder — it'll auto-load if found, or you can pick a file manually with the "Load candidates.json…" button.

Note: the FastAPI server (`main.py`) still exists separately and is what satisfies the hackathon's technical-spec requirement for a `POST /api/interview` HTTP endpoint — this desktop app is an additional, easier way to use the exact same underlying agent for your own testing, demos, or day-to-day use.

## Running this in VS Code instead of a bare terminal

1. Open VS Code, then **File → Open Folder…** and select this project's folder.
2. Open the built-in terminal: **Terminal → New Terminal** (or `` Ctrl+` ``). This is functionally the same terminal you were using before, just docked inside the editor. Note: VS Code's terminal defaults to **PowerShell**, so use `$env:GROQ_API_KEY="your_key_here"` instead of `set GROQ_API_KEY=...`.
3. In that terminal:
   ```
   pip install -r requirements.txt
   $env:GROQ_API_KEY="your_key_here"
   uvicorn main:app --reload --port 8000
   ```
4. Open a second terminal tab inside VS Code (the `+` icon in the terminal panel) to run `run_interview.py` or curl commands while the server keeps running in the first tab.
5. For the browser UI, just right-click `interview_ui.html` in VS Code's file explorer and choose "Reveal in File Explorer" (or similar), then double-click it to open in your browser — VS Code doesn't need to "run" an HTML file, browsers just open it directly.

## Deploying it so anyone can use it (not just your computer)

Everything above only runs while your own computer is running the server — for a hackathon submission, judges need a link that works without you doing anything. That means putting the server on a free hosting service that stays on. Here's the free, no-credit-card path using **Render**:

**1. Push this project to GitHub** (if you haven't already):
```
git init
git add .
git commit -m "AI Interview Agent"
```
Then create a new empty repository at github.com (click the "+" top-right → "New repository"), and follow the push instructions it shows you (it'll give you the exact `git remote add origin ...` and `git push` commands for your specific repo).

**2. Sign up at render.com** (free, no card needed for this).

**3. Create a new Web Service**: click **New → Web Service**, connect your GitHub account, and pick this repository.

**4. Set these two fields** in Render's setup form:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

   (There's also a `Procfile` in this project with the same start command — Render may auto-detect it.)

**5. Add your API key as an environment variable** (never put it directly in code): in the Render dashboard for this service, go to **Environment**, add a variable named `GROQ_API_KEY` with your actual key as the value.

**6. Click Create Web Service.** Render will build and deploy it — takes a couple minutes. When it's done, you'll get a public URL like `https://your-app-name.onrender.com`.

**7. Open that URL in a browser.** Since the server now serves the chat UI directly at its root address (see `main.py`'s `/` route), that one link *is* the whole app — judges just open it and start chatting, no setup on their end at all.

Note: Render's free tier "spins down" after 15 minutes of no traffic and takes ~30-60 seconds to wake back up on the next visit — normal for free hosting, just means the first request after a while feels slow.


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
