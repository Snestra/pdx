"""Python work per row or per value, and code that looks similar but stays.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `xpd check --fix` can be compared with this file.
"""

import math
from collections import Counter

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
    return df["raw"].apply(pd.to_datetime)  # xpd: apply-known-function


@case
def apply_missing_check(df):
    return df["b"].apply(pd.isna), df["b"].map(pd.notna)  # xpd: apply-known-function


@case
def apply_len(df):
    return df["s"].apply(len)  # xpd: apply-known-function


@case
def apply_round(df):
    return df["b"].apply(lambda v: round(v, 2))  # xpd: apply-known-function


@case
def apply_that_stays(df):
    return df[["a", "b"]].apply(len), df["b"].apply(lambda v: round(v, 2) + 1)


@case
def literal_contains(df):
    return (
        df["s"].str.contains("ta_"),  # xpd: literal-contains
        df["s"].str.contains("alpha", case=False),  # xpd: literal-contains
    )


@case
def regex_contains(df):
    return df["s"].str.contains("^Al"), df["s"].str.contains("a.p", case=False), df["s"].str.contains("ta_", regex=False)


@case
def copy_after_indexing(df):
    part = df[df["a"] > 50].copy()  # xpd: copy-after-indexing
    part["a"] = 0
    cols = df.loc[:, ["a", "b"]].copy()  # xpd: copy-after-indexing
    cols["a"] = 1
    pair = df[["a", "w"]].copy()  # xpd: copy-after-indexing
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


@case
def row_loops(df):
    small = df.head(50)
    total = 0.0
    for _, row in small.iterrows():  # xpd: row-loop
        total += row["a"] * row["w"]
    for row in small.itertuples():  # xpd: row-loop
        total += row.a
    names = [r["k"] for r in small.to_dict("records")]  # xpd: row-loop
    for i in range(len(small)):  # xpd: row-loop
        total += small.iloc[i]["a"]
    return round(total, 6), names


@case
def loops_that_stay(df):
    items = list(range(5))
    total = 0
    for i in range(len(items)):
        total += items[i]
    records = df[["a", "k"]].head(2).to_dict("records")
    for name in df.columns:
        total += len(name)
    # Rows that become Python objects: a function receives the row values.
    small = df.head(5)
    pairs = [divmod(row["a"], 3) for row in small.to_dict("records")]
    labels = []
    for row in small.itertuples():
        labels.append("{}:{}".format(row.k, row.a))
    # A frame built inside a loop from other objects, which copies each row once.
    halves = []
    for start in (0, 2):
        halves.append(pd.concat([small.iloc[start : start + 1], small.iloc[start + 1 : start + 2]]))
    return total, records, pairs, labels, len(halves)


@case
def concat_in_loop(df):
    out = df.head(0)
    for start in (0, 2):
        out = pd.concat([out, df.iloc[start : start + 2]])  # xpd: concat-in-loop
    return out


@case
def apply_axis_1(df):
    return df.apply(lambda r: r["a"] + r["b"], axis=1)  # xpd: apply-axis-1


@case
def apply_per_column(df):
    return df[["a", "b"]].apply(lambda c: c.max() - c.min()), df["a"] + df["b"]


@case
def apply_text_method(df):
    return (
        df["s"].apply(lambda v: v.strip()),  # xpd: apply-text-method
        df["s"].map(lambda v: v.startswith("A")),  # xpd: apply-text-method
        df["s"].map(lambda v: v.replace("_", " ")),  # xpd: apply-text-method
    )


@case
def text_method_that_stays(df):
    return df["s"].map(lambda v: v.split("_")), df["s"].map(lambda v: v.replace(v[0], "")), df["s"].str.strip()


@case
def apply_date_part(df):
    return df["d"].apply(lambda t: t.year), (df["d"] - pd.Timestamp("2022-01-01")).map(lambda t: t.days)  # xpd: apply-date-part


@case
def date_part_that_stays(df):
    return df["d"].dt.year, df["d"].dt.year * 100 + df["d"].dt.month


@case
def apply_condition(df):
    return (
        df["a"].apply(lambda v: 1 if v > 50 else 0),  # xpd: apply-condition
        df["b"].apply(lambda v: min(v, 1.0)),  # xpd: apply-condition
    )


