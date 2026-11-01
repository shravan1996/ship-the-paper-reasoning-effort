"""BIG-Bench Extra Hard (mini): items, the prompt suffix, and grading.

The 460 mini examples carry no task label, so `scripts/fetch_bbeh.sh` matched each back to its
task file by its exact input text and saved the labels in `data/bbeh_mini_tasks.json`. Grading is the benchmark's own `evaluate_correctness`, vendored unchanged in
`effort/bbeh_evaluate.py` (Apache 2.0, Google LLC).
"""
import json
from pathlib import Path

from effort import bbeh_evaluate

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

SUFFIX = ("\n\nThink it through, then end your reply with one line that starts with "
          "\"The answer is: \" followed by the final answer only, with no bold, no LaTeX and no "
          "other markup. For a multiple-choice question with one correct option, give only the "
          "option, for example \"The answer is: (A)\".")


def load_items(per_task=None):
    """Mini examples as dicts: id, task, input, target. Ordered by task, then mini order."""
    with open(DATA / "bbeh_mini.json") as f:
        mini = json.load(f)["examples"]
    with open(DATA / "bbeh_mini_tasks.json") as f:
        tasks = json.load(f)
    items, seen = [], {}
    for e, task in zip(mini, tasks):
        k = seen.get(task, 0)
        seen[task] = k + 1
        if per_task is not None and k >= per_task:
            continue
        items.append({"id": f"{task}-{k:02d}", "task": task, "input": e["input"], "target": e["target"]})
    items.sort(key=lambda x: x["id"])
    return items


def prompt(item):
    return item["input"] + SUFFIX


def answer(reply):
    """The normalised answer string the benchmark would compare, or '' if none."""
    if not reply:
        return ""
    return bbeh_evaluate.preprocess_sample(reply)


def correct(reply, target):
    if not reply:
        return False
    return bbeh_evaluate.evaluate_correctness(reply, target)
