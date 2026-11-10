# Embedded in the pdx binary (include_str!) and run with the project's Python.
# Usage: python -c <this> PATH  → prints JSON column profile to stdout.
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError as e:
    sys.exit(f"pdx profile needs pandas in the project's Python. {e}")


def unique_count(s: pd.Series) -> int | None:
    try:
        return int(s.nunique(dropna=True))
    except TypeError:  # cells hold unhashable values such as lists or dicts
        return None


path = Path(sys.argv[1])
readers = {
    ".csv": pd.read_csv,
    ".parquet": pd.read_parquet,
    ".feather": pd.read_feather,
    ".json": pd.read_json,
    ".xlsx": pd.read_excel,
}
reader = readers.get(path.suffix.lower())
if reader is None:
    sys.exit(f"pdx profile: unsupported file type {path.suffix!r}")
try:
    df = reader(path)
except ImportError as e:  # pandas names the optional package it needs, such as openpyxl
    sys.exit(f"pdx profile: reading {path.suffix} files needs an extra package. {e}")
except OSError as e:
    sys.exit(f"pdx profile: cannot read {path}. {e}")

mem = df.memory_usage(deep=True)
cols = []
for c in df.columns:
    s = df[c]
    cols.append(
        {
            "column": str(c),
            "dtype": str(s.dtype),
            "nulls": int(s.isna().sum()),
            "unique": unique_count(s),
            "memory_bytes": int(mem[c]),
        }
    )
print(
    json.dumps(
        {
            "file": str(path),
            "pandas": pd.__version__,
            "rows": len(df),
            "memory_bytes": int(mem.sum()),
            "columns": cols,
        }
    )
)
