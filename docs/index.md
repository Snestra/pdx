# pdx

pdx lints Python code for library habits that make it slow or wrong, starting with pandas.
It parses each file once with [ast-grep](https://ast-grep.github.io/), runs files in parallel,
and starts no Python on the hot path, so it is fast enough to run after every edit a coding
agent makes.

## Install

```sh
uv tool install pdx-lint
```

Or run it once without installing:

```sh
uvx --from pdx-lint pdx check .
```

The package is `pdx-lint` because the name `pdx` is taken on PyPI and crates.io. The command
is `pdx`.

## First run

```sh
pdx check .
```

pdx prints one line per issue and a summary that names the pandas version and rule set it used.
Fix every `error`. Fix a `warning` unless you can say why the pattern is right in that spot.

Next: [Commands](commands.md) for every command, or [Claude Code](claude-code.md) to lint each
agent edit.
