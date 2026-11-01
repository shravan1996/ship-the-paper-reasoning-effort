"""Fold the Haiku arm's separate call file into results/calls.jsonl.

Haiku was collected in parallel with Sonnet, into results/calls-haiku.jsonl, so that two
processes never appended to one file. This keeps every Sonnet record from calls.jsonl, drops any
Haiku record there (a few calls started by the main runner before it was stopped), and appends
the Haiku file in its original order.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
main = ROOT / "results" / "calls.jsonl"
haiku = ROOT / "results" / "calls-haiku.jsonl"

kept = [line for line in main.open() if json.loads(line)["model"] != "claude-haiku-5-5"]
dropped = sum(1 for _ in main.open()) - len(kept)
added = [line for line in haiku.open() if line.strip()]
main.write_text("".join(kept) + "".join(added))
haiku.unlink()
print(f"kept {len(kept)} Sonnet records, dropped {dropped} stray Haiku records, added {len(added)} Haiku records")
