import warnings, pandas as pd, numpy as np
print("pandas", pd.__version__)
def t(label, fn):
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try: r = fn(); status = "ok"
        except Exception as e: r = None; status = f"RAISES {type(e).__name__}: {str(e)[:90]}"
    print(f"- {label}: {status} {'WARN ' + w[0].category.__name__ if w else ''} {str(r)[:60] if r is not None and not isinstance(r, (pd.DataFrame, pd.Series)) else ''}")
df = pd.DataFrame({"a": [3, 1, 2], "k": ["x", "y", "x"]})
for m, args, kw in [("drop", (), {"columns": "a"}), ("rename", (), {"columns": {"a": "b"}}), ("rename_axis", ("i",), {}), ("reset_index", (), {}), ("set_index", ("a",), {}),
                    ("dropna", (), {}), ("drop_duplicates", (), {}), ("sort_values", ("a",), {}), ("sort_index", (), {}), ("eval", ("c = a + 1",), {}), ("query", ("a > 1",), {}),
                    ("fillna", (0,), {}), ("replace", (1, 2), {}), ("ffill", (), {}), ("clip", (0, 1), {}), ("interpolate", (), {}), ("mask", (df[["a"]] > 1,), {})]:
    obj = df[["a"]].copy() if m in ("clip", "interpolate", "mask") else df.copy()
    t(f"{m}(inplace=True)", lambda: getattr(obj, m)(*args, inplace=True, **kw))
t('Period.asfreq("M")', lambda: pd.Period("2024", "Y").asfreq("M", how="start"))
t('Period.asfreq("H")', lambda: pd.Period("2024-01", "M").asfreq("H", "start"))
t('Series.asfreq("M") on DatetimeIndex', lambda: pd.Series([1, 2], index=pd.date_range("2024-01-31", periods=2, freq="ME")).asfreq("M"))
t('resample("M") on PeriodIndex', lambda: pd.Series([1, 2], index=pd.period_range("2024-01-01", periods=2, freq="D")).resample("M").sum())
t('merge how="left_anti"', lambda: len(df.merge(df.iloc[:1], on="a", how="left_anti")))
t('merge how="right_anti"', lambda: len(df.merge(df.iloc[:1], on="a", how="right_anti")))
t("g.name inside groupby.apply", lambda: df.groupby("k").apply(lambda g: g.name).tolist())
t("round py vs numpy", lambda: (round(2.675, 2), float(pd.Series([2.675]).round(2).iloc[0]), round(0.125, 2), float(pd.Series([0.125]).round(2).iloc[0])))
