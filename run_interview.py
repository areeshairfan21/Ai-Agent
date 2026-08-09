
import json
import sys
import uuid

import requests

SERVER_URL = "http://localhost:8000/api/interview"
CANDIDATES_FILE = "candidates.json"


def load_candidates() -> list[dict]:
    try:
        with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Couldn't find {CANDIDATES_FILE} in this folder. Make sure it's named exactly that.")
        sys.exit(1)
    return data["candidates"]


def pick_candidate(candidates: list[dict]) -> dict:
    print("\nAvailable candidates:")
    for i, c in enumerate(candidates):
        m = c["member"]
        print(f"  [{i}] {m['name']} — {m['jobRole']} ({m.get('yearsExperience', '?')} yrs)")
    while True:
        choice = input("\nPick a candidate number: ").strip()
        if choice.isdigit() and 0 <= int(choice) < len(candidates):
            return candidates[int(choice)]
        print("Not a valid number, try again.")


def main():
    candidates = load_candidates()
    candidate = pick_candidate(candidates)
    session_id = str(uuid.uuid4())

    print(f"\nStarting interview for {candidate['member']['name']}...\n" + "-" * 60)

    resp = requests.post(SERVER_URL, json={"sessionId": session_id, "candidate": candidate})
    if resp.status_code != 200:
        print(f"Server error ({resp.status_code}): {resp.text}")
        sys.exit(1)
    data = resp.json()

    turn = 0
    while not data.get("done"):
        turn += 1
        print(f"\nINTERVIEWER: {data['reply']}\n")
        answer = input("YOU: ").strip()
        if not answer:
            answer = "I'm not sure, can we move on?"
        resp = requests.post(SERVER_URL, json={"sessionId": session_id, "message": answer})
        if resp.status_code != 200:
            print(f"Server error ({resp.status_code}): {resp.text}")
            sys.exit(1)
        data = resp.json()

    print("\n" + "=" * 60)
    print("INTERVIEW COMPLETE")
    print("=" * 60)
    print(f"\n{data['reply']}\n")

    fb = data.get("feedback")
    if fb:
        print("SUMMARY:")
        print(f"  {fb['summary']}\n")
        print("STRENGTHS:")
        for s in fb.get("strengths", []):
            print(f"  - {s}")
        print("\nGAPS:")
        for g in fb.get("gaps", []):
            print(f"  - {g}")
        print("\nNEXT STEPS:")
        for n in fb.get("next", []):
            print(f"  - {n}")
    print()


if __name__ == "__main__":
    main()
