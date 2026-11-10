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


@case
def text_time_key(df):
    return df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum()  # pdx: text-time-key


@case
def period_time_key(df):
    return df.groupby(df["d"].dt.to_period("M"))["b"].sum(), df["d"].dt.strftime("%Y-%m")


@case
def object_dates(df):
    return df["d"].dt.date  # pdx: object-dates


@case
def datetime_dates(df):
    return df["d"].dt.normalize(), df["d"].dt.floor("D"), df["d"].dt.day


@case
def apply_on_dates(df):
    return (
        df["d"].apply(lambda t: t + pd.Timedelta(days=7)),  # pdx: apply-on-dates
        df["d"].apply(lambda t: t.strftime("%Y-%m")),  # pdx: apply-on-dates
    )


@case
def apply_month_start(df):
    return df["d"].map(lambda t: t.replace(day=1))  # pdx: apply-on-dates


@case
def dates_on_whole_column(df):
    return df["d"] + pd.Timedelta(days=7), df["d"].apply(lambda t: t + pd.Timedelta(days=t.day))


@case
def index_year_mask(df):
    ts = df.set_index("d").sort_index()
    return ts[ts.index.year == 2023]  # pdx: index-year-mask


@case
def index_year_label(df):
    ts = df.set_index("d").sort_index()
    return ts.loc["2023"], ts[ts.index.month == 3]
