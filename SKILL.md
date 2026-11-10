---
name: pdx
description: "Python library habits: run pdx to lint code for slow or wrong use of libraries such as pandas, profile data files, and prove refactors are equivalent."
---

# pdx

Use `pdx` whenever you write or change Python code that uses a library pdx has rules for.
`pdx -h` and `pdx <command> -h` are the source of truth; prefer them over this file.

- `pdx check <paths…> --format json`: lint. Fix every `error`. Fix `warning`s
  unless you can state why the pattern is right here. Don't silence rules.
  A `missing-<package>` warning names a package the project lacks. Ask the user
  before you add a dependency.
- `pdx check <paths…> --fix`: apply safe fixes. Add `--unsafe-fixes` for fixes
  that may change behavior, then read the diff.
- `pdx profile <data file>`: dtypes, nulls, cardinality, memory. Run it before
  choosing methods, so choices are based on the real data. Needs pandas.
- `pdx equiv old.py new.py`: both scripts must assign `result`. Run it after
  any refactor of data logic; a refactor isn't done until it prints
  `"equivalent": true`. Needs pandas.
