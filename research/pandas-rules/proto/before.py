"""One function per prototype rule. Each holds the form the rule reports."""
import numpy as np
import pandas as pd

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame(n=2000, seed=0):
    r = np.random.default_rng(seed)
    return pd.DataFrame({
        "a": r.integers(0, 100, n),
        "b": r.normal(size=n).round(4),
        "w": r.random(n) + 0.1,
        "k": r.choice(["g1", "g2", "g3", "g4", "g5"], n),
        "s": r.choice(["Alpha_one", " beta_two", "Gamma_three ", "delta_four"], n),
        "d": pd.Timestamp("2022-01-01") + pd.to_timedelta(r.integers(0, 400 * 86400, n), unit="s"),
    })


@case
def lambda_column_assign(df):
    return df.assign(c=lambda d: d["a"] * d["w"] + 1, u=lambda d: d["s"].str.strip().str.upper())


@case
def lambda_column_loc(df):
    return df.loc[lambda d: (d["a"] > 50) & (d["b"] < 0)]


@case
def lambda_column_left_alone(df):
    lookup = {"x": 2}
    return df.assign(n=lambda d: len(d), m=lambda d: np.where(d["a"] > 5, 1, 0), z=lambda d: d["a"] * lookup["x"], y=lambda d: d.a + 1)


@case
def sort_then_reset_index(df):
    return df.sort_values("b").reset_index(drop=True)


@case
def dropna_then_reset_index(df):
    return df.mask(df["a"] > 90).dropna().reset_index(drop=True)


@case
def set_index_then_resample(df):
    return df.set_index("d").resample("D")["b"].sum()


@case
def concat_then_category(df):
    x, y = df["k"].iloc[:1000].astype("category"), df["s"].iloc[1000:].astype("category")
    return pd.concat([x, y]).astype("category")


@case
def filter_items(df):
    return df.filter(items=["a", "b"])


@case
def assign_then_select(df):
    return df[["k", "a"]].assign(c=lambda d: d["a"] * 2)


@case
def apply_text_method(df):
    return df["s"].apply(lambda x: x.strip()), df["s"].map(lambda v: v.startswith("A")), df["s"].map(lambda v: v.replace("_", " "))


@case
def apply_date_part(df):
    return df["d"].apply(lambda x: x.year), (df["d"] - pd.Timestamp("2022-01-01")).map(lambda t: t.days)


@case
def apply_known_function(df):
    return df["d"].astype(str).apply(pd.to_datetime), df["b"].apply(lambda x: round(x, 2))


@case
def builtin_on_column(df):
    return sum(df["a"]), max(df["b"]), min(df["w"])


@case
def groupby_lambda_reduction(df):
    g = df.groupby("k")
    return g["b"].agg(lambda x: x.mean()), g["b"].transform(lambda x: x.sum()), g[["a", "b"]].agg(np.sum), df.pivot_table(index="k", columns="s", values="b", aggfunc=np.mean)


@case
def groupby_lambda_window(df):
    g = df.groupby("k")["b"]
    return g.transform(lambda x: x.cumsum()), g.transform(lambda x: x.shift(1)), g.transform(lambda x: x.rank())


@case
def groupby_lambda_share(df):
    return df.groupby("k")["w"].transform(lambda x: x / x.sum())


@case
def groupby_lambda_filter(df):
    return df.groupby("k").filter(lambda g: len(g) > 400)


@case
def sort_then_head(df):
    return df.sort_values("b").head(5), df.sort_values("b", ascending=False).head(5)


@case
def len_of_filter(df):
    return len(df[df["a"] > 50]), len(df[(df["a"] > 50) & (df["b"] < 0)]), len(df[["a", "b"]])


@case
def rolling_apply(df):
    return df["b"].rolling(20).apply(lambda x: x.mean())


@case
def literal_contains(df):
    return df["s"].str.contains("ta_"), df["s"].str.contains("^Al")


@case
def copy_after_indexing(df):
    part = df[df["a"] > 50].copy()
    part["a"] = 0
    cols = df.loc[:, ["a", "b"]].copy()
    cols["a"] = 1
    return part, cols, df


@case
def value_counts_share(df):
    return df["k"].value_counts() / len(df["k"])


@case
def subtract_shift(df):
    return df["b"] - df["b"].shift(), df["b"] - df["b"].shift(1)


@case
def range_mask(df):
    return df[(df["a"] >= 10) & (df["a"] <= 20)]


@case
def compare_to_missing(df):
    df = df.mask(df["a"] > 90)
    return df[df["b"] == np.nan], df[df["b"] != np.nan]


@case
def in_column(df):
    return 5000 in df["a"], 37 in df["a"]


@case
def object_dtype_check(df):
    return [c for c in df.columns if df[c].dtype == object]


@case
def groupby_then_reset_index(df):
    return df.groupby("k")[["a", "b"]].sum().reset_index()


@case
def deprecated_utcnow(df):
    return pd.Timestamp.utcnow().tz is not None


@case
def reported_only(df):
    out = pd.DataFrame(columns=["x"])
    for i, row in df.head(3).iterrows():
        out.loc[len(out)] = [row["a"]]
    for i in range(len(df.head(3))):
        pass
    for i in range(len(df)):
        if i > 2:
            break
        _ = df.iloc[i]
    mapping = {"g1": "one"}
    total = df.apply(lambda r: r["a"] + r["b"], axis=1)
    band = np.where(df["a"] < 20, "low", np.where(df["a"] < 70, "mid", "high"))
    days = df["d"].dt.date
    monthly = df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum()
    merged = df.merge(df[["k"]].drop_duplicates())
    text = df.head(2).to_csv()
    firsts = df.groupby("k").first()
    spread = df["b"].rolling(5).apply(lambda x: x.max() - x.min())
    named = df["k"].replace(mapping)
    q = df.query("a > 50")
    bad = df[df["a"] > 1 & df["a"]]
    epoch = df["d"].astype("int64") // 10**9
    return len(out)
