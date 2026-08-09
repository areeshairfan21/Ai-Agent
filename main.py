"""
AI Interview Agent — backend

Implements exactly one endpoint per the technical spec:

    POST /api/interview

Session state lives in memory (no persistent accounts / long-term history
required per the challenge's "Out of Scope" section). Each session tracks:
  - the candidate profile
  - the deterministic interview plan (see planner.py)
  - a pointer into that plan
  - whether a follow-up has already been used on the current topic
  - the full transcript (for context + final feedback synthesis)

Control flow per turn (see llm.py for prompt/JSON contract):
  1. Start (no "message" in body): build the plan, ask the first question.
  2. Turn (message present): record the answer, ask the LLM whether a follow-up
     is warranted on the *current* topic (up to 2 per topic, so it can genuinely
     dig into what the candidate said rather than always moving on after one
     exchange); if not (or the cap is reached), advance the plan pointer and ask
     the next question. Repeat until the plan is exhausted.
  3. Once the plan is exhausted: synthesize structured feedback and return
     done=true per the spec's feedback schema.
"""

from typing import Any, Optional
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from planner import build_plan, curriculum_context_for_days
from llm import call_json

app = FastAPI(title="AI Interview Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# sessionId -> session state
SESSIONS: dict[str, dict[str, Any]] = {}

MIN_QUESTIONS = 8
MAX_FOLLOWUPS_PER_TOPIC = 2


class InterviewRequest(BaseModel):
    sessionId: str
    candidate: Optional[dict[str, Any]] = None
    message: Optional[str] = None


class TopicCovered(BaseModel):
    day: int
    title: str
    module: int
    type: str
    probe: bool


class FeedbackModel(BaseModel):
    summary: str
    strengths: list[str]
    gaps: list[str]
    next: list[str]
    # Extra fields beyond the spec's required 4, purely to power the results-page
    # graphs. Built from the deterministic interview plan (not LLM-generated), so
    # they're always accurate and never hallucinated.
    topicsCovered: list[TopicCovered] = []
    strengthsCount: int = 0
    gapsCount: int = 0


class InterviewResponse(BaseModel):
    reply: str
    done: bool
    feedback: Optional[FeedbackModel] = None


SYSTEM_INTERVIEWER = """You are a warm but rigorous senior technical interviewer running a live \
technical interview for graduates of a 31-day enterprise AI engineering cohort (RAG, vector \
databases, prompt engineering, agentic AI, MCP, and production AI deployment).

You will be given: the candidate's profile, the current topic (with the curriculum's own \
learning objectives and tools for that day), the FULL back-and-forth transcript for THIS topic \
only (every question you've asked and every answer they've given on it so far), and how many \
follow-ups have already been used on this topic.

Your job each turn is to decide ONE of two things and respond with STRICT JSON ONLY (no \
markdown fences, no commentary outside the JSON):

{
  "followup": true | false,
  "advance": true | false,
  "reply": "<the exact text to say to the candidate next>"
}

Rules:
- A great follow-up quotes or directly references something SPECIFIC the candidate just said \
(a term, a claim, a design choice) and pushes on it — asks them to justify it, probe an edge \
case in it, or clarify something vague about it. A generic "can you tell me more?" is a bad \
follow-up; don't write those.
- If the candidate's last answer was shallow, vague, made a claim worth challenging, or opens an \
interesting thread worth pulling on THIS topic, and fewer than __MAX_FOLLOWUPS__ follow-ups have \
been used on it yet, set followup=true, advance=false, and write that specific follow-up in \
"reply" (no preamble, just the question, optionally one short sentence of context referencing \
what they said).
- If the candidate's answer was already strong and complete, don't force a follow-up just because \
you're allowed one — it's fine to advance early.
- Otherwise set followup=false, advance=true, and write "reply" as a brief (1 sentence) natural \
transition that reacts to something specific in their last answer (not a generic "Got it"), \
followed by the next question (using the "next topic" info given to you). Vary these transitions.
- If this is a "probe" topic, frame it as exploratory and lower-pressure rather than a "gotcha": \
if status is "skipped" or "failed", something like "I see you skipped/didn't pass Day X — even \
without the hands-on build, do you have a conceptual sense of how you'd approach it?"; if status \
is "not_attempted" (topic wasn't in their completed missions at all), just ask it as a general \
knowledge/reasoning question about the concept, no need to reference their record. Don't penalize \
tone for probes.
- Calibrate difficulty to the "difficulty_hint" for the topic: "deepen" = ask about edge cases, \
trade-offs, or production failure modes; "verify" = ask them to explain the core concept clearly, \
since they struggled with the hands-on version; "standard" = a normal solid technical question.
- Never ask more than one question in a single "reply".
- Keep questions concrete and grounded in the actual curriculum objectives/tools given to you — \
avoid generic trivia.
- This is the LAST topic in the plan: if advancing past it, instead set advance=true, followup=false, \
and write a brief, warm closing line thanking them and telling them their results are being compiled \
(do not ask another question)."""


SYSTEM_FEEDBACK = """You are a senior technical interviewer writing the final structured feedback \
for a completed interview. You will receive the candidate's profile and the full interview \
transcript (questions and answers). Respond with STRICT JSON ONLY in exactly this shape:

{
  "summary": "<2-4 sentence overall assessment, specific to what they actually said>",
  "strengths": ["<concise, actionable point>", "..."],
  "gaps": ["<concise, actionable point>", "..."],
  "next": ["<concise, actionable recommended next step>", "..."]
}

Base every point on evidence from the transcript, not on the candidate's profile stats alone. \
Be honest and specific — vague praise or vague criticism is not useful. Aim for 2-5 items per \
array."""


def _current_topic_payload(plan_entry: dict) -> dict:
    return {
        "day": plan_entry["day"],
        "title": plan_entry["title"],
        "type": plan_entry["type"],
        "objectives": plan_entry["objectives"],
        "tools": plan_entry["tools"],
        "probe": plan_entry["probe"],
        "status": plan_entry.get("status"),
        "difficulty_hint": plan_entry["difficulty_hint"],
    }


def _start_session(session_id: str, candidate: dict) -> InterviewResponse:
    plan = build_plan(candidate)
    session = {
        "candidate": candidate,
        "plan": plan,
        "index": 0,
        "followups_used": 0,
        "topic_transcript": [],   # resets every time we advance to a new topic
        "transcript": [],         # full interview transcript (for final feedback)
        "questions_asked": 0,
        "days_covered": set(),
    }
    SESSIONS[session_id] = session

    first = plan[0]
    member = candidate.get("member", {})
    user_prompt = (
        f"Candidate profile: name={member.get('name')}, role={member.get('jobRole')}, "
        f"experience={member.get('yearsExperience')} years, education={member.get('education')}.\n"
        f"This is the very first question of the interview. Greet them briefly by first name and "
        f"ask about this topic:\n{_current_topic_payload(first)}\n"
        f"Respond with followup=false, advance=false, and put the greeting + first question in "
        f"\"reply\"."
    )
    result = call_json(SYSTEM_INTERVIEWER, user_prompt)
    reply = result.get("reply", "Welcome! Let's get started.")

    session["transcript"].append({"role": "assistant", "content": reply})
    session["topic_transcript"].append({"role": "assistant", "content": reply})
    session["questions_asked"] += 1
    session["days_covered"].add(first["day"])

    return InterviewResponse(reply=reply, done=False)


def _finish_session(session_id: str) -> InterviewResponse:
    session = SESSIONS[session_id]
    candidate = session["candidate"]
    member = candidate.get("member", {})

    transcript_text = "\n".join(
        f"{'INTERVIEWER' if t['role']=='assistant' else 'CANDIDATE'}: {t['content']}"
        for t in session["transcript"]
    )
    user_prompt = (
        f"Candidate: name={member.get('name')}, role={member.get('jobRole')}, "
        f"experience={member.get('yearsExperience')} years.\n\n"
        f"Full transcript:\n{transcript_text}"
    )
    result = call_json(SYSTEM_FEEDBACK, user_prompt, max_tokens=800)

    strengths = result.get("strengths", [])
    gaps = result.get("gaps", [])
    topics_covered = [
        TopicCovered(
            day=p["day"], title=p["title"], module=p["module"],
            type=p["type"], probe=p["probe"],
        )
        for p in session["plan"]
    ]

    feedback = FeedbackModel(
        summary=result.get("summary", "Interview completed."),
        strengths=strengths,
        gaps=gaps,
        next=result.get("next", []),
        topicsCovered=topics_covered,
        strengthsCount=len(strengths),
        gapsCount=len(gaps),
    )
    del SESSIONS[session_id]
    return InterviewResponse(reply="Interview completed.", done=True, feedback=feedback)


def _continue_session(session_id: str, message: str) -> InterviewResponse:
    session = SESSIONS[session_id]
    plan = session["plan"]
    session["transcript"].append({"role": "user", "content": message})
    session["topic_transcript"].append({"role": "user", "content": message})

    current = plan[session["index"]]
    is_last = session["index"] == len(plan) - 1
    next_topic = None if is_last else plan[session["index"] + 1]

    topic_convo = "\n".join(
        f"{'INTERVIEWER' if t['role']=='assistant' else 'CANDIDATE'}: {t['content']}"
        for t in session["topic_transcript"]
    )
    user_prompt = (
        f"Current topic: {_current_topic_payload(current)}\n"
        f"Follow-ups already used on this topic: {session['followups_used']} "
        f"(max allowed: {MAX_FOLLOWUPS_PER_TOPIC})\n"
        f"Is this the last topic in the plan: {is_last}\n"
        f"Next topic (only relevant if advancing): "
        f"{_current_topic_payload(next_topic) if next_topic else 'None (interview ends)'}\n\n"
        f"Full back-and-forth on THIS topic so far:\n{topic_convo}"
    )
    result = call_json(
        SYSTEM_INTERVIEWER.replace("__MAX_FOLLOWUPS__", str(MAX_FOLLOWUPS_PER_TOPIC)),
        user_prompt,
    )

    followup = bool(result.get("followup")) and session["followups_used"] < MAX_FOLLOWUPS_PER_TOPIC
    reply = result.get("reply", "Thanks — let's move on.")

    if followup:
        session["followups_used"] += 1
        session["questions_asked"] += 1
        session["transcript"].append({"role": "assistant", "content": reply})
        session["topic_transcript"].append({"role": "assistant", "content": reply})
        return InterviewResponse(reply=reply, done=False)

    # advance to next topic
    session["index"] += 1
    session["followups_used"] = 0
    session["topic_transcript"] = []

    if session["index"] >= len(plan):
        session["transcript"].append({"role": "assistant", "content": reply})
        return _finish_session(session_id)

    new_current = plan[session["index"]]
    session["days_covered"].add(new_current["day"])
    session["questions_asked"] += 1
    session["transcript"].append({"role": "assistant", "content": reply})
    session["topic_transcript"].append({"role": "assistant", "content": reply})
    return InterviewResponse(reply=reply, done=False)


@app.post("/api/interview", response_model=InterviewResponse)
def interview(req: InterviewRequest) -> InterviewResponse:
    if req.message is None:
        # Start (or restart) of a session
        if req.candidate is None:
            raise HTTPException(status_code=400, detail="candidate is required to start a session")
        return _start_session(req.sessionId, req.candidate)

    if req.sessionId not in SESSIONS:
        raise HTTPException(
            status_code=404,
            detail="Unknown sessionId. Start a session first with a candidate payload.",
        )
    return _continue_session(req.sessionId, req.message)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def serve_ui():
    """Serves the chat UI at the app's root URL, so there's a single link to
    share — the same server that answers /api/interview also serves the page
    that talks to it, avoiding any separate hosting or CORS setup for judges."""
    ui_path = os.path.join(os.path.dirname(__file__), "interview_ui.html")
    with open(ui_path, "r", encoding="utf-8") as f:
        return f.read()
