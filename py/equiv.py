# Embedded in the pdx binary (include_str!) and run with the project's Python.
# Usage: python -c <this> OLD.py NEW.py
# Contract: each script must leave its output in a variable named `result`. Both run in fresh
# namespaces. DataFrames and Series are compared with pandas.testing, anything else with
# numpy.testing, so arrays compare element-wise and `python -O` can't skip the check.
# Prints JSON; exit 0 = equivalent, 1 = differs, 2 = bad input or pdx can't run.
import json
import runpy
import sys
from typing import NoReturn


def fail(error: str) -> NoReturn:
    print(json.dumps({"equivalent": None, "error": error}))
    sys.exit(2)


try:
    import pandas as pd
    from numpy import testing as npt
    from pandas import testing as pdt
except ImportError as e:
    fail(f"pdx equiv needs pandas in the project's Python. {e}")


def run(path: str) -> object:
    try:
        ns = runpy.run_path(path, run_name="__pdx_equiv__")
    except Exception as e:  # noqa: BLE001  any failure in the user's script is bad input
        fail(f"{path} raised {type(e).__name__}: {e}")
    if "result" not in ns:
        fail(f"{path} defines no `result`")
    return ns["result"]


old, new = run(sys.argv[1]), run(sys.argv[2])
try:
    if isinstance(old, pd.DataFrame):
        pdt.assert_frame_equal(old, new)
    elif isinstance(old, pd.Series):
        pdt.assert_series_equal(old, new)
    else:
        npt.assert_equal(new, old)
except AssertionError as e:
    print(json.dumps({"equivalent": False, "detail": str(e)}))
    sys.exit(1)
print(json.dumps({"equivalent": True}))
