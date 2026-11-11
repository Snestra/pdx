# Rules

## pandas

Every rule below has a direct heading link, its severity, fix safety, and before and after code.
Examples assume `import pandas as pd` and `import numpy as np`. Names such as `df`,
`output_columns` and `mapping` represent values supplied by your program. The replacement may
change behavior when repairing a bug or using an unsafe fix. Read the notes before applying it.

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

#### chained-assignment

**Severity:** error. **Fix:** unsafe: `df.loc[i, "a"] = v`.

Reports `df["a"][i] = v`, `df[mask]["a"] = v` and `df.loc[mask]["a"] = v`, which write to a copy.

Example:

```python
df["load"][row] = value
```

Use instead:

```python
df.loc[row, "load"] = value
```

#### inplace-on-column

**Severity:** error. **Fix:** unsafe: `df["b"] = df["b"].fillna(0)`.

Reports `df["b"].fillna(0, inplace=True)`, which changes a copy.

Example:

```python
df["load"].fillna(0, inplace=True)
```

Use instead:

```python
df["load"] = df["load"].fillna(0)
```

#### inplace-result-assigned

**Severity:** error. **Fix:** unsafe: `df = df.dropna()`.

Reports `df = df.dropna(inplace=True)`, which leaves `df` as None.

Example:

```python
df = df.dropna(inplace=True)
```

Use instead:

```python
df = df.dropna()
```

#### no-inplace

**Severity:** warning. **Fix:** unsafe: `df = df.dropna()`.

Reports any other `inplace=True`, which gives no speedup and blocks chaining.

Example:

```python
df.dropna(inplace=True)
```

Use instead:

```python
df = df.dropna()
```

#### epoch-from-int-cast

**Severity:** error. **Fix:** none.

Reports `df["d"].astype("int64") // 10**9`, which is off by 1,000 now that datetimes default to microseconds.

Example:

```python
seconds = df["time"].astype("int64") // 10**9
```

Use instead:

```python
seconds = (df["time"] - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")
```

The epoch example assumes dates without a time zone. For dates with a time zone, use a UTC epoch. Missing timestamps remain missing.

The replacement is advice. pdx does not apply it automatically.

#### compare-to-missing

**Severity:** error. **Fix:** unsafe: `df["b"].isna()`.

Reports `df["b"] == np.nan` and `df["k"].astype(str) == "nan"`, which are never true.

Example:

```python
missing = df["load"] == np.nan
```

Use instead:

```python
missing = df["load"].isna()
```

#### in-column

**Severity:** error. **Fix:** unsafe: `(df["a"] == 2).any()`.

Reports `2 in df["a"]`, which checks the index labels.

Example:

```python
found = 2 in df["load"]
```

Use instead:

```python
found = (df["load"] == 2).any()
```

#### mask-precedence

**Severity:** error. **Fix:** none.

Reports `df["a"] > 1 & df["b"] < 3`, where `&` binds first.

Example:

```python
selected = df[df["load"] > 1 & df["wind"] < 3]
```

Use instead:

```python
selected = df[(df["load"] > 1) & (df["wind"] < 3)]
```

The replacement is advice. pdx does not apply it automatically.

#### write-through-values

**Severity:** error. **Fix:** none.

Reports `df["a"].values[0] = 9`, which raises because the array is read-only.

Example:

```python
df["load"].values[0] = value
```

Use instead:

```python
df.loc[df.index[0], "load"] = value
```

The replacement is advice. pdx does not apply it automatically.

#### object-dtype-check

**Severity:** error. **Fix:** unsafe: `pd.api.types.is_string_dtype(df["k"])`.

Reports `df["k"].dtype == object` and `select_dtypes(include="object")`, which miss the new str dtype.

Example:

```python
is_text = df["name"].dtype == object
```

Use instead:

```python
is_text = pd.api.types.is_string_dtype(df["name"])
```

