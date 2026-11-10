#!/bin/sh
cd "$(dirname "$0")" || exit 1
while [ "$(tail -1 runs2/progress 2>/dev/null)" != "done" ]; do sleep 5; done
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow python bench5.py > runs2/bench5-3.1.1.jsonl 2> runs2/bench5-3.1.1.err
echo extra >> runs2/progress
