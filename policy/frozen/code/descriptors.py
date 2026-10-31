import itertools

def descriptors(root, cfg, distance):
    n = len(root)
    if n > cfg["max_blocks"]:
        raise ValueError("Input exceeds frozen maximum block count")
    if n <= 12:
        all_sets = [k for size in range(n) for k in itertools.combinations(range(n), size)]
        if len(all_sets) > cfg["max_screen_topologies"]:
            raise ValueError("Exact small-root descriptors exceed frozen cap")
        return all_sets, "ALL_PROPER_SUBSETS"
    # O(n^3) finite generation for the frozen n<=64 limit, never 2^n.
    buckets = {size: set(itertools.combinations(range(n), size)) for size in range(4)}
    for removed in itertools.chain(((i,) for i in range(n)), itertools.combinations(range(n), 2)):
        r = set(removed); k = tuple(i for i in range(n) if i not in r)
        buckets.setdefault(len(k), set()).add(k)
    cheap = sorted(range(n), key=lambda i: (sum(g["name"] == "cx" for g in root[i]["gates"]), -distance[i], i))
    important = sorted(range(n), key=lambda i: (-distance[i], i))
    for size in range(4, n):
        b = buckets.setdefault(size, set())
        for order in (list(range(n)), cheap, important):
            for offset in range(n):
                b.add(tuple(sorted((order[offset:] + order[:offset])[:size])))
    costs = [sum(g["name"] == "cx" for g in b["gates"]) for b in root]
    ranks = [iter(sorted(buckets[size], key=lambda k: (-sum(distance[i] for i in k), sum(costs[i] for i in k), k)))
             for size in sorted(buckets)]
    selected = []
    for row in itertools.zip_longest(*ranks):
        for k in row:
            if k is not None:
                selected.append(k)
                if len(selected) == cfg["max_screen_topologies"]:
                    return selected, "BOUNDED_STRATIFIED_SUBSETS"
    return selected, "BOUNDED_STRATIFIED_SUBSETS"
