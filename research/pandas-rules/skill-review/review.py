"""Builds the review of the old skill snippet from the measurement files in this folder."""
import html
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
e = html.escape


def rows(name):
    return [json.loads(line) for line in open(os.path.join(HERE, name))]


shapes = [r for r in rows("shapes-3.1.1.jsonl") if "form" in r]
replace = [r for r in rows("replace-3.1.1.jsonl") if "form" in r]
proposal = open(os.path.join(HERE, "..", "show-me-pdx-pandas-rules.html")).read()
style = re.search(r"<style>(.*?)</style>", proposal, re.S).group(1)
script = re.search(r"<script>.*?</script>", proposal, re.S).group(0)


def ms(v):
    if v >= 1000:
        return f"{v / 1000:.1f} s"
    if v >= 100:
        return f"{v:.0f} ms"
    if v >= 10:
        return f"{v:.1f} ms"
    return f"{v:.2f} ms"


SHAPE_CODE = {
    "skill_shape": "source_data.assign(x=lambda df: ...)[output_columns]",
    "assign_col": 'source_data.assign(x=pd.col("load") - ...)[output_columns]',
    "select_col": 'source_data.select(x=pd.col("load") - ...)',
    "select_lambda": "source_data.select(x=lambda df: ...)",
    "assign_then_select_list": "source_data.assign(x=lambda df: ...).select(output_columns)",
    "frame_from_dict": 'pd.DataFrame({"x": source_data["load"] - ...})',
}
frames = list(dict.fromkeys(r["frame"] for r in shapes))
shape_rows = ""
for form, code in SHAPE_CODE.items():
    cells = "".join(f"<td>{ms(next(r['ms'] for r in shapes if r['form'] == form and r['frame'] == f))}</td>" for f in frames)
    shape_rows += f"<tr><td><code>{e(code)}</code></td>{cells}</tr>"
shape_head = "".join(f"<th>{e(f)}</th>" for f in frames)

FORM_ORDER = ["replace(mapping)", "map(lambda v: mapping.get(v, v))", "category, then rename_categories(mapping)", "map(mapping).fillna(s)"]
keys = sorted({r["keys"] for r in replace})


def replace_table(kind):
    out = ""
    for form in FORM_ORDER:
        cells = ""
        for k in keys:
            r = next(x for x in replace if x["kind"] == kind and x["keys"] == k and x["form"] == form)
            base = next(x for x in replace if x["kind"] == kind and x["keys"] == k and x["form"] == "replace(mapping)")
            slow = ' class="bad"' if r["ms"] > 3 * min(x["ms"] for x in replace if x["kind"] == kind and x["keys"] == k) else ""
            cells += f"<td{slow}>{ms(r['ms'])}</td>"
        out += f"<tr><td><code>{e(form)}</code></td>{cells}</tr>"
    return out


key_head = "".join(f"<th>{k:,} keys</th>" for k in keys)

