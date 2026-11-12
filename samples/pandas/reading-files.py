"""Reading and writing files: options that are slow, removed or wrong, and the ones that stay.

A line that xpd reports ends with a comment that names the rule. Each case returns what the
code computes.
"""

import io
import json
import os
import tempfile

import pandas as pd

CASES = {}
TEXT = "a,b\n1,x\n2,y\n3,z\n"
LINES = '{"a": 1, "b": "x"}\n{"a": 2, "b": "y"}\n'


def case(fn):
    CASES[fn.__name__] = fn
    return fn


def frame():
    return None


@case
def read_csv_slow_option(_):
    return (
        pd.read_csv(io.StringIO(TEXT), engine="python"),  # xpd: read-csv-slow-option
        pd.read_csv(io.StringIO(TEXT), low_memory=False),  # xpd: read-csv-slow-option
    )


@case
def read_csv_python_engine_needed(_):
    return (
        pd.read_csv(io.StringIO(TEXT + "total\n"), engine="python", skipfooter=1),
        pd.read_csv(io.StringIO("a::b\n1::2\n"), engine="python", sep="::"),
        pd.read_csv(io.StringIO(TEXT), dtype={"a": "int64"}),
    )


@case
def read_then_head(_):
    return (
        pd.read_csv(io.StringIO(TEXT)).head(2),  # xpd: read-then-head
        pd.read_csv(io.StringIO(TEXT), sep=",").head(),  # xpd: read-then-head
        pd.read_csv(io.StringIO(TEXT)).iloc[:2],  # xpd: read-then-head
    )


@case
def read_first_rows_only(_):
    return pd.read_csv(io.StringIO(TEXT), nrows=2), pd.read_csv(io.StringIO(TEXT), nrows=3).head(2), pd.read_csv(io.StringIO(TEXT)).tail(2)


@case
def read_csv_guessed_separator(_):
    return pd.read_csv(io.StringIO(TEXT), sep=None)  # xpd: read-csv-slow-option


@case
def read_csv_converters(_):
    return pd.read_csv(io.StringIO(TEXT), converters={"a": float})  # xpd: read-csv-converters


@case
def read_csv_dtype(_):
    return pd.read_csv(io.StringIO(TEXT), dtype={"a": float})


@case
def read_json_lines(_):
    return (
        pd.read_json(io.BytesIO(LINES.encode()), lines=True),  # xpd: read-json-lines-engine
        pd.DataFrame([json.loads(line) for line in LINES.splitlines()]),  # xpd: read-json-lines-engine
    )


@case
def read_json_that_stays(_):
    return pd.read_json(io.BytesIO(LINES.encode()), lines=True, engine="pyarrow"), pd.read_json(io.StringIO(LINES), lines=True), pd.read_json(io.StringIO("[" + LINES.replace("\n", ",")[:-1] + "]"))


@case
def to_csv_append_header(_):
    part = pd.read_csv(io.StringIO(TEXT))
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "log.csv")
        part.to_csv(path, mode="a", index=False)  # xpd: to-csv-append-header
        part.to_csv(path, mode="a", index=False)  # xpd: to-csv-append-header
        return pd.read_csv(path)


@case
def to_csv_append_with_header_choice(_):
    part = pd.read_csv(io.StringIO(TEXT))
    with tempfile.TemporaryDirectory() as folder:
        path = os.path.join(folder, "log.csv")
        part.to_csv(path, mode="a", index=False, header=not os.path.exists(path))
        part.to_csv(path, mode="a", index=False, header=False)
        part.to_csv(os.path.join(folder, "other.csv"), index=False)
        return pd.read_csv(path)


@case
def removed_read_and_write_arguments(_):
    part = pd.read_csv(io.StringIO(TEXT))
    writer = pd.ExcelWriter(io.BytesIO())
    writer.save()  # xpd: removed-in-pandas-3
    return (
        pd.read_csv(io.StringIO(TEXT), error_bad_lines=False),  # xpd: removed-in-pandas-3
        pd.read_csv(io.StringIO(TEXT), squeeze=True),  # xpd: removed-in-pandas-3
        pd.read_csv(io.StringIO(TEXT), date_parser=pd.to_datetime),  # xpd: removed-in-pandas-3
        pd.read_csv(io.StringIO(TEXT), ","),  # xpd: removed-in-pandas-3
        pd.read_excel(io.BytesIO(), squeeze=True),  # xpd: removed-in-pandas-3
        part.to_csv(index=False, line_terminator="\n"),  # xpd: removed-in-pandas-3
        part.to_csv(None, ";"),  # xpd: removed-in-pandas-3, to-csv-index
        part.to_excel(io.BytesIO(), encoding="utf-8"),  # xpd: removed-in-pandas-3
    )


@case
def current_read_and_write_arguments(_):
    part = pd.read_csv(io.StringIO(TEXT), sep=",", on_bad_lines="skip")
    return part.to_csv(index=False, lineterminator="\n"), part.to_csv(None, sep=";", index=False)
