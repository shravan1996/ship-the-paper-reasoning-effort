#!/bin/sh
# Re-download BBEH mini and rebuild the task label of each example from the full task files.
# The committed data/bbeh_mini.json and data/bbeh_mini_tasks.json are what this produces.
set -e
cd "$(dirname "$0")/.."
base=https://raw.githubusercontent.com/google-deepmind/bbeh/main/bbeh
curl -sL "$base/mini/data.json" -o data/bbeh_mini.json
mkdir -p data/bbeh_tasks
for t in boardgame_qa boolean_expressions buggy_tables causal_understanding disambiguation_qa \
         dyck_languages geometric_shapes hyperbaton linguini movie_recommendation \
         multistep_arithmetic nycc object_counting object_properties sarc_triples \
         shuffled_objects spatial_reasoning sportqa temporal_sequence time_arithmetic \
         web_of_lies word_sorting zebra_puzzles; do
  curl -sL "$base/benchmark_tasks/bbeh_$t/task.json" -o "data/bbeh_tasks/bbeh_$t.json"
done
python3 -c "
import json, glob, os
mini = json.load(open('data/bbeh_mini.json'))['examples']
owner = {}
for f in sorted(glob.glob('data/bbeh_tasks/*.json')):
    t = os.path.basename(f)[:-5].removeprefix('bbeh_')
    for e in json.load(open(f))['examples']:
        owner[e['input']] = t
json.dump([owner[e['input']] for e in mini], open('data/bbeh_mini_tasks.json', 'w'))
"
rm -r data/bbeh_tasks
