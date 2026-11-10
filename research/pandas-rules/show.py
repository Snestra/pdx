import json, sys
def load(p):
    try: return {r["id"]: r for r in map(json.loads, open(p)) if "id" in r}
    except FileNotFoundError: return {}
name = sys.argv[1]
a, b = load(f"runs/{name}-3.1.1.jsonl"), load(f"runs/{name}-3.0.6.jsonl")
for id in dict.fromkeys(list(a) + list(b)):
    r, o = a.get(id, {}), b.get(id, {})
    print(f'{id:42s} 3.1: {r.get("before_ms","-"):>10} -> {r.get("after_ms","-"):>9} x{r.get("speedup","-"):<7} | 3.0: {o.get("before_ms","-"):>10} -> {o.get("after_ms","-"):>9} x{o.get("speedup","-"):<7} {(r or o).get("same", "")[:70]} {r.get("before_err","")} {r.get("after_err","")}')
