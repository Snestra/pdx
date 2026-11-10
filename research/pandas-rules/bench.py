"""Before/after pairs for candidate pdx rules. Prints one JSON line per case.
Timing: best of R runs of the whole expression on an in-memory frame; frame build is excluded."""
import json, sys, time, warnings, gc
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
META = {"pandas": pd.__version__, "pandas_path": pd.__file__, "numpy": np.__version__,
        "python": sys.version.split()[0],
        "pyarrow": __import__("pyarrow").__version__ if __import__("importlib").util.find_spec("pyarrow") else None}
print(json.dumps({"meta": META}))

def frame(n, seed=0):
    r = np.random.default_rng(seed)
    d0 = pd.Timestamp("2022-01-01")
    return pd.DataFrame({
        "a": r.integers(0, 100, n),
        "b": r.normal(size=n),
        "w": r.random(n) + 0.1,
        "k": r.choice([f"g{i:04d}" for i in range(1000)], n),
        "s": r.choice(["Alpha_one", "beta_two", "Gamma_three", "delta_four"], n),
        "d": d0 + pd.to_timedelta(r.integers(0, 3 * 365 * 86400, n), unit="s"),
    })

def best(fn, reps):
    out, ts = None, []
    for _ in range(reps):
        gc.collect()
        t = time.perf_counter(); out = fn(); ts.append(time.perf_counter() - t)
    return out, min(ts), ts

def same(x, y):
    try:
        if isinstance(x, pd.DataFrame) and isinstance(y, pd.DataFrame):
            pd.testing.assert_frame_equal(x, y); return "equal"
        if isinstance(x, pd.Series) and isinstance(y, pd.Series):
            pd.testing.assert_series_equal(x, y); return "equal"
        if isinstance(x, (pd.Series, pd.DataFrame, np.ndarray)) or isinstance(y, (pd.Series, pd.DataFrame, np.ndarray)):
            xa = np.asarray(x); ya = np.asarray(y)
            if xa.shape == ya.shape and bool(pd.Series(xa.ravel()).equals(pd.Series(ya.ravel()))): return "equal values, different container"
            if xa.shape == ya.shape and np.allclose(xa.astype(float), ya.astype(float), equal_nan=True): return "equal values (float tolerance), different container"
            return "DIFFERS"
        return "equal" if x == y else f"DIFFERS {x!r} vs {y!r}"
    except AssertionError as e:
        try:
            kw = dict(check_dtype=False, check_names=False, check_index_type=False, check_freq=False, check_categorical=False)
            if isinstance(x, pd.DataFrame):
                pd.testing.assert_frame_equal(x, y, check_column_type=False, **kw)
            else:
                pd.testing.assert_series_equal(x, y, **kw)
            return "equal values; dtype or name differs: " + str(e).split("\n")[0][:60] + " | " + " ".join(str(e).split("\n")[1:4])[:140]
        except Exception as e2:
            return "DIFFERS: " + " ".join(str(e2).split())[:200]
    except Exception as e:
        return f"compare failed {type(e).__name__}: {str(e)[:120]}"

CASES = []
def case(id, n, before, after, reps=5, note=""):
    CASES.append((id, n, before, after, reps, note))

