"""Ways to translate values through a mapping while keeping the values the mapping does not list.

1,000,000 rows, 1,000 distinct values, mappings of 3 to 1,000 keys. Best of 3 runs (1 run when a run takes over 2 s).
"""
import gc
import json
import sys
import time
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
print(json.dumps({"meta": {"pandas": pd.__version__, "python": sys.version.split()[0]}}))
N = 1_000_000
r = np.random.default_rng(0)
text = pd.Series(r.choice([f"g{i:04d}" for i in range(1000)], N), name="k")
ints = pd.Series(r.integers(0, 1000, N), name="k")

FORMS = {
    "replace(mapping)": lambda s, m: s.replace(m),
    "map(mapping).fillna(s)": lambda s, m: s.map(m).fillna(s),
    "map(lambda v: mapping.get(v, v))": lambda s, m: s.map(lambda v: m.get(v, v)),
    "s.where(~s.isin(mapping), s.map(mapping))": lambda s, m: s.where(~s.isin(list(m)), s.map(m)),
    "category, then rename_categories(mapping)": lambda s, m: s.astype("category").cat.rename_categories(m).astype(s.dtype),
}
for kind, s, key, val in (("text", text, lambda i: f"g{i:04d}", lambda i: f"x{i}"), ("integer", ints, lambda i: i, lambda i: i + 5000)):
    for keys in (3, 10, 30, 100, 300, 1000):
        m = {key(i): val(i) for i in range(keys)}
        want = None
        for name, fn in FORMS.items():
            ts = []
            try:
                for _ in range(3):
                    gc.collect()
                    t = time.perf_counter()
                    got = fn(s, m)
                    ts.append(time.perf_counter() - t)
                    if ts[-1] > 2:
                        break
                if want is None:
                    want, same = got, "reference"
                else:
                    try:
                        pd.testing.assert_series_equal(want, got)
                        same = "identical"
                    except AssertionError as e:
                        same = "values equal, dtype differs" if want.astype(str).equals(got.astype(float).astype(int).astype(str) if kind == "integer" else got.astype(str)) else "DIFFERS"
                        same += " (" + str(want.dtype) + " vs " + str(got.dtype) + ")"
                rec = {"kind": kind, "keys": keys, "form": name, "ms": round(min(ts) * 1e3, 2), "result": same}
            except Exception as e:
                rec = {"kind": kind, "keys": keys, "form": name, "error": f"{type(e).__name__}: {str(e)[:80]}"}
            print(json.dumps(rec), flush=True)
# Two cases where the forms can disagree.
s = pd.Series(["a", "b", None, "c"])
print(json.dumps({"case": "mapping value is None", "replace": s.replace({"a": None}).tolist(), "map_fillna": s.map({"a": None}).fillna(s).tolist(),
                  "where_isin": s.where(~s.isin(["a"]), s.map({"a": None})).tolist()}, default=str))
try:
    out = s.astype("category").cat.rename_categories({"a": "c"}).tolist()
except Exception as e:
    out = f"{type(e).__name__}: {str(e)[:70]}"
print(json.dumps({"case": "two keys end at the same value", "replace": s.replace({"a": "c"}).tolist(), "rename_categories": out}, default=str))
