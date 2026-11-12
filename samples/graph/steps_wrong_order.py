"""Two errors in a pipeline, for `xpd graph samples/graph/steps_wrong_order.py`.

`margin()` reads a column that `costs()` adds after it, and `costs_again()` joins a column that
exists. Both raise when the pipeline runs. The steps are run by reassignment here, which reads
the same as `.pipe()`.
"""

import pandas as pd


def margin(orders: pd.DataFrame) -> pd.DataFrame:
    new = pd.DataFrame(index=orders.index).assign(
        margin=orders["revenue"] - orders["total_cost"],
    )
    return orders.join(new)


def costs(orders: pd.DataFrame) -> pd.DataFrame:
    new = pd.DataFrame(index=orders.index).assign(
        total_cost=orders["unit_cost"] * orders["quantity"],
    )
    return orders.join(new)


def costs_again(orders: pd.DataFrame) -> pd.DataFrame:
    new = pd.DataFrame(index=orders.index).assign(
        total_cost=orders["unit_cost"] * orders["quantity"] + orders["shipping"],
    )
    return orders.join(new)


def report(orders: pd.DataFrame) -> pd.DataFrame:
    orders = margin(orders)
    orders = costs(orders)
    orders = costs_again(orders)
    return orders