@case
def condition_on_whole_column(df):
    return pd.Series(np.where(df["a"] > 50, 1, 0)), df["b"].clip(upper=1.0), df["s"].apply(str.title)


@case
def apply_arithmetic(df):
    return df["b"].apply(lambda v: v * 2 + 1), df["a"].map(lambda v: -v // 3)  # xpd: apply-arithmetic


@case
def arithmetic_that_stays(df):
    scale = 3
    return df["b"].apply(lambda v: v * scale), df["b"] * 2 + 1


@case
def builtin_on_column(df):
    return sum(df["a"]), max(df["w"]), len(set(df["k"]))  # xpd: builtin-on-column


@case
def builtin_on_python_values(df):
    values = [1, 2, 3]
    return sum(values), max(df["w"].tolist()), df["a"].sum()


@case
def list_over_column(df):
    return [v.upper() for v in df["s"]]  # xpd: list-over-column


@case
def list_over_python_values(df):
    return [c.upper() for c in df.columns], df["s"].str.upper().tolist()


@case
def frame_growth_in_loop(df):
    out = pd.DataFrame(columns=["a", "b"])
    for a, b in zip(df["a"].head(30), df["b"].head(30)):
        out.loc[len(out)] = [a, b]  # xpd: frame-growth-in-loop
    return out


@case
def frame_built_once(df):
    rows = [[a, b] for a, b in zip(df["a"].head(30), df["b"].head(30))]
    out = pd.DataFrame(rows, columns=["a", "b"])
    out.loc[len(out)] = [0, 0.0]
    return out


@case
def len_of_filter(df):
    return len(df[df["a"] > 50]), len(df[(df["a"] > 50) & (df["b"] < 0)])  # xpd: len-of-filter


@case
def len_that_stays(df):
    return len(df[["a", "b"]]), int((df["a"] > 50).sum())


@case
def sort_then_head(df):
    return (
        df.sort_values("b").head(5),  # xpd: sort-then-head
        df.sort_values("b", ascending=False).head(5),  # xpd: sort-then-head
        df.sort_values("w").iloc[0],  # xpd: sort-then-head
    )


@case
def sort_that_stays(df):
    return df.sort_values(["k", "b"]).head(5), df.nsmallest(5, "b"), df.sort_values("b").iloc[5], df["b"].sort_values().iloc[5]


@case
def replace_with_mapping(df):
    mapping = {"g1": "one", "g2": "two"}
    return df["k"].replace(mapping)  # xpd: replace-with-mapping


@case
def replace_with_literals(df):
    return df["k"].replace({"g1": "one"}), df["s"].str.replace("_", " "), df["k"].map({"g1": "one"}).fillna(df["k"])


@case
def apply_math_function(df):
    return (
        df["w"].map(np.sqrt),  # xpd: apply-math-function
        df["w"].apply(lambda v: np.log(v)),  # xpd: apply-math-function
        df["w"].apply(math.sqrt),  # xpd: apply-math-function
        df["w"].map(lambda v: math.log(v)),  # xpd: apply-math-function
        df["b"].apply(abs),  # xpd: apply-math-function
        df["b"].map(lambda v: abs(v)),  # xpd: apply-math-function
    )


@case
def math_that_stays(df):
    return df["w"].apply(np.sqrt), np.log(df["w"]), df[["b", "w"]].apply(abs), df["w"].apply(lambda v: np.log(v) + 1)


@case
def apply_cast(df):
    return (
        df["w"].apply(int),  # xpd: apply-cast
        df["a"].map(float),  # xpd: apply-cast
        df["w"].apply(lambda v: int(v)),  # xpd: apply-cast
    )


@case
def cast_that_stays(df):
    return df["b"].apply(str), df["w"].astype(int), df["a"].map(lambda v: int(v) + 1)


@case
def apply_comparison(df):
    wanted = {1, 5, 9}
    return (
        df["a"].apply(lambda v: v > 50),  # xpd: apply-comparison
        df["k"].map(lambda v: v == "g2"),  # xpd: apply-comparison
        df["b"].apply(lambda v: v != 0).sum(),  # xpd: apply-comparison
        df["a"].apply(lambda v: v in wanted),  # xpd: apply-comparison
        df["a"].map(lambda v: v not in wanted).sum(),  # xpd: apply-comparison
    )


@case
def comparison_that_stays(df):
    return (
        df["a"] > 50,
        df["a"].apply(lambda v: 10 < v < 50),
        df["a"].apply(lambda v: v > len(str(v))),
        df["s"].apply(lambda v: "ta" in v),
        df["k"].apply(lambda v: v in "g1g2"),
    )


@case
def apply_pd_series(df):
    pairs = df.assign(pair=[[a, w] for a, w in zip(df["a"].tolist(), df["w"].tolist())])  # xpd: zip-over-columns
    return (
        pairs["pair"].apply(pd.Series),  # xpd: apply-pd-series
        pairs["pair"].apply(lambda v: pd.Series(v)),  # xpd: apply-pd-series
    )


@case
def pd_series_that_stays(df):
    return df[["a", "w"]].apply(pd.Series.sum), pd.DataFrame(df[["a", "w"]].to_numpy().tolist(), index=df.index)


def bigger(b, w):
    if b > w:
        return b * 2
    return w


@case
def np_vectorize(df):
    return (
        np.vectorize(bigger)(df["a"], df["w"]),  # xpd: np-vectorize
        np.frompyfunc(bigger, 2, 1)(df["a"], df["w"]),  # xpd: np-vectorize
        np.apply_along_axis(lambda row: row[0] * row[1], 1, df[["a", "w"]].to_numpy()),  # xpd: np-vectorize
    )


@case
def np_where_instead(df):
    return np.where(df["a"] > df["w"], df["a"] * 2, df["w"])


@case
def index_loop(df):
    out = []
    for label in df.index:  # xpd: index-loop
        out.append(df.loc[label, "a"] * df.at[label, "w"])
    return out, [df.loc[label, "a"] * 2 for label in df.index]  # xpd: index-loop


@case
def index_loop_that_stays(df):
    other = df.head(3)
    labels = [str(label) for label in df.index]
    return labels[:3], [df.loc[label, "a"] for label in other.index]


@case
def zip_over_columns(df):
    out = []
    for a, w in zip(df["a"].values, df["w"].to_numpy()):  # xpd: zip-over-columns
        out.append(a * w)
    return out, [a * w for a, w in zip(df["a"], df["w"])]  # xpd: zip-over-columns


@case
def zip_that_stays(df):
    names = ["x", "y"]
    return dict(zip(df["k"], df["a"])), [n * 2 for n, c in zip(names, df.columns)], [a for a, n in zip(df["a"], names)]


@case
def sorted_column_read_at_one_end(df):
    return (
        df["a"].sort_values().iloc[0],  # xpd: sort-then-head
        df["a"].sort_values().values[0],  # xpd: sort-then-head
        df["a"].sort_values(ascending=False).iloc[0],  # xpd: sort-then-head
        df["a"].sort_values().index[0],  # xpd: sort-then-head
        df["b"].sort_values().iloc[-1],  # xpd: sort-then-head
        df.sort_values("w").iloc[-1],  # xpd: sort-then-head
        df.sort_values("w").tail(5),  # xpd: sort-then-head
        sorted(df["a"])[0],  # xpd: sort-then-head
    )


@case
def reductions_instead_of_a_sort(df):
    return df["a"].min(), df["a"].max(), df["a"].idxmin(), df.nlargest(5, "w"), sorted(["b", "a"])[0]


def lookup_table():
    return pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]}, index=["g1", "g2", "g3", "g4", "g5"])


