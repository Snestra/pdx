"""Shows what each form does when something is wrong: an error, or a frame with silent missing values."""
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
print("pandas", pd.__version__)
source = pd.DataFrame({"load": [10.0, 20.0, 30.0], "wind": [1.0, 2.0, 3.0], "k": ["a", "b", "c"]}, index=[0, 1, 2])
other = pd.DataFrame({"solar": [5.0, 6.0, 7.0]}, index=[1, 2, 3])


def show(label, fn):
    try:
        out = fn()
        text = out.to_dict("list") if isinstance(out, pd.DataFrame) else repr(out)
        print(f"{label}\n    returns {text}")
    except Exception as e:
        print(f"{label}\n    raises {type(e).__name__}: {' '.join(str(e).split())[:150]}")


show("missing column, lambda", lambda: source.assign(x=lambda df: df["sloar"] + 1))
show("missing column, pd.col", lambda: source.assign(x=pd.col("sloar") + 1))
show("missing column, select", lambda: source.select(x=pd.col("sloar") + 1))
show("missing output column, assign()[list]", lambda: source.assign(x=lambda df: df["load"] + 1)[["x", "y"]])
show("missing output column, select(list)", lambda: source.assign(x=lambda df: df["load"] + 1).select(["x", "y"]))
show("missing output column, filter(items=list)", lambda: source.assign(x=lambda df: df["load"] + 1).filter(items=["x", "y"]))
show("series from another frame with a different index, assign", lambda: source.assign(residual=source["load"] - other["solar"]))
show("series from another frame with a different index, bracket assignment", lambda: (lambda d: (d.__setitem__("solar", other["solar"]), d)[1])(source.copy()))
show("array of the wrong length, assign", lambda: source.assign(x=np.array([1.0, 2.0])))
show("method typo, lambda (fails when assign runs)", lambda: source.assign(x=lambda df: df["k"].str.uper()))
print("method typo, pd.col (fails when the expression is built, before assign runs)")
try:
    expr = pd.col("k").str.uper()
    print("    built", expr)
except Exception as e:
    print(f"    raises {type(e).__name__}: {' '.join(str(e).split())[:150]}")
show("np.where on a lambda column", lambda: source.assign(x=lambda df: np.where(df["load"] > 15, 1, 0)))
show("np.where on pd.col", lambda: source.assign(x=np.where(pd.col("load") > 15, 1, 0)))
show("row-wise maximum of two columns, lambda", lambda: source.assign(x=lambda df: df[["load", "wind"]].max(axis=1)))
show("later column uses an earlier one, lambda", lambda: source.assign(a=lambda df: df["load"] * 2, b=lambda df: df["a"] + 1))
show("later column uses an earlier one, pd.col", lambda: source.assign(a=pd.col("load") * 2, b=pd.col("a") + 1))
show("later column uses an earlier one, select", lambda: source.select(a=pd.col("load") * 2, b=pd.col("a") + 1))
show("select with a named list plus computed columns", lambda: source.select(["load", "wind"], residual=pd.col("load") - pd.col("wind")))
show("select reuses a selected name", lambda: source.select("load", load=pd.col("load") * 2))
show("assign reuses an existing name", lambda: source.assign(load=pd.col("load") * 2)[["load"]])
print("repr of an expression:", repr(pd.col("load") - pd.col("wind") - 1))
