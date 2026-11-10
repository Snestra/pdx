"""Times the same pandas calls with and without the optional performance libraries. Best of 5, frame in memory."""
import gc, importlib.util, json, sys, time, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
has = lambda m: importlib.util.find_spec(m) is not None
libs = [m for m in ("numexpr", "bottleneck", "numba", "pyarrow") if has(m)]
def frame(n):
    r = np.random.default_rng(0)
    b = r.normal(size=n); b[r.random(n) < 0.05] = np.nan
    return pd.DataFrame({"a": r.integers(0, 100, n), "b": b, "w": r.random(n) + 0.1, "x": r.normal(size=n),
                         "k": r.choice([f"g{i:04d}" for i in range(1000)], n)})
def best(fn, reps=5):
    ts = []
    for _ in range(reps):
        gc.collect(); t = time.perf_counter(); fn(); ts.append(time.perf_counter() - t)
    return round(min(ts) * 1e3, 3)
out = {"libs": libs, "pandas": pd.__version__, "python": sys.version.split()[0]}
for n in (1_000_000, 10_000_000):
    df = frame(n); num = df[["b", "w", "x"]]; tag = f"{n // 1_000_000}M"
    cases = {
        "series arithmetic a*w+b": lambda: df["a"] * df["w"] + df["b"],
        "frame arithmetic num*2+1": lambda: num * 2 + 1,
        "mask (a>50)&(x<0)": lambda: (df["a"] > 50) & (df["x"] < 0),
        "sum": lambda: df["b"].sum(), "mean": lambda: df["b"].mean(), "std": lambda: df["b"].std(),
        "median": lambda: df["b"].median(), "max": lambda: df["b"].max(),
        "frame mean": lambda: num.mean(), "frame median": lambda: num.median(), "frame std": lambda: num.std(),
    }
    for k, fn in cases.items(): out[f"{tag} {k}"] = best(fn)
df = frame(1_000_000); small = df.iloc[:200_000]
def spread(w): return w.max() - w.min()
def gmean(values, index): return values.mean()
def rowsum(row): return row[0] + row[1]
out["rolling.apply raw=True (200k)"] = best(lambda: small["x"].rolling(20).apply(spread, raw=True), 2)
out["groupby.agg python func (1M, 1000 groups)"] = best(lambda: df.groupby("k")["x"].agg(lambda v: v.max() - v.min()), 2)
out["rolling.mean builtin (1M)"] = best(lambda: df["x"].rolling(20).mean())
if has("numba"):
    t = time.perf_counter(); small["x"].rolling(20).apply(spread, raw=True, engine="numba"); out["rolling.apply engine=numba first call (200k)"] = round((time.perf_counter() - t) * 1e3, 1)
    out["rolling.apply engine=numba (200k)"] = best(lambda: small["x"].rolling(20).apply(spread, raw=True, engine="numba"), 3)
    def gspread(values, index): return values.max() - values.min()
    t = time.perf_counter(); df.groupby("k")["x"].agg(gspread, engine="numba"); out["groupby.agg engine=numba first call (1M)"] = round((time.perf_counter() - t) * 1e3, 1)
    out["groupby.agg engine=numba (1M, 1000 groups)"] = best(lambda: df.groupby("k")["x"].agg(gspread, engine="numba"), 3)
    t = time.perf_counter(); df["x"].rolling(20).mean(engine="numba"); out["rolling.mean engine=numba first call (1M)"] = round((time.perf_counter() - t) * 1e3, 1)
    out["rolling.mean engine=numba (1M)"] = best(lambda: df["x"].rolling(20).mean(engine="numba"), 3)
    try:
        t = time.perf_counter(); small[["w", "x"]].apply(rowsum, axis=1, raw=True, engine="numba"); out["apply axis=1 engine=numba first call (200k)"] = round((time.perf_counter() - t) * 1e3, 1)
        out["apply axis=1 engine=numba (200k)"] = best(lambda: small[["w", "x"]].apply(rowsum, axis=1, raw=True, engine="numba"), 3)
    except Exception as e: out["apply axis=1 engine=numba"] = f"{type(e).__name__}: {str(e)[:80]}"
out["apply axis=1 raw=True python (200k)"] = best(lambda: small[["w", "x"]].apply(rowsum, axis=1, raw=True), 2)
out["column form w+x (200k)"] = best(lambda: small["w"] + small["x"])
print(json.dumps(out))