@case
def lookup_per_row(df):
    table = lookup_table()
    flat = table.reset_index(names="k")
    return (
        df["k"].apply(lambda key: table.loc[key, "v"]),  # xpd: lookup-per-row
        df["k"].map(lambda key: table.at[key, "v"]),  # xpd: lookup-per-row
        df["k"].head(50).apply(lambda key: flat[flat["k"] == key]["v"].iloc[0]),  # xpd: lookup-per-row
        df["k"].head(50).map(lambda key: flat.loc[flat["k"] == key, "v"].values[0]),  # xpd: lookup-per-row
    )


@case
def lookup_on_whole_column(df):
    table = lookup_table()
    codes = {"g1": 1, "g2": 2}
    return df["k"].map(table["v"]), df["k"].apply(lambda key: codes.get(key, 0))


@case
def apply_recomputes_aggregate(df):
    part = df.head(200)
    return (
        part["b"].apply(lambda v: v - part["b"].mean()),  # xpd: apply-recomputes-aggregate
        part["w"].map(lambda v: (v - part["w"].min()) / (part["w"].max() - part["w"].min())),  # xpd: apply-recomputes-aggregate
    )


@case
def aggregate_computed_once(df):
    mean = df["b"].mean()
    return df["b"] - mean, df["b"].apply(lambda v: v - mean), df["s"].apply(lambda v: v.count("a"))