#### groupby-apply-reads-key

**Severity:** error. **Fix:** none.

Reports `df.groupby("k").apply(lambda g: g["k"])`, which raises KeyError.

Example:

```python
keys = df.groupby("region").apply(lambda group: group["region"].iloc[0])
```

Use instead:

```python
keys = df.groupby("region").apply(lambda group: group.name)
```

Read group.name only inside the function passed to apply. Multiple group keys give a tuple.

The replacement is advice. pdx does not apply it automatically.

#### removed-in-pandas-3

**Severity:** error. **Fix:** safe: `map`, `ffill()`, `"ME"`, `"h"`, `"min"`, `sep=r"\s+"`. unsafe: `"M"` in `resample`, `dt.isocalendar().week`.

Reports `applymap`, `fillna(method=)`, frequencies such as `"M"`, `"H"` and `"T"`, `delim_whitespace=True` and `dt.week`.

Example:

```python
filled = df["load"].fillna(method="ffill")
months = df.resample("M", on="time")["load"].sum()
```

Use instead:

```python
filled = df["load"].ffill()
months = df.resample("ME", on="time")["load"].sum()
```

#### deprecated-in-pandas-3

**Severity:** warning. **Fix:** safe: delete the line, drop `copy=`, `pd.Timestamp.now("UTC")`. unsafe: drop `copy=` from `astype`.

Reports `pd.set_option("mode.copy_on_write", True)`, `copy=False` and `pd.Timestamp.utcnow()`.

Example:

```python
now = pd.Timestamp.utcnow()
```

Use instead:

```python
now = pd.Timestamp.now("UTC")
```


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

#### sort-then-reset-index

**Severity:** warning. **Fix:** safe: `df.sort_values("b", ignore_index=True)`.

Reports `df.sort_values("b").reset_index(drop=True)`, also after `sort_index`, `dropna`, `drop_duplicates`, `explode` and `sample`.

Example:

```python
ordered = df.sort_values("load").reset_index(drop=True)
```

Use instead:

```python
ordered = df.sort_values("load", ignore_index=True)
```

#### set-index-then-resample

**Severity:** warning. **Fix:** safe: `df.resample("D", on="d").sum()`.

Reports `df.set_index("d").resample("D").sum()`.

Example:

```python
daily = df.set_index("time").resample("D")["load"].sum()
```

Use instead:

```python
daily = df.resample("D", on="time")["load"].sum()
```

#### subtract-shift

**Severity:** warning. **Fix:** unsafe: `df["b"].diff()`.

Reports `df["b"] - df["b"].shift()`.

Example:

```python
change = df["load"] - df["load"].shift()
```

Use instead:

```python
change = df["load"].diff()
```

#### range-mask

**Severity:** warning. **Fix:** unsafe: `df["a"].between(10, 20)`.

Reports `(df["a"] >= 10) & (df["a"] <= 20)`.

Example:

```python
inside = (df["load"] >= 10) & (df["load"] <= 20)
```

Use instead:

```python
inside = df["load"].between(10, 20)
```

#### groupby-then-reset-index

**Severity:** warning. **Fix:** unsafe: `df.groupby("k", as_index=False)[["a", "b"]].sum()`.

Reports `df.groupby("k")[["a", "b"]].sum().reset_index()`.

Example:

```python
totals = df.groupby("region")["load"].sum().reset_index()
```

Use instead:

```python
totals = df.groupby("region", as_index=False)["load"].sum()
```

#### rename-after-agg

**Severity:** warning. **Fix:** none.

Reports `g.agg({"b": "mean"}).rename(columns={"b": "b_mean"})`.

Example:

```python
summary = df.groupby("region").agg({"load": "mean"}).rename(columns={"load": "mean_load"})
```

Use instead:

```python
summary = df.groupby("region").agg(mean_load=("load", "mean"))
```

The replacement is advice. pdx does not apply it automatically.

