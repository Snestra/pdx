"""A fix that writes pd. applies only when the file imports pandas as pd.

This file imports pandas under its own name, so xpd reports the issue without a fix.
"""

import pandas

df = pandas.DataFrame({"k": ["x", "y"], "a": [1, 2]})
text = [c for c in df.columns if df[c].dtype == object]  # xpd: object-dtype-check
