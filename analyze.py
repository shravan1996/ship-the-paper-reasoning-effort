"""Score every pre-registered policy from results/calls.jsonl.

    python3 analyze.py                      # both models, writes results/summary.json
    python3 analyze.py --model claude-sonnet-5-5

No calls are made here. Each policy is replayed from the recorded replies, charging every call it
would have made, as the paper's Appendix H does for its laddering numbers.
"""
import argparse
import json
import random
import re
from collections import defaultdict
from pathlib import Path

from effort import bbeh

ROOT = Path(__file__).parent
CALLS = ROOT / "results" / "calls.jsonl"
ROLES = ("a1", "a2", "x1", "chk1", "chk2")

# Added after the Sonnet run, not pre-registered. The CLI writes about 700 tokens of its own to a
# one-hour cache entry on every call, at twice the input price, which charges a policy for every
# extra call it makes. This estimate drops that overhead and prices the rest at list, as a direct
# API call with no caching would be billed. Prices were read back from the CLI's own cost figures.
CLI_OVERHEAD_TOKENS = 695
PRICES = {"claude-sonnet-5-5": (2.0e-6, 10.0e-6), "claude-haiku-5-5": (0.1e-6, 0.5e-6)}
VERDICT = re.compile(r"verdict\s*[:：]\s*[*_`]*\s*\b(in)?correct\b", re.IGNORECASE)
ANSWER_LINE = re.compile(r"the (final )?answer is", re.IGNORECASE)
B = 10_000


def verdict_ok(reply):
    """True only if the last verdict line says CORRECT. Missing or unparseable escalates."""
    found = VERDICT.findall(reply or "")
    return bool(found) and found[-1].lower() != "in"


def load(model, path=CALLS):
    """Latest ok record per (item, role) for one model."""
    latest = {}
    for line in Path(path).open():
        c = json.loads(line)
        if c["model"] == model and c["status"] == "ok":
            latest[(c["id"], c["role"])] = c
    return latest


def build_rows(model, path=CALLS, per_task=16):
    """One row per item that has all five roles; also returns the ids that were dropped."""
    latest = load(model, path)
    rows, dropped = [], []
    for it in bbeh.load_items(per_task=per_task):
        recs = {r: latest.get((it["id"], r)) for r in ROLES}
        if any(v is None for v in recs.values()):
            dropped.append(it["id"])
            continue
        row = {"id": it["id"], "task": it["task"]}
        for r in ("a1", "a2", "x1"):
            row[f"{r}_ok"] = bbeh.correct(recs[r]["content"], it["target"])
            row[f"{r}_ans"] = bbeh.answer(recs[r]["content"])
            row[f"{r}_line"] = bool(ANSWER_LINE.search(recs[r]["content"] or ""))
        for r in ("chk1", "chk2"):
            row[f"{r}_pass"] = verdict_ok(recs[r]["content"])
        p_in, p_out = PRICES[model]
        for r in ROLES:
            row[f"{r}_usd"] = recs[r]["cost_usd"] or 0.0
            row[f"{r}_api"] = (max(recs[r]["input_tokens"] - CLI_OVERHEAD_TOKENS, 0) * p_in
                               + recs[r]["output_tokens"] * p_out)
            row[f"{r}_s"] = recs[r]["seconds"]
            row[f"{r}_out"] = recs[r]["output_tokens"]
        rows.append(row)
    return rows, dropped


