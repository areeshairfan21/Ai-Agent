"""
Builds a per-candidate interview plan from curriculum.json + the candidate profile.

Design goals (mapping to the technical spec's minimum requirements):
- At least 8 questions, covering at least 4 distinct curriculum days -> enforced
  deterministically here, not left to the LLM's discretion.
- Personalization: topics are chosen from what the candidate actually completed,
  weighted toward the concepts the challenge cares most about (RAG, vector search,
  prompting, agentic AI, MCP, deployment), and difficulty framing is informed by
  attempts-to-pass (a mission passed on attempt 1 => can go deeper/harder; a
  mission passed on attempt 5 => probe fundamentals more carefully).
- One or two "integrity probes" are woven in for topics the candidate skipped or
  failed, to test whether they understand the concept conceptually even without
  a passing hands-on submission (or to surface an honest gap).
"""

import json
import os
from typing import Any

CURRICULUM_PATH = os.path.join(os.path.dirname(__file__), "curriculum.json")

# Days most central to the challenge's own topic list (RAG, vector DBs, prompting,
# agentic AI, MCP, deployment) get a priority boost during selection.
PRIORITY_DAYS = {
    7: 3, 8: 3, 9: 2, 10: 4, 11: 4,      # embeddings / vector search / RAG
    12: 4, 13: 3,                          # prompt engineering / structured outputs
    16: 2, 20: 2,                          # chatbot app / memory
    21: 4, 22: 4, 23: 5, 24: 4,            # agentic AI + MCP (name-checked in the brief)
    25: 2, 27: 2, 28: 3, 30: 2,            # eval, security, deployment
    31: 3,                                 # capstone
}

MIN_QUESTIONS = 8
MIN_DAYS = 4
TARGET_MAIN_TOPICS = 9  # main topics in the plan; follow-ups can push total >= 8 easily
MAX_PROBES = 2


def _load_curriculum() -> dict[int, dict]:
    with open(CURRICULUM_PATH, "r") as f:
        data = json.load(f)
    return {d["day"]: d for d in data["days"]}


def _module_for_day(day: int, modules: list[dict]) -> int:
    for m in modules:
        lo, hi = m["days"]
        if lo <= day <= hi:
            return m["n"]
    return 0


def build_plan(candidate: dict[str, Any]) -> list[dict]:
    """
    Returns an ordered list of plan entries:
      {day, title, type, objectives, tools, module, attempts, probe: bool,
       difficulty_hint: "deepen" | "verify" | "standard"}
    Guaranteed: len >= MIN_QUESTIONS (as main topics) spanning >= MIN_DAYS distinct days.
    """
    with open(CURRICULUM_PATH, "r") as f:
        raw = json.load(f)
    day_lookup = {d["day"]: d for d in raw["days"]}
    modules = raw["modules"]

    missions = candidate.get("missions", [])
    passed = [m for m in missions if m.get("passed") is True]
    troubled = [m for m in missions if m.get("passed") is False or m.get("skipped") is True]

    # Score passed missions: priority weight, minus a small penalty for very high
    # attempt counts (still testable, just framed as "verify understanding" not "deepen").
    def score(m):
        day = m["day"]
        base = PRIORITY_DAYS.get(day, 1)
        return base

    passed_sorted = sorted(passed, key=lambda m: (-score(m), m["day"]))

    chosen: list[dict] = []
    seen_days = set()
    for m in passed_sorted:
        if len(chosen) >= TARGET_MAIN_TOPICS:
            break
        day = m["day"]
        if day in seen_days or day not in day_lookup:
            continue
        curr = day_lookup[day]
        attempts = m.get("attempts", 1)
        if attempts <= 1:
            hint = "deepen"       # nailed it first try -> push into edge cases / trade-offs
        elif attempts >= 4:
            hint = "verify"       # struggled -> verify real understanding, go gentler
        else:
            hint = "standard"
        chosen.append({
            "day": day,
            "title": curr["title"],
            "type": curr["type"],
            "objectives": curr["objectives"],
            "tools": curr["tools"],
            "module": _module_for_day(day, modules),
            "attempts": attempts,
            "probe": False,
            "difficulty_hint": hint,
        })
        seen_days.add(day)

    # Backfill if the candidate simply hasn't passed enough distinct days (e.g. low completion)
    if len(chosen) < MIN_DAYS:
        for day, curr in sorted(day_lookup.items()):
            if len(chosen) >= MIN_DAYS:
                break
            if day in seen_days:
                continue
            chosen.append({
                "day": day, "title": curr["title"], "type": curr["type"],
                "objectives": curr["objectives"], "tools": curr["tools"],
                "module": _module_for_day(day, modules), "attempts": None,
                "probe": False, "difficulty_hint": "standard",
            })
            seen_days.add(day)

    # Weave in up to MAX_PROBES integrity-probe questions on skipped/failed topics
    troubled_sorted = sorted(troubled, key=lambda m: -PRIORITY_DAYS.get(m["day"], 1))
    probes_added = 0
    for m in troubled_sorted:
        if probes_added >= MAX_PROBES:
            break
        day = m["day"]
        if day in seen_days or day not in day_lookup:
            continue
        curr = day_lookup[day]
        chosen.append({
            "day": day, "title": curr["title"], "type": curr["type"],
            "objectives": curr["objectives"], "tools": curr["tools"],
            "module": _module_for_day(day, modules),
            "attempts": m.get("attempts"),
            "probe": True,
            "status": "skipped" if m.get("skipped") else "failed",
            "difficulty_hint": "verify",
        })
        seen_days.add(day)
        probes_added += 1

    # Final backfill: some candidates (low completion, many skips) won't have
    # enough passed+probe topics to hit the spec's 8-question minimum. Fill the
    # remainder from the untouched curriculum, highest priority first, framed as
    # general-knowledge questions rather than "defend your submission" questions.
    if len(chosen) < MIN_QUESTIONS:
        remaining_days = sorted(
            (d for d in day_lookup if d not in seen_days),
            key=lambda d: (-PRIORITY_DAYS.get(d, 1), d),
        )
        for day in remaining_days:
            if len(chosen) >= MIN_QUESTIONS:
                break
            curr = day_lookup[day]
            chosen.append({
                "day": day, "title": curr["title"], "type": curr["type"],
                "objectives": curr["objectives"], "tools": curr["tools"],
                "module": _module_for_day(day, modules), "attempts": None,
                "probe": True, "status": "not_attempted",
                "difficulty_hint": "verify",
            })
            seen_days.add(day)

    # Order roughly by curriculum progression, but push probes near a related module
    # and put a capstone/production-level topic last if present, for a natural close.
    chosen.sort(key=lambda c: (c["day"]))
    capstone = [c for c in chosen if c["type"] == "CAPSTONE"]
    others = [c for c in chosen if c["type"] != "CAPSTONE"]
    ordered = others + capstone

    # Final safety net for the hard minimums (spec: >= 8 questions, >= 4 distinct days)
    assert len(ordered) >= min(MIN_QUESTIONS, len(day_lookup))
    assert len({c["day"] for c in ordered}) >= min(MIN_DAYS, len(day_lookup))
    return ordered


def curriculum_context_for_days(days: list[int]) -> str:
    lookup = _load_curriculum()
    parts = []
    for d in days:
        if d in lookup:
            entry = lookup[d]
            parts.append(
                f"Day {d} - {entry['title']} ({entry['type']}): "
                f"objectives={entry['objectives']}; tools={entry['tools']}"
            )
    return "\n".join(parts)