PAGE = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Review of the transformations skill against measurements</title>
{script}
<style>{style}
  td.bad {{ color: var(--destructive, #f85149); font-weight: 600; }}
  td:first-child code {{ white-space: nowrap; }}
  td code {{ overflow-wrap: anywhere; }}
  .scroll {{ overflow-x: auto; }}
  .verdict {{ border-left: 3px solid var(--primary, var(--chart-1, #6aa3ff)); padding: 2px 0 2px 12px; margin-top: 12px; }}
  h3 {{ margin-top: 18px; }}
</style></head>
<body><div class="wrap">

<section>
  <h2>The assign shape</h2>
  <p class="lead">Your shape costs nothing. Six ways to build the same two columns gave identical frames and the same time, also when the source frame had 205 or 2,005 columns, because copy-on-write lets <code>assign</code> share the untouched columns.</p>
  <div class="scroll"><table><thead><tr><th>Form</th>{shape_head}</tr></thead><tbody>{shape_rows}</tbody></table></div>

  <h3>Where the forms differ</h3>
  <div class="scroll"><table><thead><tr><th>Situation</th><th>lambda in assign</th><th>pd.col</th></tr></thead><tbody>
    <tr><td>A source column is misspelled</td><td><code>KeyError: 'sloar'</code></td><td><code>ValueError: Column 'sloar' not found in given DataFrame. Hint: did you mean one of ['load', 'wind', 'k'] instead?</code></td></tr>
    <tr><td>A function that needs data, such as <code>np.where</code></td><td>Works</td><td><code>ValueError: invalid __array_struct__</code></td></tr>
    <tr><td>A calculation across columns, such as <code>df[["load", "wind"]].max(axis=1)</code></td><td>Works</td><td>Cannot be written, because an expression stands for one column</td></tr>
    <tr><td>A later column uses an earlier one</td><td>Works</td><td>Works</td></tr>
    <tr><td>mypy and pyright with pandas-stubs 3.1.0, on a misspelled method</td><td>Reported</td><td>Reported</td></tr>
    <tr><td>mypy and pyright with pandas-stubs 3.1.0, on correct code</td><td>No error</td><td>No error in <code>assign</code> and <code>.loc</code>. <code>pd.col("load").clip(...)</code> is reported as an error.</td></tr>
  </tbody></table></div>

  <h3>Why a result from assign can be trusted</h3>
  <p>Your sense that the data stays inside the frame matches what I measured. A column read through the lambda or through <code>pd.col</code> comes from the frame itself, so its rows always line up. The one way I found to get a frame back with missing data and no error is to pass a column from another frame: <code>source.assign(residual=source["load"] - other["solar"])</code> returned <code>[nan, 15.0, 24.0]</code> when the two indexes differed. An array of the wrong length raised.</p>

  <h3>The pandas 3.1 methods and type checkers</h3>
  <p>pandas-stubs 3.1.0 does not know <code>DataFrame.select</code> or <code>filter(cond=)</code>. mypy and pyright both report correct calls to them as errors. Three rules in the proposal rewrite code to those two methods, and step 5 recommends pandas-stubs, so a project that follows both would get type errors on correct code.</p>

  <div class="verdict">
    <p><b>What the measurements support.</b> Neither form is faster or safer overall. The lambda works everywhere, and <code>pd.col</code> gives a better error for a misspelled column and is shorter. A rule that rewrites one to the other moves code between two equal forms, and it leaves a mixed style, because <code>np.where</code> and calculations across columns still need the lambda.</p>
  </div>

  <h3>An alternative that keeps what you like</h3>
<pre class="plain">output_columns = ["residual_load", "net_export"]
features = source_data.assign(
    residual_load=pd.col("load") - pd.col("wind") - pd.col("solar"),
    net_export=pd.col("outgoing") - pd.col("incoming"),
)[output_columns]</pre>
  <p class="ev">It keeps <code>assign</code> and the named list. It gains the better error message and drops the repeated <code>lambda df: df[...]</code>. It loses the single style, because some columns will still need a lambda.</p>
</section>

<section>
  <h2>A named list of columns</h2>
  <p class="lead">A named list costs nothing, and the way you apply it is the safe one. With one name missing from the frame, <code>frame[output_columns]</code> and <code>frame.select(output_columns)</code> both raised <code>KeyError: "['y'] not in index"</code>. <code>frame.filter(items=output_columns)</code> returned the frame without the missing column and without an error.</p>
  <div class="verdict">
    <p><b>What the measurements support.</b> Keep the shape. pdx can also enforce it with a new rule that reports a list of several column names written inside a call or a subscript. The proposal has no such rule today, and the number of names that triggers it is your call.</p>
  </div>
</section>

<section>
  <h2>replace or map for a mapping</h2>
  <p class="lead">The skill is right about meaning and wrong about cost. <code>replace</code> keeps the values the mapping does not list, but its time grows with every key. On 1,000,000 text values it took about 12 ms per key. Times that are more than three times the fastest form are marked.</p>
  <h3>Text values</h3>
  <div class="scroll"><table><thead><tr><th>Form</th>{key_head}</tr></thead><tbody>{replace_table("text")}</tbody></table></div>
  <h3>Integer values</h3>
  <div class="scroll"><table><thead><tr><th>Form</th>{key_head}</tr></thead><tbody>{replace_table("integer")}</tbody></table></div>
  <h3>Where the forms give different results</h3>
  <div class="scroll"><table><thead><tr><th>Form</th><th>Result</th></tr></thead><tbody>
    <tr><td><code>map(lambda v: mapping.get(v, v))</code></td><td>The same values and dtype as <code>replace</code> in all 12 runs.</td></tr>
    <tr><td><code>category, then rename_categories(mapping)</code></td><td>The same values and dtype in all 12 runs. It raises <code>ValueError: Categorical categories must be unique</code> when two keys end at the same value.</td></tr>
    <tr><td><code>map(mapping).fillna(s)</code></td><td>Integer columns became float64 in 5 of the 6 integer runs. A key mapped to None got its old value back.</td></tr>
  </tbody></table></div>
  <div class="verdict">
    <p><b>What the measurements support.</b> Keep <code>replace</code> for a short mapping, up to about 3 text keys or 100 integer keys. Above that, <code>s.map(lambda v: mapping.get(v, v))</code> keeps the same meaning at a flat cost of about 85 ms. The category form is the fastest one with the same result, at about 58 ms for text and 5 ms for integers, and it only works when no two keys end at the same value. The proposal page recommended <code>map(mapping).fillna(s)</code>, which was wrong in the two cases above, and I have corrected the page.</p>
  </div>
</section>

<section>
  <h2>The rest of the snippet</h2>
  <div class="scroll"><table><thead><tr><th>The skill says</th><th>Measured</th><th>In pdx</th></tr></thead><tbody>
    <tr><td>Use named aggregations for group summaries</td><td>The same speed as a dict and a rename, 18.5 ms against 17.2 ms, and an equal result.</td><td><code>rename-after-agg</code> asks for it.</td></tr>
    <tr><td>Use grouped cumulative operations within ordered groups</td><td><code>g["b"].cumsum()</code> was 345 times faster than a lambda in <code>transform</code> with 100,000 groups.</td><td><code>groupby-lambda-window</code> rewrites the lambda.</td></tr>
    <tr><td>Use <code>.loc</code> or <code>.iloc</code>, never chained assignment</td><td>A chained assignment changed nothing on pandas 3.1.1, and pandas only warned.</td><td><code>chained-assignment</code> is an error with a fix, merged in PR 4.</td></tr>
    <tr><td>Use <code>.to_numpy()</code> only at a positional boundary</td><td>An array taken from a frame is read-only, and a write to it raised.</td><td><code>write-through-values</code> is an error.</td></tr>
    <tr><td>Decide how indexes must match before combining</td><td>The <code>assign</code> case above returned missing values without an error.</td><td>No rule, because pdx reads code and cannot see an index.</td></tr>
  </tbody></table></div>
</section>

<section>
  <h2>Decisions for you</h2>
  <ol>
    <li><b>lambda-column.</b> It rewrites your lambdas to <code>pd.col</code>, and the second PR of the build adds it with a safe fix. I recommend turning it into a rule that only reports, or removing it. Removing it fits the measurements best, because the two forms are equal.</li>
    <li><b>assign-then-select.</b> It rewrites <code>frame[cols].assign(...)</code> to <code>select</code>. I recommend removing it, because the shape it replaces is as fast and type checkers do not know <code>select</code> yet.</li>
    <li><b>query-string and filter-items.</b> I recommend keeping both and changing their targets to forms that type checkers accept. <code>query</code> strings would point to <code>.loc[pd.col(...) &gt; 1]</code>, and <code>filter(items=cols)</code> would point to <code>frame[cols]</code>, which also raises on a missing name.</li>
    <li><b>A rule for inline column lists.</b> Say whether you want it, and from how many names.</li>
  </ol>
</section>

<p class="foot">Method: pandas 3.1.1, Python 3.15.2 and pyarrow 26.0.1 on a machine with 32 cores, while the build agent was also running, so small differences are noise. A time is the best of 3 to 7 runs on a frame held in memory. The scripts and raw output are in <code>research/pandas-rules/skill-review</code>.</p>

</div></body></html>
"""
out = os.path.join(HERE, "show-me-skill-review.html")
open(out, "w").write(PAGE)
print(out, len(PAGE), "bytes")
