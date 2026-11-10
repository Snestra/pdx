import pandas as pd

df = pd.DataFrame({"a": [1, 2], "k": [1, 2]})
other = df.copy()
df["a"] = df["a"] * 2
df = df.dropna()
m = df.merge(other, on="k", validate="one_to_one")
frames = [pd.read_csv(f) for f in ["x.csv"]]
out = pd.concat(frames)
