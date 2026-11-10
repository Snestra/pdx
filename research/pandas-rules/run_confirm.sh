#!/bin/sh
# Second, independent run of every measurement, one process at a time, with nothing else running.
cd "$(dirname "$0")" || exit 1
while [ "$(tail -1 runs/progress 2>/dev/null)" != "done" ]; do sleep 5; done
mkdir -p runs2
for v in 3.1.1 3.0.6; do
  uv run -q --no-project --with "pandas==$v" --with pyarrow python bench4.py > "runs2/bench4-$v.jsonl" 2> "runs2/bench4-$v.err"
done
echo bench4 > runs2/progress
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow --with numexpr python bench3.py > runs2/bench3-3.1.1.jsonl 2> runs2/bench3-3.1.1.err
echo bench3 >> runs2/progress
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow python bench.py > runs2/bench-3.1.1.jsonl 2> runs2/bench-3.1.1.err
echo bench >> runs2/progress
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow --with numexpr python bench2.py replace apply map list G100k T-gb-dt T-gb-strftime T-gb-year T-gb-key > runs2/bench2-3.1.1.jsonl 2> runs2/bench2-3.1.1.err
echo done >> runs2/progress
