# Ship the Paper: the effort ladder without an answer key

A small, pre-registered test of one claim from Sun, Kwon, Hasan, Zhu, Zhou and Bianchi,
[What Effort Level Should I Choose? On the Economics of Reasoning Effort in LLM Agents](https://arxiv.org/abs/2610.34491)
(arXiv:2610.34491, first posted 25 October 2026; code at
[KaiserWhoLearns/ReasoningEffortLLM](https://github.com/KaiserWhoLearns/ReasoningEffortLLM)).

The paper finds that **naive laddering**, starting every task at the lowest reasoning effort and
retrying once at the highest only after a failed correctness check, matches or beats always
running the highest effort, usually for less. On its single-call benchmarks the correctness
check is the answer key. A live service answering one question has no answer key, so this repo
asks what is left of the result when the check is one a deployment can actually run:

- **agreement**: run low twice and escalate when the two answers differ;
- **self-check**: ask the model, at low effort, to review its own reply.

Written up on the site as an article in the Ship the Paper series.

## Result

368 BIG-Bench Extra Hard questions per model. Accuracy, and mean cost per question as a multiple
of always running xhigh: first at the CLI's list price (the pre-registered measure), then in a
direct-API estimate without the CLI's own tokens (added after the run).

| Policy | Sonnet 5.5 | cost (CLI / API) | Haiku 5.5 | cost (CLI / API) |
| --- | ---: | ---: | ---: | ---: |
| Always low | 68.2% | 0.44 / 0.35 | 63.9% | 0.35 / 0.32 |
| Always xhigh | 75.8% | 1.00 / 1.00 | 69.8% | 1.00 / 1.00 |
| Ladder, gold answer (the paper's check) | 77.4% | 0.88 / 0.78 | 75.3% | 0.73 / 0.70 |
| Ladder, two low answers agree | 73.1% | 1.11 / 0.98 | 69.8% | 1.07 / 1.03 |
| Ladder, low-effort self-check | 73.4% | 1.12 / 0.91 | 70.1% | 1.00 / 0.93 |

- **Replication held.** With the answer key as its check, the ladder beat always-xhigh on both
  models (Sonnet +1.6 points, 95% interval 0.5 to 3.0; Haiku +5.4, 3.3 to 7.9) and cost less.
- **The realistic checks did not stand in for it.** On Sonnet both realistic ladders were less
  accurate than always-xhigh (agreement -2.7, interval -4.6 to -1.1; self-check -2.4, -4.6 to
  -0.5) and cost more at the CLI's price. On Haiku they tied it on accuracy at about its cost.
- **Pre-registered outcome:** Sonnet, which decides, **stop** (both realistic ladders cost more
  than always-xhigh). Haiku, partial. Under the direct-API estimate both models read partial.
- **Why:** of the questions low got wrong, most were wrong at xhigh too (Sonnet 83 of 117), so
  only a minority were fixable by escalating (Sonnet 34). The checks flagged about two thirds of
  those, paid for a call on every question, and also flagged most of the few questions where low
  was right and xhigh wrong (Sonnet: agreement flagged 5 of 6).
- **With a perfect check, effort barely mattered:** retrying at low instead of xhigh, with the
  answer key deciding, scored 75.5% on Sonnet at 0.55 times always-xhigh's cost (exploratory).

`python3 analyze.py` prints all of this, plus both orderings of the low attempts, check
catch rates, latency and token tails, per-task numbers and the random-split comparison.

## What was run

- **Items:** BIG-Bench Extra Hard, mini split, items 00 to 15 of each of its 23 tasks: 368
  questions, graded by the benchmark's own `evaluate_correctness`. Items 18 and 19 of each task
  were a pilot and are never scored.
- **Models:** Claude Sonnet 5.5 (primary) and Claude Haiku 5.5, through the Claude Code CLI with no
  tools and an empty system prompt, at `--effort low` and `--effort xhigh`.
- **Calls per item and model:** two low attempts, one xhigh attempt, and one low-effort self-check
  of each low reply. 3,680 scored calls in all.
- **Policies** are replayed from those calls, charging every call a policy would make. See
  [`PREREGISTRATION.md`](PREREGISTRATION.md) for the policies, thresholds and expectations, all
  committed before the first scored call.

## Run it

Python 3.10 or later, no third-party packages. You need the `claude` CLI, signed in.

```bash
python3 -m unittest discover -s tests        # 19 tests: grader, verdict parser, policy replay
python3 analyze.py                           # re-score every policy from results/calls.jsonl
python3 make_figures.py figures/prototype-result.svg
```

To collect your own replies (1,840 calls per model; 30 to 40 minutes per model at 22 to 30
parallel workers on the machine this ran on, longer for Haiku, which thinks far longer per call):

```bash
python3 collect.py --model claude-sonnet-5-5 --stage solve
python3 collect.py --model claude-sonnet-5-5 --stage check
```

Both stages resume from what is already in `results/calls.jsonl`.

## Files

```
collect.py           makes the calls (resumable)
analyze.py           replays every policy, bootstraps intervals, applies the pre-registered rule
make_figures.py      the result figure
effort/claude.py     one CLI call at one effort level
effort/bbeh.py       BBEH mini items, the answer-format suffix, grading
effort/bbeh_evaluate.py   BBEH's grader, vendored (Apache 2.0)
results/calls.jsonl  every scored call: reply, tokens, list-price cost, seconds
results/summary.json the numbers in the article
logs/                pilots, the smoke test and collector logs, never scored
scripts/             BBEH fetch, the collection runner, the Haiku merge
```

## Deviations from the pre-registration

- The pre-registration says Haiku runs after Sonnet. To save wall-clock time it ran alongside
  Sonnet, into its own file, `results/calls-haiku.jsonl`, which `scripts/merge_haiku.py` then
  folded into `results/calls.jsonl`. Nothing about the calls or the analysis changed.
- Three analyses were added after the Sonnet run, and none of them is part of the pre-registered
  decision: a direct-API cost estimate that removes the CLI's own ~700 cached tokens per call
  (`CLI_OVERHEAD_TOKENS`, `PRICES` in `analyze.py`, prices read back from the CLI's own cost
  figures); the accuracy a random split of traffic between low and xhigh would reach at each
  policy's cost; and a split of each ladder's gains and losses into fixable questions (low
  wrong, xhigh right) and low-only wins (low right, xhigh wrong).
- Each collector was restarted once to raise its worker count: Sonnet from 14 to 22, Haiku from
  14 to 30, because Haiku thinks for far longer per call. Calls in flight at that moment were
  lost and remade; no completed call was discarded.

## Limitations

- One sampled run per call, at the CLI's default temperature; every effort level thinks
  adaptively, and nothing here can turn thinking off.
- Dollars are the CLI's `total_cost_usd` at list price. The CLI adds several hundred tokens of
  its own to each call and writes cache entries, which raises every arm's cost, and raises a
  cheap call's cost proportionally more than an expensive one's.
- Single-call reasoning questions only. Agents, where a test suite can stand in for the answer
  key honestly, are out of scope.
- BBEH is public and has been since February 2025; some items may be in the models' training
  data. That affects every policy alike.
- 368 items, 16 per task. Per-task numbers are too small to act on.

## Licence

Code: MIT. BBEH data and grader: Apache 2.0, Google LLC. See [`LICENSE-DATA.md`](LICENSE-DATA.md).
