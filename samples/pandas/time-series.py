"""Time series, and code that looks similar but stays.

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


def spread(window):
    return window.max() - window.min()


@case
def rolling_apply(df):
    return (
        df["b"].rolling(20).apply(lambda w: w.mean()),  # pdx: rolling-apply
        df["b"].expanding().apply(lambda w: w.max()),  # pdx: rolling-apply
    )


@case
def rolling_apply_without_raw(df):
    return df["b"].rolling(20).apply(spread)  # pdx: rolling-apply


@case
def rolling_that_stays(df):
    return df["b"].rolling(20).apply(spread, raw=True), df["b"].rolling(20).apply(lambda w: w.count()), df["b"].rolling(20).mean()
