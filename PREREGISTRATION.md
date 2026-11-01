# Pre-registration

Written on 2026-11-01, after two pilots and before any scored call. Both pilots are kept in
`logs/` and are never scored: one ran AIME 2026 at low effort (Sonnet 5.5 solved 29 of 30, Haiku
5.5 solved 28, so AIME was dropped as too easy to show escalation), the other ran BBEH mini items
18 and 19 of each task at low effort (Sonnet 32 of 46, Haiku 31 of 46).

## The claim under test

Sun, Kwon, Hasan, Zhu, Zhou and Bianchi, "What Effort Level Should I Choose? On the Economics of
Reasoning Effort in LLM Agents" (arXiv:2610.34491, v1 25 October 2026), report that naive
laddering, which starts at the lowest reasoning effort and retries once at the highest effort
only after a failed correctness check, matches or improves on fixed top effort for every model
and benchmark they ran, at lower cost for most proprietary models (Section 3.4, Appendix H).

Their Appendix H states the assumption: the check is "a reliable external correctness verdict".
On their single-call benchmarks that verdict is the gold answer. This trial asks how much of the
result survives when the check is one a deployment has at run time.

**Question.** On single-call reasoning items, does a low-to-xhigh ladder whose escalation trigger
is (a) disagreement between two low-effort attempts or (b) a low-effort self-check match fixed
xhigh accuracy at lower cost, as the gold-answer ladder does?

## Items

BIG-Bench Extra Hard, mini split (google-deepmind/bbeh, Apache 2.0): items 00 to 15 of each of
the 23 tasks, 368 items. Each mini example is matched back to its task by its exact input text.
Graded by the benchmark's own `evaluate_correctness`, vendored unchanged.

## Models and calls

Claude Sonnet 5.5 (`claude-sonnet-5-5`) is the primary model; its results decide the outcome.
Claude Haiku 5.5 (`claude-haiku-5-5`) runs the same design afterwards as a secondary model.

Both are called through the Claude Code CLI with no tools, no MCP servers, no settings and an
empty system prompt. The CLI cannot set temperature, so replies are sampled at the default, and
every effort level thinks adaptively. Effort is the CLI's `--effort` flag: `low` and `xhigh`,
the same pair the paper uses for Claude (it skipped `max` on price). Dollars are the CLI's
`total_cost_usd` at list price, which includes a few hundred tokens of CLI overhead per call;
every arm pays it.

Per item and model: two low attempts (a1, a2), one xhigh attempt (x1), and one low-effort check
of each low reply (chk1 on a1, chk2 on a2). The check sees the problem and the full reply and
must end with "Verdict: CORRECT" or "Verdict: INCORRECT". A missing or unparseable verdict counts
as INCORRECT, so it escalates. A call that errors is retried up to three times in all; an item
with any role still missing after that is dropped from every policy for that model, and the
count is reported.

## Policies

Every policy pays for every call it makes. An escalation is a fresh xhigh attempt (x1) that does
not see the low reply, as in the paper.

| Policy | Calls | Escalates when | Final answer |
| --- | --- | --- | --- |
| fixed low | a1 | never | a1 |
| fixed xhigh | x1 | always | x1 |
| gold ladder (the paper's) | a1, then x1 if escalated | a1 is wrong by the gold answer | a1, or x1 |
| agreement ladder | a1 and a2, then x1 if escalated | a1 and a2 give different answers | a1, or x1 |
| self-check ladder | a1 and chk1, then x1 if escalated | chk1 does not say CORRECT | a1, or x1 |

"Different answers" compares the normalised answer strings the grader would read
(`preprocess_sample`), so "(A)" and "(a)" agree.

Accuracy is the share of items whose final answer is correct. Cost is mean dollars per item.
Latency is per item: the agreement ladder runs a1 and a2 at once, so its latency is the slower of
the two plus x1 when it escalates; the self-check ladder's is a1 plus chk1 plus x1 when it
escalates. Intervals are 95% percentile bootstrap over items, 10,000 resamples, paired.

## Thresholds

- **Replication.** The gold ladder's accuracy is at least fixed xhigh's minus 1 point, at lower
  mean cost. If this fails on Sonnet, the paper's result did not transfer to this setting and the
  realistic ladders are reported without a verdict on them.
- **Continue.** At least one realistic ladder (agreement or self-check) is within 2 points of
  fixed xhigh's accuracy, point estimate, at no more than 75% of its mean cost.
- **Stop.** Both realistic ladders trail fixed xhigh by more than 5 points, or both cost more
  than it.
- Anything else is reported as partial, with the numbers.

## What I expect, written before collection

- The gold ladder beats fixed xhigh on accuracy by several points, because it keeps every low
  success, and costs less. This replicates the paper.
- The agreement ladder loses 2 to 4 points against the gold ladder, from items where both low
  attempts agree on the same wrong answer, and lands near fixed xhigh. I am unsure of its cost:
  it always pays for two low calls, so if xhigh costs less than about twice what low does, it
  could cost more than fixed xhigh.
- The self-check ladder approves most of its own wrong answers, catching fewer than half, and
  lands 3 to 6 points below the gold ladder.

## Exploratory, not part of the decision

- Both orderings (a2 first, with chk2) as a stability check on the single-ordering numbers.
- A format-only ladder that escalates when the low reply has no answer line.
- A same-effort retry: a1, then a2 on a gold-answer failure, to separate "a second try" from
  "a second try at higher effort", as the paper's Appendix H.1 does.
- Regressions: items a1 solved that x1 failed.
- Per-task breakdowns.
