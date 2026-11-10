---
name: pdx
description: "pandas code quality: run pdx to lint pandas code for bad habits, profile data files, and prove refactors are equivalent."
---

# pdx

Use `pdx` whenever you write or change pandas code. `pdx -h` and
`pdx <command> -h` are the source of truth; prefer them over this file.

- `pdx check <paths…> --format json`: lint. Fix every `error`. Fix `warning`s
  unless you can state why the pattern is right here. Don't silence rules.
- `pdx profile <data file>`: dtypes, nulls, cardinality, memory. Run it before
  choosing methods, so choices are based on the real data.
- `pdx equiv old.py new.py`: both scripts must assign `result`. Run it after
  any refactor of pandas logic; a refactor isn't done until it prints
  `"equivalent": true`.

Rules adapt to the project's installed pandas major version. Output says
which version and rule set (`v2`/`v3`) were used.
