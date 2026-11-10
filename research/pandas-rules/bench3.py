"""Reruns of cases whose first version rebuilt inputs inside the timed call.

Inputs are built once, outside the timing. Timing is the best of R runs of the whole expression.
"""
import importlib.util
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
has = lambda m: importlib.util.find_spec(m) is not None
ns = {}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench.py")).read().split("CASES = []")[0], ns)
frame, best, same = ns["frame"], ns["best"], ns["same"]
print(json.dumps({"meta": {"pandas": pd.__version__, "pandas_path": pd.__file__, "pyarrow": has("pyarrow"),
                           "numexpr": has("numexpr"), "python": sys.version.split()[0], "cpus": os.cpu_count()}}))
M = 1_000_000
df = frame(M)
sd = df.sort_values("d", ignore_index=True)
si = sd.set_index("d")
dmy = df["d"].dt.strftime("%d/%m/%Y %H:%M:%S")
iso = df["d"].astype(str)
iso_small = iso.iloc[:100_000]
lk_df = pd.DataFrame({"k": [f"g{i:04d}" for i in range(1000)], "v": range(1000)})
lk_s = lk_df.set_index("k")["v"]
lk_d = dict(zip(lk_df["k"], lk_df["v"]))
c1, c2 = df["s"].iloc[: M // 2].astype("category"), df["k"].iloc[M // 2:].astype("category")
ticks = sd[["d", "b"]].iloc[::5].reset_index(drop=True)
q = df[["d"]].iloc[:5000].clip(lower=ticks["d"].iloc[0], upper=ticks["d"].iloc[-1]).sort_values("d").reset_index(drop=True)
small = df.iloc[:200_000]
CASES = []


def case(id, before, after, reps=5):
    CASES.append((id, before, after, reps))


case("T-gb-normalize-key-vs-resample-sorted", lambda: sd.groupby(sd["d"].dt.normalize())["b"].sum(), lambda: sd.resample("D", on="d")["b"].sum())
case("T-gb-normalize-key-vs-resample-unsorted", lambda: df.groupby(df["d"].dt.normalize())["b"].sum(), lambda: df.resample("D", on="d")["b"].sum())
case("T-gb-normalize-key-vs-grouper-sorted", lambda: sd.groupby(sd["d"].dt.normalize())["b"].sum(), lambda: sd.groupby(pd.Grouper(key="d", freq="D"))["b"].sum())
case("T-resample-on-datetimeindex-sorted", lambda: sd.groupby(sd["d"].dt.normalize())["b"].sum(), lambda: si.resample("D")["b"].sum())
case("T-gb-to-period-M-vs-resample-MS-sorted", lambda: sd.groupby(sd["d"].dt.to_period("M"))["b"].sum(), lambda: sd.resample("MS", on="d")["b"].sum())
case("T-set-index-resample-vs-on", lambda: df.set_index("d").resample("D")["b"].sum(), lambda: df.resample("D", on="d")["b"].sum())
case("T-year-mask-vs-partial-string-loc", lambda: si[si.index.year == 2023], lambda: si.loc["2023"])
case("T-range-mask-vs-loc-slice", lambda: si[(si.index >= "2023-03-01") & (si.index < "2023-04-01")], lambda: si.loc["2023-03"])
case("T-hour-mask-vs-between-time", lambda: si[(si.index.hour >= 9) & (si.index.hour < 17)], lambda: si.between_time("09:00", "17:00", inclusive="left"))
case("T-asof-loop-vs-merge-asof", lambda: pd.Series([ticks.at[ticks["d"].searchsorted(t, side="right") - 1, "b"] for t in q["d"]]), lambda: pd.merge_asof(q, ticks, on="d")["b"].rename(None), 2)
case("T-shift-days-apply-vs-offset", lambda: small["d"].apply(lambda x: x + pd.Timedelta(days=7)), lambda: small["d"] + pd.Timedelta(days=7), 3)
case("T-month-start-strftime-vs-period", lambda: pd.to_datetime(df["d"].dt.strftime("%Y-%m-01")), lambda: df["d"].dt.to_period("M").dt.start_time, 3)
case("T-month-start-replace-apply-vs-period", lambda: small["d"].apply(lambda x: x.replace(day=1, hour=0, minute=0, second=0)), lambda: small["d"].dt.to_period("M").dt.start_time, 3)
case("T-to-datetime-dmy-no-format-vs-format", lambda: pd.to_datetime(dmy), lambda: pd.to_datetime(dmy, format="%d/%m/%Y %H:%M:%S"), 3)
case("T-to-datetime-iso-no-format-vs-iso8601", lambda: pd.to_datetime(iso), lambda: pd.to_datetime(iso, format="ISO8601"), 3)
case("T-apply-to-datetime-per-element", lambda: iso_small.apply(pd.to_datetime), lambda: pd.to_datetime(iso_small), 2)
case("T-rolling-int-window-vs-time-window", lambda: sd["b"].rolling(1000).mean(), lambda: sd.rolling("1h", on="d")["b"].mean(), 3)
case("T-gb-rolling-apply-vs-gb-rolling", lambda: sd.groupby("s")["b"].apply(lambda x: x.rolling(10).mean()).droplevel(0).sort_index(), lambda: sd.groupby("s")["b"].rolling(10).mean().droplevel(0).sort_index(), 3)
case("merge-lookup-vs-map-series", lambda: df.merge(lk_df, on="k", how="left")["v"], lambda: df["k"].map(lk_s).rename("v"))
case("merge-lookup-vs-map-dict", lambda: df.merge(lk_df, on="k", how="left")["v"], lambda: df["k"].map(lk_d).rename("v"))
if pd.__version__ >= "3.1":
    case("31-union-categoricals-vs-concat", lambda: pd.Series(pd.api.types.union_categoricals([c1, c2])), lambda: pd.concat([c1, c2], union_categories=True, ignore_index=True))
    case("31-concat-cat-astype-vs-union", lambda: pd.concat([c1, c2], ignore_index=True).astype("category"), lambda: pd.concat([c1, c2], union_categories=True, ignore_index=True))
if has("numexpr"):
    big = frame(10_000_000)
    case("query-numexpr-vs-col-expr-1M", lambda: df.query("a > 50 and b < 0"), lambda: df.loc[(pd.col("a") > 50) & (pd.col("b") < 0)])
    case("query-numexpr-vs-col-expr-10M", lambda: big.query("a > 50 and b < 0 and w > 0.5"), lambda: big.loc[(pd.col("a") > 50) & (pd.col("b") < 0) & (pd.col("w") > 0.5)], 3)
    case("eval-numexpr-vs-plain-10M", lambda: big.eval("a * w + b"), lambda: big["a"] * big["w"] + big["b"], 3)
only = set(sys.argv[1:])
for id, before, after, reps in CASES:
    if only and not any(id.startswith(o) for o in only):
        continue
    rec = {"id": id, "n": M}
    try:
        x, tb, _ = best(before, reps)
        rec["before_ms"] = round(tb * 1e3, 3)
    except Exception as e:
        x = None
        rec["before_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    try:
        y, ta, _ = best(after, reps)
        rec["after_ms"] = round(ta * 1e3, 3)
    except Exception as e:
        y = None
        rec["after_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    if "before_ms" in rec and "after_ms" in rec:
        rec["speedup"] = round(tb / ta, 2)
        rec["same"] = same(x, y)
    print(json.dumps(rec), flush=True)
