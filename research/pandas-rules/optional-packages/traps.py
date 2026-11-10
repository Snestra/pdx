import io

import numpy as np
import pandas as pd

df = pd.DataFrame({"a": [1, 2, 3], "b": [1.0, None, 3.0], "k": ["x", "y", "x"], "d": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"])})

df[df["a"] > 1]["b"] = 0  # chained-assignment
df["b"].fillna(0, inplace=True)  # inplace-on-column
df2 = df.dropna(inplace=True)  # inplace-result-assigned
epoch = df["d"].astype("int64") // 10**9  # epoch-from-int-cast
missing = df[df["b"] == np.nan]  # compare-to-missing
found = 2 in df["a"]  # in-column
mask = df[df["a"] > 1 & df["b"] < 3]  # mask-precedence
df["a"].values[0] = 9  # write-through-values
is_text = df["k"].dtype == object  # object-dtype-check
first = df.groupby("k").apply(lambda g: g["k"].iloc[0])  # groupby-apply-reads-key
m1 = df[["a"]].applymap(lambda v: v * 2)  # removed: applymap
m2 = df["b"].fillna(method="ffill")  # removed: fillna(method=)
m3 = df.resample("M", on="d")["a"].sum()  # removed: freq M
m4 = pd.read_csv(io.StringIO("a b\n1 2"), delim_whitespace=True)  # removed: delim_whitespace
m5 = df["d"].dt.week  # removed: dt.week
m6 = df.append(df)  # removed: append
m7 = df.iteritems()  # removed: iteritems
m8 = pd.to_datetime(["x"], errors="ignore")  # removed: errors=ignore
m9 = df.groupby("k", axis=0).sum()  # removed: groupby axis
d1 = df.astype({"a": "int32"}, copy=False)  # deprecated: copy=
d2 = pd.Timestamp.utcnow()  # deprecated: utcnow
d3 = pd.api.types.is_categorical_dtype(df["k"])  # deprecated
slow = df.apply(lambda r: r["a"] + r["b"], axis=1)  # apply-axis-1 (valid code)
