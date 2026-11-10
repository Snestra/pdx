"""Builds the rule proposal page from the measurement files in runs2/ (or runs/ when a case is missing there)."""
import html
import json
import math
import os

ROOT = os.path.dirname(os.path.abspath(__file__))


def load(*paths):
    out = {}
    for p in paths:
        p = os.path.join(ROOT, p)
        if not os.path.exists(p):
            continue
        for line in open(p):
            r = json.loads(line)
            if "id" in r and "speedup" in r and r["id"] not in out:
                out[r["id"]] = r
    return out


V31 = load("runs2/bench-3.1.1.jsonl", "runs2/bench2-3.1.1.jsonl", "runs2/bench3-3.1.1.jsonl", "runs2/bench5-3.1.1.jsonl",
           "runs/bench-3.1.1.jsonl", "runs/bench3-3.1.1.jsonl", "runs/bench2-3.1.1.jsonl")
V30 = load("runs/bench-3.0.6.jsonl", "runs/bench2-3.0.6.jsonl", "runs/bench3-3.0.6.jsonl")
NOPA = load("runs/bench2-nopyarrow-3.1.1.jsonl", "runs/bench-nopyarrow-3.1.1.jsonl")


def csv_times(version):
    p = os.path.join(ROOT, f"runs2/bench4-{version}.jsonl")
    return {r["id"]: r["ms"] for r in map(json.loads, open(p)) if "ms" in r}


CSV31, CSV30 = csv_times("3.1.1"), csv_times("3.0.6")
# Times for the forms that translate values through a mapping, from skill-review/replace.py.
REPL = {(r["kind"], r["keys"], r["form"]): r["ms"]
        for r in map(json.loads, open(os.path.join(ROOT, "skill-review/replace-3.1.1.jsonl"))) if "form" in r}


def x(case, src=V31):
    return src[case]["speedup"]


def times(v):
    if v >= 10:
        return f"{round(v):,} times"
    return f"{v:.1f} times"


def ms(v):
    if v >= 1000:
        return f"{v / 1000:.1f} s"
    if v >= 100:
        return f"{v:.0f} ms"
    if v >= 10:
        return f"{v:.1f} ms"
    return f"{v:.2f} ms"


def span(case, src=V31):
    r = src[case]
    return f"{ms(r['before_ms'])} to {ms(r['after_ms'])}"


def gain(case, src=V31):
    """'63 times faster (18.4 ms to 0.29 ms)'"""
    return f"{times(x(case, src))} faster ({span(case, src)})"


# Rule ids that have a working ast-grep 0.51.1 prototype in proto/rules.yml. proto/check.sh runs them.
PROTO = {
    "inplace-result-assigned", "epoch-from-int-cast", "compare-to-missing", "in-column", "mask-precedence",
    "write-through-values", "object-dtype-check", "removed-in-pandas-3", "deprecated-in-pandas-3", "lambda-column",
    "sort-then-reset-index", "set-index-then-resample", "groupby-then-reset-index", "concat-then-category",
    "filter-items", "assign-then-select", "query-string", "nested-np-where", "row-loop", "apply-axis-1",
    "apply-text-method", "apply-date-part", "apply-known-function", "builtin-on-column", "groupby-lambda",
    "sort-then-head", "len-of-filter", "rolling-apply", "object-dates", "text-time-key", "literal-contains",
    "copy-after-indexing", "frame-growth-in-loop", "replace-with-mapping", "merge-without-on", "to-csv-index",
    "groupby-first-skips-missing", "value-counts-share", "subtract-shift", "range-mask", "groupby-apply-reads-key",
    "groupby-lambda-window", "groupby-lambda-arithmetic", "groupby-filter-lambda", "aggregate-then-merge-back",
}

R = []


def rule(group, id, fix, before, after, ev, state="new", since="3.0"):
    R.append(dict(group=group, id=id, fix=fix, before=before, after=after, ev=ev, state=state, since=since))


G1 = "Code that is wrong or broken on pandas 3"
G2 = "Shorter forms, including the pandas 3.0 and 3.1 API"
G3 = "Python work per row or per value"
G4 = "groupby, agg and transform"
G5 = "Time series"
G6 = "Stated intent"
G7 = "Reading files"

# ------------------------------------------------------------------ group 1
rule(G1, "chained-assignment", "unsafe", ['df[df["a"] > 1]["b"] = 0'], ['df.loc[df["a"] > 1, "b"] = 0'],
     'The rule exists, but its fix is wrong for the mask shape. pdx 0.1.0 rewrites the line above to '
     '<code>df.loc["b", df["a"] > 1] = 0</code>, with row and column swapped. The fix needs one form per shape.',
     state="exists, fix needs repair")
rule(G1, "inplace-on-column", "unsafe", ['df["b"].fillna(0, inplace=True)'], ['df["b"] = df["b"].fillna(0)'],
     "The column stays unchanged on pandas 3.1.1, and pandas only warns. Today no-inplace reports the line as a "
     "warning about style, so the proposal is to report it as an error.", state="exists as no-inplace")
rule(G1, "inplace-result-assigned", "unsafe", ["df = df.dropna(inplace=True)"], ["df = df.dropna()"],
     "The name df is None after the line runs.")
rule(G1, "epoch-from-int-cast", "none", ['df["d"].astype("int64") // 10**9'],
     ['(df["d"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")'],
     "Datetimes default to microseconds in pandas 3. The old form returned 1704067 for 2024-01-01, and the "
     "correct value is 1704067200.")
rule(G1, "compare-to-missing", "unsafe", ['df[df["b"] == np.nan]', 'df["k"].astype(str) == "nan"'],
     ['df[df["b"].isna()]', 'df["k"].isna()'],
     "Both comparisons were False for every row. astype(str) keeps missing values missing in pandas 3, so the "
     'text "nan" never appears.')
