# Commands

`pdx -h` and `pdx <command> -h` always match the installed version.

## check

```sh
pdx check [PATHS]... [--format text|json] [--fix] [--unsafe-fixes]
```

Lints files and folders. Folders respect `.gitignore`. A library's rules run only on files
that import it. A rule for a newer library version than the one installed in the project's venv
is skipped. `check` also warns once per run about a package the project's venv lacks, such as
pyarrow. See [Rules](rules.md).

Some rules have a fix, which is safe or unsafe. A safe fix keeps what the code does. An unsafe
fix may change it, for example because another name still points at the old object.

| Flags | Effect |
| --- | --- |
| none | Lint. `[*]` marks an issue with a safe fix |
| `--fix` | Write the safe fixes, then lint what is left |
| `--unsafe-fixes` | Lint. `[*]` also marks an issue with an unsafe fix |
| `--fix --unsafe-fixes` | Write every fix, then lint what is left |

Output is text on a terminal and JSON otherwise. The JSON has `fixed`, the number of fixes
written, and `issues`, each with `package`, `rule`, `file`, `line`, `column`, `severity`,
`message` and `fix`: `safe`, `unsafe` or `null`.

| Exit code | Meaning |
| --- | --- |
| 0 | No error-severity issue, after fixes |
| 1 | At least one error |
| 2 | pdx could not run, for example an unreadable path |

## profile

```sh
pdx profile data.csv
```

Prints JSON with each column's dtype, null count, unique count and memory use. Reads csv,
parquet, feather, json and xlsx. Runs with the project's Python and needs pandas there.

## equiv

```sh
pdx equiv old.py new.py
```

Runs both scripts and compares the variable `result` each one leaves. DataFrames and Series
are compared with `pandas.testing`, anything else with `numpy.testing`, so a list and an
array with the same values count as equal. Run it after you refactor data logic.

| Exit code | Meaning |
| --- | --- |
| 0 | `{"equivalent": true}` |
| 1 | The results differ, with the difference in `detail` |
| 2 | A script failed, has no `result`, or pandas is missing |

## hook

Reads a Claude Code hook event on stdin and lints the `.py` file the edit touched. See
[Claude Code](claude-code.md).

## skill

Prints the agent skill that ships with this version of pdx.
