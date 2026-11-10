#!/bin/sh
# Applies the prototype fixes to copies of the test files, then checks on pandas 3.1.1 and 3.0.6
# that every case gives the same result as before the fix.
cd "$(dirname "$0")" || exit 1
# The safe set is rules.yml with the fix taken out of every rule marked unsafe.
python3 -c '
import re
docs = open("rules.yml").read().split("\n---\n")
open("rules_safe.yml", "w").write("\n---\n".join(re.sub(r"\nfix: .*", "", d) if "fix: unsafe" in d else d for d in docs))
'
cp before.py after_safe.py
cp before.py after_unsafe.py
cp removed.py removed_fixed.py
cp ca.py ca_fixed.py
# A fix can create a match for another fix, so each file is fixed until nothing changes, as pdx does.
for pass in 1 2 3 4 5; do
  ast-grep scan -r rules_safe.yml -U after_safe.py > /dev/null 2>&1
  ast-grep scan -r rules.yml -U after_unsafe.py removed_fixed.py ca_fixed.py > /dev/null 2>&1
done
for version in 3.1.1 3.0.6; do
  uv run -q --no-project --with "pandas==$version" --with pyarrow python compare.py after_safe.py
done
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow python compare.py after_unsafe.py
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow python exact.py
uv run -q --no-project --with "pandas==3.1.1" --with pyarrow python removed_fixed.py
ast-grep scan -r rules.yml k.py mb.py ca.py 2> /dev/null | grep -E '^(error|warning)'