rule(G1, "in-column", "unsafe", ['if 2 in df["a"]:'], ['if (df["a"] == 2).any():'],
     "The in operator checks index labels. It returned False for a value that was in the column.")
rule(G1, "mask-precedence", "none", ['df[df["a"] > 1 & df["b"] < 3]'], ['df[(df["a"] > 1) & (df["b"] < 3)]'],
     'The first form raised TypeError here. A shorter one, <code>df["a"] == 1 &amp; df["flag"]</code>, runs and '
     "returns a different mask.")
rule(G1, "write-through-values", "none", ['df["a"].values[0] = 9'], ['df.loc[df.index[0], "a"] = 9'],
     "The write raised ValueError, because arrays taken from a frame are read-only under copy-on-write.")
rule(G1, "object-dtype-check", "unsafe", ['if df["k"].dtype == object:', 'df.select_dtypes(include="object")'],
     ['if pd.api.types.is_string_dtype(df["k"]):', 'df.select_dtypes(include="str")'],
     "Text columns have dtype str in pandas 3, so the comparison was False. select_dtypes still works and "
     "warns that the behavior will go away.")
rule(G1, "groupby-apply-reads-key", "none", ['df.groupby("k").apply(lambda g: g["k"].iloc[0])'],
     ['df.groupby("k").apply(lambda g: g.name)'],
     "groupby.apply no longer passes the grouping column to the function. The lookup raised KeyError.")
rule(G1, "removed-in-pandas-3", "safe",
     ["df.applymap(f)", 'df["a"].fillna(method="ffill")', 'df.resample("M", on="d")', 'df["d"].dt.floor("H")',
      "pd.read_csv(path, delim_whitespace=True)"],
     ["df.map(f)", 'df["a"].ffill()', 'df.resample("ME", on="d")', 'df["d"].dt.floor("h")',
      'pd.read_csv(path, sep=r"\\s+")'],
     "Each old form raised on 3.0.6 and 3.1.1, and each rewritten form ran. One rule id holds many small "
     'patterns, as no-inplace does today. The "M" pattern leaves to_period("M") and asfreq("M") alone, because '
     'periods still use "M". For the same reason the frequency fix is unsafe inside resample.')
rule(G1, "deprecated-in-pandas-3", "safe",
     ['pd.set_option("mode.copy_on_write", True)', "df.astype(types, copy=False)", "pd.Timestamp.utcnow()"],
     ["", "df.astype(types)", 'pd.Timestamp.now("UTC")'],
     "Each old form raised Pandas4Warning. pandas 3.1 adds two more warnings. The inplace keyword now warns on "
     "11 methods, which no-inplace already reports, and .values warns on a column with a time zone.")

# ------------------------------------------------------------------ group 2
rule(G2, "lambda-column", "safe", ['df.assign(c=lambda d: d["a"] * d["w"] + 1)', 'df.loc[lambda d: d["a"] > 50]'],
     ['df.assign(c=pd.col("a") * pd.col("w") + 1)', 'df.loc[pd.col("a") > 50]'],
     "The speed is the same, so the gain is shorter code. The prototype rewrites a lambda only when every use "
     'of its parameter is d["name"], and it left len(d), np.where(...) and d.a alone.')
rule(G2, "query-string", "none", ['df.query("a > 50 and b < 0")'], ['df.filter(cond=(pd.col("a") > 50) & (pd.col("b") < 0))'],
     f"The expression form was {times(x('query-numexpr-vs-col-expr-1M'))} faster on 1,000,000 rows and "
     f"{times(x('query-numexpr-vs-col-expr-10M'))} faster on 10,000,000 rows, with numexpr installed. Editors and "
     "pdx can also read column names in an expression, and they cannot read them in a string.", since="3.1")
rule(G2, "assign-then-select", "unsafe", ['df[["k", "a"]].assign(c=pd.col("a") * 2)'], ['df.select("k", "a", c=pd.col("a") * 2)'],
     "The speed is the same. The fix is unsafe because select returns a name twice when a computed column "
     "reuses a selected name.", since="3.1")
rule(G2, "filter-items", "unsafe", ["df.filter(items=cols)"], ["df.select(cols)"],
     "The 3.1 documentation says items=, like= and regex= will be deprecated. The fix is unsafe because "
     "select raises on a label that is absent, and filter skipped it.", since="3.1")
rule(G2, "concat-then-category", "unsafe", ['pd.concat(parts).astype("category")'], ["pd.concat(parts, union_categories=True)"],
     f"The new keyword was {gain('31-concat-cat-astype-vs-union')} when the parts were already categorical. "
     "The category order differs, so the fix is unsafe.", since="3.1")
rule(G2, "nested-np-where", "none", ['np.where(a < 20, "low", np.where(a < 70, "mid", "high"))'],
     ['pd.Series("high", index=a.index).case_when([(a < 20, "low"), (a < 70, "mid")])'],
     f"case_when was {times(x('nested-np-where-vs-case-when'))} faster for text results. For numeric bins, pd.cut "
     f"was {times(x('nested-np-where-vs-cut'))} faster.")
rule(G2, "sort-then-reset-index", "safe", ['df.sort_values("b").reset_index(drop=True)'], ['df.sort_values("b", ignore_index=True)'],
     "The speed is the same. The rule also covers dropna, drop_duplicates, explode, sort_index and sample.")
rule(G2, "set-index-then-resample", "safe", ['df.set_index("d").resample("D")'], ['df.resample("D", on="d")'],
     "The speed and the result are the same.")
rule(G2, "groupby-then-reset-index", "unsafe", ['df.groupby("k")[["a", "b"]].sum().reset_index()'],
     ['df.groupby("k", as_index=False)[["a", "b"]].sum()'], "The speed is the same, and the prototype gave an equal frame.")
