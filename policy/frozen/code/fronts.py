"""Source-only frontier rules. No molecular names or outcome lookup tables."""
import math
import itertools
from policy import METRICS, resource_key

ENDPOINTS=('best_depth_safe','best_all_resource_safe','cnot_depth_tradeoff')

def eligible(a,o,tol,endpoint):
    if a['energy']>o['energy']+tol:return False
    if endpoint=='cnot_depth_tradeoff':return True
    if a['resources']['cnot_depth']>o['resources']['cnot_depth']:return False
    return endpoint!='best_all_resource_safe' or all(a['resources'][m]<=o['resources'][m] for m in METRICS)

def choose(o,archive,tol,endpoint,budget=math.inf):
    choices=[dict(o,kind='NO_ACTION',available_W=0)]+[a for a in archive if a['available_W']<=budget and eligible(a,o,tol,endpoint)]
    if endpoint=='cnot_depth_tradeoff':
        default=choose(o,archive,tol,'best_depth_safe',budget)
        choices=[a for a in choices if a['resources']['cnot']<default['resources']['cnot']]
        if not choices:return default
        key=lambda a:(a['resources']['cnot'],a['resources']['cnot_depth'],a['resources']['total_depth'],a['resources']['parameters'],a['energy'])
    else:key=lambda a:(*resource_key(a['resources']),a['energy'])
    return min(choices,key=key)

def targets(r,originals,archive,tol):
    out=[]
    for o in originals:
        if not o['growth_step']:continue
        for endpoint in ENDPOINTS:
            incumbent=choose(o,archive,tol,endpoint)['resources']
            if endpoint=='cnot_depth_tradeoff':
                better=r['cnot']<incumbent['cnot']
            else:
                better=(r['cnot_depth']<=o['resources']['cnot_depth'] and resource_key(r)[:2]<resource_key(incumbent)[:2]
                    and (endpoint!='best_all_resource_safe' or all(r[m]<=o['resources'][m] for m in METRICS)))
            if better:out.append(o);break
    return out

def rows(originals,archive,budget,tol):
    result=[]
    for o in originals:
        if not o['growth_step']:continue
        row=dict(comparator_step=o['growth_step'],comparator_energy=o['energy'],comparator_resources=o['resources'])
        for endpoint in ENDPOINTS:
            a=choose(o,archive,tol,endpoint,budget)
            row[endpoint]=dict(kind=a.get('kind','COMPRESSED'),candidate_id=a.get('candidate_id'),energy=a['energy'],
                resources=a['resources'],available_W=a.get('available_W',0),delta_energy_Ha=a['energy']-o['energy'],
                depth_increased=a['resources']['cnot_depth']>o['resources']['cnot_depth'],
                reductions={m:(o['resources'][m]-a['resources'][m])/o['resources'][m] if o['resources'][m] else None for m in METRICS})
        result.append(row)
    return result

def repair_shortlist(trials,root,distances,P0):
    cap=math.ceil(math.sqrt(P0));root_cnot=sum(g['name']=='cx' for b in root for g in b['gates'])
    selected=[]
    for removed_size in [1,2]:
        group=[r for r in trials if len(root)-len(r['kept_positions'])==removed_size]
        group.sort(key=lambda r:(r['proxy']/max(1,root_cnot-r['resources']['cnot']),r['resources']['cnot'],tuple(r['kept_positions'])))
        selected.extend(group[:cap])
    return selected

def resource_order(trials):
    return sorted(trials,key=lambda r:(*resource_key(r['resources']),r['screen_energy'],r['proxy'],tuple(r['kept_positions'])))

def coverage_queues(trials,originals,archive,tol):
    levels={}
    for t in trials:levels.setdefault(t['resources']['cnot'],[]).append(t)
    heads=[min(levels[c],key=lambda t:(t['screen_energy'],t['resources']['total_depth'],t['resources']['parameters'],t['proxy'],tuple(t['kept_positions']))) for c in sorted(levels)]
    columns=[]
    for o in originals:
        if not o['growth_step']:continue
        candidates=[t for t in trials if t['resources']['cnot']<choose(o,archive,tol,'cnot_depth_tradeoff')['resources']['cnot']]
        def priority(t):
            r=t['resources'];saving=max(1,o['resources']['cnot']-r['cnot'])
            return (max(0.,t['screen_energy']-o['energy'])*(1+2*r['parameters'])/saving,*resource_key(r),tuple(t['kept_positions']))
        columns.append(sorted(candidates,key=priority))
    target_order=[t for row in itertools.zip_longest(*columns) for t in row if t is not None]
    return heads,target_order

def significant_update(before,after,originals,tol):
    for o in originals:
        if not o['growth_step']:continue
        a=choose(o,after,tol,'best_all_resource_safe');b=choose(o,before,tol,'best_all_resource_safe')
        if resource_key(a['resources'])[:2]<resource_key(b['resources'])[:2]:return True
        for a in after[len(before):]:
            r=a['resources']
            if (a['energy']<=o['energy']+tol and all(r[m]<=o['resources'][m] for m in ['parameters','total_depth'])
                and r['cnot']<choose(o,before,tol,'best_depth_safe')['resources']['cnot']):return True
    return False
