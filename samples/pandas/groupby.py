"""groupby, agg and transform with a Python function per group, and code that looks similar but
stays.

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
def groupby_lambda(df):
    g = df.groupby("k")
    return (
        g["b"].agg(lambda v: v.mean()),  # pdx: groupby-lambda
        g["b"].transform(lambda v: v.sum()),  # pdx: groupby-lambda
        g[["a", "b"]].agg(np.sum),  # pdx: groupby-lambda
        g.agg({"b": lambda v: v.max()}),  # pdx: groupby-lambda
        g.agg(low=("b", lambda v: v.min())),  # pdx: groupby-lambda
        df.pivot_table(index="k", columns="s", values="b", aggfunc=np.mean),  # pdx: groupby-lambda
    )


@case
def groupby_function_that_stays(df):
    g = df.groupby("k")
    return g["b"].agg([lambda v: v.mean(), "sum"]), g["b"].agg(np.median), g["a"].agg(np.std), g["b"].agg(lambda v: v.max() - v.min())


@case
def groupby_lambda_window(df):
    g = df.groupby("k")["b"]
    return (
        g.transform(lambda v: v.cumsum()),  # pdx: groupby-lambda-window
        g.transform(lambda v: v.shift(1)),  # pdx: groupby-lambda-window
        g.transform(lambda v: v.rank(method="first")),  # pdx: groupby-lambda-window
    )


@case
def groupby_window_that_stays(df):
    g = df.groupby("k")["b"]
    return g.transform(lambda v: v.shift(len(v) // 2)), g.transform(lambda v: v.cumsum() / v.sum())


@case
def groupby_window_by_time(df):
    g = df.set_index("d").sort_index().groupby("k")["b"]
    return g.transform(lambda v: v.shift(1, freq="D"))


@case
def groupby_lambda_arithmetic(df):
    return (
        df.groupby("k")["w"].transform(lambda v: v / v.sum()),  # pdx: groupby-lambda-arithmetic
        df.groupby("k")["b"].transform(lambda v: (v - v.mean()) / v.std()),  # pdx: groupby-lambda-arithmetic
        df.groupby("k")["b"].transform(lambda v: v.fillna(v.mean())),  # pdx: groupby-lambda-arithmetic
    )


@case
def groupby_arithmetic_that_stays(df):
    return df["w"] / df.groupby("k")["w"].transform("sum"), df.groupby("k")["w"].transform(lambda v: v / v.max() + 1)


@case
def groupby_filter_lambda(df):
    return df.groupby("k").filter(lambda g: len(g) > 400)  # pdx: groupby-filter-lambda


@case
def groupby_filter_that_stays(df):
    return df.groupby("k").filter(lambda g: g["b"].mean() > 0), df[df.groupby("k")["k"].transform("size") > 400]


@case
def groupby_apply(df):
    return df.groupby("k").apply(lambda g: g.loc[g["b"].idxmax()])  # pdx: groupby-apply


@case
def groupby_without_apply(df):
    return df.loc[df.groupby("k")["b"].idxmax()], df.apply(lambda c: c.iloc[0])


@case
def aggregate_then_merge_back(df):
    totals = df.groupby("k")["b"].sum().rename("total").reset_index()
    return (
        df.merge(df.groupby("k")["b"].sum().rename("total").reset_index(), on="k", how="left", validate="many_to_one"),  # pdx: aggregate-then-merge-back
        df["k"].map(df.groupby("k")["b"].sum()),  # pdx: aggregate-then-merge-back
        totals,
    )


@case
def transform_instead(df):
    other = df.head(10)
    return (
        df.assign(total=df.groupby("k")["b"].transform("sum")),
        df.merge(other.groupby("k")["b"].sum().reset_index(), on="k", validate="many_to_one"),  # pdx: groupby-then-reset-index
    )


@case
def groupby_first_skips_missing(df):
    return df.sort_values("d").groupby("k").first(), df.groupby("k")["b"].last()  # pdx: groupby-first-skips-missing


@case
def groupby_first_row(df):
    return df.sort_values("d").groupby("k").first(skipna=False), df.sort_values("d").groupby("k").head(1), df.iloc[[0]]


@case
def lambda_with_own_reduction(df):
    return (
        df.groupby("k")["b"].transform(lambda v: v - v.mean()),  # pdx: groupby-lambda-arithmetic
        df.groupby("k")["w"].transform(lambda v: v / v.max()),  # pdx: groupby-lambda-arithmetic
        df.groupby("k")["w"].transform(lambda v: (v - v.min()) / (v.max() - v.min())),  # pdx: groupby-lambda-arithmetic
    )


@case
def reduction_through_transform(df):
    return df["b"] - df.groupby("k")["b"].transform("mean"), df.groupby("k")["b"].transform(lambda v: v.rolling(7).mean())


@case
def lambda_reduction_with_arguments(df):
    return (
        df.groupby("k")["w"].agg(lambda v: v.quantile(0.9)),  # pdx: groupby-lambda
        df.groupby("k")["w"].agg(lambda v: v.std(ddof=0)),  # pdx: groupby-lambda
        df.groupby("k")["b"].agg(lambda v: (v > 0).sum()),  # pdx: groupby-lambda
    )


@case
def reduction_called_on_the_groupby(df):
    return df.groupby("k")["w"].quantile(0.9), (df["b"] > 0).groupby(df["k"]).sum(), df.groupby("k")["w"].agg(lambda v: v.max() - v.min())