rule(G2, "rename-after-agg", "none", ['g.agg({"b": "mean", "w": "sum"}).rename(columns={"b": "b_mean", "w": "w_total"})'],
     ['g.agg(b_mean=("b", "mean"), w_total=("w", "sum"))'], "The speed is the same, and the result was equal.")
rule(G2, "merge-indicator-anti-join", "none", ['m = a.merge(b, on="k", how="left", indicator=True)', 'm[m["_merge"] == "left_only"]'],
     ['a.merge(b, on="k", how="left_anti")'], 'how="left_anti" and how="right_anti" are new in pandas 3.0.')
rule(G2, "subtract-shift", "safe", ['df["b"] - df["b"].shift()'], ['df["b"].diff()'], f"diff was {gain('sub-shift-vs-diff')}.")
rule(G2, "range-mask", "safe", ['(df["a"] >= 10) & (df["a"] <= 20)'], ['df["a"].between(10, 20)'], "The speed is the same.")
rule(G2, "value-counts-share", "unsafe", ['df["k"].value_counts() / len(df["k"])'], ['df["k"].value_counts(normalize=True)'],
     "The speed is the same. The result name changes from count to proportion, and missing values are left out "
     "of the total.")

# ------------------------------------------------------------------ group 3
rule(G3, "row-loop", "none", ["for i, row in df.iterrows():", "for i in range(len(df)): df.iloc[i]"], ['df["a"] * df["w"]'],
     f"On 100,000 rows the column form was {times(x('iterrows-sum'))} faster than iterrows and "
     f"{times(x('itertuples-sum'))} faster than itertuples. On 20,000 rows it was {times(x('range-len-iloc'))} "
     "faster than range(len(df)) with iloc. The rule widens no-iterrows to all three loops and to a loop over "
     'to_dict("records").', state="widens no-iterrows")
rule(G3, "apply-axis-1", "none", ['df.apply(lambda r: r["a"] + r["b"], axis=1)'], ['df["a"] + df["b"]'],
     f"The column form was {gain('apply-axis-1')} on 100,000 rows.")
rule(G3, "apply-text-method", "unsafe", ['df["s"].map(lambda v: v.startswith("A"))'], ['df["s"].str.startswith("A")'],
     f"The .str form was {times(x('map-lambda-startswith'))} faster for startswith, {times(x('map-lambda-strip'))} for "
     f"strip, {times(x('map-lambda-str-method'))} for lower and {times(x('map-lambda-replace'))} for replace. The rule "
     "names a fixed list of methods. It leaves split alone, because the lambda was faster there. Without pyarrow "
     f"installed the gain fell to {times(x('map-lambda-startswith', NOPA))} for startswith, and strip and replace "
     "gained nothing.")
rule(G3, "apply-date-part", "unsafe", ['df["d"].apply(lambda t: t.year)'], ['df["d"].dt.year'],
     f"The .dt form was {gain('apply-lambda-dt-attr')}. The fix is unsafe because the result is int32, not int64.")
rule(G3, "apply-known-function", "safe", ['df["raw"].apply(pd.to_datetime)', 'df["b"].apply(lambda v: round(v, 2))'],
     ['pd.to_datetime(df["raw"])', 'df["b"].round(2)'],
     f"pd.to_datetime on the whole column was {gain('T-apply-to-datetime-per-element')} on 100,000 rows. round was "
     f"{times(x('apply-round-vs-round'))} faster, pd.isna {times(x('apply-isnull-vs-isna'))} and len "
     f"{times(x('apply-len-vs-str-len'))}. The round fix is unsafe, because Python and numpy round 0.15% of the "
     "test values differently.")
rule(G3, "apply-condition", "none", ['df["a"].apply(lambda v: 1 if v > 50 else 0)', 'df["b"].apply(lambda v: min(v, 1.0))'],
     ['np.where(df["a"] > 50, 1, 0)', 'df["b"].clip(upper=1.0)'],
     f"np.where was {times(x('apply-ifelse-vs-np-where-numeric'))} faster and clip was {times(x('apply-min-vs-clip'))} "
     f"faster. With text results the gain fell to {times(x('apply-ifelse-vs-np-where'))}.")
rule(G3, "apply-arithmetic", "unsafe", ['df["b"].apply(lambda v: v * 2 + 1)'], ['df["b"] * 2 + 1'],
     f"The column form was {gain('apply-arith-lambda')}.")
rule(G3, "builtin-on-column", "unsafe", ['sum(df["a"])', 'len(set(df["k"]))'], ['df["a"].sum()', 'df["k"].nunique()'],
     f"The method was {times(x('builtin-sum-on-column'))} faster for sum, {times(x('builtin-max-on-column'))} for max "
     f"and {times(x('builtin-len-set'))} for the distinct count. The fix is unsafe because the methods skip missing "
     "values.")
rule(G3, "list-over-column", "none", ['[v.upper() for v in df["s"]]'], ['df["s"].str.upper()'],
     f"The .str form was {gain('list-comp-str-vs-str')}.")
rule(G3, "frame-growth-in-loop", "none", ["for row in rows:", "    out.loc[len(out)] = row"], ["out = pd.DataFrame(rows, columns=cols)"],
     f"Building the frame once was {gain('loc-append-in-loop-vs-list')} for 3,000 rows, and the gap grows with the "
     f"row count. The existing concat-in-loop rule covers a gain of {times(x('concat-in-loop-vs-once'))} for 200 parts.")
rule(G3, "len-of-filter", "unsafe", ['len(df[df["a"] > 50])'], ['int((df["a"] > 50).sum())'], f"Summing the mask was {gain('len-filter-vs-mask-sum')}.")
rule(G3, "sort-then-head", "unsafe", ['df.sort_values("b").head(10)', 'df.sort_values("b").iloc[0]'],
     ['df.nsmallest(10, "b")', 'df.loc[df["b"].idxmin()]'],
     f"nsmallest was {gain('sort-head-vs-nsmallest')} and idxmin was {gain('sort-iloc0-vs-idxmin')}. The fix is "
     "unsafe because nsmallest raises on a text column and orders ties differently.")
