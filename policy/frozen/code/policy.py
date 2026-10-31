"""One fixed resource-first coverage rule; no molecule names or historical data."""
import itertools
import math

METRICS = ('cnot', 'cnot_depth', 'parameters', 'total_depth')


def resource_key(resources):
    return (resources['cnot'], resources['total_depth'], resources['parameters'])


def qualified(candidate, original, tolerance, all_safe=False):
    return (candidate['energy'] <= original['energy'] + tolerance
            and candidate['resources']['cnot_depth'] <= original['resources']['cnot_depth']
            and (not all_safe or all(candidate['resources'][m] <= original['resources'][m]
                                     for m in METRICS)))


def incumbent(original, archive, tolerance, all_safe=False, budget=math.inf):
    choices = [dict(original, kind='NO_ACTION', available_W=0)]
    choices += [a for a in archive if a['available_W'] <= budget
                and qualified(a, original, tolerance, all_safe)]
    return min(choices, key=lambda a: (*resource_key(a['resources']), a['energy']))


def useful_targets(resources, originals, archive, tolerance):
    return [o for o in originals if o['growth_step'] > 0
            and resources['cnot_depth'] <= o['resources']['cnot_depth']
            and resource_key(resources)[:2] < resource_key(
                incumbent(o, archive, tolerance)['resources'])[:2]]


def coverage_order(trials):
    levels = {}
    for trial in trials:
        levels.setdefault(trial['resources']['cnot'], []).append(trial)
    key = lambda r: (r['screen_energy'], r['resources']['total_depth'],
                     r['resources']['parameters'], r['proxy'], tuple(r['kept_positions']))
    columns = [sorted(levels[c], key=key) for c in sorted(levels)]
    return [r for row in itertools.zip_longest(*columns) for r in row if r is not None]


def continuation_order(states, originals, archive, tolerance, gtol, max_calls):
    ranked = []
    for state in states:
        targets = useful_targets(state['trial']['resources'], originals, archive, tolerance)
        if (not targets or state['calls'] >= max_calls or state['terminal_optimizer']
                or (state['gradient_inf'] is not None and state['gradient_inf'] <= gtol)):
            continue
        gap = max(0., state['best_energy'] - max(o['energy'] for o in targets))
        drop = max(state['trial']['screen_energy'] - state['best_energy'], 1e-12)
        priority = (gap / drop, *resource_key(state['trial']['resources']),
                    tuple(state['trial']['kept_positions']))
        ranked.append((priority, state))
    return [s for _, s in sorted(ranked, key=lambda item: item[0])]


def comparison_rows(originals, archive, budget, tolerance):
    rows = []
    for o in originals:
        if not o['growth_step']:
            continue
        result = dict(comparator_step=o['growth_step'], comparator_energy=o['energy'],
                      comparator_resources=o['resources'])
        for name, all_safe in [('best_depth_safe', False), ('best_all_resource_safe', True)]:
            a = incumbent(o, archive, tolerance, all_safe, budget)
            result[name] = dict(kind=a.get('kind', 'COMPRESSED'), candidate_id=a.get('candidate_id'),
                                energy=a['energy'], resources=a['resources'],
                                available_W=a.get('available_W', 0),
                                delta_energy_Ha=a['energy'] - o['energy'],
                                reductions={m: (o['resources'][m]-a['resources'][m])/o['resources'][m]
                                            if o['resources'][m] else None for m in METRICS})
        rows.append(result)
    return rows
