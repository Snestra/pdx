"""read_csv options that turn off reading on several threads, and options that need them.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes.
"""

import io

import pandas as pd

CASES = {}
TEXT = "a,b\n1,x\n2,y\n3,z\n"


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame():
    return None


@case
def read_csv_slow_option(_):
    return (
        pd.read_csv(io.StringIO(TEXT), engine="python"),  # pdx: read-csv-slow-option
        pd.read_csv(io.StringIO(TEXT), low_memory=False),  # pdx: read-csv-slow-option
    )


@case
def read_csv_python_engine_needed(_):
    return (
        pd.read_csv(io.StringIO(TEXT + "total\n"), engine="python", skipfooter=1),
        pd.read_csv(io.StringIO("a::b\n1::2\n"), engine="python", sep="::"),
        pd.read_csv(io.StringIO(TEXT), dtype={"a": "int64"}),
    )
