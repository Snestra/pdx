# xpd

xpd is an opinionated linter for Python library habits that make code slow or wrong, starting
with pandas and scikit-learn.
It parses each file once with [ast-grep](https://ast-grep.github.io/), runs files in parallel,
and starts no Python on the hot path, so it is fast enough to run after every edit a coding
agent makes.

## Install

```sh
uv tool install xpd
```

Or run it once without installing:

```sh
uvx xpd check .
```

Before version 0.7.0 the package was `pdx-lint` and the command was `pdx`.

## First run

```sh
xpd check .
```

xpd prints one line per issue and a summary. Fix every `error`. Fix a `warning` unless you can
say why the pattern is right in that spot.

`xpd check . --fix` applies safe fixes. `xpd check . --fix --unsafe-fixes` also applies fixes
that may change behavior, so read the diff afterwards.

Next: [Commands](commands.md) for every command, or [Claude Code](claude-code.md) to lint each
agent edit.
