"""Forms that raise on pandas 3. The file only runs after the fixes are applied."""
import io

import pandas as pd

pd.set_option("mode.copy_on_write", True)
df = pd.DataFrame({"a": [1.0, None, 3.0], "d": pd.date_range("2024-01-01", periods=3, freq="H")})
out = {
    "applymap": df[["a"]].applymap(lambda v: v * 2),
    "fillna_method": df["a"].fillna(method="ffill"),
    "freq_month": df.resample("M", on="d")["a"].sum(),
    "freq_hour": df["d"].dt.floor("H"),
    "delim_whitespace": pd.read_csv(io.StringIO("a b\n1 2"), delim_whitespace=True),
    "week": df["d"].dt.week,
    "to_period_keeps_M": df["d"].dt.to_period("M"),
}
print({k: type(v).__name__ for k, v in out.items()})
