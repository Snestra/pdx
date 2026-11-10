# Rules

## pandas

The rules follow pandas 3, where copy-on-write is always on. A fix that writes `pd.` or `np.`
applies only in a file with `import pandas as pd` or `import numpy as np`. In any other file pdx
reports the issue without a fix.

One rule asks for an API that pandas 3.1 added, `concat-then-category`. pdx reads the installed
pandas version from the name of the `pandas-<version>.dist-info` folder in the project's venv,
which is `$VIRTUAL_ENV` or the nearest `.venv` above the working directory, without starting
Python. On pandas 3.0 it skips that rule. When the venv has no pandas, or there is no venv, every
rule runs.

### Code that is wrong or broken on pandas 3

Each old form gives a wrong result, raises, or warns on pandas 3.0 and 3.1.

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `chained-assignment` | error | `df["a"][i] = v`, `df[mask]["a"] = v` and `df.loc[mask]["a"] = v`, which write to a copy | unsafe: `df.loc[i, "a"] = v` |
| `inplace-on-column` | error | `df["b"].fillna(0, inplace=True)`, which changes a copy | unsafe: `df["b"] = df["b"].fillna(0)` |
| `inplace-result-assigned` | error | `df = df.dropna(inplace=True)`, which leaves `df` as None | unsafe: `df = df.dropna()` |
| `no-inplace` | warning | any other `inplace=True`, which gives no speedup and blocks chaining | unsafe: `df = df.dropna()` |
| `epoch-from-int-cast` | error | `df["d"].astype("int64") // 10**9`, which is off by 1,000 now that datetimes default to microseconds | none |
| `compare-to-missing` | error | `df["b"] == np.nan` and `df["k"].astype(str) == "nan"`, which are never true | unsafe: `df["b"].isna()` |
| `in-column` | error | `2 in df["a"]`, which checks the index labels | unsafe: `(df["a"] == 2).any()` |
| `mask-precedence` | error | `df["a"] > 1 & df["b"] < 3`, where `&` binds first | none |
| `write-through-values` | error | `df["a"].values[0] = 9`, which raises because the array is read-only | none |
| `object-dtype-check` | error | `df["k"].dtype == object` and `select_dtypes(include="object")`, which miss the new str dtype | unsafe: `pd.api.types.is_string_dtype(df["k"])` |
| `groupby-apply-reads-key` | error | `df.groupby("k").apply(lambda g: g["k"])`, which raises KeyError | none |
| `removed-in-pandas-3` | error | `applymap`, `fillna(method=)`, frequencies such as `"M"`, `"H"` and `"T"`, `delim_whitespace=True` and `dt.week` | safe: `map`, `ffill()`, `"ME"`, `"h"`, `"min"`, `sep=r"\s+"`. unsafe: `"M"` in `resample`, `dt.isocalendar().week` |
| `deprecated-in-pandas-3` | warning | `pd.set_option("mode.copy_on_write", True)`, `copy=False` and `pd.Timestamp.utcnow()` | safe: delete the line, drop `copy=`, `pd.Timestamp.now("UTC")`. unsafe: drop `copy=` from `astype` |

The `chained-assignment` fix covers the three shapes above. A mask held in a name is fixed when
the enclosing function assigns that name only masks, such as a comparison or a call to `isin`.
Any other chain, such as `df.iloc[0]["a"] = v`, is reported without a fix. Two plain keys, as in
`rows[0]["name"] = v`, are left alone, because they are more often a list or a dict.

`in-column` and `inplace-on-column` can report a dict, such as `"x" in data["names"]`, because pdx
cannot tell it from a frame. Their fixes are unsafe for that reason.

`removed-in-pandas-3` rewrites a frequency where the call takes only datetimes, such as
`date_range`, `Grouper`, `floor` and `rolling`. Inside `resample` and `shift` the fix for `"M"`,
`"Q"` and `"Y"` is unsafe, because those aliases stay valid when the index holds periods. It
leaves `to_period("M")` and `asfreq("M")` alone, and it reports `"A"` inside `resample`, `asfreq`
and `shift` without a fix, because the new alias is `"YE"` for datetimes and `"Y"` for periods.

`deprecated-in-pandas-3` deletes the copy-on-write option only at the top level of a file, and
reports it without a fix inside a function or another block. Dropping `copy=` from `astype` is
unsafe, because a numpy array also has `astype(copy=False)`, and there it can return the same
array.

The `no-inplace` fix applies only to a call that stands alone as a statement, on a name, attribute
or subscript. The inplace fixes drop comments between the call's arguments.

