"""Source-only native circuit edit representation, one deterministic scheduler."""
import copy
import itertools
import math
import numpy as np
import core
from descriptors import descriptors
from fast_kernel import operator_matrix

def localize(block):
    qs=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
    b=copy.deepcopy(block)
    b['gates']=[dict(g,wires=[qs.index(q) for q in g['wires']]) for g in block['gates'] if g['name']!='barrier']
    return qs,b

def registry_key(block):
    _,b=localize(block)
    return core.digest(dict(gates=b['gates'],arity=len(b['theta'])))

def replacement(block,match):
    qs,_=localize(block);child=copy.deepcopy(match['local_template']);v=np.asarray(match['coordinate_direction'])
    phi=float(v@np.asarray(block['theta'])/(v@v))
    child['theta']=[phi];child['occurrence_id']=block['occurrence_id']+':OVP'
    child['generator_digest']=core.digest(dict(parent=block['generator_digest'],direction=v.tolist(),template=match['template_id']))
    child['gates']=[dict(g,wires=[qs[q] for q in g['wires']]) for g in child['gates']]
    child['gates'] += [dict(g,weights=[0.]) for g in block['gates'] if g['name']=='barrier']
    return child

def blocks_for(source,probe,registry):
    frame=source['frames'][probe['anchor_step']]['blocks'];edits={e['position']:e for e in probe.get('replacements',[])}
    blocks=[]
    for i in probe['kept_positions']:
        block=frame[i]
        if i in edits:
            edit=edits[i];match=next(m for m in registry[edit['registry_key']] if m['template_id']==edit['template_id'])
            block=replacement(block,match)
        blocks.append(block)
    return blocks

def structure_id(blocks):
    return core.digest([{k:v for k,v in b.items() if k not in ('theta','occurrence_id')} for b in blocks])

def source_candidates(source,cfg,registry,resource_counter=None):
    count_resources=resource_counter or core.resources
    root=source['frames'][-1]['blocks'];candidates=[];columns=[]
    # The root supplies its bounded dictionary; every checkpoint supplies local edits.
    frames=list(reversed(source['frames'][1:]))
    for frame in frames:
        blocks=frame['blocks'];m=len(blocks);distance=[core.local_distance(b) for b in blocks]
        original=count_resources(blocks,source['n']);buckets={}
        sets,_=descriptors(blocks,cfg,distance) if frame['growth_step']==source['frames'][-1]['growth_step'] else ([], 'LOCAL_PREFIX_EDITS')
        # Every original checkpoint supplies its own near-neighbour coefficients.
        neighbours={tuple(i for i in range(m) if i not in removed)
                    for size in (1,2) for removed in itertools.combinations(range(m),size)}
        sets=sorted(set(sets)|neighbours,key=lambda kept:(len(kept),kept))
        def put(kept,edits,proxy):
            p=dict(anchor_step=frame['growth_step'],kept_positions=list(kept),removed_positions=sorted(set(range(m))-set(kept)),
                   replacements=edits,proxy=float(proxy))
            bs=blocks_for(source,p,registry);rr=count_resources(bs,source['n']);saving=original['cnot']-rr['cnot']
            if saving<=0 or rr['cnot_depth']>original['cnot_depth']:return
            p.update(resources=rr,saving=saving,initial_theta=core.theta_of(bs).tolist(),topology_id=structure_id(bs))
            buckets.setdefault(len(kept),[]).append(p)
        for kept in sets:
            put(kept,[],sum(distance[i] for i in range(m) if i not in kept))
        if frame['growth_step']!=source['frames'][-1]['growth_step']:
            slots=max(1,math.ceil(math.sqrt(len(core.theta_of(root)))))
            for size,group in buckets.items():
                group.sort(key=lambda p:(p['proxy']/p['saving'],p['resources']['cnot'],p['resources']['total_depth'],p['topology_id']))
                buckets[size]=group[:slots]
        for i,block in enumerate(blocks):
            if len(block['theta'])<2:continue
            key=registry_key(block)
            for match in registry.get(key,[]):
                # One common phase-invariant local-unitary distance for deletion and restriction.
                _,local=localize(block);child=replacement(block,match);_,child_local=localize(child)
                _,u,_=operator_matrix(local,local['theta']);_,w,_=operator_matrix(child_local,child_local['theta'])
                proxy=max(0.,float(2-2*abs(np.trace(w.conj().T@u))/len(u)))
                put(range(m),[dict(position=i,registry_key=key,template_id=match['template_id'])],proxy)
        column=[p for group in buckets.values() for p in group]
        column.sort(key=lambda p:(p['proxy']/p['saving'],p['resources']['cnot'],p['resources']['total_depth'],p['topology_id']))
        columns.append(column)
    seen=set()
    for row in itertools.zip_longest(*columns):
        for p in row:
            if p is None:continue
            key=(p['topology_id'],tuple(float(x).hex() for x in p['initial_theta']))
            if key in seen:continue
            seen.add(key);candidates.append(p)
    return candidates,True