def policies(row, first="a1", second="a2", check="chk1"):
    """(correct, usd, seconds, escalated) for each policy on one item, one ordering."""
    a, b, x, c = first, second, "x1", check
    out = {}
    out["fixed_low"] = (row[f"{a}_ok"], row[f"{a}_usd"], row[f"{a}_s"], False)
    out["fixed_xhigh"] = (row["x1_ok"], row["x1_usd"], row["x1_s"], True)

    def ladder(name, escalate, usd, sec):
        if escalate:
            out[name] = (row["x1_ok"], usd + row["x1_usd"], sec + row["x1_s"], True)
        else:
            out[name] = (row[f"{a}_ok"], usd, sec, False)

    ladder("gold_ladder", not row[f"{a}_ok"], row[f"{a}_usd"], row[f"{a}_s"])
    ladder("agreement_ladder", row[f"{a}_ans"] != row[f"{b}_ans"],
           row[f"{a}_usd"] + row[f"{b}_usd"], max(row[f"{a}_s"], row[f"{b}_s"]))
    ladder("selfcheck_ladder", not row[f"{c}_pass"],
           row[f"{a}_usd"] + row[f"{c}_usd"], row[f"{a}_s"] + row[f"{c}_s"])
    # exploratory
    ladder("format_ladder", not row[f"{a}_line"], row[f"{a}_usd"], row[f"{a}_s"])
    if row[f"{a}_ok"]:
        out["retry_low_gold"] = (True, row[f"{a}_usd"], row[f"{a}_s"], False)
    else:
        out["retry_low_gold"] = (row[f"{b}_ok"], row[f"{a}_usd"] + row[f"{b}_usd"],
                                 row[f"{a}_s"] + row[f"{b}_s"], True)
    return out


PRIMARY = ["fixed_low", "fixed_xhigh", "gold_ladder", "agreement_ladder", "selfcheck_ladder"]
EXPLORATORY = ["format_ladder", "retry_low_gold"]


def summarise(rows, order=("a1", "a2", "chk1")):
    per = [policies(r, *order) for r in rows]
    n = len(rows)
    res = {}
    for p in PRIMARY + EXPLORATORY:
        vals = [q[p] for q in per]
        res[p] = {
            "accuracy": sum(v[0] for v in vals) / n,
            "usd_per_item": sum(v[1] for v in vals) / n,
            "seconds_per_item": sum(v[2] for v in vals) / n,
            "escalation_rate": sum(v[3] for v in vals) / n,
        }
    return res, per


def bootstrap(per, n_boot=B, seed=0):
    """Paired 95% intervals for accuracy and cost of each policy against fixed xhigh."""
    rng = random.Random(seed)
    n = len(per)
    names = PRIMARY + EXPLORATORY
    diffs = {p: {"acc": [], "cost_ratio": []} for p in names}
    for _ in range(n_boot):
        idx = [rng.randrange(n) for _ in range(n)]
        base_acc = sum(per[i]["fixed_xhigh"][0] for i in idx) / n
        base_usd = sum(per[i]["fixed_xhigh"][1] for i in idx) / n
        for p in names:
            acc = sum(per[i][p][0] for i in idx) / n
            usd = sum(per[i][p][1] for i in idx) / n
            diffs[p]["acc"].append(acc - base_acc)
            diffs[p]["cost_ratio"].append(usd / base_usd)
    out = {}
    for p in names:
        a = sorted(diffs[p]["acc"])
        c = sorted(diffs[p]["cost_ratio"])
        out[p] = {"acc_vs_xhigh_ci": [a[int(0.025 * n_boot)], a[int(0.975 * n_boot) - 1]],
                  "cost_ratio_ci": [c[int(0.025 * n_boot)], c[int(0.975 * n_boot) - 1]]}
    return out


def check_quality(rows):
    """How each realistic trigger sorts right and wrong low replies (both orderings pooled)."""
    out = {}
    for name, flag in [("selfcheck", lambda r, a, c, b: not r[f"{c}_pass"]),
                       ("agreement", lambda r, a, c, b: r[f"{a}_ans"] != r[f"{b}_ans"])]:
        tp = fn = fp = tn = 0
        for r in rows:
            for a, c, b in (("a1", "chk1", "a2"), ("a2", "chk2", "a1")):
                f = flag(r, a, c, b)
                if r[f"{a}_ok"]:
                    fp += f
                    tn += not f
                else:
                    tp += f
                    fn += not f
        out[name] = {"wrong_flagged": tp, "wrong_missed": fn, "right_flagged": fp, "right_passed": tn,
                     "catch_rate": tp / max(tp + fn, 1), "false_alarm_rate": fp / max(fp + tn, 1)}
    return out


