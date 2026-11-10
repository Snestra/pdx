# Commands

`pdx -h` and `pdx <command> -h` always match the installed version.

## check

```sh
pdx check [PATHS]... [--format text|json] [--pin MODULE=MAJOR]
```

Lints files and folders. Folders respect `.gitignore`. A library's rules run only on files
that import it.

Output is text on a terminal and JSON otherwise. The JSON has two lists:

- `packages`: for each library, its version, where pdx found it, and the rule set it used.
- `issues`: `package`, `rule`, `file`, `line`, `column`, `severity`, `message`.

| Exit code | Meaning |
| --- | --- |
| 0 | No error-severity issue |
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
