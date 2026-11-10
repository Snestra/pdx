import importlib.util, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
def load(path):
    spec = importlib.util.spec_from_file_location(path[:-3], path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def flat(x):
    if isinstance(x, tuple):
        for i in x: yield from flat(i)
    else: yield x
b, a = load("before.py"), load("after_safe.py")
print("pandas", pd.__version__)
inexact = 0
for k, fn in b.CASES.items():
    xs, ys = list(flat(fn(b.frame()))), list(flat(a.CASES[k](a.frame())))
    worst = 0.0; exact = True
    for x, y in zip(xs, ys):
        try:
            if isinstance(x, pd.DataFrame): pd.testing.assert_frame_equal(x, y, check_exact=True)
            elif isinstance(x, pd.Series): pd.testing.assert_series_equal(x, y, check_exact=True)
        except AssertionError:
            exact = False
            xv = x.select_dtypes("number").to_numpy(float) if isinstance(x, pd.DataFrame) else x.to_numpy(float)
            yv = y.select_dtypes("number").to_numpy(float) if isinstance(y, pd.DataFrame) else y.to_numpy(float)
            with np.errstate(all="ignore"):
                rel = np.nanmax(np.abs(xv - yv) / np.maximum(np.abs(xv), 1e-300))
            worst = max(worst, float(rel))
    if not exact: inexact += 1; print(f"  {k}: not bit-identical, largest relative difference {worst:.2e}")
print(f"{len(b.CASES) - inexact} of {len(b.CASES)} cases are bit-identical")
