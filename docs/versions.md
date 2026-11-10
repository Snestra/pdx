# Library versions

Each library has a rule pack with rules for every version and rules for one major version.
pdx picks the set for the version your project has installed.

## Where pdx looks

1. `$VIRTUAL_ENV`, then the nearest `.venv` folder above the working directory.
2. Otherwise `python3` on `PATH`. pdx asks it once for its site folders and caches the answer
   in `~/.cache/pdx/site-dirs`. A shim from a version manager such as mise or pyenv is asked
   every time, because the shim picks a different Python per project.

pdx reads the version from the `<module>-<version>.dist-info` folder, so an upgrade shows up on
the next run.

## Which set applies

pdx uses the newest set at or below the installed major version. A version older than every set
gets the oldest set. When the library is not installed, the newest set applies.

## Pinning

To lint for a version you don't have installed:

```sh
pdx check . --pin pandas=2
PDX_PIN=pandas=2 pdx check .
```

A `--pin` flag wins over `PDX_PIN` for the same library.
