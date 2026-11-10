"""Python work per row or per value, and code that looks similar but stays.

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
def apply_to_datetime(df):
    return df["raw"].apply(pd.to_datetime)  # pdx: apply-known-function


@case
def apply_missing_check(df):
    return df["b"].apply(pd.isna), df["b"].map(pd.notna)  # pdx: apply-known-function


@case
def apply_len(df):
    return df["s"].apply(len)  # pdx: apply-known-function


@case
def apply_round(df):
    return df["b"].apply(lambda v: round(v, 2))  # pdx: apply-known-function


@case
def apply_that_stays(df):
    return df[["a", "b"]].apply(len), df["b"].apply(lambda v: round(v, 2) + 1)


@case
def literal_contains(df):
    return (
        df["s"].str.contains("ta_"),  # pdx: literal-contains
        df["s"].str.contains("alpha", case=False),  # pdx: literal-contains
    )


@case
def regex_contains(df):
    return df["s"].str.contains("^Al"), df["s"].str.contains("a.p", case=False), df["s"].str.contains("ta_", regex=False)


@case
def copy_after_indexing(df):
    part = df[df["a"] > 50].copy()  # pdx: copy-after-indexing
    part["a"] = 0
    cols = df.loc[:, ["a", "b"]].copy()  # pdx: copy-after-indexing
    cols["a"] = 1
    pair = df[["a", "w"]].copy()  # pdx: copy-after-indexing
    pair["w"] = 2.0
    return part, cols, pair, df


@case
def copy_that_stays(df):
    defaults = {"x": {"y": 1}}
    mine = defaults["x"].copy()
    mine["y"] = 2
    values = df["a"].to_numpy()
    head = values[:3].copy()
    head[0] = -1
    return defaults["x"]["y"], values[0], df["a"].copy()
