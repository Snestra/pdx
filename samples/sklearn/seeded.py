"""A file that seeds NumPy. scikit-learn then draws from that seed, so xpd reports nothing here."""

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

np.random.seed(0)
X = np.random.normal(size=(100, 3))
y = (X[:, 0] > 0).astype(int)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = RandomForestClassifier(n_estimators=10).fit(X_train, y_train)
