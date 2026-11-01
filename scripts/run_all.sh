#!/bin/sh
# The whole collection, in the pre-registered order: Sonnet first, then Haiku. Resumable.
cd "$(dirname "$0")/.."
for m in claude-sonnet-5-5 claude-haiku-5-5; do
  python3 collect.py --model "$m" --stage solve --workers "${WORKERS:-22}"
  python3 collect.py --model "$m" --stage solve --workers "${WORKERS:-22}"   # second pass retries any errors
  python3 collect.py --model "$m" --stage check --workers "${WORKERS:-22}"
  python3 collect.py --model "$m" --stage check --workers "${WORKERS:-22}"
done
