import json
import sys

path = sys.argv[1]
for line in open(path):
    if line.startswith("FIDELITY "):
        d = json.loads(line[len("FIDELITY "):])
        break
else:
    raise SystemExit("no FIDELITY line")

m = d["matrix"]
print("cases", len(m), "failures", d["failures"])
total = 0
for name in ("rich_turns_400", "dense_turns_400"):
    v = m[name]
    groups = [g for g in v if g not in ("blocks", "planned_group", "planned")]
    if isinstance(v["planned"], dict):
        groups.append("planned")
    total += len(groups)
    print(name, "blocks", v["blocks"], "planned_group", v["planned_group"])
    for g in groups:
        c = v[g]
        ok = all(c[k] for k in ("sig_eq", "tables_eq", "height_eq", "html_eq"))
        print("   group=%-7s blocks=%-6d ok=%s" % (g, c["blocks"], ok))
print("cells checked in this spot-check:", total)
bad = [(n, g) for n, v in m.items() for g in v
       if g not in ("blocks", "planned_group") and isinstance(v[g], dict)
       and not all(v[g][k] for k in ("sig_eq", "tables_eq", "height_eq", "html_eq"))]
print("bad cells anywhere:", bad)