def target_for(probe,originals,archive,tol):
    rr=probe['resources'];qualified=[]
    for o in originals[1:]:
        if rr['cnot']>=o['resources']['cnot'] or rr['cnot_depth']>o['resources']['cnot_depth']:continue
        existing=[a['resources']['cnot'] for a in archive if a['energy']<=o['energy']+tol and a['resources']['cnot_depth']<=o['resources']['cnot_depth']]
        if existing and rr['cnot']>=min(existing):continue
        qualified.append(o)
    return min(qualified,key=lambda o:(o['energy'],-o['growth_step'])) if qualified else None


def resource_first_key(probe):
    r=probe['resources']
    return (r['cnot'],r['total_depth'],r['parameters'],probe['screen_energy'],probe['proxy'],probe['anchor_step'],probe['topology_id'])


def select_resource_levels(candidates,limit):
    groups={}
    for p in candidates:groups.setdefault(p['resources']['cnot'],[]).append(p)
    for group in groups.values():
        group.sort(key=lambda p:(-p['anchor_step'],p['proxy']/p['saving'],p['resources']['total_depth'],p['topology_id'],tuple(p['initial_theta'])))
    levels=sorted(groups);order=[]
    for i in range((len(levels)+1)//2):
        order.append(levels[i])
        if i!=len(levels)-i-1:order.append(levels[-i-1])
    return [p for row in itertools.zip_longest(*(groups[c] for c in order)) for p in row if p is not None][:limit]

def prefix_representatives(trials,originals,tol):
    """One source-anchored head, not a separate solver or budget."""
    bystep={o['growth_step']:o for o in originals[1:]}
    groups={}
    for trial in trials:
        original=bystep.get(trial.get('anchor_step'))
        if original is None or not trial['initial_theta']:continue
        r=trial['resources'];saving=original['resources']['cnot']-r['cnot']
        if saving<=0 or r['cnot_depth']>original['resources']['cnot_depth']:continue
        key=(max(0.,trial['screen_energy']-original['energy']-tol)*(1+2*r['parameters'])/saving,
             r['cnot'],r['total_depth'],trial['probe_id'])
        old=groups.get(trial['anchor_step'])
        if old is None or key<old[0]:groups[trial['anchor_step']]=(key,trial)
    return [t for _,t in sorted(groups.values(),key=lambda pair:pair[0])]


def coverage_order(trials,originals,tol):
    """One queue interleaves resource-level and energy-gap representatives."""
    groups={}
    for t in trials:
        if not t['initial_theta']:continue
        groups.setdefault(t['resources']['cnot'],[]).append(t)
    def tie(t):
        r=t['resources']
        return (t['screen_energy'],r['total_depth'],r['parameters'],t['proxy'],t['probe_id'])
    heads=[min(groups[c],key=tie) for c in sorted(groups)]
    columns=[]
    for o in originals[1:]:
        eligible=[t for t in trials if t['initial_theta'] and
                  t['resources']['cnot']<o['resources']['cnot'] and
                  t['resources']['cnot_depth']<=o['resources']['cnot_depth']]
        def priority(t):
            r=t['resources'];saving=o['resources']['cnot']-r['cnot']
            return (max(0.,t['screen_energy']-o['energy']-tol)*(1+2*r['parameters'])/saving,
                    r['cnot'],r['total_depth'],t['probe_id'])
        columns.append(sorted(eligible,key=priority))
    target_order=[t for row in itertools.zip_longest(*columns) for t in row if t is not None]
    seen=set();out=[]
    for t in prefix_representatives(trials,originals,tol):
        if t['probe_id'] not in seen:seen.add(t['probe_id']);out.append(t['probe_id'])
    for pair in itertools.zip_longest(heads,target_order):
        for t in pair:
            if t is None or t['probe_id'] in seen:continue
            seen.add(t['probe_id']);out.append(t['probe_id'])
    return out

def continuation_key(probe,target,tol):
    s=probe['state'];r=probe['resources']
    gap=max(0.,s['energy']-target['energy']-tol)
    drop=max(probe['screen_energy']-s['energy'],1e-12)
    return (gap/drop*(1+2*r['parameters'])*(1+s['calls'])/
            max(1,target['resources']['cnot']-r['cnot']),
            r['cnot'],r['total_depth'],probe['probe_id'])


def easiest_target_for(probe,originals,archive,tol):
    rr=probe['resources'];qualified=[]
    for o in originals[1:]:
        if rr['cnot']>=o['resources']['cnot'] or rr['cnot_depth']>o['resources']['cnot_depth']:continue
        existing=[a['resources']['cnot'] for a in archive if a['energy']<=o['energy']+tol
                  and a['resources']['cnot_depth']<=o['resources']['cnot_depth']]
        if existing and rr['cnot']>=min(existing):continue
        qualified.append(o)
    return max(qualified,key=lambda o:(o['energy'],-o['growth_step'])) if qualified else None


def select_anchor_screens(candidates,limit):
    """Round-robin original anchors, each stratified over its CNOT levels."""
    groups={}
    for candidate in candidates:groups.setdefault(candidate['anchor_step'],[]).append(candidate)
    columns=[select_resource_levels(groups[a],len(groups[a])) for a in sorted(groups,reverse=True)]
    return [p for row in itertools.zip_longest(*columns) for p in row if p is not None][:limit]
