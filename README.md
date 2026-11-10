# pdx

pdx is a fast linter for Python library habits that make code slow or wrong, starting with
pandas. It picks the rules for the library version your project has installed, and it is built
to run after every edit a coding agent makes.

```console
$ pdx check samples/bad.py
samples/bad.py:5:15: warning [pandas/no-iterrows] Row-wise loop. Prefer vectorized ops; itertuples() if a loop is unavoidable.
samples/bad.py:6:5: error [pandas/chained-assignment] Chained assignment never updates the original under copy-on-write (pandas 3). Use .loc[row, col] = value.
samples/bad.py:7:11: warning [pandas/no-inplace] inplace=True gives no speedup and blocks chaining. Reassign instead.
samples/bad.py:8:5: warning [pandas/merge-without-validate] merge without validate= can silently duplicate rows.
samples/bad.py:11:11: warning [pandas/concat-in-loop] Concatenating inside a loop is quadratic. Collect frames in a list, concat once.
pdx: 5 issue(s); pandas 3.1.1 (venv, rules v3)
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
| `pdx profile data.csv` | Show dtypes, nulls, unique counts and memory per column. Needs pandas. |
| `pdx equiv old.py new.py` | Check that two scripts leave an equal `result`. Needs pandas. |
| `pdx hook` | Lint the file a Claude Code edit touched. |
| `pdx skill` | Print the agent skill for this version. |

Run `pdx -h` for every flag.

## Documentation

The full guide, including the Claude Code hook setup and how to write a rule, lives at
<https://bjoernaagaard.github.io/pdx/>.

## License

MIT or Apache-2.0, at your choice.
