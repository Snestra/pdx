"""Code that is wrong or broken on pandas 3, and code that looks similar but is right.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `xpd check --fix` can be compared with this file.
"""

import io
import warnings

import numpy as np
import pandas as pd

pd.set_option("mode.copy_on_write", True)  # xpd: deprecated-in-pandas-3

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
    df["b"][0] = 5.0  # xpd: chained-assignment
    df["a"][1] += 1  # xpd: chained-assignment
    return df


@case
def chained_mask_then_column(df):
    df[df["a"] > 50]["b"] = 0.0  # xpd: chained-assignment
    df[(df["a"] < 5) | df["k"].isna()]["b"] = 1.0  # xpd: chained-assignment
    high = df["a"] > 90
    df[high]["b"] = 2.0  # xpd: chained-assignment
    return df


@case
def chained_loc_then_column(df):
    df.loc[df["a"] > 50]["b"] = 0.0  # xpd: chained-assignment
    return df


@case
def chained_without_fix(df):
    df.iloc[0]["b"] = 7.0  # xpd: chained-assignment
    return df


@case
def one_loc_call_and_nested_dict(df):
    df.loc[df["a"] > 50, "b"] = 0.0
    config = {"db": {"host": "a"}}
    config["db"]["host"] = "b"
    rows = [{"name": "a"}]
    rows[0]["name"] = "b"
    key = "db"
    config[key]["host"] = "c"
    return df, config["db"]["host"], rows[0]["name"]


@case
def inplace_on_column(df):
    df["b"].fillna(0.0, inplace=True)  # xpd: inplace-on-column
    df.loc[:, "a"].clip(0, 10, inplace=True)  # xpd: inplace-on-column
    return df


@case
def inplace_on_frame(df):
    df.fillna({"b": 0.0}, inplace=True)  # xpd: no-inplace
    return df


@case
def inplace_result_assigned(df):
    df = df.dropna(inplace=True)  # xpd: inplace-result-assigned
    return type(df).__name__


@case
def result_assigned(df):
    df = df.dropna()
    return df


@case
def epoch_from_int_cast(df):
    return df["d"].astype("int64") // 10**9  # xpd: epoch-from-int-cast


