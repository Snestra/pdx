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
`message` and `fix`: `safe`, `unsafe` or `null`. A package warning is about the project and not
about a place in a file, so its `line` and `column` are `null`.

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

## graph

```sh
pdx graph [PATHS]... [--format text|json]
```

Prints the dataflow of [Apache Hamilton](https://hamilton.apache.org/) modules. Hamilton turns
every function in a module into a node: the function name is the output and the parameter names
are its inputs. `graph` reads the files and prints which node reads which. It imports nothing
and runs nothing, so it needs no Python and no Hamilton.

Pass the modules you give to one Driver. Together they are one dataflow, as with
`with_modules(loaders, features)`. A folder means every `.py` file in it. A script that builds
the Driver is not a node module, and its functions would show as nodes.

```console
$ pdx graph samples/graph/features.py
samples/graph/features.py:10: (no input) -> uk
samples/graph/features.py:14: (no input) -> dk
samples/graph/features.py:18: uk + dk -> spread
samples/graph/features.py:22: spraed -> spread_sq
inputs: spraed
read by no node: spread, spread_sq
samples/graph/features.py:22: warning: spread_sq reads spraed, which no function defines and which is one edit from the node spread. If it is a typing error, Hamilton raises "Required input spraed not provided" at execute.
pdx: 4 nodes from 4 functions in 1 file, 1 input, 1 warning
```

Each node line is `file:line: inputs -> node`. An input with `?` has a default. `inputs` lists
the names that no function defines, which the caller has to pass. `read by no node` lists the
ends of the dataflow. Then come the findings:

| Finding | Severity | What happens in Hamilton |
| --- | --- | --- |
| A function name defined twice in one file | error | Python keeps the last `def`, so the others never become nodes. Two `@config.when` versions need the names `rate__uk` and `rate__dk` |
| A node defined by two functions | error | The Driver raises "Cannot define function ... more than once" when it is built |
| A plain `def rate` beside `@config.when` on `rate__dk` | error | The same error, once the config selects the version |
| No type hint on the return value or on a parameter | error | The Driver raises "Missing type hint" when it is built |
| An input one edit from a node name | warning | If it is a typing error, execute raises "Required input ... not provided" |
| A decorator that `graph` cannot read | note | Nothing. The graph may lack nodes |

`graph` reads `@config.when` and its relatives, `@extract_columns`, `@extract_fields`,
`@unpack_fields`, `@parameterize`, `@parameterize_values`, `@parameterize_sources`, `@inject`,
`@load_from` and `@save_to`, when their arguments are literals. It prints a note for names that
the file computes, such as `@extract_columns(*COLUMNS)`, and for `@subdag`, `@pipe_input`,
`@pipe_output`, `@mutate`, `@with_columns`, `@does` and `@resolve`. It does not know the config
the Driver gets, so it lists every version of a node. It does not compare type hints between
nodes.

Output is text on a terminal and JSON otherwise. The JSON has `nodes`, each with `name`, `file`,
`line`, `function`, `inputs`, `kind` and `config`; `inputs`, each with `name`, `optional` and
`readers`; `unread`; and `problems`, each with `file`, `line`, `severity` and `message`.

| Exit code | Meaning |
| --- | --- |
| 0 | No error |
| 1 | At least one error |
| 2 | pdx could not run, for example an unreadable path |

## hook

Reads a Claude Code hook event on stdin and lints the `.py` file the edit touched. See
[Claude Code](claude-code.md).

## skill

Prints the agent skill that ships with this version of pdx.
