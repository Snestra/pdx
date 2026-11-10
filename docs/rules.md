# Rules

## pandas

The rules follow pandas 3, where copy-on-write is always on. A fix that writes `pd.` or `np.`
applies only in a file that imports pandas as `pd` or numpy as `np`. In any other file pdx
reports the issue without a fix.

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
| `lambda-column` | warning | `df.assign(c=lambda d: d["a"] + 1)` and `df.loc[lambda d: d["a"] > 50]` | safe: `pd.col("a") + 1` |
| `sort-then-reset-index` | warning | `df.sort_values("b").reset_index(drop=True)`, also after `sort_index`, `dropna`, `drop_duplicates`, `explode` and `sample` | safe: `df.sort_values("b", ignore_index=True)` |
| `set-index-then-resample` | warning | `df.set_index("d").resample("D").sum()` | safe: `df.resample("D", on="d").sum()` |
| `subtract-shift` | warning | `df["b"] - df["b"].shift()` | safe: `df["b"].diff()` |
| `range-mask` | warning | `(df["a"] >= 10) & (df["a"] <= 20)` | safe: `df["a"].between(10, 20)` |

`lambda-column` rewrites a lambda only when every use of its parameter is `d["name"]` and the body
has no plain function call such as `len(d)`, and no `if`, `and`, `or`, `not` or `in`.
`set-index-then-resample` applies only when an aggregation such as `sum` or `agg` follows, because
upsampling with `asfreq` raises with `on=`. `range-mask` leaves a plain name alone, because it may
be a numpy array. `subtract-shift` gives booleans for a boolean column, where the subtraction gave
numbers, so it leaves a comparison alone.

### Python work per row or per value

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `apply-known-function` | warning | `df["b"].apply(pd.isna)`, `df["s"].apply(len)`, `df["raw"].apply(pd.to_datetime)` and `df["b"].apply(lambda v: round(v, 2))` | safe: `df["b"].isna()`, `df["s"].str.len()`. unsafe: `pd.to_datetime(df["raw"])`, `df["b"].round(2)` |
| `literal-contains` | warning | `df["s"].str.contains("ta_")`, a pattern with no regex character | safe: `str.contains("ta_", regex=False)` |
| `copy-after-indexing` | warning | `df[["a", "b"]].copy()`, `df[mask].copy()` and `df.loc[...].copy()` | safe: drop `.copy()` |
| `no-iterrows` | warning | `df.iterrows()`, a row-by-row loop | none |
| `concat-in-loop` | warning | `pd.concat` inside a loop, which is quadratic | none |

`apply-known-function` reports only a column taken by a text label, because on a frame `apply`
works per column. Its `pd.to_datetime` fix is unsafe, because a call per value parses each text
on its own, and the whole column must share one format. The `round` fix is unsafe, because
Python and numpy round some halfway values differently. `copy-after-indexing` leaves a single text
label and a slice alone, because on a dict or a numpy array the copy keeps a later write away
from the original.

### groupby, agg and transform

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `groupby-lambda` | warning | `g["b"].agg(lambda v: v.mean())`, `g.agg(np.sum)` and `pivot_table(aggfunc=np.mean)` | safe: `"mean"`, `"sum"` |
| `groupby-lambda-window` | warning | `g["b"].transform(lambda v: v.cumsum())` | safe: `g["b"].cumsum()` |

`groupby-lambda` leaves a lambda inside a list alone, because the result column would get a new
name. It also leaves `np.median`, `np.std` and `np.var` alone, because they treat missing values
and degrees of freedom differently from the named methods.

### Time series

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `rolling-apply` | warning | `rolling(20).apply(lambda w: w.mean())`, and `rolling(20).apply(f)` without `raw=True` | safe: `rolling(20).mean()`. The `raw=True` case has no fix |

### Stated intent

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `merge-without-validate` | warning | `merge` without `validate=`, which can duplicate rows | none |

## Write a rule

Rules are [ast-grep rules](https://ast-grep.github.io/guide/rule-config.html) in `.yml` files,
compiled into the binary. A pack lives at `rules/<module>/`, where `<module>` is the name you
import, such as `rules/pandas/no-iterrows.yml`. A file may hold several rule documents with the
same id, one per shape.

A rule may have one ast-grep `fix:`. It must then say whether the fix keeps what the code does,
with `metadata: { fix: safe }` or `metadata: { fix: unsafe }`. A fix may write `pd.` or `np.`,
and pdx applies it only in a file that imports pandas as `pd` or numpy as `np`.

Add a file, rebuild, and check it against a sample:

```sh
cargo build --release
target/release/pdx check samples/bad.py
cp samples/bad.py /tmp/bad.py && target/release/pdx check /tmp/bad.py --fix --unsafe-fixes
```

The files in `samples/pandas/` mark each line a rule reports with a comment that names the rule.

A new folder under `rules/` is a new pack, with no Rust change. Its rules run only on files that
import the module.
