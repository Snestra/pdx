# Embedded in the pdx binary (include_str!) and run with the project's Python.
# Usage: python -c <this> OLD.py NEW.py
# Contract: each script must leave a DataFrame or Series in a variable named
# `result`. Both run in fresh namespaces; results are compared with
# pandas.testing. Prints JSON; exit 0 = equivalent, 1 = differs, 2 = bad input.
import json
import runpy
import sys

import pandas as pd
from pandas import testing as pdt


def run(path):
    ns = runpy.run_path(path, run_name="__pdx_equiv__")
    if "result" not in ns:
        print(json.dumps({"equivalent": None, "error": f"{path} defines no `result`"}))
        sys.exit(2)
    return ns["result"]


old, new = run(sys.argv[1]), run(sys.argv[2])
try:
    if isinstance(old, pd.DataFrame):
        pdt.assert_frame_equal(old, new)
    elif isinstance(old, pd.Series):
        pdt.assert_series_equal(old, new)
    else:
        assert old == new, f"{old!r} != {new!r}"
except AssertionError as e:
    print(json.dumps({"equivalent": False, "detail": str(e)}))
    sys.exit(1)
print(json.dumps({"equivalent": True}))