rule(G3, "replace-with-mapping", "none", ['df["k"].replace(mapping)'], ['df["k"].map(lambda v: mapping.get(v, v))'],
     f"replace takes longer with every key. On text values it took {ms(REPL['text', 3, 'replace(mapping)'])} with 3 keys and "
     f"{ms(REPL['text', 1000, 'replace(mapping)'])} with 1,000 keys, and the map form took "
     f"{ms(REPL['text', 1000, 'map(lambda v: mapping.get(v, v))'])} with 1,000 keys and gave the same values and dtype. The rule "
     "fires on a named mapping and stays silent on a short literal. An earlier version of the page named "
     "map(mapping).fillna(column), which turns integer columns into float64 and undoes a key mapped to None.")
rule(G3, "literal-contains", "safe", ['df["s"].str.contains("ta_")'], ['df["s"].str.contains("ta_", regex=False)'],
     f"regex=False was {gain('str-contains-literal-regex')}. The rule fires only when the pattern has no regex "
     "character.")
rule(G3, "copy-after-indexing", "safe", ['part = df[["a", "b", "w"]].copy()'], ['part = df[["a", "b", "w"]]'],
     f"Dropping the copy was {gain('copy-after-column-select')} for a column selection and "
     f"{times(x('copy-after-filter'))} for a row filter. Copy-on-write already keeps a later write to part away "
     "from df, and the prototype confirmed that df was unchanged.")

# ------------------------------------------------------------------ group 4
rule(G4, "groupby-lambda", "safe", ['g["b"].agg(lambda v: v.mean())', 'g[["a", "b"]].agg(np.sum)', "df.pivot_table(..., aggfunc=np.mean)"],
     ['g["b"].agg("mean")', 'g[["a", "b"]].agg("sum")', 'df.pivot_table(..., aggfunc="mean")'],
     f"The cost of a lambda grows with the number of groups. The named form was {times(x('gb-agg-lambda-vs-name'))} "
     f"faster with 1,000 groups and {times(x('G100k-agg-lambda-vs-name'))} faster with 100,000 groups. A numpy "
     f"function was {times(x('G100k-agg-np-func-vs-name'))} slower than the name with 100,000 groups.")
rule(G4, "groupby-lambda-window", "safe", ['g["b"].transform(lambda v: v.cumsum())', 'g["b"].transform(lambda v: v.shift(1))'],
     ['g["b"].cumsum()', 'g["b"].shift(1)'],
     f"With 100,000 groups the method was {times(x('G100k-transform-cumsum'))} faster for cumsum, "
     f"{times(x('G100k-transform-shift'))} for shift, {times(x('G100k-transform-ffill'))} for ffill and "
     f"{times(x('G100k-transform-rank'))} for rank. With 1,000 groups cumsum was "
     f"{times(x('gb-transform-lambda-cumsum'))} faster and rank gained nothing.")
rule(G4, "groupby-lambda-arithmetic", "unsafe", ['df.groupby("k")["w"].transform(lambda v: v / v.sum())'],
     ['df["w"] / df.groupby("k")["w"].transform("sum")'],
     f"The column form was {times(x('gb-transform-share'))} faster with 1,000 groups and "
     f"{times(x('G100k-transform-share'))} faster with 100,000 groups. The same rule covers the z-score "
     f"({times(x('gb-transform-zscore'))} with 1,000 groups) and filling gaps with the group mean "
     f"({times(x('gb-apply-fillna-mean'))}).")
rule(G4, "groupby-filter-lambda", "unsafe", ['df.groupby("k").filter(lambda g: len(g) > 10)'],
     ['df[df.groupby("k")["k"].transform("size") > 10]'],
     f"The mask form was {times(x('gb-filter-lambda-vs-transform-mask'))} faster with 1,000 groups and "
     f"{times(x('G100k-filter-lambda-vs-mask'))} faster with 100,000 groups.")
rule(G4, "groupby-apply", "none", ['df.groupby("k").apply(lambda g: g.loc[g["b"].idxmax()])',
                                   'df.groupby("k").apply(lambda g: (g["b"] * g["w"]).sum() / g["w"].sum())'],
     ['df.loc[df.groupby("k")["b"].idxmax()]', 't = df.assign(bw=df["b"] * df["w"]).groupby("k")[["bw", "w"]].sum()'],
     f"With 100,000 groups the row lookup was {times(x('G100k-apply-top1-vs-idxmax'))} faster and the weighted mean "
     f"was {times(x('G100k-apply-weighted-mean'))} faster. The latest row per key through idxmax was "
     f"{times(x('sort-gb-tail1-vs-idxmax'))} faster than sort_values, groupby and tail(1). The rule reports every "
     "groupby.apply with a lambda, and the message lists the forms that replace it.")
rule(G4, "aggregate-then-merge-back", "none",
     ['totals = df.groupby("k")["b"].sum().rename("total").reset_index()', 'df = df.merge(totals, on="k", how="left")'],
     ['df = df.assign(total=df.groupby("k")["b"].transform("sum"))'],
     f"transform was {gain('agg-merge-back-vs-transform')} with 1,000 groups, and {times(x('G100k-agg-merge-back-vs-transform'))} "
     f"faster with 100,000 groups. Against <code>df[\"k\"].map(df.groupby(\"k\")[\"b\"].sum())</code> it was "
     f"{times(x('agg-map-back-vs-transform'))} faster. The prototype matches when the merge and the groupby use the same frame "
     "in one expression.")
rule(G4, "groupby-first-skips-missing", "none", ['df.sort_values("d").groupby("k").first()'],
     ['df.sort_values("d").groupby("k").first(skipna=False)'],
     "first() takes the first value that is not missing in each column. In the test, one result row held "
     "values from two different input rows.")

