"""Times the code shape from the old skill against the pandas 3.0 and 3.1 forms, on a narrow and a wide frame.

Best of 7 runs, frame in memory. Prints one JSON line per form.
"""
import gc
import json
import sys
import time
import tracemalloc
import warnings

import numpy as np
import pandas as pd

warnings.simplefilter("ignore")
print(json.dumps({"meta": {"pandas": pd.__version__, "python": sys.version.split()[0]}}))


def frame(n, extra):
    r = np.random.default_rng(0)
    data = {name: r.normal(size=n) for name in ("load", "wind", "solar", "outgoing", "incoming")}
    data.update({f"other_{i:03d}": r.normal(size=n) for i in range(extra)})
    return pd.DataFrame(data)


output_columns = ["residual_load", "net_export"]


def skill_shape(source_data):
    return source_data.assign(
        residual_load=lambda df: df["load"] - df["wind"] - df["solar"],
        net_export=lambda df: df["outgoing"] - df["incoming"],
    )[output_columns]


def assign_col(source_data):
    return source_data.assign(
        residual_load=pd.col("load") - pd.col("wind") - pd.col("solar"),
        net_export=pd.col("outgoing") - pd.col("incoming"),
    )[output_columns]


def select_col(source_data):
    return source_data.select(
        residual_load=pd.col("load") - pd.col("wind") - pd.col("solar"),
        net_export=pd.col("outgoing") - pd.col("incoming"),
    )


def select_lambda(source_data):
    return source_data.select(
        residual_load=lambda df: df["load"] - df["wind"] - df["solar"],
        net_export=lambda df: df["outgoing"] - df["incoming"],
    )


def assign_then_select_list(source_data):
    return source_data.assign(
        residual_load=lambda df: df["load"] - df["wind"] - df["solar"],
        net_export=lambda df: df["outgoing"] - df["incoming"],
    ).select(output_columns)


def frame_from_dict(source_data):
    return pd.DataFrame({
        "residual_load": source_data["load"] - source_data["wind"] - source_data["solar"],
        "net_export": source_data["outgoing"] - source_data["incoming"],
    })


FORMS = [skill_shape, assign_col, select_col, select_lambda, assign_then_select_list, frame_from_dict]
for label, n, extra in (("5 columns, 1,000,000 rows", 1_000_000, 0), ("205 columns, 1,000,000 rows", 1_000_000, 200),
                        ("2,005 columns, 100,000 rows", 100_000, 2000)):
    source = frame(n, extra)
    want = skill_shape(source)
    for form in FORMS:
        ts = []
        for _ in range(7):
            gc.collect()
            t = time.perf_counter()
            got = form(source)
            ts.append(time.perf_counter() - t)
        tracemalloc.start()
        form(source)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        try:
            pd.testing.assert_frame_equal(want, got, check_exact=True)
            same = "identical"
        except AssertionError as e:
            same = "DIFFERS " + " ".join(str(e).split())[:80]
        print(json.dumps({"frame": label, "form": form.__name__, "ms": round(min(ts) * 1e3, 3), "peak_mb": round(peak / 1e6, 1), "result": same}), flush=True)