### Shorter forms, including the pandas 3.0 and 3.1 API

These rules are warnings. Most of them make code shorter and do not change its speed.

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `sort-then-reset-index` | warning | `df.sort_values("b").reset_index(drop=True)`, also after `sort_index`, `dropna`, `drop_duplicates`, `explode` and `sample` | safe: `df.sort_values("b", ignore_index=True)` |
| `set-index-then-resample` | warning | `df.set_index("d").resample("D").sum()` | safe: `df.resample("D", on="d").sum()` |
| `subtract-shift` | warning | `df["b"] - df["b"].shift()` | unsafe: `df["b"].diff()` |
| `range-mask` | warning | `(df["a"] >= 10) & (df["a"] <= 20)` | unsafe: `df["a"].between(10, 20)` |
| `groupby-then-reset-index` | warning | `df.groupby("k")[["a", "b"]].sum().reset_index()` | unsafe: `df.groupby("k", as_index=False)[["a", "b"]].sum()` |
| `rename-after-agg` | warning | `g.agg({"b": "mean"}).rename(columns={"b": "b_mean"})` | none |
| `merge-indicator-anti-join` | warning | `m[m["_merge"] == "left_only"]` after `merge(..., indicator=True)` | none |
| `value-counts-share` | warning | `df["k"].value_counts() / len(df["k"])` | unsafe: `df["k"].value_counts(normalize=True)` |
| `nested-np-where` | warning | `np.where(a < 20, "low", np.where(a < 70, "mid", "high"))` | none |
| `query-string` | warning | `df.query("a > 50 and b < 0")` | none |
| `filter-items` | warning | `df.filter(items=cols)` | unsafe: `df[cols]` |
| `inline-column-list` | warning | `df[["k", "a", "b"]]` and `df.groupby(["k", "s", "raw"])`, three or more names written inside the expression | none |
| `concat-then-category` | warning | `pd.concat(parts).astype("category")`, on pandas 3.1 | unsafe: `pd.concat(parts, union_categories=True)` |

pdx has no rule for or against a lambda in `assign`. A lambda and `pd.col` gave the same result
at the same speed, and a lambda also works with `np.where` and with calculations across columns.
`set-index-then-resample` applies only when a named aggregation such as `sum` or `mean` follows,
because upsampling with `asfreq` raises with `on=`, and a function passed to `agg` sees other
data. The `range-mask` fix is unsafe, because the operand may be a numpy array, which has no
`between`. The `subtract-shift` fix is unsafe, because `diff` wraps around on an unsigned integer
column and returns booleans for a boolean column. The `groupby-then-reset-index` fix is unsafe,
because a key that is not a column comes back in another place. The `value-counts-share` fix names
the result proportion instead of count and leaves missing values out of the total.
`query-string` leaves a string that reads like SQL alone, such as `conn.query("SELECT ...")`, and
it asks for `df.loc[pd.col("a") > 50]`, which type checkers accept. The `filter-items` fix is
unsafe, because `df[cols]` raises on a label that is absent, where `filter` skipped it.
`inline-column-list` reports a list of three or more text literals in `df[[...]]`, in
`df.loc[rows, [...]]`, as an argument of `groupby`, `sort_values`, `set_index`, `select` or
`drop_duplicates`, and in `by=`, `subset=`, `on=`, `left_on=`, `right_on=`, `columns=`,
`id_vars=`, `value_vars=` or `usecols=`. It leaves `pd.DataFrame(data, columns=[...])` alone,
because the list there defines the frame. It asks for a named list, such as
`output_columns = ["k", "a", "b"]`, passed by name. The `concat-then-category`
fix is unsafe, because the category order differs, and parts that are not categorical stay so.