#### merge-indicator-anti-join

**Severity:** warning. **Fix:** none.

Reports `m[m["_merge"] == "left_only"]` after `merge(..., indicator=True)`.

Example:

```python
merged = left.merge(right, on="key", how="left", indicator=True)
unmatched = merged[merged["_merge"] == "left_only"]
```

Use instead:

```python
unmatched = left.merge(right, on="key", how="left_anti")
```

The anti join returns the left columns, without the indicator or the right-hand columns. Use it when the result needs unmatched left rows rather than the full merged schema.

The replacement is advice. pdx does not apply it automatically.

#### value-counts-share

**Severity:** warning. **Fix:** unsafe: `df["k"].value_counts(normalize=True)`.

Reports `df["k"].value_counts() / len(df["k"])`.

Example:

```python
shares = df["region"].value_counts() / len(df["region"])
```

Use instead:

```python
shares = df["region"].value_counts(normalize=True)
```

#### nested-np-where

**Severity:** warning. **Fix:** none.

Reports `np.where(a < 20, "low", np.where(a < 70, "mid", "high"))`.

Example:

```python
band = np.where(df["load"] < 20, "low", np.where(df["load"] < 70, "mid", "high"))
```

Use instead:

```python
band = pd.Series("high", index=df.index).case_when([
    (df["load"] < 20, "low"),
    (df["load"] < 70, "mid"),
])
```

case_when uses the first matching condition. It returns a Series rather than a NumPy array.

The replacement is advice. pdx does not apply it automatically.

#### query-string

**Severity:** warning. **Fix:** none.

Reports `df.query("a > 50 and b < 0")`.

Example:

```python
selected = df.query("load > 50 and wind < 3")
```

Use instead:

```python
selected = df.loc[(pd.col("load") > 50) & (pd.col("wind") < 3)]
```

The replacement is advice. pdx does not apply it automatically.

#### filter-items

**Severity:** warning. **Fix:** unsafe: `df[cols]`.

Reports `df.filter(items=cols)`.

Example:

```python
selected = df.filter(items=output_columns)
```

Use instead:

```python
selected = df[output_columns]
```

The replacement raises when a requested column is absent. filter silently skips it, which is why the fix is unsafe.

#### inline-column-list

**Severity:** warning. **Fix:** none.

Reports `df[["k", "a", "b"]]` and `df.groupby(["k", "s", "raw"])`, three or more names written inside the expression.

Example:

```python
selected = df[["load", "wind", "solar"]]
```

Use instead:

```python
output_columns = ["load", "wind", "solar"]
selected = df[output_columns]
```

The replacement is advice. pdx does not apply it automatically.

#### concat-then-category

**Severity:** warning. **Fix:** unsafe: `pd.concat(parts, union_categories=True)`.

Reports `pd.concat(parts).astype("category")`, on pandas 3.1.

Example:

```python
combined = pd.concat(parts).astype("category")
```

Use instead:

```python
combined = pd.concat(parts, union_categories=True)
```


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

#### apply-known-function

**Severity:** warning. **Fix:** safe: `df["s"].str.len()`. unsafe: `df["b"].isna()`, `pd.to_datetime(df["raw"])`, `df["b"].round(2)`.

Reports `df["s"].apply(len)`, `df["b"].apply(pd.isna)`, `df["raw"].apply(pd.to_datetime)` and `df["b"].apply(lambda v: round(v, 2))`.

Example:

```python
lengths = df["name"].apply(len)
```

Use instead:

```python
lengths = df["name"].str.len()
```

#### literal-contains

**Severity:** warning. **Fix:** safe: `str.contains("ta_", regex=False)`.

Reports `df["s"].str.contains("ta_")`, a pattern with no regex character.

Example:

```python
matches = df["name"].str.contains("load_")
```

Use instead:

```python
matches = df["name"].str.contains("load_", regex=False)
```

#### copy-after-indexing

