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
def lambda_column_assign(df):
    return df.assign(
        c=lambda d: d["a"] * d["w"] + 1,  # pdx: lambda-column
        u=lambda d: d["s"].str.strip().str.upper(),  # pdx: lambda-column
    )


@case
def lambda_column_loc(df):
    return df.loc[lambda d: (d["a"] > 50) & (d["b"] < 0)], df.loc[lambda d: d["a"] > 90, "w"]  # pdx: lambda-column


@case
def lambda_that_needs_data(df):
    lookup = {"x": 2}
    return df.assign(
        n=lambda d: len(d),
        m=lambda d: np.where(d["a"] > 5, 1, 0),
        z=lambda d: d["a"] * lookup["x"],
        y=lambda d: d.a + 1,
        t=lambda d: d["a"] if len(d) > 5 else 0,
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
    return df.sort_values("b").reset_index(), df.groupby("k").sample(2, random_state=1).reset_index(drop=True)


@case
def set_index_then_resample(df):
    return (
        df.set_index("d").resample("D")["b"].sum(),  # pdx: set-index-then-resample
        df[["a", "b", "d"]].set_index("d").resample("W").mean(),  # pdx: set-index-then-resample
    )


@case
def set_index_for_upsampling(df):
    return df.drop_duplicates("d").set_index("d").sort_index().resample("h").asfreq().shape


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
