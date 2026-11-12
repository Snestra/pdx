"""Metrics given the wrong input, and the same metrics given the right one.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `pdx check --fix` can be compared with this file.
"""

import numpy as np
import pandas as pd
from sklearn import metrics
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, confusion_matrix, precision_score, r2_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

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


def fitted(df):
    X_train, X_test, y_train, y_test = train_test_split(df[["x1", "x2"]], df["y"], test_size=0.3, random_state=0)
    return LogisticRegression().fit(X_train, y_train), X_test, y_test


@case
def auc_from_labels(df):
    model, X_test, y_test = fitted(df)
    return (
        roc_auc_score(y_test, model.predict(X_test)),  # pdx: auc-from-labels
        average_precision_score(y_test, model.predict(X_test), pos_label=1),  # pdx: auc-from-labels
        roc_auc_score(y_test, model.predict_proba(X_test)[:, 0]),  # pdx: auc-from-labels
    )


@case
def auc_from_a_label_variable(df):
    model, X_test, y_test = fitted(df)
    y_pred = model.predict(X_test)  # pdx: auc-from-labels
    accuracy = accuracy_score(y_test, y_pred)
    return accuracy, roc_auc_score(y_test, y_pred)


@case
def auc_from_scores(df):
    model, X_test, y_test = fitted(df)
    y_pred = model.predict(X_test)
    return (
        roc_auc_score(y_test, model.predict_proba(X_test)[:, 1]),
        roc_auc_score(y_test, model.decision_function(X_test)),
        accuracy_score(y_test, model.predict(X_test)),
        accuracy_score(y_test, y_pred),
    )


@case
def metric_arguments_swapped(df):
    model, X_test, y_test = fitted(df)
    y_true = y_test
    y_pred = model.predict(X_test)
    predictions = model.predict_proba(X_test)[:, 1]
    return (
        precision_score(y_pred, y_test),  # pdx: metric-arguments-swapped
        recall_score(y_pred, y_true, average="macro"),  # pdx: metric-arguments-swapped
        metrics.r2_score(predictions, y_test),  # pdx: metric-arguments-swapped
        confusion_matrix(y_pred, y_test),  # pdx: metric-arguments-swapped
    )


@case
def metric_arguments_in_order(df):
    model, X_test, y_test = fitted(df)
    y_pred = model.predict(X_test)
    y_test_pred = y_pred
    return precision_score(y_test, y_pred), r2_score(y_test, y_test_pred), accuracy_score(y_pred, y_test)
