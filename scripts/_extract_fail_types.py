import re, sys, collections

def load(path):
    # latin-1 never fails (1 byte -> 1 char); stripping NULs collapses UTF-16-LE
    # ascii content to plain ascii and leaves UTF-8 untouched. Robust for both.
    raw = open(path, "rb").read()
    return raw.decode("latin-1", errors="replace").replace("\x00", "")

def classify(line):
    m = re.search(r" - (\w*(?:Error|Exception))\b", line)
    if m:
        return m.group(1)
    low = line.lower()
    if "database is locked" in low or "operationalerror" in low:
        return "OperationalError(lock)"
    if "timeout" in low:
        return "timeout"
    return "NO_EXC_TAG"

def node_set(path):
    txt = load(path).replace("\x00", "")
    return sorted(set(m.group(1).strip() for m in re.finditer(r"FAILED ([^\r\n]+)", txt)))

if len(sys.argv) == 3 and sys.argv[1] == "--diff-nodes":
    # placeholder
    pass

if "--diff" in sys.argv:
    a, b = [p for p in sys.argv[1:] if p != "--diff"][:2]
    ha, hb = node_set(a), node_set(b)
    print(f"HEAD({a}) nodes: {len(ha)}   MAIN({b}) nodes: {len(hb)}")
    print("identical failing node-id set:", ha == hb)
    print("only on HEAD:", sorted(set(ha) - set(hb)))
    print("only on MAIN:", sorted(set(hb) - set(ha)))
    sys.exit(0)

for path in sys.argv[1:]:
    txt = load(path)
    fails = [l for l in txt.splitlines() if l.startswith("FAILED ")]
    print(f"\n=== {path} ===")
    print(f"FAILED count: {len(fails)}")
    types = collections.Counter(classify(l) for l in fails)
    print("exc types:", dict(types))
    prefixes = collections.Counter(l.split("::")[0].replace("FAILED ", "").strip() for l in fails)
    print("by file:")
    for k, v in sorted(prefixes.items()):
        print(f"  {v:>3}  {k}")
    lock = sum(v for k, v in types.items() if "lock" in k.lower() or "timeout" in k.lower())
    print(f"lock/timeout share: {lock}/{len(fails)}")