M = 1_000_000
# ---- row loops and apply
case("apply-axis-1", 100_000, lambda df: df.apply(lambda r: r["a"] + r["b"], axis=1), lambda df: df["a"] + df["b"], 3)
case("iterrows-sum", 100_000, lambda df: sum(r["a"] * r["w"] for _, r in df.iterrows()), lambda df: (df["a"] * df["w"]).sum(), 3)
case("itertuples-sum", 100_000, lambda df: sum(r.a * r.w for r in df.itertuples()), lambda df: (df["a"] * df["w"]).sum(), 3)
case("range-len-iloc", 20_000, lambda df: [df.iloc[i]["a"] for i in range(len(df))], lambda df: df["a"].tolist(), 3)
case("loc-scalar-vs-at", 20_000, lambda df: [df.loc[i, "a"] for i in range(len(df))], lambda df: [df.at[i, "a"] for i in range(len(df))], 3)
case("apply-arith-lambda", M, lambda df: df["b"].apply(lambda x: x * 2 + 1), lambda df: df["b"] * 2 + 1)
case("apply-numpy-func", M, lambda df: df["w"].apply(np.sqrt), lambda df: np.sqrt(df["w"]))
case("map-lambda-str-method", M, lambda df: df["s"].map(lambda x: x.lower()), lambda df: df["s"].str.lower())
case("apply-lambda-str-split", M, lambda df: df["s"].apply(lambda x: x.split("_")[0]), lambda df: df["s"].str.split("_").str[0])
case("str-split-get-vs-partition", M, lambda df: df["s"].str.split("_").str[0], lambda df: df["s"].str.partition("_")[0])
case("str-split-vs-extract", M, lambda df: df["s"].str.split("_").str[0], lambda df: df["s"].str.extract(r"^([^_]*)", expand=False))
case("apply-lambda-dt-attr", M, lambda df: df["d"].apply(lambda x: x.year), lambda df: df["d"].dt.year)
case("apply-ifelse-vs-np-where", M, lambda df: df["a"].apply(lambda x: "hi" if x > 50 else "lo"), lambda df: pd.Series(np.where(df["a"] > 50, "hi", "lo"), index=df.index))
case("apply-in-set-vs-isin", M, lambda df: df["a"].apply(lambda x: x in {1, 5, 9}), lambda df: df["a"].isin([1, 5, 9]))
case("builtin-sum-on-column", M, lambda df: sum(df["a"]), lambda df: df["a"].sum())
case("builtin-max-on-column", M, lambda df: max(df["b"]), lambda df: df["b"].max())
case("builtin-len-set", M, lambda df: len(set(df["k"])), lambda df: df["k"].nunique())
# ---- boolean masks, conditionals
case("or-chain-vs-isin", M, lambda df: df[(df["a"] == 1) | (df["a"] == 5) | (df["a"] == 9)], lambda df: df[df["a"].isin([1, 5, 9])])
case("range-compare-vs-between", M, lambda df: df[(df["a"] >= 10) & (df["a"] <= 20)], lambda df: df[df["a"].between(10, 20)])
case("nested-np-where-vs-np-select", M, lambda df: np.where(df["a"] < 20, "low", np.where(df["a"] < 70, "mid", "high")), lambda df: np.select([df["a"] < 20, df["a"] < 70], ["low", "mid"], "high"))
case("nested-np-where-vs-case-when", M, lambda df: pd.Series(np.where(df["a"] < 20, "low", np.where(df["a"] < 70, "mid", "high")), index=df.index), lambda df: pd.Series("high", index=df.index).case_when([(df["a"] < 20, "low"), (df["a"] < 70, "mid")]))
case("nested-np-where-vs-cut", M, lambda df: pd.Series(np.where(df["a"] < 20, "low", np.where(df["a"] < 70, "mid", "high")), index=df.index), lambda df: pd.cut(df["a"], [-np.inf, 20, 70, np.inf], right=False, labels=["low", "mid", "high"]))
case("np-where-vs-clip", M, lambda df: pd.Series(np.where(df["a"] > 80, 80, df["a"]), index=df.index, name="a"), lambda df: df["a"].clip(upper=80))
case("len-filter-vs-mask-sum", M, lambda df: len(df[df["a"] > 50]), lambda df: int((df["a"] > 50).sum()))
case("len-unique-vs-nunique", M, lambda df: len(df["k"].unique()), lambda df: df["k"].nunique())
case("value-counts-div-len-vs-normalize", M, lambda df: df["k"].value_counts() / len(df), lambda df: df["k"].value_counts(normalize=True))
case("sort-head-vs-nsmallest", M, lambda df: df.sort_values("b").head(10), lambda df: df.nsmallest(10, "b"))
case("sort-desc-head-vs-nlargest", M, lambda df: df.sort_values("b", ascending=False).head(10), lambda df: df.nlargest(10, "b"))
case("sort-iloc0-vs-idxmin", M, lambda df: df.sort_values("b").iloc[0], lambda df: df.loc[df["b"].idxmin()])
case("replace-dict-vs-map", M, lambda df, m={f"g{i:04d}": i for i in range(1000)}: df["k"].replace(m), lambda df, m={f"g{i:04d}": i for i in range(1000)}: df["k"].map(m), 3)
case("sub-shift-vs-diff", M, lambda df: df["b"] - df["b"].shift(1), lambda df: df["b"].diff())
case("div-shift-vs-pct-change", M, lambda df: df["w"] / df["w"].shift(1) - 1, lambda df: df["w"].pct_change())
case("reset-index-after-sort-vs-ignore-index", M, lambda df: df.sort_values("b").reset_index(drop=True), lambda df: df.sort_values("b", ignore_index=True))
case("str-contains-literal-regex", M, lambda df: df["s"].str.contains("ta_"), lambda df: df["s"].str.contains("ta_", regex=False))
case("in-values-vs-eq-any", M, lambda df: 37 in df["a"].values, lambda df: bool((df["a"] == 37).any()))
# ---- groupby
case("gb-apply-reduce-vs-builtin", M, lambda df: df.groupby("k")["b"].apply(lambda x: x.sum()), lambda df: df.groupby("k")["b"].sum())
case("gb-agg-lambda-vs-name", M, lambda df: df.groupby("k")["b"].agg(lambda x: x.mean()), lambda df: df.groupby("k")["b"].agg("mean"))
case("gb-agg-np-func-vs-name", M, lambda df: df.groupby("k")["b"].agg(np.mean), lambda df: df.groupby("k")["b"].agg("mean"))
case("gb-agg-builtin-sum-vs-name", M, lambda df: df.groupby("k")["b"].agg(sum), lambda df: df.groupby("k")["b"].agg("sum"))
case("gb-agg-lambda-range", M, lambda df: df.groupby("k")["b"].agg(lambda x: x.max() - x.min()), lambda df: (lambda g: g.max() - g.min())(df.groupby("k")["b"]))
case("gb-agg-lambda-nunique", M, lambda df: df.groupby("k")["a"].agg(lambda x: x.nunique()), lambda df: df.groupby("k")["a"].nunique())
case("gb-transform-lambda-vs-name", M, lambda df: df.groupby("k")["b"].transform(lambda x: x.mean()), lambda df: df.groupby("k")["b"].transform("mean"))
case("gb-transform-zscore", M, lambda df: df.groupby("k")["b"].transform(lambda x: (x - x.mean()) / x.std()), lambda df: (lambda g: (df["b"] - g.transform("mean")) / g.transform("std"))(df.groupby("k")["b"]))
case("gb-transform-share", M, lambda df: df.groupby("k")["w"].transform(lambda x: x / x.sum()), lambda df: df["w"] / df.groupby("k")["w"].transform("sum"))
case("gb-apply-fillna-mean", M, lambda df: df.groupby("k")["b"].transform(lambda x: x.fillna(x.mean())), lambda df: df["b"].fillna(df.groupby("k")["b"].transform("mean")))
case("gb-apply-shift", M, lambda df: df.groupby("k")["b"].apply(lambda x: x.shift(1)), lambda df: df.groupby("k")["b"].shift(1))
case("gb-transform-lambda-cumsum", M, lambda df: df.groupby("k")["b"].transform(lambda x: x.cumsum()), lambda df: df.groupby("k")["b"].cumsum())
case("gb-transform-lambda-rank", M, lambda df: df.groupby("k")["b"].transform(lambda x: x.rank()), lambda df: df.groupby("k")["b"].rank())
case("gb-transform-lambda-rolling", M, lambda df: df.groupby("k")["b"].transform(lambda x: x.rolling(5).mean()), lambda df: df.groupby("k")["b"].rolling(5).mean().droplevel(0).sort_index())
case("gb-apply-weighted-mean", M, lambda df: df.groupby("k").apply(lambda g: (g["b"] * g["w"]).sum() / g["w"].sum()), lambda df: (lambda t: t["bw"] / t["w"])(df.assign(bw=df["b"] * df["w"]).groupby("k")[["bw", "w"]].sum()))
case("gb-apply-top1-vs-idxmax", M, lambda df: df.groupby("k").apply(lambda g: g.loc[g["b"].idxmax()]), lambda df: df.loc[df.groupby("k")["b"].idxmax()].set_index("k"))
case("gb-apply-nlargest-vs-sort-head", M, lambda df: df.groupby("k", group_keys=False).apply(lambda g: g.nlargest(3, "b")), lambda df: df.sort_values("b", ascending=False).groupby("k").head(3), 3)
case("gb-filter-lambda-vs-transform-mask", M, lambda df: df.groupby("k").filter(lambda g: len(g) > 1000), lambda df: df[df.groupby("k")["k"].transform("size") > 1000])
case("gb-sum-reset-index-vs-as-index", M, lambda df: df.groupby("k")[["a", "b"]].sum().reset_index(), lambda df: df.groupby("k", as_index=False)[["a", "b"]].sum())
case("gb-dict-agg-rename-vs-named", M, lambda df: df.groupby("k").agg({"b": "mean", "w": "sum"}).rename(columns={"b": "b_mean", "w": "w_total"}), lambda df: df.groupby("k").agg(b_mean=("b", "mean"), w_total=("w", "sum")))
case("gb-size-vs-value-counts", M, lambda df: df.groupby("k").size(), lambda df: df["k"].value_counts(sort=False).sort_index())
case("gb-str-key-vs-category-key", M, lambda df: df.groupby("k")["b"].sum(), lambda df, c=[None]: df.assign(k=df["k"].astype("category")).groupby("k", observed=True)["b"].sum())
case("pivot-table-lambda-vs-name", M, lambda df: df.pivot_table(index="k", columns="s", values="b", aggfunc=lambda x: x.sum()), lambda df: df.pivot_table(index="k", columns="s", values="b", aggfunc="sum"))
# ---- time series
case("dt-date-vs-normalize", M, lambda df: df["d"].dt.date, lambda df: df["d"].dt.normalize())
case("gb-dt-date-vs-grouper", M, lambda df: df.groupby(df["d"].dt.date)["b"].sum(), lambda df: df.groupby(pd.Grouper(key="d", freq="D"))["b"].sum())
case("gb-strftime-month-vs-grouper", M, lambda df: df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum(), lambda df: df.groupby(pd.Grouper(key="d", freq="MS"))["b"].sum())
case("gb-strftime-month-vs-to-period", M, lambda df: df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum(), lambda df: df.groupby(df["d"].dt.to_period("M"))["b"].sum())
case("gb-year-month-vs-resample", M, lambda df: df.groupby([df["d"].dt.year, df["d"].dt.month])["b"].sum(), lambda df: df.resample("MS", on="d")["b"].sum())
case("set-index-resample-vs-on", M, lambda df: df.set_index("d").resample("D")["b"].sum(), lambda df: df.resample("D", on="d")["b"].sum())
case("apply-strftime-vs-dt-strftime", 200_000, lambda df: df["d"].apply(lambda x: x.strftime("%Y-%m-%d")), lambda df: df["d"].dt.strftime("%Y-%m-%d"))
case("astype-str-slice-vs-dt-strftime", M, lambda df: df["d"].astype(str).str[:10], lambda df: df["d"].dt.strftime("%Y-%m-%d"))
case("timedelta-apply-days-vs-dt-days", 200_000, lambda df: (df["d"] - pd.Timestamp("2022-01-01")).apply(lambda x: x.days), lambda df: (df["d"] - pd.Timestamp("2022-01-01")).dt.days)
case("to-datetime-no-format-vs-format", M, lambda df, c={}: pd.to_datetime(c.setdefault("s", df["d"].dt.strftime("%d/%m/%Y %H:%M:%S"))), lambda df, c={}: pd.to_datetime(c.setdefault("s", df["d"].dt.strftime("%d/%m/%Y %H:%M:%S")), format="%d/%m/%Y %H:%M:%S"), 3)
case("to-datetime-iso-no-format-vs-format", M, lambda df, c={}: pd.to_datetime(c.setdefault("s", df["d"].astype(str))), lambda df, c={}: pd.to_datetime(c.setdefault("s", df["d"].astype(str)), format="ISO8601"), 3)
case("apply-to-datetime-per-element", 100_000, lambda df, c={}: c.setdefault("s", df["d"].astype(str)).apply(pd.to_datetime), lambda df, c={}: pd.to_datetime(c.setdefault("s", df["d"].astype(str))), 3)
case("rolling-apply-lambda-vs-builtin", 200_000, lambda df: df["b"].rolling(20).apply(lambda x: x.mean()), lambda df: df["b"].rolling(20).mean(), 3)
case("rolling-apply-no-raw-vs-raw", 200_000, lambda df: df["b"].rolling(20).apply(lambda x: x.max() - x.min()), lambda df: df["b"].rolling(20).apply(lambda x: x.max() - x.min(), raw=True), 3)
case("rolling-apply-range-vs-two-builtins", 200_000, lambda df: df["b"].rolling(20).apply(lambda x: x.max() - x.min()), lambda df: (lambda r: r.max() - r.min())(df["b"].rolling(20)), 3)
case("expanding-manual-cumsum-vs-expanding-mean", M, lambda df: df["b"].cumsum() / np.arange(1, len(df) + 1), lambda df: df["b"].expanding().mean())
case("filter-dt-year-vs-between", M, lambda df: df[df["d"].dt.year == 2023], lambda df: df[df["d"].between("2023-01-01", "2023-12-31 23:59:59.999999")])
# ---- frame building / combining
case("loc-append-in-loop-vs-list", 3_000, lambda df: (lambda out: [out.__setitem__(slice(None), None) for _ in ()] or [out.loc.__setitem__(len(out), [i, i * 2]) for i in range(len(df))] and out)(pd.DataFrame(columns=["x", "y"])), lambda df: pd.DataFrame([[i, i * 2] for i in range(len(df))], columns=["x", "y"]), 3)
case("concat-in-loop-vs-once", 200_000, lambda df: __import__("functools").reduce(lambda acc, p: pd.concat([acc, p]), [df.iloc[i:i + 1000] for i in range(0, len(df), 1000)]), lambda df: pd.concat([df.iloc[i:i + 1000] for i in range(0, len(df), 1000)]), 3)
case("dummy-key-merge-vs-cross", 2_000, lambda df: df[["a"]].assign(_k=1).merge(df[["b"]].assign(_k=1), on="_k").drop(columns="_k"), lambda df: df[["a"]].merge(df[["b"]], how="cross"), 3)
case("merge-lookup-vs-map", M, lambda df, c={}: df.merge(c.setdefault("lk", pd.DataFrame({"k": [f"g{i:04d}" for i in range(1000)], "v": range(1000)})), on="k", how="left")["v"], lambda df, c={}: df["k"].map(c.setdefault("lk", pd.Series(range(1000), index=[f"g{i:04d}" for i in range(1000)]))))
case("copy-after-filter", M, lambda df: df[df["a"] > 50].copy(), lambda df: df[df["a"] > 50])
case("copy-after-column-select", M, lambda df: df[["a", "b", "w"]].copy(), lambda df: df[["a", "b", "w"]])
case("values-vs-to-numpy", M, lambda df: df["b"].values, lambda df: df["b"].to_numpy())
case("query-string-vs-col-expr", M, lambda df: df.query("a > 50 and b < 0"), lambda df: df.loc[(pd.col("a") > 50) & (pd.col("b") < 0)])
case("mask-vs-col-expr", M, lambda df: df[(df["a"] > 50) & (df["b"] < 0)], lambda df: df.loc[(pd.col("a") > 50) & (pd.col("b") < 0)])
case("assign-lambda-vs-col", M, lambda df: df.assign(c=lambda d: d["a"] * d["w"] + 1), lambda df: df.assign(c=pd.col("a") * pd.col("w") + 1))
case("columns-list-comp-vs-str", 1000, lambda df: [c.upper() for c in df.columns], lambda df: list(df.columns.str.upper()))
if pd.__version__ >= "3.1":
    case("31-mask-vs-filter-cond", M, lambda df: df[(df["a"] > 50) & (df["b"] < 0)], lambda df: df.filter(cond=(pd.col("a") > 50) & (pd.col("b") < 0)))
    case("31-select-vs-assign-then-columns", M, lambda df: df.assign(c=df["a"] * df["w"])[["k", "c"]], lambda df: df.select("k", c=pd.col("a") * pd.col("w")))
    case("31-union-categoricals-vs-concat", M, lambda df, c={}: (lambda x, y: pd.Series(pd.api.types.union_categoricals([x, y])))(*c.setdefault("p", (df["s"].iloc[: len(df) // 2].astype("category"), df["k"].iloc[len(df) // 2:].astype("category")))), lambda df, c={}: pd.concat(c.setdefault("p", (df["s"].iloc[: len(df) // 2].astype("category"), df["k"].iloc[len(df) // 2:].astype("category"))), union_categories=True, ignore_index=True))

only = set(sys.argv[1:])
frames = {}
for id, n, before, after, reps, note in CASES:
    if only and id not in only: continue
    df = frames.setdefault(n, frame(n))
    rec = {"id": id, "n": n}
    try:
        x, tb, tbs = best(lambda: before(df), reps)
        rec["before_ms"] = round(tb * 1e3, 3)
    except Exception as e:
        x = None; rec["before_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    try:
        y, ta, tas = best(lambda: after(df), reps)
        rec["after_ms"] = round(ta * 1e3, 3)
    except Exception as e:
        y = None; rec["after_err"] = f"{type(e).__name__}: {str(e)[:150]}"
    if "before_ms" in rec and "after_ms" in rec:
        rec["speedup"] = round(tb / ta, 2) if ta > 0 else None
        rec["same"] = same(x, y)
    print(json.dumps(rec), flush=True)
