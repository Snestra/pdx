"""Steps fitted on rows they should not see, and the same steps fitted on the training rows.

A line that pdx reports ends with a comment that names the rule. Each case returns what the
code computes, so a copy fixed with `pdx check --fix` can be compared with this file.
"""

import numpy as np
import pandas as pd
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, cross_validate, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import LabelEncoder, OneHotEncoder, OrdinalEncoder, StandardScaler

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


def split(df):
    X = df[["x1", "x2"]]
    return train_test_split(X, df["y"], test_size=0.3, random_state=0)


@case
def fit_transform_on_test(df):
    X_train, X_test, y_train, y_test = split(df)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.fit_transform(X_test)  # pdx: fit-on-test
    X_val = X_test
    X_val_scaled = StandardScaler().fit_transform(X_val)  # pdx: fit-on-test
    test = df.tail(30)
    codes = OrdinalEncoder().fit_transform(test[["city"]])  # pdx: fit-on-test
    picked = SelectKBest(f_classif, k=1).fit_transform(X_test, y_test)  # pdx: fit-on-test
    return X_train_scaled, X_test_scaled, X_val_scaled, codes, picked


@case
def fit_on_test(df):
    X_train, X_test, y_train, y_test = split(df)
    model = LogisticRegression().fit(X_test, y_test)  # pdx: fit-on-test
    scaler = StandardScaler()
    scaler.fit(X_test)  # pdx: fit-on-test
    return model.score(X_test, y_test), scaler.mean_


@case
def fit_on_train(df):
    X_train, X_test, y_train, y_test = split(df)
    X_val = X_test
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    model = LogisticRegression().fit(X_train_scaled, y_train)
    calibrated = LogisticRegression().fit(X_val, y_test)
    latest = scaler.fit_transform(X_train)
    return model.score(X_test_scaled, y_test), calibrated.coef_, latest


@case
def fit_before_split(df):
    X = df[["x1", "x2"]]
    y = df["y"]
    X_scaled = StandardScaler().fit_transform(X)  # pdx: fit-before-split
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.3, random_state=0)
    return LogisticRegression().fit(X_train, y_train).score(X_test, y_test)


@case
def fit_columns_before_split(df):
    numeric = ["x1", "x2"]
    df[numeric] = StandardScaler().fit_transform(df[numeric])  # pdx: fit-before-split
    train, test = train_test_split(df, random_state=0)
    return train.shape, test.shape


@case
def resample_before_split(df):
    from imblearn.over_sampling import SMOTE

    X_more, y_more = SMOTE(random_state=0).fit_resample(df[["x1", "x2"]], df["y"])  # pdx: fit-before-split
    return train_test_split(X_more, y_more, random_state=0)


@case
def split_before_fit(df):
    y = LabelEncoder().fit_transform(df["y"])
    X_train, X_test, y_train, y_test = train_test_split(df[["x1", "x2"]], y, test_size=0.3, random_state=0)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_all = StandardScaler().fit_transform(df[["x1", "x2"]])
    return LogisticRegression().fit(X_train_scaled, y_train).score(scaler.transform(X_test), y_test), X_all.shape


@case
def cross_val_on_fitted_data(df):
    X = df[["x1", "x2"]]
    y = df["y"]
    model = LogisticRegression()
    X_picked = SelectKBest(f_classif, k=1).fit_transform(X, y)  # pdx: cross-val-on-fitted-data
    scores = cross_val_score(model, X_picked, y, cv=3)
    inline = cross_val_score(model, StandardScaler().fit_transform(X), y, cv=3)  # pdx: cross-val-on-fitted-data
    more = cross_validate(model, StandardScaler().fit_transform(X), y, cv=3)["test_score"]  # pdx: cross-val-on-fitted-data
    return scores, inline, more


@case
def cross_val_on_a_pipeline(df):
    X = df[["x1", "x2"]]
    return cross_val_score(make_pipeline(StandardScaler(), LogisticRegression()), X, df["y"], cv=3)


@case
def get_dummies_on_test(df):
    X_train, X_test = train_test_split(df[["city", "x1"]], test_size=0.1, random_state=0)
    train_columns = pd.get_dummies(X_train).columns
    X_test_dummies = pd.get_dummies(X_test)  # pdx: get-dummies-on-test
    test_df = pd.get_dummies(X_test, columns=["city"])  # pdx: get-dummies-on-test
    return list(train_columns), list(X_test_dummies.columns), list(test_df.columns)


@case
def one_hot_fitted_on_train(df):
    X_train, X_test = train_test_split(df[["city", "x1"]], test_size=0.1, random_state=0)
    encoder = OneHotEncoder(handle_unknown="ignore").fit(X_train[["city"]])
    aligned = pd.get_dummies(X_test).reindex(columns=pd.get_dummies(X_train).columns, fill_value=0)
    return encoder.transform(X_test[["city"]]).shape, aligned.shape, pd.get_dummies(df).shape
