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
