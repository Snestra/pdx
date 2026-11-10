"""Extra pairs: aggregate then merge back, and groupby combined with time. Inputs are built outside the timing."""
import importlib.util, json, os, sys, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
ns = {}; exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench.py")).read().split("CASES = []")[0], ns)
frame, best, same = ns["frame"], ns["best"], ns["same"]
print(json.dumps({"meta": {"pandas": pd.__version__, "pandas_path": pd.__file__, "python": sys.version.split()[0], "pyarrow": importlib.util.find_spec("pyarrow") is not None}}))
M = 1_000_000
df = frame(M)
many = df.assign(g=np.random.default_rng(1).integers(0, 100_000, M))
sd = df.sort_values("d", ignore_index=True)
CASES = []
def case(id, before, after, reps=3): CASES.append((id, before, after, reps))
case("agg-merge-back-vs-transform", lambda: df.merge(df.groupby("k")["b"].sum().rename("total").reset_index(), on="k", how="left")["total"], lambda: df.groupby("k")["b"].transform("sum").rename("total"))
case("G100k-agg-merge-back-vs-transform", lambda: many.merge(many.groupby("g")["b"].sum().rename("total").reset_index(), on="g", how="left")["total"], lambda: many.groupby("g")["b"].transform("sum").rename("total"))
case("agg-map-back-vs-transform", lambda: df["k"].map(df.groupby("k")["b"].sum()).rename("b"), lambda: df.groupby("k")["b"].transform("sum"))
case("gb-apply-resample-vs-grouper", lambda: sd.groupby("s").apply(lambda g: g.set_index("d")["b"].resample("D").sum()), lambda: sd.groupby(["s", pd.Grouper(key="d", freq="D")])["b"].sum())
case("gb-apply-resample-vs-groupby-resample", lambda: sd.groupby("s").apply(lambda g: g.set_index("d")["b"].resample("D").sum()), lambda: sd.groupby("s").resample("D", on="d")["b"].sum())
case("gb-transform-expanding-vs-gb-expanding", lambda: df.groupby("k")["b"].transform(lambda v: v.expanding().mean()), lambda: df.groupby("k")["b"].expanding().mean().droplevel(0).sort_index())
case("gb-apply-latest-row-vs-idxmax", lambda: df.groupby("k").apply(lambda g: g.sort_values("d").iloc[-1]), lambda: df.loc[df.groupby("k")["d"].idxmax()].set_index("k"))
case("sort-gb-tail1-vs-idxmax", lambda: df.sort_values("d").groupby("k").tail(1).sort_values("k").reset_index(drop=True), lambda: df.loc[df.groupby("k")["d"].idxmax()].reset_index(drop=True))
case("gb-lag-apply-vs-gb-shift", lambda: sd.groupby("k")["b"].apply(lambda v: v.shift(1)).droplevel(0).sort_index(), lambda: sd.groupby("k")["b"].shift(1))
case("gb-time-rolling-apply-vs-gb-rolling-on", lambda: sd.groupby("s").apply(lambda g: g.rolling("1D", on="d")["b"].mean()).droplevel(0).sort_index(), lambda: sd.groupby("s").rolling("1D", on="d")["b"].mean().droplevel(0).sort_index())
for id, before, after, reps in CASES:
    rec = {"id": id, "n": M}
    try: x, tb, _ = best(before, reps); rec["before_ms"] = round(tb * 1e3, 3)
    except Exception as e: x = None; rec["before_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    try: y, ta, _ = best(after, reps); rec["after_ms"] = round(ta * 1e3, 3)
    except Exception as e: y = None; rec["after_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    if "before_ms" in rec and "after_ms" in rec: rec["speedup"] = round(tb / ta, 2); rec["same"] = same(x, y)
    print(json.dumps(rec), flush=True)
