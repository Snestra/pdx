import importlib.util, sys, warnings
import numpy as np, pandas as pd
warnings.simplefilter("ignore")
def load(path):
    spec = importlib.util.spec_from_file_location(path[:-3], path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
def same(x, y):
    if isinstance(x, tuple): return len(x) == len(y) and all(same(a, b) for a, b in zip(x, y))
    if isinstance(x, pd.DataFrame): pd.testing.assert_frame_equal(x, y); return True
    if isinstance(x, pd.Series): pd.testing.assert_series_equal(x, y); return True
    return bool(x == y)
print("pandas", pd.__version__)
b = load("before.py")
for name in sys.argv[1:]:
    a = load(name); ok = bad = 0
    for k, fn in b.CASES.items():
        try: x = fn(b.frame())
        except Exception as e: x = e
        try:
            y = a.CASES[k](a.frame())
            if isinstance(x, Exception): res = f"before raised {type(x).__name__}; after runs"
            else: res = "equal" if same(x, y) else "DIFFERS"
        except AssertionError as e: res = "DIFFERS: " + " ".join(str(e).split())[:230]
        except Exception as e: res = f"AFTER RAISES {type(e).__name__}: {str(e)[:160]}"
        ok += res == "equal"; bad += res != "equal"
        if res != "equal": print(f"  {name} {k}: {res}")
    print(f"{name}: {ok} of {ok + bad} cases give equal results")
