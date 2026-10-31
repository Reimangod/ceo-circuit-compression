"""One deterministic screen order balancing local-edit and resource coverage.

Inputs are source-only descriptors. No Hamiltonian, measured energy, old
compressed point, molecule identity, or learned parameters are consulted.
"""
import itertools


def candidate_key(candidate):
    return (candidate['topology_id'], tuple(float(x).hex() for x in candidate['initial_theta']))


def balanced_anchor_screens(candidates, limit, resource_level_selector):
    if type(limit) is not int or limit < 0: raise ValueError('Nonnegative integer screen limit required')
    groups = {}
    for candidate in candidates: groups.setdefault(candidate['anchor_step'], []).append(candidate)
    anchors = sorted(groups, reverse=True)
    # source_candidates already orders each anchor by local distance/saving.
    local = [p for row in itertools.zip_longest(*(groups[a] for a in anchors)) for p in row if p is not None]
    grid = [p for row in itertools.zip_longest(*(resource_level_selector(groups[a],len(groups[a])) for a in anchors))
            for p in row if p is not None]
    selected, seen = [], set()
    for pair in itertools.zip_longest(local, grid):
        for candidate in pair:
            if candidate is None:continue
            key = candidate_key(candidate)
            if key in seen:continue
            seen.add(key);selected.append(candidate)
    return selected[:limit]