**Severity:** warning. **Fix:** safe: drop `.copy()`.

Reports `df[["a", "b"]].copy()`, `df[mask].copy()` and `df.loc[...].copy()`.

Example:

```python
part = df[["load", "wind"]].copy()
```

Use instead:

```python
part = df[["load", "wind"]]
```

#### row-loop

**Severity:** warning. **Fix:** none.

Reports a loop over `iterrows()`, `itertuples()` or `to_dict("records")`, and `for i in range(len(df))` with `df.iloc[i]`.

Example:

```python
total = sum(row.load * row.weight for row in df.itertuples())
```

Use instead:

```python
total = (df["load"] * df["weight"]).sum()
```

The example sums numeric columns without missing values. Check missing values and floating point rounding when replacing a Python reduction. Keep a loop when its work cannot be expressed on columns.

The replacement is advice. pdx does not apply it automatically.

#### apply-axis-1

**Severity:** warning. **Fix:** none.

Reports `df.apply(f, axis=1)`.

Example:

```python
total = df.apply(lambda row: row["load"] + row["wind"], axis=1)
```

Use instead:

```python
total = df["load"] + df["wind"]
```

The replacement is advice. pdx does not apply it automatically.

#### apply-text-method

**Severity:** warning. **Fix:** unsafe: `df["s"].str.startswith("A")`.

Reports `df["s"].map(lambda v: v.startswith("A"))`.

Example:

```python
names = df["name"].map(lambda name: name.upper())
```

Use instead:

```python
names = df["name"].str.upper()
```

#### apply-date-part

**Severity:** warning. **Fix:** unsafe: `df["d"].dt.year`.

Reports `df["d"].apply(lambda t: t.year)`.

Example:

```python
years = df["time"].apply(lambda time: time.year)
```

Use instead:

```python
years = df["time"].dt.year
```

#### apply-condition

**Severity:** warning. **Fix:** none.

Reports `df["a"].apply(lambda v: 1 if v > 50 else 0)` and `lambda v: min(v, 1.0)`.

Example:

```python
flag = df["load"].apply(lambda value: 1 if value > 50 else 0)
```

Use instead:

```python
flag = pd.Series(np.where(df["load"] > 50, 1, 0), index=df.index)
```

The explicit Series constructor preserves the row labels. Check the result name, dtype and missing-value behavior.

The replacement is advice. pdx does not apply it automatically.

#### apply-arithmetic

**Severity:** warning. **Fix:** unsafe: `df["b"] * 2 + 1`.

Reports `df["b"].apply(lambda v: v * 2 + 1)`.

Example:

```python
scaled = df["load"].apply(lambda value: value * 2 + 1)
```

Use instead:

```python
scaled = df["load"] * 2 + 1
```

#### builtin-on-column

**Severity:** warning. **Fix:** unsafe: `df["a"].sum()`, `df["k"].nunique()`.

Reports `sum(df["a"])` and `len(set(df["k"]))`.

Example:

```python
total = sum(df["load"])
```

Use instead:

```python
total = df["load"].sum()
```

#### list-over-column

**Severity:** warning. **Fix:** none.

Reports `[v.upper() for v in df["s"]]`.

Example:

```python
names = [name.upper() for name in df["name"]]
```

Use instead:

```python
names = df["name"].str.upper()
```

The result is a labeled Series rather than a Python list. Use tolist only at a boundary that needs a list.

The replacement is advice. pdx does not apply it automatically.

#### frame-growth-in-loop

**Severity:** warning. **Fix:** none.

Reports `out.loc[len(out)] = row` inside a loop.

Example:

```python
out = pd.DataFrame(columns=output_columns)
for row in rows:
    out.loc[len(out)] = row
```

Use instead:

```python
out = pd.DataFrame(rows, columns=output_columns)
```

The replacement is advice. pdx does not apply it automatically.

#### len-of-filter