### Python work per row or per value

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `apply-known-function` | warning | `df["s"].apply(len)`, `df["b"].apply(pd.isna)`, `df["raw"].apply(pd.to_datetime)` and `df["b"].apply(lambda v: round(v, 2))` | safe: `df["s"].str.len()`. unsafe: `df["b"].isna()`, `pd.to_datetime(df["raw"])`, `df["b"].round(2)` |
| `literal-contains` | warning | `df["s"].str.contains("ta_")`, a pattern with no regex character | safe: `str.contains("ta_", regex=False)` |
| `copy-after-indexing` | warning | `df[["a", "b"]].copy()`, `df[mask].copy()` and `df.loc[...].copy()` | safe: drop `.copy()` |
| `row-loop` | warning | a loop over `iterrows()`, `itertuples()` or `to_dict("records")`, and `for i in range(len(df))` with `df.iloc[i]` | none |
| `apply-axis-1` | warning | `df.apply(f, axis=1)` | none |
| `apply-text-method` | warning | `df["s"].map(lambda v: v.startswith("A"))` | unsafe: `df["s"].str.startswith("A")` |
| `apply-date-part` | warning | `df["d"].apply(lambda t: t.year)` | unsafe: `df["d"].dt.year` |
| `apply-condition` | warning | `df["a"].apply(lambda v: 1 if v > 50 else 0)` and `lambda v: min(v, 1.0)` | none |
| `apply-arithmetic` | warning | `df["b"].apply(lambda v: v * 2 + 1)` | unsafe: `df["b"] * 2 + 1` |
| `builtin-on-column` | warning | `sum(df["a"])` and `len(set(df["k"]))` | unsafe: `df["a"].sum()`, `df["k"].nunique()` |
| `list-over-column` | warning | `[v.upper() for v in df["s"]]` | none |
| `frame-growth-in-loop` | warning | `out.loc[len(out)] = row` inside a loop | none |
| `len-of-filter` | warning | `len(df[df["a"] > 50])` | unsafe: `int((df["a"] > 50).sum())` |
| `sort-then-head` | warning | `df.sort_values("b").head(10)` and `df.sort_values("b").iloc[0]` | unsafe: `df.nsmallest(10, "b")`, `df.iloc[df["b"].argmin()]` |
| `replace-with-mapping` | warning | `df["k"].replace(mapping)` with a mapping held in a name | none |
| `concat-in-loop` | warning | `pd.concat` inside a loop, which is quadratic | none |

`apply-known-function` reports only a column taken by a text label, because on a frame `apply`
works per column. Its `pd.to_datetime` fix is unsafe, because a call per value parses each text
on its own, and the whole column must share one format. The `isna` fix is unsafe, because on a
column of lists `pd.isna` per value returned an array per cell. The `round` fix is unsafe, because
Python and numpy round some halfway values differently. `copy-after-indexing` leaves a single text
label and a slice alone, because on a dict or a numpy array the copy keeps a later write away
from the original.

`row-loop` replaces the `no-iterrows` rule of pdx 0.1.0. The fixes of `apply-text-method`,
`apply-date-part` and `apply-arithmetic` are unsafe, because a column method returns a missing
value where the lambda raised, and the dtype can change: `dt.year` is int32 where the lambda gave
int64. `builtin-on-column` skips missing values after the fix. `sort-then-head` is unsafe, because
`nsmallest` raises on a text column and orders ties differently, and `argmin` raises when every
value is missing. `replace-with-mapping` asks for
`df["k"].map(lambda v: mapping.get(v, v))`, which keeps the values and the dtype.

### groupby, agg and transform

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `groupby-lambda` | warning | `g["b"].agg(lambda v: v.max())`, `g.agg(np.sum)` and `pivot_table(aggfunc=np.mean)` | safe: `"max"` for min, max, median, count and nunique. unsafe: `"sum"`, `"mean"` |
| `groupby-lambda-window` | warning | `g["b"].transform(lambda v: v.shift(1))` | safe: `g["b"].shift(1)`. unsafe: `g["b"].cumsum()` |

`groupby-lambda` leaves a lambda inside a list alone, because the result column would get a new
name. It also leaves `np.median`, `np.std` and `np.var` alone, because they treat missing values
and degrees of freedom differently from the named methods. The fixes for sum, mean, std, var, prod,
cumsum and cumprod are unsafe, because pandas adds up each group with compensated summation. On
values such as 1e16, 1, 1 and -1e16 the sum changes from 0 to 2. `groupby-lambda-window` leaves
`shift(freq=)` alone, because it moves the index.

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `groupby-lambda-arithmetic` | warning | `g["w"].transform(lambda v: v / v.sum())`, the z-score and `v.fillna(v.mean())` | unsafe: `df["w"] / df.groupby("k")["w"].transform("sum")` |
| `groupby-filter-lambda` | warning | `df.groupby("k").filter(lambda g: len(g) > 10)` | unsafe: `df[df.groupby("k")["k"].transform("size") > 10]` |
| `groupby-apply` | warning | any `groupby(...).apply` with a lambda | none |
| `aggregate-then-merge-back` | warning | `df.merge(df.groupby("k")["b"].sum()...)` and `df["k"].map(df.groupby("k")["b"].sum())` | none |
| `groupby-first-skips-missing` | warning | `df.groupby("k").first()` and `last()` | none |

