"""Splits and models that draw from a new seed on every run, and the same with a seed.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes.
"""

import numpy as np
import pandas as pd
from sklearn import cluster
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import KFold, ShuffleSplit, train_test_split

CASES = {}


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame(n=300, seed=0):
    r = np.random.default_rng(seed)
    city = r.choice(["berlin", "paris", "rome", "oslo"], n, p=[0.4, 0.3, 0.25, 0.05])
    x1 = r.normal(size=n)
    x2 = r.normal(size=n)
    y = ((city == "berlin") * 1.5 + x1 + r.normal(scale=0.5, size=n) > 0.8).astype(int)
    return pd.DataFrame({"city": city, "x1": x1, "x2": x2, "y": y})


@case
def missing_random_state(df):
    X = df[["x1", "x2"]]
    y = df["y"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)  # xpd: missing-random-state
    model = RandomForestClassifier(n_estimators=10).fit(X_train, y_train)  # xpd: missing-random-state
    groups = cluster.KMeans(n_clusters=3).fit_predict(X)  # xpd: missing-random-state
    folds = KFold(n_splits=5, shuffle=True)  # xpd: missing-random-state
    splits = ShuffleSplit(5)  # xpd: missing-random-state
    return model.score(X_test, y_test), groups, folds.get_n_splits(), splits.get_n_splits()


@case
def with_random_state(df):
    X = df[["x1", "x2"]]
    y = df["y"]
    params = {"n_estimators": 10, "random_state": 0}
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    past, future = train_test_split(X, shuffle=False)
    model = RandomForestClassifier(n_estimators=10, random_state=0).fit(X_train, y_train)
    other = RandomForestClassifier(**params).fit(X_train, y_train)
    plain = LogisticRegression().fit(X_train, y_train)
    return model.score(X_test, y_test), other.score(X_test, y_test), plain.score(X_test, y_test), KFold(n_splits=5).get_n_splits(), KFold(5, shuffle=True, random_state=1).get_n_splits(), len(past), len(future)
