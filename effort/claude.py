"""One Claude call through the Claude Code CLI, with the effort level as the only knob.

There is no API key in the environment this was built in, so every call goes through
`claude -p` with no tools, no MCP servers and no settings files. The CLI cannot set temperature,
so replies are sampled at the default, and every effort level runs adaptive thinking. Sessions
are written under a scratch working directory, never this repository.

The JSON result carries token usage and `total_cost_usd` at list price. The CLI adds a few
hundred tokens of its own to every prompt and writes cache entries, so its dollar figures run a
little above what a direct API call would cost. Every arm pays the same overhead.
"""
import json
import os
import subprocess
import tempfile
import time

SCRATCH = os.environ.get("EFFORT_CLAUDE_CWD", os.path.join(tempfile.gettempdir(), "effort-claude"))
EFFORTS = ("low", "medium", "high", "xhigh", "max")


def call(model, effort, prompt, system="", timeout=900):
    """Send one user message at one effort level. Returns a flat record, never raises."""
    if effort not in EFFORTS:
        raise ValueError(f"unknown effort {effort!r}")
    os.makedirs(SCRATCH, exist_ok=True)
    cmd = ["claude", "-p", "--model", model, "--effort", effort,
           "--tools", "", "--strict-mcp-config", "--setting-sources", "",
           "--no-session-persistence", "--output-format", "json",
           "--system-prompt", system]
    t = time.time()
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=timeout, cwd=SCRATCH)
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "timeout", "seconds": round(time.time() - t, 3)}
    seconds = round(time.time() - t, 3)
    if proc.returncode != 0:
        return {"status": "error", "error": (proc.stderr or proc.stdout)[-500:], "seconds": seconds}
    try:
        out = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"status": "error", "error": "bad json: " + proc.stdout[-300:], "seconds": seconds}
    if out.get("is_error"):
        return {"status": "error", "error": str(out.get("result"))[-500:], "seconds": seconds}
    u = out.get("usage") or {}
    return {
        "status": "ok",
        "content": out.get("result") or "",
        "stop_reason": out.get("stop_reason"),
        "input_tokens": (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0)
                        + (u.get("cache_read_input_tokens") or 0),
        "output_tokens": u.get("output_tokens") or 0,
        "thinking_tokens": (u.get("output_tokens_details") or {}).get("thinking_tokens"),
        "cost_usd": out.get("total_cost_usd"),
        "seconds": seconds,
    }