# ------------------------------------------------------------------ group 5
rule(G5, "rolling-apply", "safe", ['df["b"].rolling(20).apply(lambda w: w.mean())', 'df["b"].rolling(20).apply(spread)'],
     ['df["b"].rolling(20).mean()', 'df["b"].rolling(20).apply(spread, raw=True)'],
     f"The window method was {gain('rolling-apply-lambda-vs-builtin')} on 200,000 rows. For a function with no "
     f"window method, raw=True was {times(x('rolling-apply-no-raw-vs-raw'))} faster. The raw=True change is "
     "reported without a fix, because the function then receives an array.")
rule(G5, "text-time-key", "none", ['df.groupby(df["d"].dt.strftime("%Y-%m"))["b"].sum()'],
     ['df.groupby(df["d"].dt.to_period("M"))["b"].sum()'],
     f"The period key was {gain('gb-strftime-month-vs-to-period')}, and {times(x('gb-strftime-month-vs-to-period', V30))} "
     f"faster on pandas 3.0.6. For hours, dt.floor(\"h\") was {times(x('T-gb-strftime-hour-vs-floor-h'))} faster.")
rule(G5, "object-dates", "none", ['df["d"].dt.date'], ['df["d"].dt.normalize()'],
     f"dt.date builds a column of Python objects. normalize was {gain('dt-date-vs-normalize')}, and grouping on "
     f"dt.floor(\"D\") was {times(x('T-gb-dt-date-vs-floor-key'))} faster than grouping on dt.date.")
rule(G5, "apply-on-dates", "unsafe", ['df["d"].apply(lambda t: t + pd.Timedelta(days=7))', 'df["d"].apply(lambda t: t.replace(day=1))'],
     ['df["d"] + pd.Timedelta(days=7)', 'df["d"].dt.to_period("M").dt.start_time'],
     f"On 200,000 rows the offset was {times(x('T-shift-days-apply-vs-offset'))} faster and the month start was "
     f"{times(x('T-month-start-replace-apply-vs-period'))} faster. strftime through .dt was "
     f"{times(x('apply-strftime-vs-dt-strftime'))} faster.")
rule(G5, "index-year-mask", "none", ["df[df.index.year == 2023]"], ['df.loc["2023"]'],
     f"On a sorted DatetimeIndex the label form was {gain('T-year-mask-vs-partial-string-loc')}. A month, "
     f"such as df.loc[\"2023-03\"], was {times(x('T-range-mask-vs-loc-slice'))} faster than two comparisons, and "
     f"between_time was {times(x('T-hour-mask-vs-between-time'))} faster than a mask on index.hour.")

# ------------------------------------------------------------------ group 6
rule(G6, "merge-without-validate", "none", ['a.merge(b, on="k")'], ['a.merge(b, on="k", validate="many_to_one")'],
     "No change is proposed.", state="exists")
rule(G6, "merge-without-on", "none", ["a.merge(b)"], ['a.merge(b, on="k")'],
     "Without on=, merge joins on every column name the two frames share, so a new shared column changes the join.")
rule(G6, "to-csv-index", "none", ["df.to_csv(path)"], ["df.to_csv(path, index=False)"],
     "The default writes the index as a first column with no name, and the next read_csv returns it as a column "
     'called "Unnamed: 0".')

rule(G7, "read-csv-slow-option", "none", ['pd.read_csv(path, engine="python")', "pd.read_csv(path, low_memory=False)"],
     ["pd.read_csv(path)", "pd.read_csv(path, dtype=types)"],
     f"pandas 3.1 reads a large CSV file on several threads, and some options turn that off. A 78 MB file took "
     f"{ms(CSV31['default'])} with the defaults on 3.1.1, {ms(CSV31['low_memory=False'])} with low_memory=False and "
     f"{ms(CSV31['engine=python'])} with engine=\"python\". On 3.0.6 the defaults took {ms(CSV30['default'])}.")

GROUP_NOTE = {
    G1: "Severity is error. Each old form was run on pandas 3.0.6 and 3.1.1 to confirm the failure.",
    G2: "Severity is warning. Most of these rules make code shorter and do not change the speed.",
    G3: "Severity is warning. Times are for 1,000,000 rows on pandas 3.1.1 unless a row count is given.",
    G4: "Severity is warning. A lambda runs once per group, so the gain depends on the number of groups.",
    G5: "Severity is warning. The frequency aliases, the epoch cast and utcnow are in the first group.",
    G6: "Severity is warning. The rules ask for a keyword that states what the code is meant to do.",
    G7: "Severity is warning. The times are for a file of 1,000,000 rows and 78 MB, read from the page cache.",
}

