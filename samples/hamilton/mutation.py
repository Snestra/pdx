"""Hamilton nodes that write to their inputs, and the same nodes without the write.

A line that xpd reports ends with a comment that names the rule. Hamilton hands one object to
every node that takes it, so `total_uk` is 2.0 when asked for alone and 4.0 after `clipped`.
"""

import pandas as pd
from hamilton.function_modifiers import extract_columns, hamilton_exclude, load_from, value


def raw() -> pd.DataFrame:
    return pd.DataFrame({"uk": [1.0, -2.0, 3.0], "dk": [1.0, 1.0, 1.0]})


def total_uk(raw: pd.DataFrame) -> float:
    return float(raw["uk"].sum())


def clipped(raw: pd.DataFrame) -> pd.DataFrame:
    raw.loc[raw["uk"] < 0, "uk"] = 0  # xpd: node-mutates-input
    return raw


def with_spread(raw: pd.DataFrame, offset: float = 0.0) -> pd.DataFrame:
    raw["spread"] = raw["uk"] - raw["dk"]  # xpd: node-mutates-input
    raw["spread"] += offset  # xpd: node-mutates-input
    del raw["dk"]  # xpd: node-mutates-input
    raw.columns = [name.upper() for name in raw.columns]  # xpd: node-mutates-input
    return raw


@extract_columns("uk")
def doubled(raw: pd.DataFrame) -> pd.DataFrame:
    raw["uk"] = raw["uk"] * 2  # xpd: node-mutates-input
    return raw


def uk_clean(uk: pd.Series) -> pd.Series:
    uk[uk < 0] = 0  # xpd: node-mutates-input
    return uk


def labels(raw: pd.DataFrame, target: str) -> pd.Series:
    return raw.pop(target)  # xpd: node-mutates-input


def settings(defaults: dict, seen: list) -> dict:
    defaults["checked"] = True  # xpd: node-mutates-input
    defaults.update(region="uk")  # xpd: node-mutates-input
    seen.append("settings")  # xpd: node-mutates-input
    return defaults


def plan_area(buildings: pd.DataFrame) -> pd.DataFrame:
    gdf = buildings
    gdf["area"] = gdf["width"] * gdf["depth"]  # xpd: node-mutates-input
    return gdf


# The same results with no write to an input.


def clipped_new(raw: pd.DataFrame) -> pd.DataFrame:
    return raw.assign(uk=raw["uk"].clip(lower=0))


def with_spread_copy(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw.copy()
    raw["spread"] = raw["uk"] - raw["dk"]
    return raw


def with_spread_local(raw: pd.DataFrame) -> pd.DataFrame:
    out = raw.copy()
    out["spread"] = out["uk"] - out["dk"]
    return out


def uk_clean_new(uk: pd.Series) -> pd.Series:
    return uk.clip(lower=0)


def labels_new(raw: pd.DataFrame, target: str) -> pd.Series:
    return raw[target]


def settings_new(defaults: dict) -> dict:
    return {**defaults, "checked": True}


def next_state(state: dict, row: dict) -> dict:
    return state.update(row)


# Functions that are no ordinary nodes.


@load_from.csv(path=value("spend.csv"))
def spend(data: pd.DataFrame) -> pd.DataFrame:
    data["date"] = pd.date_range("2020-01-01", periods=len(data))
    return data


@hamilton_exclude
def excluded(raw: pd.DataFrame) -> pd.DataFrame:
    raw["checked"] = True
    return raw


def _helper(raw: pd.DataFrame) -> pd.DataFrame:
    raw["checked"] = True
    return raw


def run(raw):
    raw["checked"] = True
    return raw


class Writer:
    def write(self, raw: pd.DataFrame) -> pd.DataFrame:
        raw["checked"] = True
        return raw