### Time series

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `rolling-apply` | warning | `rolling(20).apply(lambda w: w.max())`, and `rolling(20).apply(f)` without `raw=True` | safe: `rolling(20).max()` for min, max and median. unsafe: sum, mean, std and var. The `raw=True` case has no fix |
| `text-time-key` | warning | `df.groupby(df["d"].dt.strftime("%Y-%m"))` | none |
| `object-dates` | warning | `df["d"].dt.date` and `dt.time` | none |
| `apply-on-dates` | warning | `df["d"].apply(lambda t: t + pd.Timedelta(days=7))`, `t.replace(day=1)` and `t.strftime(...)` | unsafe: `df["d"] + pd.Timedelta(days=7)` |
| `index-year-mask` | warning | `df[df.index.year == 2023]` | none |

The `rolling-apply` fixes for sum, mean, std and var are unsafe, because the window methods keep
running totals, so values far apart in size can give another result. For a function with no
window method the message names `raw=True` and `engine="numba"`. `apply-on-dates` writes
`df["d"] - pd.to_timedelta(df["d"].dt.day - 1, unit="D")` for `replace(day=1)`, which keeps the
time of day. Its fixes are unsafe, because a missing date gives a missing result where the
lambda raised.

### Stated intent

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `merge-without-validate` | warning | `merge` without `validate=`, which can duplicate rows | none |
| `merge-without-on` | warning | `merge` without `on=`, which joins on every shared column name | none |
| `to-csv-index` | warning | `df.to_csv(path)` without `index=` | none |

### Reading files

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `read-csv-slow-option` | warning | `read_csv(..., engine="python")` and `low_memory=False`, which turn off reading on several threads | none |

`read-csv-slow-option` leaves `engine="python"` alone when the call needs it, for `skipfooter` or
a separator of several characters other than `\s+`.

### Packages

`pdx check` also looks at the project's venv once per run. When the venv has pandas, it warns
about each package below that the venv lacks. The warning points at the project's
`pyproject.toml`, or at the venv when there is none. A project without a venv gets no package
warning, and `pdx hook` never gives one.

| Rule | Warns when | Why |
| --- | --- | --- |
| `missing-pyarrow` | pyarrow is not installed | Text columns are stored as Python strings without it. The `.str` methods ran 3 to 11 times faster with it on 1,000,000 rows |
| `missing-bottleneck` | bottleneck is not installed | `std` ran 4 times faster and `median` 1.7 times faster with it on 10,000,000 rows |
| `missing-pandas-stubs` | pandas-stubs is not installed, and the project uses mypy, pyright, basedpyright, ty or pyrefly | Without the stubs a type checker does not check calls to pandas |

A project uses a type checker when the venv has it or `pyproject.toml` has a `[tool.<name>]`
table for it. numexpr and numba have no check. numexpr changed little in measurements, and numba
only helps a function passed to `rolling(...).apply`, where the `rolling-apply` message names it.

## Write a rule

Rules are [ast-grep rules](https://ast-grep.github.io/guide/rule-config.html) in `.yml` files,
compiled into the binary. A pack lives at `rules/<module>/`, where `<module>` is the name you
import.

```text
rules/pandas/
├── pack.yml        # the pack's manifest: import aliases and package checks
├── row-loop.yml    # one file per rule, named after the rule id
└── ...
```

A rule file holds the documents of one rule, one per shape, and each document has the file's name
as its `id`. The build fails on any other id.

A rule may have one ast-grep `fix:`. It must then say whether the fix keeps what the code does,
with `metadata: { fix: safe }` or `metadata: { fix: unsafe }`. A fix may write an alias that
`pack.yml` lists under `aliases`, such as `pd.`, and pdx applies it only in a file that imports
the module under that alias.

A rule that needs a newer library version says so with `metadata: { since: "3.1" }`. pdx skips it
when the project's venv holds an older version of the pack's library. It finds the version for any
pack the same way: from the dist-info folder whose name is the module, or whose `top_level.txt`
lists the module.

Add a file, rebuild, and check it against a sample:

```sh
cargo build --release
target/release/pdx check samples/bad.py
cp samples/bad.py /tmp/bad.py && target/release/pdx check /tmp/bad.py --fix --unsafe-fixes
```

The files in `samples/pandas/` mark each line a rule reports with a comment that names the rules.

`pack.yml` may list package checks under `packages`. Each entry has an `id`, the `package` to
look for, a `message`, and optionally `onlyWith`, a list of tools. pdx warns when the venv has the
pack's library and lacks the package. With `onlyWith`, it warns only when the project also uses
one of the tools.

A new folder under `rules/` is a new pack, with no Rust change. Its rules run only on files that
import the module.
