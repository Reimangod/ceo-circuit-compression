"""Source-only nested coverage, retaining the original 128-grid prefix.

This produces ONE initial-screen list for ONE optimizer queue. There is no
old quantum result, old compressed circuit, second solver, or best-of run.
"""
from candidate_screen_coverage import balanced_anchor_screens,candidate_key


def nested_anchor_screens(candidates,limit,anchor_grid_selector,resource_level_selector,base_limit=128):
    if type(limit) is not int or limit<0:raise ValueError('Nonnegative integer limit required')
    if type(base_limit) is not int or base_limit<1:raise ValueError('Positive base prefix required')
    grid=anchor_grid_selector(candidates,base_limit)
    local_and_grid=balanced_anchor_screens(candidates,base_limit,resource_level_selector)
    sequence=[];seen=set()
    for candidate in grid+local_and_grid:
        key=candidate_key(candidate)
        if key in seen:continue
        seen.add(key);sequence.append(candidate)
    return sequence[:limit]
