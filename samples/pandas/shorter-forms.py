"""Longer forms that pandas 3 can write shorter, and code that looks similar but stays.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `pdx check --fix` can be compared with this file.
"""

import numpy as np
import pandas as pd

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame(n=2000, seed=0):
    r = np.random.default_rng(seed)
    b = r.normal(size=n).round(4)
    b[::11] = np.nan
    return pd.DataFrame({
        "a": r.integers(0, 100, n),
        "b": b,
        "w": r.random(n) + 0.1,
        "k": r.choice(["g1", "g2", "g3", "g4", "g5"], n),
        "s": r.choice(["Alpha_one", " beta_two", "Gamma_three ", "delta_four"], n),
        "raw": r.choice(["2024-01-05", "2024-02-11", "2023-12-31"], n),
        "d": pd.Timestamp("2022-01-01") + pd.to_timedelta(r.integers(0, 400 * 86400, n), unit="s"),
    })


@case
def assign_with_a_named_list(df):
    output_columns = ["c", "u", "m"]
    return df.assign(
        c=lambda d: d["a"] * d["w"] + 1,
        u=pd.col("s").str.strip().str.upper(),
        m=lambda d: np.where(d["a"] > 5, 1, 0),
    )[output_columns]


@case
def inline_column_list(df):
    return (
        df[["k", "a", "b"]],  # pdx: inline-column-list
        df.loc[df["a"] > 50, ["k", "a", "b"]],  # pdx: inline-column-list
        df.groupby(["k", "s", "raw"])["b"].sum(),  # pdx: inline-column-list
        df.drop_duplicates(subset=["k", "s", "raw"]),  # pdx: inline-column-list
    )


@case
def lists_that_stay(df):
    key_columns = ["k", "s", "raw"]
    return (
        df[["k", "a"]],
        df[key_columns],
        df.groupby(key_columns)["b"].sum(),
        df[df["k"].isin(["g1", "g2", "g3"])],
        df.groupby("k")["b"].agg(["sum", "mean", "max"]),
    )


@case
def sort_then_reset_index(df):
    return (
        df.sort_values("b").reset_index(drop=True),  # pdx: sort-then-reset-index
        df.mask(df["a"] > 90).dropna().reset_index(drop=True),  # pdx: sort-then-reset-index
        df["k"].drop_duplicates().reset_index(drop=True),  # pdx: sort-then-reset-index
    )


@case
def reset_index_that_stays(df):
    return (
        df.sort_values("b").reset_index(),
        df.groupby("k").sample(2, random_state=1).reset_index(drop=True),
        df[["a", "b"]].sort_values(0, axis=1).reset_index(drop=True),
    )


@case
def set_index_then_resample(df):
    return (
        df.set_index("d").resample("D")["b"].sum(),  # pdx: set-index-then-resample
        df[["a", "d"]].set_index("d").resample("W").mean(),  # pdx: set-index-then-resample
    )


@case
def set_index_for_upsampling(df):
    by_day = df.drop_duplicates("d").set_index("d").sort_index()
    return by_day.resample("h").asfreq().shape, df.set_index("d").resample("D")["a"].agg(lambda v: v.index.max())


@case
def subtract_shift(df):
    return df["b"] - df["b"].shift(), df["a"] - df["a"].shift(1), df["d"] - df["d"].shift()  # pdx: subtract-shift


@case
def subtract_that_stays(df):
    return df["b"] - df["b"].shift(2), (df["a"] > 5) - (df["a"] > 5).shift(), df["b"].shift() - df["b"]


@case
def range_mask(df):
    return (
        df[(df["a"] >= 10) & (df["a"] <= 20)],  # pdx: range-mask
        df[(df["b"] > -0.5) & (df["b"] < 0.5)],  # pdx: range-mask
    )


@case
def range_that_stays(df):
    x = df["a"].to_numpy()
    return ((x >= 10) & (x <= 20)).sum(), df[(df["a"] >= 10) & (df["b"] <= 20)]


@case
def groupby_then_reset_index(df):
    return (
        df.groupby("k")[["a", "b"]].sum().reset_index(),  # pdx: groupby-then-reset-index
        df.groupby(["k", "s"]).mean(numeric_only=True).reset_index(),  # pdx: groupby-then-reset-index
    )


@case
def groupby_as_index(df):
    return df.groupby("k", as_index=False)[["a", "b"]].sum(), df.groupby("k").size().reset_index()


@case
def rename_after_agg(df):
    g = df.groupby("k")
    return g.agg({"b": "mean", "w": "sum"}).rename(columns={"b": "b_mean", "w": "w_total"})  # pdx: rename-after-agg


@case
def named_agg(df):
    g = df.groupby("k")
    return g.agg(b_mean=("b", "mean"), w_total=("w", "sum")), g.agg({"b": "mean"}).rename(index=str.upper)


@case
def merge_indicator_anti_join(df):
    other = df[df["a"] > 50][["k"]].drop_duplicates()
    m = df.merge(other, on="k", how="left", indicator=True, validate="many_to_one")
    return m[m["_merge"] == "left_only"]  # pdx: merge-indicator-anti-join


@case
def merge_indicator_kept(df):
    other = df[df["a"] > 50][["k"]].drop_duplicates()
    m = df.merge(other, on="k", how="left", indicator=True, validate="many_to_one")
    return m["_merge"].value_counts()


@case
def value_counts_share(df):
    return df["k"].value_counts() / len(df["k"])  # pdx: value-counts-share


@case
def value_counts_normalized(df):
    return df["k"].value_counts(normalize=True), df["k"].value_counts() / len(df)


@case
def nested_np_where(df):
    a = df["a"]
    return pd.Series(np.where(a < 20, "low", np.where(a < 70, "mid", "high")))  # pdx: nested-np-where


@case
def single_np_where(df):
    a = df["a"]
    return pd.Series(np.where(a < 20, "low", "high")), pd.Series("high", index=a.index).case_when([(a < 20, "low"), (a < 70, "mid")])


@case
def query_string(df):
    return df.query("a > 50 and b < 0")  # pdx: query-string


@case
def query_with_expressions(df):
    return df.loc[(pd.col("a") > 50) & (pd.col("b") < 0)]


@case
def select_then_assign(df):
    return df[["k", "a"]].assign(c=pd.col("a") * 2), df.assign(c=pd.col("a") * 2)[["k", "c"]]


@case
def filter_items(df):
    return df.filter(items=["a", "b"])  # pdx: filter-items


@case
def filter_that_stays(df):
    return df.filter(like="a"), df.filter(items=[0, 1], axis=0)


@case
def concat_then_category(df):
    x, y = df["k"].iloc[:1000].astype("category"), df["k"].iloc[1000:].astype("category")
    return pd.concat([x, y]).astype("category")  # pdx: concat-then-category


@case
def concat_that_stays(df):
    return pd.concat([df["k"], df["s"]]).astype("str"), pd.concat([df["k"], df["s"]])
