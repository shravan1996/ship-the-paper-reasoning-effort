"""Draw the result figure from results/summary.json as a transparent SVG in the site's palette.

    python3 make_figures.py figures/prototype-result.svg
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
INK, MUTED, FAINT, RULE = "#191F1D", "#3F4945", "#5C6964", "#D3DBD7"
GREEN, AMBER = "#1F6B4C", "#8F6019"

LABELS = {
    "fixed_low": "Always low",
    "fixed_xhigh": "Always xhigh",
    "gold_ladder": "Ladder, gold answer",
    "agreement_ladder": "Ladder, two lows agree",
    "selfcheck_ladder": "Ladder, self-check",
}
NAMES = {"claude-sonnet-5-5": "CLAUDE SONNET 5.5", "claude-haiku-5-5": "CLAUDE HAIKU 5.5"}
STYLE = """  <style>
    text { stroke: none; }
    .serif { font-family: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, serif; }
    .sans  { font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
    .h1 { font-size: 26px; font-weight: 600; fill: #191F1D; }
    .sub { font-size: 14.5px; fill: #3F4945; }
    .label { font-size: 11px; font-weight: 700; letter-spacing: 1.1px; fill: #5C6964; }
    .colhead { font-size: 11px; font-weight: 700; letter-spacing: 1.1px; fill: #5C6964; }
    .row { font-size: 14.5px; fill: #191F1D; }
    .val { font-size: 13px; font-weight: 700; fill: #1F6B4C; }
    .valk { font-size: 13px; font-weight: 700; fill: #191F1D; }
    .valw { font-size: 13px; font-weight: 700; fill: #8F6019; }
    .num { font-size: 14px; fill: #3F4945; }
    .numw { font-size: 14px; font-weight: 700; fill: #8F6019; }
    .tick { font-size: 12px; fill: #5C6964; }
    .foot { font-size: 13.5px; fill: #3F4945; }
  </style>"""


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def panel(res, y0, lo_acc, hi_acc):
    """One model's five policies as ruled rows: an accuracy dot on a shared axis, then costs."""
    p = res["primary"]
    api = res["direct_api_estimate"]
    base, base_api = p["fixed_xhigh"]["usd_per_item"], api["fixed_xhigh"]["usd_per_item"]
    ax0, ax1 = 240, 440
    px = lambda a: ax0 + (ax1 - ax0) * (a - lo_acc) / (hi_acc - lo_acc)
    out = [f'<text class="sans label" x="32" y="{y0}">{NAMES[res["model"]]}, {res["items"]} QUESTIONS</text>']
    y = y0 + 20
    xr = px(p["fixed_xhigh"]["accuracy"])
    out.append(f'<line x1="{xr:.1f}" y1="{y - 4}" x2="{xr:.1f}" y2="{y + 30 * len(LABELS) - 6}" '
               f'stroke="{FAINT}" stroke-width="1" stroke-dasharray="3 3"/>')
    for k in LABELS:
        acc = p[k]["accuracy"]
        realistic = k in ("agreement_ladder", "selfcheck_ladder")
        colour = AMBER if realistic else (GREEN if k == "gold_ladder" else INK)
        cls = "valw" if realistic else ("val" if k == "gold_ladder" else "valk")
        out.append(f'<line x1="{ax0}" y1="{y + 9}" x2="{ax1}" y2="{y + 9}" stroke="{RULE}" stroke-width="1"/>')
        out.append(f'<text class="sans row" x="32" y="{y + 14}">{esc(LABELS[k])}</text>')
        out.append(f'<circle cx="{px(acc):.1f}" cy="{y + 9}" r="6" fill="{colour}"/>')
        left = acc > xr_acc(p) - 0.005 and k != "fixed_xhigh" or k == "fixed_xhigh"
        dx, anchor = (10, "start") if left else (-10, "end")
        out.append(f'<text class="sans {cls}" x="{px(acc) + dx:.1f}" y="{y + 4}" text-anchor="{anchor}">{acc * 100:.1f}%</text>')
        cli = p[k]["usd_per_item"] / base
        direct = api[k]["usd_per_item"] / base_api
        out.append(f'<text class="sans {"numw" if cli > 1.0 else "num"}" x="522" y="{y + 14}" text-anchor="end">{cli:.2f}x</text>')
        out.append(f'<text class="sans {"numw" if direct > 1.0 else "num"}" x="586" y="{y + 14}" text-anchor="end">{direct:.2f}x</text>')
        out.append(f'<text class="sans num" x="648" y="{y + 14}" text-anchor="end">{p[k]["escalation_rate"] * 100:.0f}%</text>')
        y += 30
    a = lo_acc
    while a <= hi_acc + 1e-9:
        out.append(f'<text class="sans tick" x="{px(a):.1f}" y="{y + 8}" text-anchor="middle">{a * 100:.0f}%</text>')
        a += 0.05
    return out, y + 8


def xr_acc(p):
    return p["fixed_xhigh"]["accuracy"]


def main(path):
    summary = json.load(open(ROOT / "results" / "summary.json"))
    models = [m for m in ("claude-sonnet-5-5", "claude-haiku-5-5") if m in summary]
    accs = [summary[m]["primary"][k]["accuracy"] for m in models for k in LABELS]
    lo_acc = (int(min(accs) * 100) // 5) * 5 / 100
    hi_acc = (int(max(accs) * 100) // 5 + 1) * 5 / 100
    W = 680
    body = []
    y = 176
    for m in models:
        rows, y = panel(summary[m], y, lo_acc, hi_acc)
        body += ["  " + r for r in rows]
        y += 46
    H = y + 46
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">',
           '  <title id="title">What each ladder bought</title>',
           f'  <desc id="desc">{esc(describe(summary, models))}</desc>',
           STYLE,
           '  <text class="serif h1" x="32" y="44">What each ladder bought</text>',
           '  <text class="sans sub" x="32" y="72">Accuracy on BBEH questions, and mean cost per question as a</text>',
           '  <text class="sans sub" x="32" y="92">multiple of always running xhigh. Dashed line: always xhigh.</text>',
           f'  <line x1="32" y1="110" x2="648" y2="110" stroke="{RULE}" stroke-width="1"/>',
           '  <text class="sans colhead" x="340" y="140" text-anchor="middle">ACCURACY</text>',
           '  <text class="sans colhead" x="522" y="132" text-anchor="end">COST,</text>',
           '  <text class="sans colhead" x="522" y="146" text-anchor="end">CLI</text>',
           '  <text class="sans colhead" x="586" y="132" text-anchor="end">COST,</text>',
           '  <text class="sans colhead" x="586" y="146" text-anchor="end">API</text>',
           '  <text class="sans colhead" x="648" y="132" text-anchor="end">TO</text>',
           '  <text class="sans colhead" x="648" y="146" text-anchor="end">XHIGH</text>']
    out += body
    out.append(f'  <text class="sans foot" x="32" y="{H - 34}">CLI: the Claude Code CLI\'s list-price figure, the pre-registered measure.</text>')
    out.append(f'  <text class="sans foot" x="32" y="{H - 14}">API: the same calls priced without the CLI\'s own tokens. Amber: real checks.</text>')
    out.append("</svg>")
    Path(path).write_text("\n".join(out) + "\n")


def describe(summary, models):
    parts = []
    for m in models:
        p = summary[m]["primary"]
        a = summary[m]["direct_api_estimate"]
        base, base_a = p["fixed_xhigh"]["usd_per_item"], a["fixed_xhigh"]["usd_per_item"]
        bits = [f"{LABELS[k].lower()}, {p[k]['accuracy'] * 100:.1f} percent correct, "
                f"{p[k]['usd_per_item'] / base:.2f} times the cost of always xhigh at the CLI's price "
                f"and {a[k]['usd_per_item'] / base_a:.2f} times without the CLI's overhead, "
                f"{p[k]['escalation_rate'] * 100:.0f} percent sent to xhigh"
                for k in LABELS]
        parts.append(f"{NAMES[m].title()}, {summary[m]['items']} questions: " + "; ".join(bits) + ".")
    return "Five policies compared on BBEH questions. " + " ".join(parts)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "figures/prototype-result.svg")
