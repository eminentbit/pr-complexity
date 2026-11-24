def find_dupes(items):
    seen = set()
    names = []
    out = []
    for x in items:
        if x in seen:
            out.append(x)
        seen.add(x)
        names.append(str(x))
    return out


def lookup(customers, ids):
    table = {c.id: c for c in customers}
    return [table[i] for i in ids]
