import pandas as pd
df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
result = df.assign(w=df["v"] * 3)
