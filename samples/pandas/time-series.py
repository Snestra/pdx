"""Time series, and code that looks similar but stays.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `xpd check --fix` can be compared with this file.
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
        df["b"].rolling(20).apply(lambda w: w.mean()),  # xpd: rolling-apply
        df["b"].expanding().apply(lambda w: w.max()),  # xpd: rolling-apply
    )


@case
def rolling_apply_without_raw(df):
    return df["b"].rolling(20).apply(spread)  # xpd: rolling-apply


@case
def rolling_that_stays(df):
    return df["b"].rolling(20).apply(spread, raw=True), df["b"].rolling(20).apply(lambda w: w.count()), df["b"].rolling(20).mean()


@case
def text_time_key(df):
    return df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum()  # xpd: text-time-key


@case
def period_time_key(df):
    return df.groupby(df["d"].dt.to_period("M"))["b"].sum(), df["d"].dt.strftime("%Y-%m")


@case
def object_dates(df):
    return df["d"].dt.date  # xpd: object-dates


@case
def datetime_dates(df):
    return df["d"].dt.normalize(), df["d"].dt.floor("D"), df["d"].dt.day


@case
def apply_on_dates(df):
    return (
        df["d"].apply(lambda t: t + pd.Timedelta(days=7)),  # xpd: apply-on-dates
        df["d"].apply(lambda t: t.strftime("%Y-%m")),  # xpd: apply-on-dates
    )


@case
def apply_month_start(df):
    return df["d"].map(lambda t: t.replace(day=1))  # xpd: apply-on-dates


@case
def dates_on_whole_column(df):
    return df["d"] + pd.Timedelta(days=7), df["d"] + pd.to_timedelta(df["d"].dt.day, unit="D")


@case
def index_year_mask(df):
    ts = df.set_index("d").sort_index()
    return ts[ts.index.year == 2023]  # xpd: index-year-mask


@case
def index_year_label(df):
    ts = df.set_index("d").sort_index()
    return ts.loc["2023"], ts[ts.index.month == 3]


@case
def apply_date_method(df):
    gaps = df["d"] - pd.Timestamp("2022-01-01")
    return (
        df["d"].apply(lambda t: t.floor("h")),  # xpd: apply-date-method
        df["d"].map(lambda t: t.tz_localize("UTC")),  # xpd: apply-date-method
        df["d"].apply(lambda t: t.day_name()),  # xpd: apply-date-method
        gaps.apply(lambda v: v.total_seconds()),  # xpd: apply-date-method
        df["d"].apply(lambda t: t.weekday()),  # xpd: apply-date-method
    )


@case
def date_method_that_stays(df):
    return df["d"].dt.floor("h"), df["d"].apply(lambda t: t.round("h")), df["d"].apply(lambda t: t.isoformat())


@case
def apply_parse_date(df):
    return (
        df["raw"].apply(lambda v: datetime.strptime(v, "%Y-%m-%d")),  # xpd: apply-parse-date
        df["raw"].apply(lambda v: pd.to_datetime(v)),  # xpd: apply-parse-date
        df["raw"].map(lambda v: pd.to_datetime(v, format="%Y-%m-%d")),  # xpd: apply-parse-date
        df["raw"].map(pd.Timestamp),  # xpd: apply-parse-date
        df["raw"].apply(lambda v: pd.Timestamp(v)),  # xpd: apply-parse-date
        df["raw"].apply(parser.parse),  # xpd: apply-parse-date
    )


@case
def parse_date_on_whole_column(df):
    return pd.to_datetime(df["raw"], format="%Y-%m-%d"), df["raw"].apply(lambda v: pd.to_datetime(v, dayfirst=v.startswith("3")))


@case
def timedelta_per_value(df):
    return (
        df["a"].apply(lambda v: pd.Timedelta(days=v)),  # xpd: timedelta-per-value
        df["a"].map(lambda v: timedelta(hours=int(v))),
        df["d"] + df["a"].apply(lambda v: timedelta(hours=v)),  # xpd: timedelta-per-value
        df["a"].apply(lambda v: pd.Timedelta(v, unit="D")),  # xpd: timedelta-per-value
        pd.to_timedelta(df["a"].astype(str) + " days"),  # xpd: timedelta-per-value
    )


@case
def timedelta_on_whole_column(df):
    return pd.to_timedelta(df["a"], unit="D"), df["a"].head(5).apply(lambda v: pd.DateOffset(months=v))


@case
def strftime_date_part(df):
    return (
        df["d"].dt.strftime("%Y").astype(int),  # xpd: strftime-date-part
        df["d"].dt.strftime("%m").astype("int64"),  # xpd: strftime-date-part
        df["d"].dt.strftime("%H").astype(int),  # xpd: strftime-date-part
        df["d"].dt.strftime("%j").astype(int),  # xpd: strftime-date-part
        df["d"].dt.strftime("%A"),  # xpd: strftime-date-part
        df["d"].dt.strftime("%B"),  # xpd: strftime-date-part
    )


@case
def date_part_from_dt(df):
    return df["d"].dt.year, df["d"].dt.day_name(), df["d"].dt.strftime("%Y-%m"), df["d"].dt.strftime("%Y").astype(str)


@case
def apply_date_expression(df):
    return (
        df["d"].apply(lambda t: t.weekday() >= 5),  # xpd: apply-date-expression
        df["d"].apply(lambda t: t.month in (12, 1, 2)),  # xpd: apply-date-expression
        df["d"].map(lambda t: t.year == 2023),  # xpd: apply-date-expression
        df["d"].apply(lambda t: t.hour * 60 + t.minute),  # xpd: apply-date-expression
        df["d"].apply(lambda t: t + pd.Timedelta(days=t.day)),  # xpd: apply-date-expression
    )


@case
def date_expression_on_whole_column(df):
    limit = pd.Timestamp("2022-06-01")
    return df["d"].dt.weekday >= 5, df["d"].dt.hour * 60 + df["d"].dt.minute, df["a"].apply(lambda v: limit.year + v)


@case
def apply_date_method_without_dt_twin(df):
    return (
        df["d"].apply(lambda t: t.date()),  # xpd: apply-date-method
        df["d"].apply(lambda t: t.isocalendar()[1]),  # xpd: apply-date-method
        df["d"].map(lambda t: t.isocalendar().week),  # xpd: apply-date-method
        df["d"].apply(lambda t: t.timestamp()),  # xpd: apply-date-method
        df["d"].map(lambda t: t.toordinal()),  # xpd: apply-date-method
    )


@case
def epoch_on_whole_column(df):
    return (df["d"] - pd.Timestamp("1970-01-01")) / pd.Timedelta("1s"), df["d"].dt.isocalendar().week, df["d"].dt.date  # xpd: object-dates


@case
def strftime_round_trip(df):
    return (
        pd.to_datetime(df["d"].dt.strftime("%Y-%m-%d")),  # xpd: strftime-round-trip
        pd.to_datetime(df["d"].dt.strftime("%Y-%m-%d %H")),  # xpd: strftime-round-trip
        df[df["d"].dt.strftime("%Y-%m-%d") == "2022-06-01"],  # xpd: strftime-round-trip
    )


@case
def dates_cut_without_text(df):
    return df["d"].dt.normalize(), df["d"].dt.floor("h"), df[df["d"].dt.normalize() == pd.Timestamp("2022-06-01")], pd.to_datetime(df["raw"])


@case
def rolling_numpy_function(df):
    return (
        df["b"].rolling(20).agg(np.max),  # xpd: rolling-apply
        df["b"].rolling(20).apply(np.mean, raw=True),  # xpd: rolling-apply
    )


@case
def resample_lambda(df):
    ts = df.set_index("d").sort_index()
    return (
        ts[["b"]].resample("D").apply(lambda v: v.sum()),  # xpd: groupby-lambda
        ts.resample("D")["b"].agg(np.max),  # xpd: groupby-lambda
    )


@case
def resample_named_method(df):
    ts = df.set_index("d").sort_index()
    return ts[["b"]].resample("D").sum(), ts.resample("D")["b"].max(), ts.resample("D")["b"].first()


@case
def epoch_from_index_values(df):
    index = pd.DatetimeIndex(df["d"])
    return (
        index.asi8 // 10**9,  # xpd: epoch-from-int-cast
        df["d"].values.astype("float64") / 1e9,  # xpd: epoch-from-int-cast
    )


@case
def removed_time_series_forms(df):
    ts = df.set_index("d").sort_index()
    return (
        ts.tshift(1),  # xpd: removed-in-pandas-3
        ts["b"].pad(),  # xpd: removed-in-pandas-3
        ts.first("3D"),  # xpd: removed-in-pandas-3
        ts.resample("D", loffset="1h").sum(),  # xpd: removed-in-pandas-3
        pd.date_range("2024-01-01", periods=3, closed="left"),  # xpd: removed-in-pandas-3
        pd.to_datetime(df["raw"], infer_datetime_format=True),  # xpd: removed-in-pandas-3
        pd.to_datetime(df["raw"], errors="ignore"),  # xpd: removed-in-pandas-3
        df["b"].pct_change(fill_method="pad"),  # xpd: removed-in-pandas-3
        pd.Timedelta("5T"),  # xpd: removed-in-pandas-3
        df["d"].diff().astype("timedelta64[D]"),  # xpd: removed-in-pandas-3
    )


@case
def time_series_forms_that_stay(df):
    ts = df.set_index("d").sort_index()
    return ts.shift(1), ts["b"].ffill(), ts.resample("D", closed="left").sum(), pd.to_datetime(df["raw"], errors="coerce"), np.pad(df["a"].to_numpy(), 1), df["s"].str.pad(12), pd.Timedelta("5min")
