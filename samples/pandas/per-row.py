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


@case
def row_loops(df):
    small = df.head(50)
    total = 0.0
    for _, row in small.iterrows():  # pdx: row-loop
        total += row["a"] * row["w"]
    for row in small.itertuples():  # pdx: row-loop
        total += row.a
    names = [r["k"] for r in small.to_dict("records")]  # pdx: row-loop
    for i in range(len(small)):  # pdx: row-loop
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
    return total, records


@case
def apply_axis_1(df):
    return df.apply(lambda r: r["a"] + r["b"], axis=1)  # pdx: apply-axis-1


@case
def apply_per_column(df):
    return df[["a", "b"]].apply(lambda c: c.max() - c.min()), df["a"] + df["b"]


@case
def apply_text_method(df):
    return (
        df["s"].apply(lambda v: v.strip()),  # pdx: apply-text-method
        df["s"].map(lambda v: v.startswith("A")),  # pdx: apply-text-method
        df["s"].map(lambda v: v.replace("_", " ")),  # pdx: apply-text-method
    )


@case
def text_method_that_stays(df):
    return df["s"].map(lambda v: v.split("_")), df["s"].map(lambda v: v.replace(v[0], "")), df["s"].str.strip()


@case
def apply_date_part(df):
    return df["d"].apply(lambda t: t.year), (df["d"] - pd.Timestamp("2022-01-01")).map(lambda t: t.days)  # pdx: apply-date-part


@case
def date_part_that_stays(df):
    return df["d"].dt.year, df["d"].apply(lambda t: t.year * 100 + t.month)


@case
def apply_condition(df):
    return (
        df["a"].apply(lambda v: 1 if v > 50 else 0),  # pdx: apply-condition
        df["b"].apply(lambda v: min(v, 1.0)),  # pdx: apply-condition
    )


@case
def condition_on_whole_column(df):
    return pd.Series(np.where(df["a"] > 50, 1, 0)), df["b"].clip(upper=1.0), df["s"].apply(str.title)


@case
def apply_arithmetic(df):
    return df["b"].apply(lambda v: v * 2 + 1), df["a"].map(lambda v: -v // 3)  # pdx: apply-arithmetic


@case
def arithmetic_that_stays(df):
    scale = 3
    return df["b"].apply(lambda v: v * scale), df["b"] * 2 + 1


@case
def builtin_on_column(df):
    return sum(df["a"]), max(df["w"]), len(set(df["k"]))  # pdx: builtin-on-column


@case
def builtin_on_python_values(df):
    values = [1, 2, 3]
    return sum(values), max(df["w"].tolist()), df["a"].sum()


@case
def list_over_column(df):
    return [v.upper() for v in df["s"]]  # pdx: list-over-column


@case
def list_over_python_values(df):
    return [c.upper() for c in df.columns], df["s"].str.upper().tolist()


@case
def frame_growth_in_loop(df):
    out = pd.DataFrame(columns=["a", "b"])
    for a, b in zip(df["a"].head(30), df["b"].head(30)):
        out.loc[len(out)] = [a, b]  # pdx: frame-growth-in-loop
    return out


@case
def frame_built_once(df):
    rows = [[a, b] for a, b in zip(df["a"].head(30), df["b"].head(30))]
    out = pd.DataFrame(rows, columns=["a", "b"])
    out.loc[len(out)] = [0, 0.0]
    return out


@case
def len_of_filter(df):
    return len(df[df["a"] > 50]), len(df[(df["a"] > 50) & (df["b"] < 0)])  # pdx: len-of-filter


@case
def len_that_stays(df):
    return len(df[["a", "b"]]), int((df["a"] > 50).sum())


@case
def sort_then_head(df):
    return (
        df.sort_values("b").head(5),  # pdx: sort-then-head
        df.sort_values("b", ascending=False).head(5),  # pdx: sort-then-head
        df.sort_values("w").iloc[0],  # pdx: sort-then-head
    )


@case
def sort_that_stays(df):
    return df.sort_values(["k", "b"]).head(5), df.nsmallest(5, "b"), df.sort_values("b").tail(5)


@case
def replace_with_mapping(df):
    mapping = {"g1": "one", "g2": "two"}
    return df["k"].replace(mapping)  # pdx: replace-with-mapping


@case
def replace_with_literals(df):
    return df["k"].replace({"g1": "one"}), df["s"].str.replace("_", " "), df["k"].map({"g1": "one"}).fillna(df["k"])
