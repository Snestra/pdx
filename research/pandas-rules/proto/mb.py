import pandas as pd
totals = df.groupby("k")["b"].sum().rename("total").reset_index()
out = df.merge(df.groupby("k")["b"].sum().rename("total").reset_index(), on="k", how="left")
out2 = df.merge(other.groupby("k")["b"].sum().reset_index(), on="k")
df["total"] = df["k"].map(df.groupby("k")["b"].sum())
