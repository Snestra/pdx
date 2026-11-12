"""Calls whose default hides what the code is meant to do, and calls that say it.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes.
"""

import io

import pandas as pd

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame():
    return pd.DataFrame({"k": ["a", "b", "c"], "v": [1, 2, 3]})


@case
def merge_without_on(df):
    other = pd.DataFrame({"k": ["a", "b"], "w": [10, 20]})
    return df.merge(other, validate="one_to_one")  # xpd: merge-without-on


@case
def merge_with_on(df):
    other = pd.DataFrame({"k": ["a", "b"], "w": [10, 20]})
    return df.merge(other, on="k", validate="one_to_one"), df.merge(other, how="cross")  # xpd: merge-without-validate


@case
def to_csv_index(df):
    return df.to_csv()  # xpd: to-csv-index


@case
def to_csv_with_index(df):
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    return buffer.getvalue(), df.set_index("k").to_csv(index=True)
