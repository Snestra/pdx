# pdx

pdx is an opinionated linter for Python library habits that make code slow or wrong, starting
with pandas.
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

pdx prints one line per issue and a summary. Fix every `error`. Fix a `warning` unless you can
say why the pattern is right in that spot.

`pdx check . --fix` applies safe fixes. `pdx check . --fix --unsafe-fixes` also applies fixes
that may change behavior, so read the diff afterwards.

Next: [Commands](commands.md) for every command, or [Claude Code](claude-code.md) to lint each
agent edit.
