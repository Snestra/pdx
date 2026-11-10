"""Follow-up measurements. Same harness as bench.py. bench3.py holds the cases that need a sorted frame."""
import json, sys, time, warnings, gc, io, os, tempfile, importlib.util
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
has = lambda m: importlib.util.find_spec(m) is not None
print(json.dumps({"meta": {"pandas": pd.__version__, "pandas_path": pd.__file__, "pyarrow": has("pyarrow"), "numexpr": has("numexpr"), "python": sys.version.split()[0]}}))
ns = {}
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "bench.py")).read().split("CASES = []")[0], ns)
frame, best, same = ns["frame"], ns["best"], ns["same"]
CASES = []
def case(id, n, before, after, reps=5): CASES.append((id, n, before, after, reps))
M = 1_000_000
def many(df, c={}):
    if "x" not in c:
        r = np.random.default_rng(1)
        c["x"] = df.assign(g=r.integers(0, 100_000, len(df)))
    return c["x"]

case("replace-3key-dict-vs-map-str", M, lambda df: df["s"].replace({"Alpha_one": "A", "beta_two": "B", "delta_four": "D"}), lambda df: df["s"].map({"Alpha_one": "A", "beta_two": "B", "delta_four": "D"}).fillna(df["s"]))
case("replace-3key-dict-vs-map-int", M, lambda df: df["a"].replace({1: 100, 2: 200, 3: 300}), lambda df: df["a"].map({1: 100, 2: 200, 3: 300}).fillna(df["a"]))
case("replace-100key-dict-vs-map-int", M, lambda df: df["a"].replace({i: i * 3 for i in range(100)}), lambda df: df["a"].map({i: i * 3 for i in range(100)}), 3)
case("replace-1000key-dict-vs-map-fillna-str", M, lambda df, m={f"g{i:04d}": f"x{i}" for i in range(1000)}: df["k"].replace(m), lambda df, m={f"g{i:04d}": f"x{i}" for i in range(1000)}: df["k"].map(m).fillna(df["k"]), 2)
case("apply-ifelse-vs-np-where-numeric", M, lambda df: df["a"].apply(lambda x: 1 if x > 50 else 0), lambda df: pd.Series(np.where(df["a"] > 50, 1, 0), index=df.index, name="a"))
case("apply-ifelse-vs-where-method", M, lambda df: df["b"].apply(lambda x: x if x > 0 else 0.0), lambda df: df["b"].where(df["b"] > 0, 0.0))
case("apply-min-vs-clip", M, lambda df: df["b"].apply(lambda x: min(x, 1.0)), lambda df: df["b"].clip(upper=1.0))
case("apply-round-vs-round", M, lambda df: df["b"].apply(lambda x: round(x, 2)), lambda df: df["b"].round(2))
case("apply-isnull-vs-isna", M, lambda df: df["b"].apply(pd.isna), lambda df: df["b"].isna())
case("apply-str-vs-astype-str", M, lambda df: df["a"].apply(str), lambda df: df["a"].astype(str))
case("apply-len-vs-str-len", M, lambda df: df["s"].apply(len), lambda df: df["s"].str.len())
case("apply-fstring-vs-concat", M, lambda df: df.apply(lambda r: f"{r['s']}-{r['k']}", axis=1), lambda df: df["s"] + "-" + df["k"], 1)
case("map-lambda-startswith", M, lambda df: df["s"].map(lambda x: x.startswith("A")), lambda df: df["s"].str.startswith("A"))
case("map-lambda-replace", M, lambda df: df["s"].map(lambda x: x.replace("_", " ")), lambda df: df["s"].str.replace("_", " "))
case("map-lambda-strip", M, lambda df: df["s"].map(lambda x: x.strip()), lambda df: df["s"].str.strip())
case("map-lambda-slice", M, lambda df: df["s"].map(lambda x: x[:3]), lambda df: df["s"].str[:3])
case("map-lambda-contains", M, lambda df: df["s"].map(lambda x: "ta" in x), lambda df: df["s"].str.contains("ta", regex=False))
case("list-comp-str-vs-str", M, lambda df: pd.Series([x.upper() for x in df["s"]], index=df.index, name="s"), lambda df: df["s"].str.upper())
# many groups
case("G100k-agg-lambda-vs-name", M, lambda df: many(df).groupby("g")["b"].agg(lambda x: x.mean()), lambda df: many(df).groupby("g")["b"].agg("mean"), 2)
case("G100k-agg-np-func-vs-name", M, lambda df: many(df).groupby("g")["b"].agg(np.mean), lambda df: many(df).groupby("g")["b"].agg("mean"), 2)
case("G100k-apply-reduce-vs-builtin", M, lambda df: many(df).groupby("g")["b"].apply(lambda x: x.max() - x.min()), lambda df: (lambda g: g.max() - g.min())(many(df).groupby("g")["b"]), 2)
case("G100k-transform-lambda-vs-name", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.mean()), lambda df: many(df).groupby("g")["b"].transform("mean"), 2)
case("G100k-transform-share", M, lambda df: many(df).groupby("g")["w"].transform(lambda x: x / x.sum()), lambda df: many(df)["w"] / many(df).groupby("g")["w"].transform("sum"), 2)
case("G100k-transform-cumsum", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.cumsum()), lambda df: many(df).groupby("g")["b"].cumsum(), 2)
case("G100k-transform-shift", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.shift(1)), lambda df: many(df).groupby("g")["b"].shift(1), 2)
case("G100k-transform-diff", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.diff()), lambda df: many(df).groupby("g")["b"].diff(), 2)
case("G100k-transform-rank", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.rank()), lambda df: many(df).groupby("g")["b"].rank(), 2)
case("G100k-transform-rolling", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.rolling(3).mean()), lambda df: many(df).groupby("g")["b"].rolling(3).mean().droplevel(0).sort_index(), 2)
case("G100k-transform-ffill", M, lambda df: many(df).groupby("g")["b"].transform(lambda x: x.ffill()), lambda df: many(df).groupby("g")["b"].ffill(), 2)
case("G100k-filter-lambda-vs-mask", M, lambda df: many(df).groupby("g").filter(lambda g: len(g) > 10), lambda df: many(df)[many(df).groupby("g")["g"].transform("size") > 10], 2)
case("G100k-apply-top1-vs-idxmax", M, lambda df: many(df).groupby("g").apply(lambda g: g.loc[g["b"].idxmax()]), lambda df: many(df).loc[many(df).groupby("g")["b"].idxmax()].set_index("g"), 1)
case("G100k-apply-weighted-mean", M, lambda df: many(df).groupby("g").apply(lambda g: (g["b"] * g["w"]).sum() / g["w"].sum()), lambda df: (lambda t: t["bw"] / t["w"])(many(df).assign(bw=many(df)["b"] * many(df)["w"]).groupby("g")[["bw", "w"]].sum()), 1)
case("G100k-agg-first-lambda-vs-name", M, lambda df: many(df).groupby("g")["b"].agg(lambda x: x.iloc[0]), lambda df: many(df).groupby("g")["b"].first(), 2)
case("G100k-sort-drop-dup-vs-idxmax", M, lambda df: many(df).sort_values("b", ascending=False).drop_duplicates("g").sort_values("g").reset_index(drop=True), lambda df: many(df).loc[many(df).groupby("g")["b"].idxmax()].reset_index(drop=True), 2)
case("G100k-apply-list-vs-agg-list", M, lambda df: many(df).groupby("g")["a"].apply(list), lambda df: many(df).groupby("g")["a"].agg(list), 2)
# time grouping
case("T-gb-dt-date-vs-normalize-key", M, lambda df: df.groupby(df["d"].dt.date)["b"].sum(), lambda df: df.groupby(df["d"].dt.normalize())["b"].sum())
case("T-gb-dt-date-vs-floor-key", M, lambda df: df.groupby(df["d"].dt.date)["b"].sum(), lambda df: df.groupby(df["d"].dt.floor("D"))["b"].sum())
case("T-gb-strftime-hour-vs-floor-h", M, lambda df: df.groupby(df["d"].dt.strftime("%Y-%m-%d %H"))["b"].sum(), lambda df: df.groupby(df["d"].dt.floor("h"))["b"].sum(), 2)
case("T-gb-year-month-vs-to-period", M, lambda df: df.groupby([df["d"].dt.year, df["d"].dt.month])["b"].sum(), lambda df: df.groupby(df["d"].dt.to_period("M"))["b"].sum())
case("T-gb-key-plus-resample-vs-grouper", M, lambda df: df.set_index("d").groupby("s").resample("MS")["b"].sum(), lambda df: df.groupby(["s", pd.Grouper(key="d", freq="MS")])["b"].sum(), 2)

only = set(sys.argv[1:]); frames = {}
for id, n, before, after, reps in CASES:
    if only and not any(id.startswith(o) for o in only): continue
    df = frames.setdefault(n, frame(n)); rec = {"id": id, "n": n}
    try:
        before(df) if id.startswith(("G100k", "T-")) and reps > 1 else None
        x, tb, _ = best(lambda: before(df), reps); rec["before_ms"] = round(tb * 1e3, 3)
    except Exception as e:
        x = None; rec["before_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    try:
        y, ta, _ = best(lambda: after(df), reps); rec["after_ms"] = round(ta * 1e3, 3)
    except Exception as e:
        y = None; rec["after_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    if "before_ms" in rec and "after_ms" in rec:
        rec["speedup"] = round(tb / ta, 2); rec["same"] = same(x, y)
    print(json.dumps(rec), flush=True)
