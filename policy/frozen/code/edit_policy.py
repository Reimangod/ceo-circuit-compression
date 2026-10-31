"""One source-only nested screen list; same native candidate and optimizer code."""
from native_policy import *
from native_policy import select_anchor_screens as original_anchor_grid
from nested_candidate_screen_coverage import nested_anchor_screens


def select_anchor_screens(candidates,limit):
    return nested_anchor_screens(candidates,limit,original_anchor_grid,select_resource_levels,base_limit=128)
