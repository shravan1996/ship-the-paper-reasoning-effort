"""Collect every reply the analysis needs, resumably.

For each item and model there are five calls:

    a1, a2   two independent attempts at low effort
    x1       one attempt at xhigh effort
    chk1     a low-effort check of a1's reply, ending in "Verdict: CORRECT" or "Verdict: INCORRECT"
    chk2     the same check of a2's reply

Stage `solve` makes a1, a2 and x1; stage `check` makes chk1 and chk2, which need the replies they
check. Every call is appended to results/calls.jsonl. A rerun skips calls that already have an ok
record and retries the rest, so the collection can stop and restart at any point.

    python3 collect.py --model claude-sonnet-5-5 --stage solve
    python3 collect.py --model claude-sonnet-5-5 --stage check
"""
import argparse
import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from effort import bbeh
from effort.claude import call

ROOT = Path(__file__).parent
CALLS = Path(os.environ.get("EFFORT_CALLS", ROOT / "results" / "calls.jsonl"))
PER_TASK = 16          # items 00-15 of each task; 18 and 19 were the pilot and are never scored
MAX_TRIES = 3

ROLES = {"a1": "low", "a2": "low", "x1": "xhigh", "chk1": "low", "chk2": "low"}

CHECK = ("Below is a problem and a reply that another assistant wrote for it. Check whether the "
         "reply's final answer is correct. Work through the problem yourself as far as you need "
         "to. End with exactly one line: \"Verdict: CORRECT\" if the final answer is right, or "
         "\"Verdict: INCORRECT\" if it is wrong or missing.\n\n<problem>\n{problem}\n</problem>"
         "\n\n<reply>\n{reply}\n</reply>")

_lock = threading.Lock()


def load_calls():
    if not CALLS.exists():
        return []
    return [json.loads(line) for line in CALLS.open() if line.strip()]


def append(rec):
    with _lock:
        CALLS.parent.mkdir(parents=True, exist_ok=True)
        with CALLS.open("a") as f:
            f.write(json.dumps(rec) + "\n")


def check_prompt(item, reply):
    return CHECK.format(problem=bbeh.prompt(item), reply=reply)


def run(model, item, role, prompt_text):
    rec = call(model, ROLES[role], prompt_text)
    rec.update(model=model, id=item["id"], task=item["task"], role=role, effort=ROLES[role],
               at=time.strftime("%Y-%m-%dT%H:%M:%S"))
    append(rec)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--stage", choices=["solve", "check"], required=True)
    ap.add_argument("--workers", type=int, default=14)
    ap.add_argument("--limit", type=int, default=None, help="only the first N items (smoke test)")
    args = ap.parse_args()

    items = bbeh.load_items(per_task=PER_TASK)
    if args.limit:
        items = items[: args.limit]
    calls = [c for c in load_calls() if c["model"] == args.model]
    done = {(c["id"], c["role"]) for c in calls if c["status"] == "ok"}
    tries = {}
    for c in calls:
        tries[(c["id"], c["role"])] = tries.get((c["id"], c["role"]), 0) + 1
    replies = {(c["id"], c["role"]): c["content"] for c in calls if c["status"] == "ok"}

    jobs = []
    for it in items:
        roles = ["a1", "a2", "x1"] if args.stage == "solve" else ["chk1", "chk2"]
        for role in roles:
            key = (it["id"], role)
            if key in done or tries.get(key, 0) >= MAX_TRIES:
                continue
            if role in ("a1", "a2", "x1"):
                jobs.append((it, role, bbeh.prompt(it)))
            else:
                src = replies.get((it["id"], "a1" if role == "chk1" else "a2"))
                if src is None:
                    continue
                jobs.append((it, role, check_prompt(it, src)))

    print(f"{args.model} {args.stage}: {len(jobs)} calls to make", flush=True)
    t0 = time.time()
    n_ok = n_err = 0
    with ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(run, args.model, it, role, p) for it, role, p in jobs]
        for i, f in enumerate(as_completed(futs), 1):
            r = f.result()
            n_ok += r["status"] == "ok"
            n_err += r["status"] != "ok"
            if i % 50 == 0 or i == len(futs):
                print(f"  {i}/{len(futs)} ok={n_ok} err={n_err} {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
