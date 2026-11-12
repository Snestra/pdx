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
- `pdx graph <files…> --format json`: the dataflow of a file, read without
  running it. Run it after you add, move or rename a step or a node. Fix every
  `error`. Fix `warning`s unless you can state why the code is right.
  - Step code is a function that passes a frame through other functions, as
    `frame.pipe(a).pipe(b)`. Before you add a column, read `pipelines[].steps`
    and reuse a column that exists instead of computing its formula again.
    Return `frame.assign(...)` or `frame.join(...)`, and don't write
    `frame["x"] = ...` on the frame a step was given.
  - Apache Hamilton modules: a `warning` names an input one edit from a node
    name, so check it for a typing error. `inputs` are what the caller passes.
