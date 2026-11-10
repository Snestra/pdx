# Rules

## pandas

The rules follow pandas 3, where copy-on-write is always on.

| Rule | Severity | Catches | Fix |
| --- | --- | --- | --- |
| `no-iterrows` | warning | `df.iterrows()`, a row-by-row loop | none |
| `no-inplace` | warning | `inplace=True`, which gives no speedup and blocks chaining | unsafe: `df = df.dropna()` |
| `merge-without-validate` | warning | `merge` without `validate=`, which can duplicate rows | none |
| `concat-in-loop` | warning | `pd.concat` inside a loop, which is quadratic | none |
| `chained-assignment` | error | `df["a"][i] = v`, which writes to a copy | unsafe: `df.loc[i, "a"] = v` |

The `no-inplace` fix applies only to a call that stands alone as a statement, on a name, attribute
or subscript. It drops comments between the call's arguments.

## Write a rule

Rules are [ast-grep rules](https://ast-grep.github.io/guide/rule-config.html), one per `.yml`
file, compiled into the binary. A pack lives at `rules/<module>/`, where `<module>` is the
name you import, such as `rules/pandas/no-iterrows.yml`.

A rule may have one ast-grep `fix:`. It must then say whether the fix keeps what the code does,
with `metadata: { fix: safe }` or `metadata: { fix: unsafe }`.

Add a file, rebuild, and check it against a sample:

```sh
cargo build --release
target/release/pdx check samples/bad.py
cp samples/bad.py /tmp/bad.py && target/release/pdx check /tmp/bad.py --fix --unsafe-fixes
```

A new folder under `rules/` is a new pack, with no Rust change. Its rules run only on files that
import the module.
