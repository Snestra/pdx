"""read_csv engines on a 1,000,000 row file. Best of 3 reads from the page cache. Prints JSON lines."""
import importlib.util
import json
import os
import sys
import time
import warnings

import pandas as pd

warnings.simplefilter("ignore")
ns = {}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench.py")).read().split("CASES = []")[0], ns)
frame = ns["frame"]
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data-1m.csv")
if not os.path.exists(path):
    frame(1_000_000).to_csv(path, index=False)
print(json.dumps({"meta": {"pandas": pd.__version__, "pandas_path": pd.__file__, "python": sys.version.split()[0],
                           "pyarrow": importlib.util.find_spec("pyarrow") is not None, "cpus": os.cpu_count(),
                           "file_mb": round(os.path.getsize(path) / 1e6, 1)}}))


def best(fn, reps=3):
    ts = []
    for _ in range(reps):
        t = time.perf_counter()
        out = fn()
        ts.append(time.perf_counter() - t)
    return out, min(ts)


CASES = {
    "default": lambda: pd.read_csv(path),
    "engine=c": lambda: pd.read_csv(path, engine="c"),
    "engine=pyarrow": lambda: pd.read_csv(path, engine="pyarrow"),
    "engine=python": lambda: pd.read_csv(path, engine="python"),
    "low_memory=False": lambda: pd.read_csv(path, low_memory=False),
    "parse_dates=[d]": lambda: pd.read_csv(path, parse_dates=["d"]),
    "to_datetime after read": lambda: (lambda f: f.assign(d=pd.to_datetime(f["d"])))(pd.read_csv(path)),
    "usecols 2 of 6": lambda: pd.read_csv(path, usecols=["a", "b"]),
    "read all then select 2": lambda: pd.read_csv(path)[["a", "b"]],
    "dtype category for k and s": lambda: pd.read_csv(path, dtype={"k": "category", "s": "category"}),
}
for name, fn in CASES.items():
    rec = {"id": name}
    try:
        out, t = best(fn, 1 if "python" in name else 3)
        rec["ms"] = round(t * 1e3, 1)
        rec["mem_mb"] = round(out.memory_usage(deep=True).sum() / 1e6, 1)
    except Exception as e:
        rec["err"] = f"{type(e).__name__}: {str(e)[:120]}"
    print(json.dumps(rec), flush=True)