**Severity:** warning. **Fix:** unsafe: `int((df["a"] > 50).sum())`.

Reports `len(df[df["a"] > 50])`.

Example:

```python
count = len(df[df["load"] > 50])
```

Use instead:

```python
count = int((df["load"] > 50).sum())
```

#### sort-then-head

**Severity:** warning. **Fix:** unsafe: `df.nsmallest(10, "b")`, `df.iloc[df["b"].argmin()]`.

Reports `df.sort_values("b").head(10)` and `df.sort_values("b").iloc[0]`.

Example:

```python
largest = df.sort_values("load", ascending=False).head(10)
```

Use instead:

```python
largest = df.nlargest(10, "load")
```

#### replace-with-mapping

**Severity:** warning. **Fix:** none.

Reports `df["k"].replace(mapping)` with a mapping held in a name.

Example:

```python
names = df["name"].replace(mapping)
```

Use instead:

```python
names = df["name"].map(lambda value: mapping.get(value, value))
```

The example uses an ordinary dictionary and scalar values. A short mapping can be faster with replace. map does not reproduce regex replacement or every special mapping behavior.

The replacement is advice. pdx does not apply it automatically.

#### concat-in-loop

**Severity:** warning. **Fix:** none.

Reports `pd.concat` inside a loop, which is quadratic.

Example:

```python
out = pd.DataFrame()
for path in paths:
    out = pd.concat([out, pd.read_csv(path)])
```

Use instead:

```python
frames = [pd.read_csv(path) for path in paths]
out = pd.concat(frames)
```

The example assumes paths is not empty and the starting frame has no schema to preserve. A single concat avoids repeatedly copying the growing result.

The replacement is advice. pdx does not apply it automatically.


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

#### groupby-lambda

**Severity:** warning. **Fix:** safe: `"max"` for min, max, median, count and nunique. unsafe: `"sum"`, `"mean"`.

Reports `g["b"].agg(lambda v: v.max())`, `g.agg(np.sum)` and `pivot_table(aggfunc=np.mean)`.

Example:

```python
maximum = df.groupby("region")["load"].agg(lambda group: group.max())
```

Use instead:

```python
maximum = df.groupby("region")["load"].agg("max")
```

#### groupby-lambda-window

**Severity:** warning. **Fix:** safe: `g["b"].shift(1)`. unsafe: `g["b"].cumsum()`.

Reports `g["b"].transform(lambda v: v.shift(1))`.

Example:

```python
previous = df.groupby("region")["load"].transform(lambda group: group.shift(1))
```

Use instead:

```python
previous = df.groupby("region")["load"].shift(1)
```


`groupby-lambda` leaves a lambda inside a list alone, because the result column would get a new
name. It also leaves `np.median`, `np.std` and `np.var` alone, because they treat missing values
and degrees of freedom differently from the named methods. The fixes for sum, mean, std, var, prod,
cumsum and cumprod are unsafe, because pandas adds up each group with compensated summation. On
values such as 1e16, 1, 1 and -1e16 the sum changes from 0 to 2. `groupby-lambda-window` leaves
`shift(freq=)` alone, because it moves the index.

#### groupby-lambda-arithmetic

**Severity:** warning. **Fix:** unsafe: `df["w"] / df.groupby("k")["w"].transform("sum")`.

Reports `g["w"].transform(lambda v: v / v.sum())`, the z-score and `v.fillna(v.mean())`.

Example:

```python
share = df.groupby("region")["load"].transform(lambda group: group / group.sum())
```

Use instead:

```python
share = df["load"] / df.groupby("region")["load"].transform("sum")
```

#### groupby-filter-lambda

**Severity:** warning. **Fix:** unsafe: `df[df.groupby("k")["k"].transform("size") > 10]`.

Reports `df.groupby("k").filter(lambda g: len(g) > 10)`.

Example:

```python
selected = df.groupby("region").filter(lambda group: len(group) > 10)
```