# Advice that was measured and not supported: (advice, measured, decision)
ph = lambda c: f"{ms(V31[c]['before_ms'])} before, {ms(V31[c]['after_ms'])} after"
REJECTED = [
    ("Replace a chain of == joined by | with isin", f"isin was slower for three values. {ph('or-chain-vs-isin')}.", "No rule."),
    ("Pass format= to pd.to_datetime for speed", f"No change. {ph('T-to-datetime-dmy-no-format-vs-format')}.", "No rule."),
    ("Use .str.split(...).str[0] in place of a lambda", f"The .str form was slower. {ph('apply-lambda-str-split')}.", "Left out of apply-text-method."),
    ("Use resample or pd.Grouper in place of a groupby on a date key",
     f"On an unsorted frame resample was slower. {ph('T-gb-normalize-key-vs-resample-unsorted')}. On a sorted frame it was faster. "
     f"{ph('T-gb-normalize-key-vs-resample-sorted')}.", "No rule, because pdx cannot see whether a frame is sorted."),
    ("Use Series.map in place of a merge for a lookup", f"map was slower on 3.1.1. {ph('merge-lookup-vs-map-series')}. The two were equal on 3.0.6.", "No rule."),
    ("Use np.select in place of nested np.where", f"No gain. {ph('nested-np-where-vs-np-select')}.", "nested-np-where names case_when and pd.cut."),
    ("Replace .apply(np.sqrt) with np.sqrt(column)", f"No change. {ph('apply-numpy-func')}.", "No rule."),
    ("Replace len(s.unique()) with s.nunique()", f"No change. {ph('len-unique-vs-nunique')}.", "No rule."),
    ("Use .at in place of .loc for one value", f"A small gain on 20,000 lookups. {ph('loc-scalar-vs-at')}.", "No rule. row-loop reports the loop."),
    ("Rewrite df[df[\"a\"] > 1] to filter(cond=...)", f"No change. {ph('31-mask-vs-filter-cond')}.", "No rule. It would fire in most pandas files."),
    ("Replace s / s.shift() - 1 with pct_change()", f"No gain. {ph('div-shift-vs-pct-change')}.", "No rule."),
    ("Pass engine=\"pyarrow\" to read_csv", f"No gain on 3.1.1. {ms(CSV31['default'])} with the defaults, {ms(CSV31['engine=pyarrow'])} with pyarrow. "
     f"On 3.0.6 the defaults took {ms(CSV30['default'])} and pyarrow took {ms(CSV30['engine=pyarrow'])}.", "No rule, because pdx writes for 3.1."),
    ("Pass usecols= to read_csv for speed", f"Slower on 3.1.1. {ms(CSV31['read all then select 2'])} to read six columns and keep two, "
     f"{ms(CSV31['usecols 2 of 6'])} with usecols. On 3.0.6 usecols was the faster one.", "No rule. usecols still saves memory."),
]

CHART = [
    ("row-loop", "iterrows-sum", "100,000 rows"),
    ("rolling-apply", "rolling-apply-lambda-vs-builtin", "200,000 rows"),
    ("apply-known-function", "T-apply-to-datetime-per-element", "100,000 rows"),
    ("apply-axis-1", "apply-axis-1", "100,000 rows"),
    ("frame-growth-in-loop", "loc-append-in-loop-vs-list", "3,000 rows"),
    ("groupby-lambda-arithmetic", "G100k-transform-share", "100,000 groups"),
    ("groupby-lambda-window", "G100k-transform-cumsum", "100,000 groups"),
    ("replace-with-mapping", "replace-1000key-dict-vs-map-fillna-str", "1,000 keys"),
    ("sort-then-head", "sort-iloc0-vs-idxmin", "idxmin"),
    ("builtin-on-column", "builtin-sum-on-column", "sum"),
    ("apply-date-part", "apply-lambda-dt-attr", ""),
    ("concat-then-category", "31-concat-cat-astype-vs-union", "pandas 3.1"),
    ("groupby-lambda", "G100k-agg-lambda-vs-name", "100,000 groups"),
    ("index-year-mask", "T-year-mask-vs-partial-string-loc", "sorted index"),
    ("apply-text-method", "map-lambda-startswith", "startswith"),
    ("text-time-key", "gb-strftime-month-vs-to-period", ""),
    ("len-of-filter", "len-filter-vs-mask-sum", ""),
    ("object-dates", "dt-date-vs-normalize", ""),
    ("copy-after-indexing", "copy-after-column-select", "column selection"),
    ("literal-contains", "str-contains-literal-regex", ""),
]

e = html.escape
FIX_LABEL = {"safe": "safe fix", "unsafe": "unsafe fix", "none": "report only"}


def rule_html(r):
    pills = [f'<span class="pill {r["fix"]}">{FIX_LABEL[r["fix"]]}</span>']
    if r["since"] == "3.1":
        pills.append('<span class="pill v31">needs pandas 3.1</span>')
    if r["state"] != "new":
        pills.append(f'<span class="pill state">{e(r["state"])}</span>')
    if r["id"] in PROTO:
        pills.append('<span class="pill proto">prototype ran</span>')
    minus = lambda b: f'<span class="del">- {e(b)}</span>'
    plus = lambda a: f'<span class="add">+ {e(a)}</span>' if a else ""
    if len(r["before"]) == len(r["after"]):
        lines = "".join(minus(b) + plus(a) for b, a in zip(r["before"], r["after"]))
    else:
        lines = "".join(map(minus, r["before"])) + "".join(map(plus, r["after"]))
    return (f'<div class="rule"><div class="head"><code class="rid">{r["id"]}</code>{"".join(pills)}</div>'
            f'<pre class="diff">{lines}</pre><p class="ev">{r["ev"]}</p></div>')


groups = {}
for r in R:
    groups.setdefault(r["group"], []).append(r)

n_rules = len(R)
n_new = sum(1 for r in R if r["state"] == "new")
n_fix = sum(1 for r in R if r["fix"] != "none")
n_safe = sum(1 for r in R if r["fix"] == "safe")
n_proto = sum(1 for r in R if r["id"] in PROTO)
n_31 = sum(1 for r in R if r["since"] == "3.1")

top = max(x(c) for _, c, _ in CHART)
bars = ""
for rid, c, note in sorted(CHART, key=lambda t: -x(t[1])):
    w = max(2.0, math.log10(x(c)) / math.log10(top) * 100)
    bars += (f'<div class="bar-row"><code>{rid}</code><div class="track"><div class="bar" style="width:{w:.1f}%"></div></div>'
             f'<span class="val">{round(x(c)):,}×</span><span class="note">{note}</span></div>' if x(c) >= 10 else
             f'<div class="bar-row"><code>{rid}</code><div class="track"><div class="bar" style="width:{w:.1f}%"></div></div>'
             f'<span class="val">{x(c):.1f}×</span><span class="note">{note}</span></div>')

sections = ""
for g, rs in groups.items():
    sections += f'<h3>{e(g)} <span class="count">{len(rs)} rules</span></h3><p class="lead">{GROUP_NOTE[g]}</p>'
    sections += "".join(rule_html(r) for r in rs)

