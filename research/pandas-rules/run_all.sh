#!/bin/sh
# Runs every measurement one after another, so that no two timed processes share the machine.
cd "$(dirname "$0")" || exit 1
mkdir -p runs
for v in 3.1.1 3.0.6; do
  uv run -q --no-project --with "pandas==$v" --with pyarrow --with numexpr python bench3.py > "runs/bench3-$v.jsonl" 2> "runs/bench3-$v.err"
done
echo bench3 > runs/progress
for v in 3.1.1 3.0.6; do
  uv run -q --no-project --with "pandas==$v" --with pyarrow python bench.py > "runs/bench-$v.jsonl" 2> "runs/bench-$v.err"
done
echo bench >> runs/progress
uv run -q --no-project --with "pandas==3.0.6" --with pyarrow --with numexpr python bench2.py replace apply map list G100k T-gb-dt T-gb-strftime T-gb-year T-gb-key > runs/bench2-3.0.6.jsonl 2> runs/bench2-3.0.6.err
echo bench2-3.0.6 >> runs/progress
# The default str dtype is backed by pyarrow when pyarrow is installed. This run shows the string cases without it.
uv run -q --no-project --with "pandas==3.1.1" python bench2.py map list apply-len apply-str > runs/bench2-nopyarrow-3.1.1.jsonl 2> runs/bench2-nopyarrow-3.1.1.err
uv run -q --no-project --with "pandas==3.1.1" python bench.py map-lambda-str-method apply-lambda-str-split str-contains-literal-regex > runs/bench-nopyarrow-3.1.1.jsonl 2> runs/bench-nopyarrow-3.1.1.err
echo done >> runs/progress
