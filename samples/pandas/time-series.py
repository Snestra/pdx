"""Time series, and code that looks similar but stays.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `pdx check --fix` can be compared with this file.
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from dateutil import parser

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


@case
def apply_date_method(df):
    gaps = df["d"] - pd.Timestamp("2022-01-01")
    return (
        df["d"].apply(lambda t: t.floor("h")),  # pdx: apply-date-method
        df["d"].map(lambda t: t.tz_localize("UTC")),  # pdx: apply-date-method
        df["d"].apply(lambda t: t.day_name()),  # pdx: apply-date-method
        gaps.apply(lambda v: v.total_seconds()),  # pdx: apply-date-method
        df["d"].apply(lambda t: t.weekday()),  # pdx: apply-date-method
    )


@case
def date_method_that_stays(df):
    return df["d"].dt.floor("h"), df["d"].apply(lambda t: t.round("h")), df["d"].apply(lambda t: t.isoformat())


@case
def apply_parse_date(df):
    return (
        df["raw"].apply(lambda v: datetime.strptime(v, "%Y-%m-%d")),  # pdx: apply-parse-date
        df["raw"].apply(lambda v: pd.to_datetime(v)),  # pdx: apply-parse-date
        df["raw"].map(lambda v: pd.to_datetime(v, format="%Y-%m-%d")),  # pdx: apply-parse-date
        df["raw"].map(pd.Timestamp),  # pdx: apply-parse-date
        df["raw"].apply(lambda v: pd.Timestamp(v)),  # pdx: apply-parse-date
        df["raw"].apply(parser.parse),  # pdx: apply-parse-date
    )


@case
def parse_date_on_whole_column(df):
    return pd.to_datetime(df["raw"], format="%Y-%m-%d"), df["raw"].apply(lambda v: pd.to_datetime(v, dayfirst=v.startswith("3")))


@case
def timedelta_per_value(df):
    return (
        df["a"].apply(lambda v: pd.Timedelta(days=v)),  # pdx: timedelta-per-value
        df["a"].map(lambda v: timedelta(hours=int(v))),
        df["d"] + df["a"].apply(lambda v: timedelta(hours=v)),  # pdx: timedelta-per-value
        df["a"].apply(lambda v: pd.Timedelta(v, unit="D")),  # pdx: timedelta-per-value
        pd.to_timedelta(df["a"].astype(str) + " days"),  # pdx: timedelta-per-value
    )


@case
def timedelta_on_whole_column(df):
    return pd.to_timedelta(df["a"], unit="D"), df["a"].head(5).apply(lambda v: pd.DateOffset(months=v))
