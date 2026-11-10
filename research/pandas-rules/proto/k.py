import pandas as pd
a = df.groupby("k").apply(lambda g: g["k"].iloc[0] + str(g["a"].sum()))
b = df.groupby("k").apply(lambda g: g["a"].sum())
c = df.groupby(["k", "s"]).apply(lambda g: g["s"].iloc[0])