Use instead:

```python
selected = df[df.groupby("region")["region"].transform("size") > 10]
```

The example assumes the group keys are not missing. Check dropna and missing-key behavior before rewriting a filter.

#### groupby-apply

**Severity:** warning. **Fix:** none.

Reports any `groupby(...).apply` with a lambda.

Example:

```python
totals = df.groupby("region")["load"].apply(lambda group: group.sum())
```

Use instead:

```python
totals = df.groupby("region")["load"].sum()
```

The built-in reduction can change the index name, the dtype and floating point rounding. Check the result before replacing a general apply.

The replacement is advice. pdx does not apply it automatically.

#### aggregate-then-merge-back

**Severity:** warning. **Fix:** none.

Reports `df.merge(df.groupby("k")["b"].sum()...)` and `df["k"].map(df.groupby("k")["b"].sum())`.

Example:

```python
result = df.merge(
    df.groupby("region")["load"].sum().rename("total").reset_index(),
    on="region",
    how="left",
    validate="many_to_one",
)
```

Use instead:

```python
result = df.assign(total=lambda frame: frame.groupby("region")["load"].transform("sum"))
```

transform keeps the original index and row order. A merge can instead create a fresh index. The report covers an inline aggregation on the same frame, as well as mapping an aggregate back to its source column. An aggregate stored in a separate variable is not detected.

The replacement is advice. pdx does not apply it automatically.

#### groupby-first-skips-missing

**Severity:** warning. **Fix:** none.

Reports `df.groupby("k").first()` and `last()`.

Example:

```python
first = df.groupby("region").first()
```

Use instead:

```python
first = df.groupby("region").first(skipna=False)
```

skipna=False preserves missing values from the first row. Without it, first can combine values from different rows.

The replacement is advice. pdx does not apply it automatically.


### Time series

#### rolling-apply

**Severity:** warning. **Fix:** safe: `rolling(20).max()` for min, max and median. unsafe: sum, mean, std and var. The `raw=True` case has no fix.

Reports `rolling(20).apply(lambda w: w.max())`, and `rolling(20).apply(f)` without `raw=True`.

Example:

```python
average = df["load"].rolling(20).apply(lambda window: window.mean())
```

Use instead:

```python
average = df["load"].rolling(20).mean()
```

#### text-time-key

**Severity:** warning. **Fix:** none.

Reports `df.groupby(df["d"].dt.strftime("%Y-%m"))`.

Example:

```python
monthly = df.groupby(df["time"].dt.strftime("%Y-%m"))["load"].sum()
```

Use instead:

```python
monthly = df.groupby(df["time"].dt.to_period("M"))["load"].sum()
```

The result has a PeriodIndex instead of text labels. Converting time zones to periods also removes the time zone.

The replacement is advice. pdx does not apply it automatically.

#### object-dates

**Severity:** warning. **Fix:** none.

Reports `df["d"].dt.date` and `dt.time`.

Example:

```python
days = df["time"].dt.date
```

Use instead:

```python
days = df["time"].dt.normalize()
```

normalize returns timestamps at midnight, not Python date objects. Keep dt.date when an external interface needs Python dates. For dt.time, choose the required datetime representation rather than normalizing away the time.

The replacement is advice. pdx does not apply it automatically.

#### apply-on-dates

**Severity:** warning. **Fix:** unsafe: `df["d"] + pd.Timedelta(days=7)`.

Reports `df["d"].apply(lambda t: t + pd.Timedelta(days=7))`, `t.replace(day=1)` and `t.strftime(...)`.

Example:

```python
next_week = df["time"].apply(lambda time: time + pd.Timedelta(days=7))
```

Use instead:

```python
next_week = df["time"] + pd.Timedelta(days=7)
```

#### index-year-mask

**Severity:** warning. **Fix:** none.

Reports `df[df.index.year == 2023]`.

