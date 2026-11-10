import pandas as pd
df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
rows = []
for _, r in df.iterrows():
    rows.append(r["v"] * 2)
df["w"] = rows
result = df
