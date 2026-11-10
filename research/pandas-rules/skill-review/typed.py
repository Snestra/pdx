import pandas as pd

source_data = pd.DataFrame({"load": [1.0], "wind": [2.0], "k": ["a"]})
output_columns = ["residual_load"]

a = source_data.assign(residual_load=lambda df: df["load"] - df["wind"])[output_columns]  # lambda, correct
b = source_data.assign(residual_load=lambda df: df["k"].str.uper())  # lambda, method typo
c = source_data.assign(residual_load=lambda df: df["load"].clip(lowr=0))  # lambda, keyword typo
d = source_data.assign(residual_load=pd.col("load") - pd.col("wind"))[output_columns]  # pd.col, correct
e = source_data.assign(residual_load=pd.col("k").str.uper())  # pd.col, method typo
f = source_data.assign(residual_load=pd.col("load").clip(lowr=0))  # pd.col, keyword typo
g = source_data.select(residual_load=pd.col("load") - pd.col("wind"))  # select, correct
h = source_data.loc[pd.col("load") > 0]  # loc with pd.col, correct
i = source_data.filter(cond=pd.col("load") > 0)  # filter(cond=), correct
reveal_type(pd.col("load") - pd.col("wind"))
reveal_type(a)
