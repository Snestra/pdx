"""A pipeline of steps, for `pdx graph samples/graph/steps.py`.

Each step takes the frame and returns it with columns added. `pdx graph` reads which step needs
which, and reports what the comments below name.

    features(orders)
    ├── totals()      net and gross amount per order
    ├── shares()      each order's share of its customer's spending
    └── flags()       large and discounted orders
"""

import pandas as pd

LARGE_ORDER = 1000.0
PRICE = "unit_price"


def totals(orders: pd.DataFrame) -> pd.DataFrame:
    gross = orders["quantity"] * orders[PRICE]
    return orders.join(
        pd.DataFrame(index=orders.index).assign(
            gross_amount=gross,
            net_amount=gross - orders["discount"],
        )
    )


def shares(orders: pd.DataFrame) -> pd.DataFrame:
    spent = orders.groupby("customer")["net_amount"].transform("sum")
    return orders.assign(customer_share=orders["net_amount"] / spent)


def discounts(orders: pd.DataFrame) -> pd.DataFrame:
    # warning: the formula of the column gross_amount, written out again
    before_discount = orders[PRICE] * orders["quantity"]
    # warning: writes to the frame it was given
    orders["discount_share"] = orders["discount"] / before_discount
    return orders


def flags(orders: pd.DataFrame) -> pd.DataFrame:
    result = orders.copy()
    result["is_large"] = result["net_amount"] > LARGE_ORDER
    # warning: the same formula as is_large, under another name
    result["over_limit"] = result["net_amount"] > LARGE_ORDER
    result["is_discounted"] = result["discount_share"] > 0
    return result


# warning: the tree in the docstring has no discounts()
def features(orders: pd.DataFrame) -> pd.DataFrame:
    return orders.pipe(totals).pipe(shares).pipe(discounts).pipe(flags)
