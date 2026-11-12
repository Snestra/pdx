"""A Hamilton module with a typing error, for `pdx graph samples/graph/features.py`.

`spread_sq` asks for `spraed`. No function has that name, so Hamilton takes it for an input the
caller passes, and raises at execute. `pdx graph` prints the graph and points at the name.
"""

import pandas as pd


def uk() -> pd.Series:
    return pd.Series([3.0, 5.0])


def dk() -> pd.Series:
    return pd.Series([1.0, 2.0])


def spread(uk: pd.Series, dk: pd.Series) -> pd.Series:
    return uk - dk


def spread_sq(spraed: pd.Series) -> pd.Series:
    return spraed**2
