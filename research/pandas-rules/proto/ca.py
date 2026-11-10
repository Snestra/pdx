import pandas as pd

df = pd.DataFrame({"a": [1, 2, 3], "b": [1.0, 2.0, 3.0]})
df[df["a"] > 1]["b"] = 0
df.loc[df["a"] > 1]["b"] = 0
df["b"][0] = 5
df["a"].values[0] = 9
df["b"].fillna(0, inplace=True)
