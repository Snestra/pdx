# pdx

pdx is a fast, opinionated linter for Python library habits that make code slow or wrong,
starting with pandas and scikit-learn. Each library gets one set of rules, written for its current
version. It fixes what it can, and it is built to run after every edit a coding agent makes.

```console
$ pdx check samples/bad.py
samples/bad.py:5:15: warning [pandas/row-loop] A loop over rows runs Python once per row. Compute on whole columns instead, such as df["a"] * df["w"].
samples/bad.py:6:5: error [pandas/chained-assignment] Chained assignment writes to a copy under copy-on-write, so the frame keeps its old values. Assign to df.loc[i, "a"] instead.
samples/bad.py:7:1: warning [pandas/no-inplace] inplace=True gives no speedup and blocks chaining. Reassign instead.
samples/bad.py:8:5: warning [pandas/merge-without-validate] merge without validate= can silently duplicate rows.
samples/bad.py:11:11: warning [pandas/concat-in-loop] Concatenating inside a loop is quadratic. Collect frames in a list, concat once.
pdx: 5 issues, 2 more with --fix --unsafe-fixes
```

## Install

```sh
uv tool install pdx-lint   # or: uvx --from pdx-lint pdx check .
```

The package is `pdx-lint` because the name `pdx` is taken. The command is `pdx`.

## Use

| Command | What it does |
| --- | --- |
| `pdx check [paths]` | Lint files and folders. Exit 1 on any error, 2 if pdx can't run. |
| `pdx check --fix` | Apply safe fixes, then lint. Add `--unsafe-fixes` to apply the rest. |
| `pdx profile data.csv` | Show dtypes, nulls, unique counts and memory per column. Needs pandas. |
| `pdx equiv old.py new.py` | Check that two scripts leave an equal `result`. Needs pandas. |
| `pdx graph features.py` | Print the dataflow of step code or Apache Hamilton modules: what reads what, and what does not connect. |
| `pdx hook` | Lint the file a Claude Code edit touched. |
| `pdx skill` | Print the agent skill for this version. |

Run `pdx -h` for every flag.

## Documentation

The full guide, including the Claude Code hook setup and how to write a rule, lives at
<https://snestra.github.io/pdx/>.

## License

MIT or Apache-2.0, at your choice.
