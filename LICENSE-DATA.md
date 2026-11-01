# Third-party data and code

- `data/bbeh_mini.json` is the mini split of BIG-Bench Extra Hard, and `effort/bbeh_evaluate.py`
  is its evaluation code with the example calls at the end removed. Both are from
  [google-deepmind/bbeh](https://github.com/google-deepmind/bbeh), Copyright 2025 Google LLC,
  licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).
  Kazemi et al., "BIG-Bench Extra Hard", arXiv:2502.19187. Several BBEH tasks build on earlier
  datasets; the BBEH README lists them and asks that they be cited too.
- `data/bbeh_mini_tasks.json` is derived: the task name of each mini example, recovered by
  matching its input text against the full task files (`scripts/fetch_bbeh.sh`).
- `logs/pilot.jsonl` holds replies to AIME 2026 problems from
  [MathArena/aime_2026](https://huggingface.co/datasets/MathArena/aime_2026)
  (CC BY-NC-SA 4.0). The problems themselves are not redistributed here.
- Everything in `results/` and `logs/` is model output from Claude Sonnet 5.5 and Claude Haiku
  5.5, collected for this trial.