Example:

```python
year = df[df.index.year == 2023]
```

Use instead:

```python
year = df.loc["2023"]
```

Use the label example on a sorted DatetimeIndex. It is a label selection, not a rewrite for every kind of index.

The replacement is advice. pdx does not apply it automatically.


The `rolling-apply` fixes for sum, mean, std and var are unsafe, because the window methods keep
running totals, so values far apart in size can give another result. For a function with no
window method the message names `raw=True` and `engine="numba"`. `apply-on-dates` writes
`df["d"] - pd.to_timedelta(df["d"].dt.day - 1, unit="D")` for `replace(day=1)`, which keeps the
time of day. Its fixes are unsafe, because a missing date gives a missing result where the
lambda raised.

### Stated intent

#### merge-without-validate

**Severity:** warning. **Fix:** none.

Reports `merge` without `validate=`, which can duplicate rows.

Example:

```python
joined = left.merge(right, on="key")
```

Use instead:

```python
joined = left.merge(right, on="key", validate="many_to_one")
```

Choose validate to match the data relationship. many_to_one is only the example, not a default pdx inserts. many_to_many does not check key uniqueness.

The replacement is advice. pdx does not apply it automatically.

#### merge-without-on

**Severity:** warning. **Fix:** none.

Reports `merge` without `on=`, which joins on every shared column name.

Example:

```python
joined = left.merge(right, validate="many_to_one")
```

Use instead:

```python
joined = left.merge(right, on="key", validate="many_to_one")
```

Choose the actual join keys. Omitting on makes every shared column name a key.

The replacement is advice. pdx does not apply it automatically.

#### to-csv-index

**Severity:** warning. **Fix:** none.

Reports `df.to_csv(path)` without `index=`.

Example:

```python
df.to_csv(path)
```

Use instead:

```python
df.to_csv(path, index=False)
```

The replacement is advice. pdx does not apply it automatically.


### Reading files

#### read-csv-slow-option

**Severity:** warning. **Fix:** none.

Reports `read_csv(..., engine="python")` and `low_memory=False`, which turn off reading on several threads.

Example:

```python
df = pd.read_csv(path, engine="python")
```

Use instead:

```python
df = pd.read_csv(path)
```

The example needs no Python-engine-only options. Keep engine="python" when the separator or skipfooter requires it. For low_memory=False, specify the required column dtypes rather than dropping it blindly.

The replacement is advice. pdx does not apply it automatically.


`read-csv-slow-option` leaves `engine="python"` alone when the call needs it, for `skipfooter` or
a separator of several characters other than `\s+`.

### Packages

`pdx check` also looks at the project's venv once per run. When the venv has pandas, it warns
about each package below that the venv lacks. The warning points at the project's
`pyproject.toml`, or at the venv when there is none. A project without a venv gets no package
warning, and `pdx hook` never gives one.

#### missing-pyarrow

**Severity:** warning. **Fix:** none.

Text columns are stored as Python strings without it. The `.str` methods ran 3 to 11 times faster with it on 1,000,000 rows.

The warning appears when pyarrow is not installed.

For a project managed with uv:

```sh
uv add pyarrow
```

Add the package to the project environment, not to pdx itself.

#### missing-bottleneck

**Severity:** warning. **Fix:** none.

`std` ran 4 times faster and `median` 1.7 times faster with it on 10,000,000 rows.

The warning appears when bottleneck is not installed.

For a project managed with uv:

```sh
uv add bottleneck
```

Add the package to the project environment, not to pdx itself.

#### missing-pandas-stubs

**Severity:** warning. **Fix:** none.

Without the stubs a type checker does not check calls to pandas.

The warning appears when pandas-stubs is not installed, and the project uses mypy, pyright, basedpyright, ty or pyrefly.

For a project managed with uv:

```sh
uv add --dev pandas-stubs
```

Add the package to the project environment, not to pdx itself.


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