@case
def agg_axis_1(df):
    return (
        df[["k", "s"]].agg("_".join, axis=1),  # xpd: apply-axis-1
        df[["a", "w"]].agg(lambda row: row["a"] + row["w"], axis=1),  # xpd: apply-axis-1
        df[["a", "w"]].head(100).transform(lambda row: row / row.sum(), axis="columns"),  # xpd: apply-axis-1
    )


@case
def agg_on_whole_columns(df):
    return df["k"] + "_" + df["s"], df[["a", "w"]].agg("sum", axis=1), df[["a", "w"]].agg(lambda column: column.max() - column.min())


@case
def enumerate_map_encoding(df):
    return (
        df["k"].map({v: i for i, v in enumerate(df["k"].unique())}),  # xpd: enumerate-map-encoding
        df["k"].replace({v: i for i, v in enumerate(df["k"].unique())}),  # xpd: enumerate-map-encoding
        df["k"].map({v: i for i, v in enumerate(sorted(df["k"].unique()))}),  # xpd: enumerate-map-encoding
        df["k"].map(dict(zip(df["k"].unique(), range(df["k"].nunique())))),  # xpd: enumerate-map-encoding
    )


@case
def encoding_that_stays(df):
    sizes = {"g1": 0, "g2": 1, "g3": 2, "g4": 3, "g5": 4}
    return pd.factorize(df["k"])[0], df["k"].map(sizes), df["k"].map({"g1": 0, "g2": 1})


@case
def builtins_that_hash_or_walk_a_column(df):
    return (
        sum(df["a"] > 50),  # xpd: builtin-on-column
        set(df["k"]),  # xpd: builtin-on-column
        Counter(df["k"]),  # xpd: builtin-on-column
        list(df["a"]),  # xpd: builtin-on-column
        np.array(df["a"].tolist()),  # xpd: builtin-on-column
    )


@case
def column_methods_instead_of_builtins(df):
    names = {"k": ["x", "y"]}["k"]
    return (df["a"] > 50).sum(), set(df["k"].unique()), df["k"].value_counts(), df["a"].tolist(), df["a"].to_numpy(), len(names), sum([1, 2])


@case
def loop_that_appends(df):
    out = []
    for value in df["a"]:  # xpd: list-over-column
        out.append(value * 2)
    for label, value in df["a"].items():  # xpd: list-over-column
        out.append(value + label)
    return out


@case
def loop_that_only_reads(df):
    total = 0
    for value in df["a"]:
        total += value
    return total, (df["a"] * 2).tolist()


@case
def copy_in_chain(df):
    return (
        df.copy().rename(columns={"a": "x"}),  # xpd: copy-in-chain
        df.rename(columns={"a": "x"}).copy(),  # xpd: copy-in-chain
        df.copy(deep=True).assign(z=1),  # xpd: copy-in-chain
        df.reset_index(drop=True).copy(),  # xpd: copy-in-chain
        df.astype({"a": "float64"}).copy(),  # xpd: copy-in-chain
        df.copy().drop(columns=["s"]),  # xpd: copy-in-chain
        df.drop(columns=["s"]).copy(),  # xpd: copy-in-chain
        pd.concat([df, df]).copy(),  # xpd: copy-in-chain
    )


@case
def copy_that_does_work(df):
    return df.copy(), df.sort_values("b").copy(), df.copy().pipe(lambda d: d), df.drop(index=[0, 1]).copy(), df.rename(columns={"a": "x"})
