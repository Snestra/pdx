# Rules

## pandas

| Rule | Severity | Catches |
| --- | --- | --- |
| `no-iterrows` | warning | `df.iterrows()`, a row-by-row loop |
| `no-inplace` | warning | `inplace=True`, which gives no speedup and blocks chaining |
| `merge-without-validate` | warning | `merge` without `validate=`, which can duplicate rows |
| `concat-in-loop` | warning | `pd.concat` inside a loop, which is quadratic |
| `chained-assignment` | warning on pandas 2, error on 3 | `df["a"][i] = v`, which writes to a copy |

## Write a rule

Rules are [ast-grep rules](https://ast-grep.github.io/guide/rule-config.html), one per `.yml`
file, compiled into the binary. A pack lives at `rules/<module>/`, where `<module>` is the
name you import:

```text
rules/pandas/
├── common/   rules for every version
├── v2/       rules for pandas 2.x
└── v3/       rules for pandas 3 and later
```

Add a file, rebuild, and check it against a sample:

```sh
cargo build --release
target/release/pdx check samples/bad.py
```

A new folder under `rules/` is a new pack, with no Rust change. Its rules run only on files that
import the module.