def random_split(s):
    """Accuracy of sending a random share of questions to xhigh and the rest to low, at each
    policy's own cost. A policy below this line is beaten by a coin with the same budget."""
    lo, x = s["fixed_low"], s["fixed_xhigh"]
    out = {}
    for p, v in s.items():
        share = (v["usd_per_item"] - lo["usd_per_item"]) / (x["usd_per_item"] - lo["usd_per_item"])
        out[p] = None if not 0 <= share <= 1 else lo["accuracy"] + share * (x["accuracy"] - lo["accuracy"])
    return out


def decompose(rows):
    """Where each ladder gains or loses against always-xhigh, first ordering (a1, a2, chk1).

    A ladder differs from always-xhigh only on questions where low and xhigh disagree in
    correctness: 'fixable' (low wrong, xhigh right) and 'low_only' (low right, xhigh wrong)."""
    fix = [r for r in rows if not r["a1_ok"] and r["x1_ok"]]
    low_only = [r for r in rows if r["a1_ok"] and not r["x1_ok"]]
    wrong = [r for r in rows if not r["a1_ok"]]
    flags = {"agreement": lambda r: r["a1_ans"] != r["a2_ans"], "selfcheck": lambda r: not r["chk1_pass"]}
    return {"low_wrong": len(wrong), "both_wrong": sum(not r["x1_ok"] for r in wrong),
            "fixable": len(fix), "low_only": len(low_only),
            "fixable_flagged": {k: sum(f(r) for r in fix) for k, f in flags.items()},
            "low_only_flagged": {k: sum(f(r) for r in low_only) for k, f in flags.items()}}


def decide(s, ci):
    """The pre-registered outcome, from the primary ordering's point estimates."""
    x = s["fixed_xhigh"]
    g = s["gold_ladder"]
    replicated = g["accuracy"] >= x["accuracy"] - 0.01 and g["usd_per_item"] < x["usd_per_item"]
    realistic = ["agreement_ladder", "selfcheck_ladder"]
    cont = [p for p in realistic
            if s[p]["accuracy"] >= x["accuracy"] - 0.02 and s[p]["usd_per_item"] <= 0.75 * x["usd_per_item"]]
    stop = all(s[p]["accuracy"] < x["accuracy"] - 0.05 for p in realistic) or \
        all(s[p]["usd_per_item"] > x["usd_per_item"] for p in realistic)
    return {"replicated": replicated, "continue_met_by": cont, "stop": stop,
            "outcome": "continue" if cont else ("stop" if stop else "partial")}


def per_task(rows):
    by = defaultdict(list)
    for r in rows:
        by[r["task"]].append(r)
    out = {}
    for t, rs in sorted(by.items()):
        n = len(rs)
        out[t] = {"n": n,
                  "low": sum((r["a1_ok"] + r["a2_ok"]) / 2 for r in rs) / n,
                  "xhigh": sum(r["x1_ok"] for r in rs) / n,
                  "low_usd": sum((r["a1_usd"] + r["a2_usd"]) / 2 for r in rs) / n,
                  "xhigh_usd": sum(r["x1_usd"] for r in rs) / n}
    return out


def analyse(model, path=CALLS):
    rows, dropped = build_rows(model, path)
    if not rows:
        return None
    s1, per1 = summarise(rows, ("a1", "a2", "chk1"))
    s2, _ = summarise(rows, ("a2", "a1", "chk2"))
    ci = bootstrap(per1)
    api_rows = [dict(r, **{f"{x}_usd": r[f"{x}_api"] for x in ROLES}) for r in rows]
    s_api, per_api = summarise(api_rows, ("a1", "a2", "chk1"))
    ci_api = bootstrap(per_api)
    regress = sum(r["a1_ok"] and not r["x1_ok"] for r in rows)
    gained = sum(r["x1_ok"] and not r["a1_ok"] for r in rows)
    out_tokens = {r: sum(row[f"{r}_out"] for row in rows) / len(rows) for r in ROLES}
    return {"model": model, "items": len(rows), "dropped": dropped,
            "primary": s1, "second_ordering": s2, "intervals": ci,
            "direct_api_estimate": s_api, "direct_api_intervals": ci_api,
            "decision_direct_api": decide(s_api, ci_api),
            "random_split": random_split(s1), "random_split_direct_api": random_split(s_api),
            "decision": decide(s1, ci), "checks": check_quality(rows),
            "a1_solved_x1_failed": regress, "x1_solved_a1_failed": gained,
            "decomposition": decompose(rows),
            "mean_output_tokens": out_tokens, "tails": tails(rows),
            "per_task": per_task(rows)}


