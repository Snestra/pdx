#!/bin/sh
# Runs the prototype rules on the code cells of every notebook that imports pandas in two pandas books,
# and writes the reports to reports.json.
cd "$(dirname "$0")" || exit 1
[ -d pydata-book ] || git clone -q --depth 1 https://github.com/wesm/pydata-book.git
[ -d PythonDataScienceHandbook ] || git clone -q --depth 1 https://github.com/jakevdp/PythonDataScienceHandbook.git
rm -rf py && mkdir py
python3 -c '
import glob, json, re
kept = 0
for path in glob.glob("*/**/*.ipynb", recursive=True):
    try:
        cells = json.load(open(path)).get("cells", [])
    except ValueError:
        continue
    code = []
    for cell in cells:
        if cell.get("cell_type") != "code":
            continue
        text = "".join(cell["source"]) if isinstance(cell["source"], list) else cell["source"]
        # IPython magics and help lookups are not Python.
        code.append("\n".join(l for l in text.split("\n") if not l.lstrip().startswith(("%", "!", "?")) and not l.rstrip().endswith("?")))
    body = "\n\n".join(code)
    if re.search(r"^\s*(import pandas|from pandas)", body, re.M):
        open("py/" + re.sub(r"[^A-Za-z0-9]+", "_", path)[:-6] + ".py", "w").write(body + "\n")
        kept += 1
print(kept, "notebooks import pandas")
'
ast-grep scan -r ../proto/rules.yml py --json=compact 2> /dev/null > reports.json
python3 -c '
import collections, json
reports = json.load(open("reports.json"))
print(len(reports), "reports")
for rule, n in collections.Counter(r["ruleId"] for r in reports).most_common():
    print(f"{n:4d}  {rule}")
'