@case
def epoch_from_timedelta(df):
    return (df["d"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s"), df["a"].astype("int64") // 10


@case
def compare_to_missing(df):
    return (
        df[df["b"] == np.nan],  # xpd: compare-to-missing
        df[df["b"] != np.nan],  # xpd: compare-to-missing
        df["k"].astype(str) == "nan",  # xpd: compare-to-missing
    )


@case
def isna_and_text_compare(df):
    return df[df["b"].isna()], df["k"] == "nan"


@case
def in_column(df):
    return 37 in df["a"], 5000 not in df["a"]  # xpd: in-column


@case
def in_values_and_columns(df):
    return 37 in df["a"].to_numpy(), "a" in df.columns


@case
def mask_precedence(df):
    return df[df["a"] > 1 & df["b"] < 3]  # xpd: mask-precedence


@case
def mask_in_parentheses(df):
    flags = 6
    return df[(df["a"] > 1) & (df["b"] < 3)], flags & 4 == 0


@case
def write_through_values(df):
    df["a"].values[0] = 9  # xpd: write-through-values
    return df


@case
def write_with_loc(df):
    arr = df["a"].to_numpy().copy()
    arr[0] = 9
    df.loc[df.index[0], "a"] = 9
    return df, arr.tolist()


@case
def object_dtype_check(df):
    text = [c for c in df.columns if df[c].dtype == object]  # xpd: object-dtype-check
    return text, df.select_dtypes(include="object")  # xpd: object-dtype-check


@case
def string_dtype_check(df):
    return [c for c in df.columns if df[c].dtype == "str"], df.select_dtypes(include="number")


@case
def groupby_apply_reads_key(df):
    return df.groupby("k").apply(lambda g: g["k"].iloc[0] + str(len(g)))  # xpd: groupby-apply-reads-key, groupby-apply


@case
def groupby_apply_reads_name(df):
    return df.groupby("k").apply(lambda g: g.name + str(len(g))), df.groupby("k").apply(lambda g: g["a"].sum())  # xpd: groupby-apply


@case
def removed_applymap(df):
    return df[["a", "b"]].applymap(lambda v: v * 2)  # xpd: removed-in-pandas-3


@case
def removed_fillna_method(df):
    return (
        df["b"].fillna(method="ffill"),  # xpd: removed-in-pandas-3
        df[["a", "b"]].fillna(method="bfill", limit=2),  # xpd: removed-in-pandas-3
    )


@case
def removed_frequencies(df):
    return (
        df["d"].dt.floor("H"),  # xpd: removed-in-pandas-3
        pd.date_range("2024-01-01", periods=4, freq="BM"),  # xpd: removed-in-pandas-3
        df.resample("15T", on="d")["a"].sum(),  # xpd: removed-in-pandas-3
    )


@case
def removed_month_in_resample(df):
    return df.resample("M", on="d")["a"].sum()  # xpd: removed-in-pandas-3


@case
def removed_year_in_resample(df):
    return df.set_index("d")["a"].resample("A").sum()  # xpd: removed-in-pandas-3


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
    return pd.read_csv(io.StringIO("a b\n1 2\n3 4"), delim_whitespace=True)  # xpd: removed-in-pandas-3


@case
def removed_dt_week(df):
    return df["d"].dt.week  # xpd: removed-in-pandas-3


@case
def deprecated_utcnow(df):
    return pd.Timestamp.utcnow().tz is not None  # xpd: deprecated-in-pandas-3


@case
def deprecated_copy_keyword(df):
    return df.rename(columns={"a": "A"}, copy=False)  # xpd: deprecated-in-pandas-3


@case
def deprecated_copy_keyword_on_astype(df):
    return df.astype({"a": "float64"}, copy=False)  # xpd: deprecated-in-pandas-3


@case
def copy_on_write_option_in_function(df):
    pd.set_option("mode.copy_on_write", True)  # xpd: deprecated-in-pandas-3
    pd.set_option("mode.copy_on_write", True)  # xpd: deprecated-in-pandas-3


@case
def copy_keyword_that_stays(df):
    return df["a"].to_numpy(copy=False).tolist(), df.astype({"a": "float64"})


@case
def reduction_level_argument(df):
    by_key = df.dropna().set_index(["k", "a"])
    return (
        by_key["b"].sum(level="k"),  # xpd: reduction-level-argument
        by_key[["b"]].mean(level=0),  # xpd: reduction-level-argument
    )


@case
def reduction_level_without_fix(df):
    by_key = df.dropna().set_index(["k", "a"])
    return by_key[["b"]].max(axis=0, level="k")  # xpd: reduction-level-argument


@case
def reduction_by_level(df):
    by_key = df.dropna().set_index(["k", "a"])
    return by_key["b"].groupby(level="k").sum(), by_key.reset_index(level="a").shape, by_key.sort_index(level="k").shape


@case
def stack_dropna(df):
    wide = df.pivot_table(index="k", columns="a", values="b")
    return (
        wide.stack(dropna=False),  # xpd: stack-dropna
        wide.stack(dropna=True),  # xpd: stack-dropna
        wide.stack(future_stack=False),  # xpd: stack-dropna
    )


@case
def stack_that_stays(df):
    wide = df.pivot_table(index="k", columns="a", values="b")
    return wide.stack(), wide.stack().dropna(), np.stack([df["a"].to_numpy(), df["a"].to_numpy()])


@case
def frame_append(df):
    out = pd.DataFrame()
    for part in (df.head(3), df.tail(3)):
        out = out.append(part)  # xpd: frame-append
    out.append({"a": 1}, ignore_index=True)  # xpd: frame-append
    return out, df["a"].append(df["a"])  # xpd: frame-append


@case
def append_that_stays(df):
    parts = []
    for part in (df.head(3), df.tail(3)):
        parts.append(part)
    columns = df.columns.append(pd.Index(["extra"]))
    return pd.concat(parts), columns, np.append(df["a"].to_numpy(), 1)


@case
def str_replace_regex_default(df):
    return (
        df["k"].str.replace(r"\d+", ""),  # xpd: str-replace-regex-default
        df["k"].str.replace("[^a-y]", ""),  # xpd: str-replace-regex-default
        df["k"].str.replace("^x", "X"),  # xpd: str-replace-regex-default
        df["k"].str.replace("x|y", "_"),  # xpd: str-replace-regex-default
        df["k"].str.replace(".*z", ""),  # xpd: str-replace-regex-default
    )


@case
def str_replace_plain_text(df):
    return df["k"].str.replace(r"\d+", "", regex=True), df["k"].str.replace(".", ""), df["k"].str.replace("$", ""), df["k"].str.replace("x", "y", regex=False), "[x]".replace("[x]", "")


@case
def positional_key_on_labels(df):
    return (
        df["k"].value_counts()[0],  # xpd: positional-key-on-labels
        df.iloc[0][1],  # xpd: positional-key-on-labels
        df.dtypes[0],  # xpd: positional-key-on-labels
        df.isna().sum()[1],  # xpd: positional-key-on-labels
    )


@case
def positional_key_through_iloc(df):
    return df["k"].value_counts().iloc[0], df.iloc[0, 1], df["k"].value_counts()["x"], df.iloc[:5]["a"], df[["a"]].to_numpy().sum(axis=0)[0]


@case
def chained_attribute_and_indexer(df):
    df.b[df.a > 50] = 0.0  # xpd: chained-assignment
    df["b"].loc[df["a"] < 5] = 1.0  # xpd: chained-assignment
    df["b"].iloc[0] = 7.0  # xpd: chained-assignment
    df["b"].update(pd.Series([9.0], index=[1]))  # xpd: chained-assignment
    df[["b"]].update(pd.DataFrame({"b": [8.0]}, index=[2]))  # xpd: chained-assignment
    return df


@case
def writes_that_reach_the_frame(df):
    df.loc[df.a > 50, "b"] = 0.0
    df.update(pd.DataFrame({"b": [9.0]}, index=[1]))
    state = {"seen": {}}
    state["seen"].update({"a": 1})
    return df, df["b"].iloc[0]


@case
def compare_to_none(df):
    return df[df["b"] == None], df.loc[df["b"] != None, "a"]  # xpd: compare-to-missing


@case
def none_outside_a_mask(df):
    config = {"mode": None}
    return df[df["b"].isna()], config["mode"] == None


@case
def object_dtype_check_other_shapes(df):
    return (
        [c for c in df if pd.api.types.is_object_dtype(df[c])],  # xpd: object-dtype-check
        [c for c in df if df[c].dtype in ("object", "category")],  # xpd: object-dtype-check
        [c for c in df if df[c].dtype.name == "object"],  # xpd: object-dtype-check
        df.select_dtypes("object"),  # xpd: object-dtype-check
        df.select_dtypes(["object", "category"]),  # xpd: object-dtype-check
    )


@case
def dtype_checks_that_stay(df):
    return df.select_dtypes("number"), [c for c in df if df[c].dtype in ("int64", "float64")], df["k"].dtype.kind == "O"


@case
def removed_names(df):
    warnings.simplefilter("ignore", pd.errors.SettingWithCopyWarning)  # xpd: removed-in-pandas-3
    pd.set_option("mode.use_inf_as_na", True)  # xpd: removed-in-pandas-3
    return (
        pd.value_counts(df["k"]),  # xpd: removed-in-pandas-3
        df.index.is_monotonic,  # xpd: removed-in-pandas-3
        df["a"].mad(),  # xpd: removed-in-pandas-3
        df.as_matrix(),  # xpd: removed-in-pandas-3
        df.ix[0],  # xpd: removed-in-pandas-3
        pd.np.nan,  # xpd: removed-in-pandas-3
        pd.datetime(2024, 1, 1),  # xpd: removed-in-pandas-3
        pd.Int64Index([1, 2]),  # xpd: removed-in-pandas-3
        pd.io.json.json_normalize([{"a": 1}]),  # xpd: removed-in-pandas-3
        pd.to_numeric(df["a"], errors="ignore"),  # xpd: removed-in-pandas-3
        list(df.iteritems()),  # xpd: removed-in-pandas-3
        df.set_index(["k", "a"]).index.is_lexsorted(),  # xpd: removed-in-pandas-3
        df[["a", "b"]].groupby(level=0, axis=1).sum(),  # xpd: removed-in-pandas-3
    )


@case
def current_names(df):
    pd.set_option("display.max_rows", 100)
    return df["k"].value_counts(), df.index.is_monotonic_increasing, df.to_numpy(), pd.json_normalize([{"a": 1}]), pd.to_numeric(df["a"], errors="coerce"), list(df.items())