HITS = [("query-string", 12), ("merge-without-on", 11), ("removed-in-pandas-3", 8), ("literal-contains", 4), ("to-csv-index", 3),
        ("apply-axis-1", 1), ("copy-after-indexing", 1), ("rolling-apply", 1), ("set-index-then-resample", 1)]
chips = "".join(f'<span class="chip"><code>{k}</code><b>{v}</b></span>' for k, v in HITS)
rej = "".join(f"<tr><td>{e(a)}</td><td>{m}</td><td>{d}</td></tr>" for a, m, d in REJECTED)

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>pdx pandas rule proposal</title>
<script>if (window.self === window.top) document.documentElement.classList.add('standalone');</script>
<style>
  html.standalone {{
    color-scheme: light dark;
    background: light-dark(#ffffff, #0d1117);
    --foreground: light-dark(#1f2328, #e6e6e6);
    --muted-foreground: light-dark(#59636e, #9a9a9a);
    --border: light-dark(#d1d9e0, #333333);
    --card: light-dark(#f6f8fa, #1b1b1b);
    --code-background: light-dark(#f6f8fa, #161616);
    --muted: light-dark(#e6eaef, #2a2a2a);
    --success: light-dark(#1a7f37, #3fb950);
    --warning: light-dark(#9a6700, #d29922);
    --destructive: light-dark(#cf222e, #f85149);
    --info: light-dark(#0969da, #58a6ff);
    --chart-1: light-dark(#0969da, #6aa3ff);
  }}
  html.standalone body {{ max-width: 760px; margin: 0 auto; padding: 24px 20px; }}
  body {{ margin: 0; font-family: var(--font-sans, system-ui, sans-serif); color: var(--foreground, #e6e6e6); font-size: 14px; line-height: 1.5; }}
  .wrap {{ display: flex; flex-direction: column; gap: 28px; }}
  h2 {{ font-size: 17px; font-weight: 600; margin: 0 0 6px; }}
  h3 {{ font-size: 15px; font-weight: 600; margin: 26px 0 2px; display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; }}
  h3:first-of-type {{ margin-top: 10px; }}
  p {{ margin: 0; }}
  .lead {{ color: var(--muted-foreground, #9a9a9a); margin-bottom: 10px; }}
  .count {{ font-size: 12px; font-weight: 400; color: var(--muted-foreground, #9a9a9a); }}
  code, pre {{ font-family: var(--font-mono, ui-monospace, monospace); font-size: 12.5px; }}
  .stats {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
  .stat {{ background: var(--card, #1b1b1b); border: 1px solid var(--border, #333); border-radius: var(--radius, 8px); padding: 12px 14px; }}
  .stat b {{ display: block; font-size: 24px; font-weight: 600; line-height: 1.2; }}
  .stat span {{ color: var(--muted-foreground, #9a9a9a); font-size: 12.5px; }}
  .bar-row {{ display: grid; grid-template-columns: 190px minmax(0, 1fr) 62px 110px; gap: 10px; align-items: center; height: 24px; }}
  .bar-row code {{ white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .track {{ height: 12px; background: var(--muted, #2a2a2a); border-radius: 3px; overflow: hidden; }}
  .bar {{ height: 100%; background: var(--chart-1, var(--primary, #6aa3ff)); border-radius: 3px; }}
  .val {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .note {{ color: var(--muted-foreground, #9a9a9a); font-size: 12px; white-space: nowrap; }}
  .rule {{ border-top: 1px solid var(--border, #333); padding: 12px 0 14px; }}
  .head {{ display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 8px; }}
  .rid {{ font-size: 13.5px; font-weight: 600; margin-right: 4px; }}
  .pill {{ font-size: 11.5px; padding: 1px 8px; border-radius: 999px; border: 1px solid var(--border, #333); color: var(--muted-foreground, #9a9a9a); white-space: nowrap; }}
  .pill.safe {{ color: var(--success, #3fb950); border-color: color-mix(in srgb, var(--success, #3fb950) 45%, transparent); }}
  .pill.unsafe {{ color: var(--warning, #d29922); border-color: color-mix(in srgb, var(--warning, #d29922) 45%, transparent); }}
  .pill.v31 {{ color: var(--info, #58a6ff); border-color: color-mix(in srgb, var(--info, #58a6ff) 45%, transparent); }}
  .diff {{ margin: 0 0 8px; padding: 8px 0; background: var(--code-background, #161616); border-radius: var(--radius, 8px); overflow-x: auto; line-height: 1.6; }}
  .diff span {{ display: block; padding: 0 12px; white-space: pre; min-width: max-content; }}
  .del {{ background: color-mix(in srgb, var(--destructive, #f85149) 13%, transparent); }}
  .add {{ background: color-mix(in srgb, var(--success, #3fb950) 13%, transparent); }}
  .ev {{ color: var(--muted-foreground, #9a9a9a); font-size: 13px; }}
  .ev code {{ color: var(--foreground, #e6e6e6); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ text-align: left; vertical-align: top; padding: 8px 10px 8px 0; border-top: 1px solid var(--border, #333); }}
  th {{ font-weight: 600; border-top: 0; color: var(--muted-foreground, #9a9a9a); font-size: 12.5px; }}
  td:nth-child(2), td:nth-child(3) {{ color: var(--muted-foreground, #9a9a9a); }}
  .chips {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .chip {{ display: inline-flex; gap: 8px; align-items: baseline; padding: 4px 10px; border: 1px solid var(--border, #333); border-radius: var(--radius, 8px); }}
  .chip b {{ font-variant-numeric: tabular-nums; }}
  .plain {{ margin: 8px 0 0; padding: 12px 14px; background: var(--code-background, #161616); border-radius: var(--radius, 8px); overflow-x: auto; line-height: 1.6; }}
  ol {{ margin: 6px 0 0; padding-left: 20px; }}
  ol li {{ margin-bottom: 6px; }}
  .foot {{ color: var(--muted-foreground, #9a9a9a); font-size: 12.5px; border-top: 1px solid var(--border, #333); padding-top: 12px; }}
  @media (max-width: 520px) {{
    .stats {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    .bar-row {{ grid-template-columns: 128px minmax(0, 1fr) 54px; }}
    .note {{ display: none; }}
    table, tbody, tr, td {{ display: block; }}
    thead {{ display: none; }}
    td {{ border-top: 0; padding: 2px 0; }}
    tr {{ border-top: 1px solid var(--border, #333); padding: 8px 0; }}
    td:first-child {{ font-weight: 600; }}
  }}
</style></head>
<body><div class="wrap">

<section class="stats">
  <div class="stat"><b>{n_rules}</b><span>rules in the proposal, {n_new} of them new</span></div>
  <div class="stat"><b>{n_fix}</b><span>rules with a fix, {n_safe} of them safe</span></div>
  <div class="stat"><b>{n_proto}</b><span>rules with a prototype that ran in ast-grep 0.51.1</span></div>
  <div class="stat"><b>31 of 31</b><span>test cases gave equal results after the safe fixes, on 3.1.1 and 3.0.6</span></div>
</section>

<section>
  <h2>Measured speed gain of the rewritten form</h2>
  <p class="lead">pandas 3.1.1, 1,000,000 rows unless noted. The bars use a log scale, and each number is the old time divided by the new time.</p>
  {bars}
</section>

<section>
  <h2>Proposed rules</h2>
  <p class="lead">Each block shows the code a rule reports and the code it asks for. A safe fix runs with <code>pdx check --fix</code>, and it keeps the result apart from float rounding below 1e-12, which 3 of the 31 test cases showed. An unsafe fix needs <code>--unsafe-fixes</code>.</p>
  {sections}
</section>

<section>
  <h2>Reports on 53 notebooks from two pandas books</h2>
  <p class="lead">The prototypes ran on the code cells of every notebook that imports pandas in Python for Data Analysis and the Python Data Science Handbook, 10,002 lines in total. They reported 42 lines, and all 42 were correct when read by hand. A first version also reported <code>asfreq("M")</code> on periods 6 times, which is valid code, so the "M" pattern no longer covers asfreq. Both books teach good pandas, so the counts say little about how often the speed rules fire in everyday code.</p>
  <div class="chips">{chips}</div>
</section>

<section>
  <h2>Common advice that the measurements did not support</h2>
  <p class="lead">The rewrites below are often recommended. On pandas 3.1.1 they gave no gain or a loss, so the proposal leaves them out.</p>
  <table><thead><tr><th>Advice</th><th>Measured on 1,000,000 rows</th><th>Decision</th></tr></thead><tbody>{rej}</tbody></table>
</section>

<section>
  <h2>Features with no old form to detect</h2>
  <p class="lead">A rule can only promote a feature when the longer code it replaces has a shape pdx can match. <code>pd.merge_asof</code> was {times(x('T-asof-loop-vs-merge-asof'))} faster than a lookup loop over 5,000 timestamps, and the loop can be written in many ways. A window over time, such as <code>rolling("7D", on="d")</code>, differs from <code>rolling(7)</code> only when dates are missing. <code>resample</code> was {times(x('T-gb-normalize-key-vs-resample-sorted'))} faster than a groupby on a sorted frame and much slower on an unsorted one. pdx cannot see whether a frame is sorted. The messages of <code>row-loop</code> and <code>text-time-key</code> can name all three features.</p>
</section>

<section>
  <h2>Support for pandas 3.0 with one rule set</h2>
  <p class="lead">{n_31} rules ask for an API that exists only in pandas 3.1. On pandas 3.0.6 <code>df.select</code> raises AttributeError, so pdx has to know the installed version before it reports or fixes those rules.</p>
<pre class="plain">on(pdx check)
  version = pandas version in the project's .venv, read from the name of the dist-info folder
  if no pandas is installed
    version = 3.1
  for each rule
    if rule.metadata.since is newer than version
      skip the rule
    report the rule, and apply its fix when asked</pre>
</section>

<section>
  <h2>Suggested build order</h2>
  <ol>
    <li>Repair the <code>chained-assignment</code> fix and add the other 11 rules for code that is wrong or broken on pandas 3. They are errors, and most have a fix.</li>
    <li>Add the rules with a safe fix and a measured gain, such as <code>groupby-lambda</code>, <code>rolling-apply</code>, <code>copy-after-indexing</code> and <code>lambda-column</code>.</li>
    <li>Add the rules that only report, such as <code>row-loop</code>, <code>apply-axis-1</code> and <code>groupby-apply</code>.</li>
    <li>Add the version lookup and the {n_31} rules that need pandas 3.1.</li>
  </ol>
</section>

<p class="foot">Method: each pair ran on pandas 3.1.1 and 3.0.6 with Python 3.15.2, numpy 2.5.4 and pyarrow 26.0.1, on a machine with 32 cores. A time is the best of 1 to 5 runs on a frame held in memory, and the two results were compared after each pair. The whole set ran twice. The gains from the two runs differed by 4% at the median and by 50% at most, and the page shows the second run. The scripts and the raw times are in <code>research/pandas-rules</code> in the pdx repository, and the 60 prototype rule documents are in <code>research/pandas-rules/proto/rules.yml</code>.</p>

</div></body></html>
"""
out = os.path.join(ROOT, "show-me-pdx-pandas-rules.html")
open(out, "w").write(PAGE)
print(out, len(PAGE), "bytes;", n_rules, "rules,", n_new, "new,", n_fix, "with fix,", n_safe, "safe,", n_proto, "prototyped,", n_31, "need 3.1")