def tails(rows):
    """Latency and output-token tails per effort level (low pools a1 and a2)."""
    out = {}
    for name, roles in (("low", ("a1", "a2")), ("xhigh", ("x1",)), ("check", ("chk1", "chk2"))):
        s = sorted(r[f"{x}_s"] for r in rows for x in roles)
        t = sorted(r[f"{x}_out"] for r in rows for x in roles)
        q = lambda v, p: v[min(len(v) - 1, int(p * len(v)))]
        out[name] = {"median_s": q(s, 0.5), "p95_s": q(s, 0.95), "max_s": s[-1],
                     "median_out": q(t, 0.5), "p95_out": q(t, 0.95), "max_out": t[-1]}
    return out


def show(res):
    print(f"\n{res['model']}: {res['items']} items, {len(res['dropped'])} dropped")
    print(f"{'policy':18} {'acc':>6} {'vs xhigh (95% CI)':>24} {'$/item':>8} {'x xhigh':>8} {'s/item':>7} {'esc':>5}")
    for p in PRIMARY + EXPLORATORY:
        s = res["primary"][p]
        ci = res["intervals"][p]
        x = res["primary"]["fixed_xhigh"]
        d = s["accuracy"] - x["accuracy"]
        print(f"{p:18} {s['accuracy']*100:6.1f} {d*100:+6.1f} [{ci['acc_vs_xhigh_ci'][0]*100:+5.1f},{ci['acc_vs_xhigh_ci'][1]*100:+5.1f}]"
              f" {s['usd_per_item']:8.4f} {s['usd_per_item']/x['usd_per_item']:8.2f} {s['seconds_per_item']:7.1f} {s['escalation_rate']*100:5.1f}")
    x = res["direct_api_estimate"]["fixed_xhigh"]["usd_per_item"]
    print("direct-API estimate, cost x xhigh:", {p: round(v["usd_per_item"] / x, 2) for p, v in res["direct_api_estimate"].items()},
          "| $ xhigh", round(x, 4), "| decision", res["decision_direct_api"]["outcome"])
    print("random split at same cost (CLI $):", {p: None if v is None else round(v * 100, 1) for p, v in res["random_split"].items()})
    print("random split at same cost (direct API):", {p: None if v is None else round(v * 100, 1) for p, v in res["random_split_direct_api"].items()})
    print("second ordering acc:", {p: round(v["accuracy"] * 100, 1) for p, v in res["second_ordering"].items()})
    print("checks:", json.dumps(res["checks"]))
    print("decomposition:", json.dumps(res["decomposition"]))
    print("a1 solved, x1 failed:", res["a1_solved_x1_failed"], "| x1 solved, a1 failed:", res["x1_solved_a1_failed"])
    print("mean output tokens:", {k: round(v) for k, v in res["mean_output_tokens"].items()})
    print("decision:", res["decision"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", nargs="*", default=["claude-sonnet-5-5", "claude-haiku-5-5"])
    args = ap.parse_args()
    out = {}
    for m in args.model:
        res = analyse(m)
        if res:
            show(res)
            out[m] = res
    (ROOT / "results").mkdir(exist_ok=True)
    json.dump(out, open(ROOT / "results" / "summary.json", "w"), indent=1)


if __name__ == "__main__":
    main()
