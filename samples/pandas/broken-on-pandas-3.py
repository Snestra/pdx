"""Code that is wrong or broken on pandas 3, and code that looks similar but is right.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `pdx check --fix` can be compared with this file.
"""

import io

import numpy as np
import pandas as pd

pd.set_option("mode.copy_on_write", True)  # pdx: deprecated-in-pandas-3

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame(n=200, seed=0):
    r = np.random.default_rng(seed)
    b = r.normal(size=n).round(4)
    b[::7] = np.nan
    return pd.DataFrame({
        "a": r.integers(0, 100, n),
        "b": b,
        "k": pd.Series(r.choice(["x", "y", "z"], n)).where(r.random(n) > 0.1),
        "d": pd.to_datetime("2024-01-01") + pd.to_timedelta(r.integers(0, 400 * 24, n), unit="h"),
    })


@case
def chained_column_then_row(df):
    df["b"][0] = 5.0  # pdx: chained-assignment
    df["a"][1] += 1  # pdx: chained-assignment
    return df


@case
def chained_mask_then_column(df):
    df[df["a"] > 50]["b"] = 0.0  # pdx: chained-assignment
    df[(df["a"] < 5) | df["k"].isna()]["b"] = 1.0  # pdx: chained-assignment
    return df


@case
def chained_loc_then_column(df):
    df.loc[df["a"] > 50]["b"] = 0.0  # pdx: chained-assignment
    return df


@case
def chained_without_fix(df):
    df.iloc[0]["b"] = 7.0  # pdx: chained-assignment
    return df


@case
def one_loc_call_and_nested_dict(df):
    df.loc[df["a"] > 50, "b"] = 0.0
    config = {"db": {"host": "a"}}
    config["db"]["host"] = "b"
    rows = [{"name": "a"}]
    rows[0]["name"] = "b"
    return df, config["db"]["host"], rows[0]["name"]


@case
def inplace_on_column(df):
    df["b"].fillna(0.0, inplace=True)  # pdx: inplace-on-column
    df.loc[:, "a"].clip(0, 10, inplace=True)  # pdx: inplace-on-column
    return df


@case
def inplace_on_frame(df):
    df.fillna({"b": 0.0}, inplace=True)  # pdx: no-inplace
    return df


@case
def inplace_result_assigned(df):
    df = df.dropna(inplace=True)  # pdx: inplace-result-assigned
    return type(df).__name__


@case
def result_assigned(df):
    df = df.dropna()
    return df


@case
def epoch_from_int_cast(df):
    return df["d"].astype("int64") // 10**9  # pdx: epoch-from-int-cast


@case
def epoch_from_timedelta(df):
    return (df["d"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s"), df["a"].astype("int64") // 10


@case
def compare_to_missing(df):
    return (
        df[df["b"] == np.nan],  # pdx: compare-to-missing
        df[df["b"] != np.nan],  # pdx: compare-to-missing
        df["k"].astype(str) == "nan",  # pdx: compare-to-missing
    )


@case
def isna_and_text_compare(df):
    return df[df["b"].isna()], df["k"] == "nan"


@case
def in_column(df):
    return 37 in df["a"], 5000 not in df["a"]  # pdx: in-column


@case
def in_values_and_columns(df):
    return 37 in df["a"].to_numpy(), "a" in df.columns


@case
def mask_precedence(df):
    return df[df["a"] > 1 & df["b"] < 3]  # pdx: mask-precedence


@case
def mask_in_parentheses(df):
    flags = 6
    return df[(df["a"] > 1) & (df["b"] < 3)], flags & 4 == 0


@case
def write_through_values(df):
    df["a"].values[0] = 9  # pdx: write-through-values
    return df


@case
def write_with_loc(df):
    arr = df["a"].to_numpy().copy()
    arr[0] = 9
    df.loc[df.index[0], "a"] = 9
    return df, arr.tolist()


@case
def object_dtype_check(df):
    text = [c for c in df.columns if df[c].dtype == object]  # pdx: object-dtype-check
    return text, df.select_dtypes(include="object")  # pdx: object-dtype-check


@case
def string_dtype_check(df):
    return [c for c in df.columns if df[c].dtype == "str"], df.select_dtypes(include="number")


@case
def groupby_apply_reads_key(df):
    return df.groupby("k").apply(lambda g: g["k"].iloc[0] + str(len(g)))  # pdx: groupby-apply-reads-key


@case
def groupby_apply_reads_name(df):
    return df.groupby("k").apply(lambda g: g.name + str(len(g))), df.groupby("k").apply(lambda g: g["a"].sum())


@case
def removed_applymap(df):
    return df[["a", "b"]].applymap(lambda v: v * 2)  # pdx: removed-in-pandas-3


@case
def removed_fillna_method(df):
    return (
        df["b"].fillna(method="ffill"),  # pdx: removed-in-pandas-3
        df[["a", "b"]].fillna(method="bfill", limit=2),  # pdx: removed-in-pandas-3
    )


@case
def removed_frequencies(df):
    return (
        df["d"].dt.floor("H"),  # pdx: removed-in-pandas-3
        pd.date_range("2024-01-01", periods=4, freq="BM"),  # pdx: removed-in-pandas-3
        df.resample("15T", on="d")["a"].sum(),  # pdx: removed-in-pandas-3
    )


@case
def removed_month_in_resample(df):
    return df.resample("M", on="d")["a"].sum()  # pdx: removed-in-pandas-3


@case
def removed_year_in_resample(df):
    return df.set_index("d")["a"].resample("A").sum()  # pdx: removed-in-pandas-3


@case
def frequencies_that_stay(df):
    periods = df.set_index(df["d"].dt.to_period("M"))["a"].sort_index()
    return (
        df["d"].dt.to_period("M"),
        periods.groupby(level=0).sum().asfreq("M"),
        df.resample("ME", on="d")["a"].sum(),
        df.groupby(pd.Grouper(key="d", freq="QE"))["a"].sum(),
    )


@case
def removed_delim_whitespace(df):
    return pd.read_csv(io.StringIO("a b\n1 2\n3 4"), delim_whitespace=True)  # pdx: removed-in-pandas-3


@case
def removed_dt_week(df):
    return df["d"].dt.week  # pdx: removed-in-pandas-3


@case
def deprecated_utcnow(df):
    return pd.Timestamp.utcnow().tz is not None  # pdx: deprecated-in-pandas-3


@case
def deprecated_copy_keyword(df):
    return df.astype({"a": "float64"}, copy=False)  # pdx: deprecated-in-pandas-3


@case
def copy_keyword_that_stays(df):
    return df["a"].to_numpy(copy=False).tolist(), df.astype({"a": "float64"})
