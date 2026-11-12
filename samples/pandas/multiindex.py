"""MultiIndex, and code that looks similar but stays.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `xpd check --fix` can be compared with this file.
"""

import itertools

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
def from_tuples_of_columns(df):
    return (
        pd.MultiIndex.from_tuples(list(zip(df["k"], df["a"])), names=["k", "a"]),  # xpd: multiindex-from-tuples
        pd.MultiIndex.from_tuples(zip(df["k"].to_numpy(), df["a"].to_numpy())),  # xpd: multiindex-from-tuples
    )


@case
def from_tuples_of_products(df):
    keys = sorted(df["k"].unique())
    numbers = range(3)
    return (
        pd.MultiIndex.from_tuples(list(itertools.product(keys, numbers)), names=["k", "n"]),  # xpd: multiindex-from-tuples
        pd.MultiIndex.from_tuples(itertools.product(keys, numbers)),  # xpd: multiindex-from-tuples
        pd.MultiIndex.from_tuples([(k, n) for k in keys for n in numbers], names=["k", "n"]),  # xpd: multiindex-from-tuples
    )


@case
def multiindex_that_stays(df):
    keys = sorted(df["k"].unique())
    pairs = [("g1", 1), ("g2", 2)]
    return (
        pd.MultiIndex.from_arrays([df["k"], df["a"]]),
        pd.MultiIndex.from_product([keys, range(3)]),
        pd.MultiIndex.from_tuples(pairs),
        pd.MultiIndex.from_tuples(list(itertools.product(keys, repeat=2))),
        pd.MultiIndex.from_tuples([(k, n) for k, n in pairs]),
    )


@case
def level_values_unique(df):
    by_key = df.set_index(["k", "a"])
    return (
        by_key.index.get_level_values("k").unique(),  # xpd: level-values-unique
        by_key.index.get_level_values(1).nunique(),  # xpd: level-values-unique
    )


@case
def level_values_that_stay(df):
    by_key = df.set_index(["k", "a"])
    return by_key.index.unique("k"), by_key.index.get_level_values("k"), by_key.index.get_level_values("a").max()
