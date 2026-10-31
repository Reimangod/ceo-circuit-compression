"""Offline archive/accounting checks. This module never imports an optimizer."""
import argparse
import collections
import json
from pathlib import Path
import sys
from archive import Archive, ROOT, sha256
from reproduce import comparisons

CURRENT='outputs/ceo-all-orbital-unified-compression-2026-10-31/'


def verify(root=ROOT, full=True):
    a=Archive(root); errors=[]; checked=set()
    if full:
        for x in a.manifest['files']:
            h=x.get('object_sha256')
            if not h or h in checked: continue
            p=a.root/'data/raw/objects'/h
            if not p.is_file() or sha256(p)!=h: errors.append('Object hash: '+h)
            checked.add(h)
    code=json.loads((a.root/'data/metadata/policy-files.json').read_text())
    for x in code:
        if sha256(a.root/x['file'])!=x['sha256']: errors.append('Frozen code: '+x['file'])
    c,s=comparisons(a)
    tasks=a.json(CURRENT+'inventory-v2.json')['tasks']
    costs=collections.Counter();ne=ng=0;aliases=0
    for task in tasks:
        path=CURRENT+'runs-v2/'+task['task_id']+'/'
        r=a.json(path+'result.json'); events=a.jsonl(path+'work.jsonl')
        assert r['source_sha256']==sha256(a.file(task['source']))
        assert r['task_id']==task['task_id'] and r['settings']==task['settings']
        w=sum(e['delta_W'] for e in events)
        starts=[e for e in events if e['status']=='STARTED']
        ends=[e for e in events if e.get('terminal')]
        assert len(starts)==len(ends)
        assert [e['sequence'] for e in events]==list(range(1,len(events)+1))
        for x in starts:
            end=next(e for e in ends if e['id']==x['id'])
            assert end['status'] in ('COMPLETED','FAILED') and end['delta_W']==0
            assert x['delta_W']==1+2*x['p']
            costs[x['label']]+=x['delta_W']; ne+=1;ng+=x['p']
        assert w==r['meter']['W'] and w<=r['meter']['limit']==task['settings']['model_budget']
        assert w==r['meter']['energy_evaluations']+2*r['meter']['gradient_components']
        assert r['physical_shots']==0 and not r['machine_learning'] and not r['historical_compression_inputs']
        assert r['status']=='MODEL_CAP_TERMINAL'
    recorded=json.loads((a.root/'data/metadata/cost-breakdown.json').read_text())
    assert ne+2*ng==recorded['production_search_W']==117745
    for pair in a.manifest['aliases']:
        assert a.file(pair['source_path'])==a.file(pair['same_as']); aliases+=1
    result=dict(status='PASS' if not errors else 'FAIL',errors=errors,objects_checked=len(checked),
        full_orbital_conditions=len(c['cases']),current_policy_conditions=len(s['current']),
        current_policy_tasks=len(tasks),ledger_search_W=ne+2*ng,energy_evaluations=ne,
        scalar_gradient_components=ng,duplicate_progress_aliases=aliases,
        new_molecular_experiments=0,new_optimizer_calls=0)
    if errors: raise ValueError(json.dumps(result))
    return result


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path)
    ap.add_argument('--metadata-only',action='store_true');args=ap.parse_args()
    report=verify(full=not args.metadata_only)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
