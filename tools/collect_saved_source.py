"""Retrospective saved-data census. Never imports a quantum/optimization kernel.

Each pair is joined inside its original Hamiltonian/run or its explicit problem
binding. Sources, old labels and experiments are read-only. Outputs are a new
descriptive view, not a common-budget method comparison.
"""
from pathlib import Path
import collections,hashlib,json,math
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=ROOT/'outputs';TAU=1e-9
M=('cnot','cnot_depth','parameters','total_depth')
Z={'H':1,'Li':3,'Be':4,'C':6,'N':7,'O':8,'F':9}
AO={'H':1,'Li':5,'Be':5,'C':5,'N':5,'O':5,'F':5}
files={};missing=[];cases={};candidates_seen=collections.Counter();seen_pairs=set();histories={}
def read(p):
    p=Path(p);b=p.read_bytes();files[str(p)]=hashlib.sha256(b).hexdigest();return json.loads(b)
def lines(p):
    p=Path(p);b=p.read_bytes();files[str(p)]=hashlib.sha256(b).hexdigest();return [json.loads(x) for x in b.splitlines()]
def resources(r):
    return dict(cnot=r.get('cnot',r.get('cnot_count',r.get('logical_cnot_count'))),
        cnot_depth=r.get('cnot_depth',r.get('logical_cnot_depth')),
        parameters=r.get('parameters',r.get('parameter_count',r.get('n_independent_ansatz_parameters'))),
        total_depth=r.get('total_depth',r.get('logical_total_depth')))
def meta(problem,n,ne):
    geom=problem['geometry'];atoms=[a[0] for a in geom];basis=problem['basis'].lower()
    if problem.get('charge',0)!=0 or any(a not in Z for a in atoms):return None
    expected=sum(Z[a] for a in atoms)
    expectedq=2*sum(AO[a] for a in atoms) if basis=='sto-3g' else (4*len(atoms) if basis=='6-31g' and set(atoms)=={'H'} else None)
    if ne!=expected or n!=expectedq or problem.get('frozen_orbitals',[]) not in ([],None):return None
    count=collections.Counter(atoms)
    molecule=({'H':1,'Li':1}==count and 'LiH') or ({'H':2,'Be':1}==count and 'BeH2') or ({'H':1,'F':1}==count and 'HF') or ({'N':2}==count and 'N2') or ({'H':2,'O':1}==count and 'H2O') or ({'H':3,'N':1}==count and 'NH3') or (len(count)==1 and atoms[0]=='H' and 'H'+str(len(atoms)))
    if not molecule:return None
    heavy=[a for a in geom if a[0]!='H']
    if heavy and 'H' in atoms:distance=math.dist(heavy[0][1],next(a[1] for a in geom if a[0]=='H'))
    else:distance=math.dist(geom[0][1],geom[1][1])
    return dict(molecule=molecule,distance_A=round(distance,6),basis=basis,n_qubits=n,n_electrons=ne,
        geometry=geom,full_orbital=True)
def key(md):return (md['molecule'],md['distance_A'],md['basis'],md['n_qubits'],md['n_electrons'])
def ensure(md):
    k=key(md)
    if k not in cases:cases[k]=dict(problem_family=md,best_depth_safe=None,best_any_depth=None,pair_count=0,cohorts=set(),cohort_best={})
    return cases[k]
def put(md,a,o,cohort,path,scope='BOUND_CERTIFIED_PAIR',candidate_id=None):
    case=ensure(md);case['cohorts'].add(cohort)
    E=float(a['energy']);eo=float(o['energy']);rr=resources(a['resources']);br=resources(o['resources'])
    if not all(type(v) is int and v>=0 for v in (*rr.values(),*br.values())):raise ValueError('Resource schema')
    if not math.isfinite(E+eo) or E>eo+TAU or not br['cnot']:return
    sid=(str(path),str(candidate_id),o['growth_step'],eo,E,tuple(rr.values()),tuple(br.values()))
    if sid in seen_pairs:return
    seen_pairs.add(sid);case['pair_count']+=1
    if rr['cnot']>=br['cnot']:return
    entry=dict(**md,cohort=cohort,evidence_scope=scope,evidence_path=str(path),candidate_id=candidate_id,
        comparator_step=o['growth_step'],ceo_energy_Ha=eo,child_energy_Ha=E,delta_energy_Ha=E-eo,
        ceo=br,child=rr,reduction_pct={m:100*(br[m]-rr[m])/br[m] if br[m] else None for m in M},
        depth_increased=rr['cnot_depth']>br['cnot_depth'])
    score=lambda r:(r['reduction_pct']['cnot'],-max(r['delta_energy_Ha'],0),-r['child']['cnot_depth'],-r['child']['total_depth'])
    if case['best_any_depth'] is None or score(entry)>score(case['best_any_depth']):case['best_any_depth']=entry
    if not entry['depth_increased'] and (case['best_depth_safe'] is None or score(entry)>score(case['best_depth_safe'])):case['best_depth_safe']=entry
    cb=case['cohort_best'].setdefault(cohort,dict(best_depth_safe=None,best_any_depth=None))
    if cb['best_any_depth'] is None or score(entry)>score(cb['best_any_depth']):cb['best_any_depth']=entry
    if not entry['depth_increased'] and (cb['best_depth_safe'] is None or score(entry)>score(cb['best_depth_safe'])):cb['best_depth_safe']=entry
def portable():
    families=[(OUT/'ceo-all-orbital-unified-compression-2026-10-31','inventory-v2.json','runs-v2','統一Policy・全軌道')]
    old=OUT/'ceo-unified-budget-reallocation-2026-10-30'
    families += [(p,'inventory.json','runs','過去統一Policy '+p.name) for p in sorted(old.glob('execution-v*')) if (p/'inventory.json').exists()]
    source_cache={}
    for folder,invname,runfolder,cohort in families:
        inv=read(folder/invname);count=0
        for t in inv['tasks']:
            sp=Path(t['source'])
            if sp not in source_cache:
                s=read(sp);md=meta(s['problem'],s['n'],len(s['reference_occupied']));source_cache[sp]=(s,md)
            s,md=source_cache[sp]
            if md is None:continue
            ensure(md);rp=folder/runfolder/t['task_id']/'result.json'
            if not rp.exists():missing.append(dict(path=str(rp),reason='MISSING_RESULT'));continue
            r=read(rp)
            if r['source_sha256']!=files[str(sp)]:raise ValueError('Source binding drift')
            count+=1
            originals=[dict(growth_step=o['growth_step'],energy=o.get('raw_native_energy',o['energy']),
                resources=o.get('raw_native_resources',o['resources'])) for o in r['originals'] if o['growth_step']>0]
            for a in r.get('archive',[]):
                c=a.get('certificate')
                if not c or abs(c['energy']-a['energy'])>TAU or c['resources']!=a['resources']:continue
                for o in originals:put(md,a,o,cohort,rp,candidate_id=a.get('candidate_id',a.get('probe_id')))
        print('READ',cohort,count,flush=True)
def canonical():
    base=OUT/'genvqe-ceo-teacher-2026-09-26/v1.2/execution/artifacts'
    root=base/'canonical-normalized-v1'
    probs={r['id']:r for r in lines(root/'problems.jsonl')}
    rr={r['state_preparation_id']:resources(r) for r in lines(root/'resources.jsonl')}
    ev=lines(root/'evaluations.jsonl');receipts=lines(base/'energy-matched-history-v1/history_receipts.jsonl')
    byproblem={}
    for receipt in receipts:
        p=probs[receipt['problem_id']];md=meta(p,p['n_qubits'],p['n_electrons'])
        if md is None:continue
        ensure(md);points=[]
        for f in receipt['files']:
            cp=read(f['path'])
            if files[f['path']]!=f['sha256']:raise ValueError('Historical checkpoint hash drift')
            if cp.get('kind')!='completed-native-growth':continue
            points.append(dict(growth_step=cp['adapt_iteration'],energy=cp['energy'],resources=resources(cp['resources'])))
        byproblem[receipt['problem_id']]=(md,points)
        histories[receipt['problem_id']]=(md,points,p)
    for e in ev:
        if e['problem_id'] not in byproblem:continue
        md,points=byproblem[e['problem_id']]
        if abs(e['value_ha']-e['qiskit_validation_value_ha'])>TAU:continue
        a=dict(energy=e['value_ha'],resources=rr[e['state_preparation_id']])
        for o in points:put(md,a,o,'過去TeacherBank',root/'evaluations.jsonl',
            scope='STORED_HISTORY_ONLY_INDIVIDUAL_BASELINE_CERTIFICATE_NOT_JOINED',candidate_id=e['id'])
    print('READ','canonical historical',len(ev),flush=True)
def old_policy():
    rows=read(OUT/'ceo-policy-achievements-2026-10-19/all-candidates.json');cache={}
    for r in rows:
        sp=ROOT/r['source_path']
        if sp not in cache:
            s=read(sp);cache[sp]=meta(s['problem'],s['n'],len(s['reference_occupied']))
        md=cache[sp]
        if md is None:continue
        ensure(md)
        if not r.get('comparator') or r.get('comparator_is_HF'):continue
        put(md,dict(energy=r['energy'],resources=r['resources']),r['comparator'],'過去Policy',
            OUT/'ceo-policy-achievements-2026-10-19/all-candidates.json',candidate_id=r['candidate_id'])
    print('READ','historical policy',len(rows),flush=True)
def campaign():
    root=OUT/'ceo-chemical-transformer-campaign-2026-10-04';d=read(root/'progress-v6.json')
    md={}
    for p in (root/'portable-circuits-v1').glob('*/circuit.json'):
        r=read(p);q=r['problem_constants'];m=meta(q,q['n_qubits'],q.get('n_electrons',q.get('n_active_electrons')))
        if m:md[r['problem_id']]=m
    curves=collections.defaultdict(list)
    for o in d['curves']:
        if o['problem_id'] not in md or not o.get('certificate',{}).get('verified'):continue
        ref=o['certificate']
        if 'path' in ref:
            cert=read(ref['path'])
            if files[ref['path']]!=ref['sha256']:raise ValueError('Campaign certificate drift')
        else:
            cert=ref
        curves[o['problem_id']].append(dict(growth_step=o['iteration'],energy=o['energy_ha'],resources=o['resources']))
    for a in d['rows']:
        pid=a['problem_id']
        if pid not in md:continue
        ensure(md[pid]);cp=Path(a['certificate_path']);c=read(cp)
        cc=c['certificate']
        if not cc['verified'] or abs(cc['qiskit_energy']['real']-a['energy_ha'])>TAU or resources(cc['resources'])!=resources(a['resources']):
            raise ValueError('Campaign candidate certification mismatch')
        if c['endpoint_binding']['problem_id']!=pid:raise ValueError('Campaign candidate problem binding mismatch')
        # Progress rows originate from the closed native/Qiskit certification.
        for o in curves[pid]:put(md[pid],dict(energy=a['energy_ha'],resources=a['resources']),o,
            '候補順位付け・再最適化',root/'progress-v6.json',candidate_id=a['request_id'])
    print('READ','campaign',len(d['rows']),flush=True)
def compressed_bank():
    root=OUT/'ceo-direct-multigeometry-plan-2026-10-25/execution'
    probs=read(root/'problems.json');d=read(root/'dataset.json')
    for a in d['rows']:
        if a['source_class']!='compressed':continue
        p=probs[a['case']];pid=p.get('existing_reference_problem_id')
        if pid not in histories:
            matches=[pid1 for pid1,(_,_,p1) in histories.items() if
                p1['hamiltonian_digest']==p['hamiltonian_digest'] and
                p1['n_qubits']==p['n_qubits'] and p1['n_electrons']==p['n_electrons']]
            if len(matches)!=1:
                missing.append(dict(case=a['case'],reason='NO_UNIQUE_BOUND_HISTORICAL_HAMILTONIAN'))
                continue
            pid=matches[0]
        md,points,original=histories[pid]
        # Explicit reference ProblemID plus the registered Hamiltonian must agree.
        if p['hamiltonian_digest']!=original['hamiltonian_digest']:raise ValueError('Dataset problem drift')
        for o in points:put(md,a,o,'過去圧縮回路・整理済みデータ',root/'dataset.json',
            scope='STORED_HISTORY_ONLY_INDIVIDUAL_BASELINE_CERTIFICATE_NOT_JOINED',candidate_id=a['source_id'])
    print('READ','compressed bank',len(d['rows']),flush=True)
def neural():
    for name in ('ceo-energy-transformer-polish-ten-2026-10-26','ceo-repaired-transformer-extra-ten-test-2026-10-25'):
        root=OUT/name/'execution';d=read(root/'comparison.json');probs=read(root/'problems.json')
        curves=collections.defaultdict(list)
        for o in d['ceo_points']:
            curves[o['case']].append(dict(growth_step=o['iteration'],energy=o['energy_ha'],resources=resources(o)))
        for a in d['points']:
            p=probs[a['case']];md=meta(p,p['n_qubits'],p['n_electrons'])
            if md is None:continue
            # This closed comparison binds its candidate and CEO points to one
            # case-specific Hamiltonian; no cross-study geometry-only joins.
            ensure(md)
            aa=dict(energy=a['energy_ha'],resources=resources(a))
            for o in curves[a['case']]:put(md,aa,o,'Transformer生成・係数最適化 '+name,
                root/'comparison.json',scope='CLOSED_CASE_BOUND_COMPARISON',
                candidate_id=str(a.get('sample_id',a.get('request_id')))+'/'+a['stage'])
        print('READ','neural',name,len(d['points']),flush=True)
def large():
    root=OUT/'ceo-large-sector-study-2026-10-25';cfg=read(root/'config.json');cs={c['id']:c for c in cfg['cases']}
    # Already closed table; only frozen_spatial=0 H8 cases enter this view.
    import csv
    p=root/'CASE_MAXIMA.csv';files[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
    for row in csv.DictReader(p.open()):
        c=cs[row['case']]
        if c['frozen_spatial']!=0:continue
        md=dict(molecule=c['molecule'],distance_A=c['distance_A'],basis=c['basis'],n_qubits=32,n_electrons=8,
            full_orbital=True,geometry='linear chain; stored in original case')
        ensure(md)
        if row['kind']!='COMPRESSED':continue
        br={m:int(row['CEO_'+m]) for m in M};ar={m:int(row['child_'+m]) for m in M}
        put(md,dict(energy=float(row['child_energy_Ha']),resources=ar),
            dict(growth_step=int(row['comparator_step']),energy=float(row['comparator_energy_Ha']),resources=br),
            '大基底・部分空間計算',p,scope='SECTOR_CERTIFICATION_NOT_GLOBAL_QISKIT',
            candidate_id=row['case']+'/'+row['root_step']+'/'+row['endpoint'])
def main():
    portable();canonical();compressed_bank();old_policy();campaign();neural();large()
    output=[]
    for k,c in sorted(cases.items()):
        c['cohorts']=sorted(c['cohorts']);output.append(c)
    payload=dict(cases=output,case_count=len(output),inputs_sha256=files,missing=missing,
        energy_rule='E_child <= E_CEO + 1e-9 Ha; same physical problem within original binding',
        main_selection='highest observed CNOT reduction per molecule/distance/basis/electron-space with non-increasing CNOT depth',
        separate_depth_tradeoff=True,mixed_protocols_not_a_fair_method_comparison=True,new_quantum_evaluations=0,
        completeness='named portable-policy versions, bound historical TeacherBank, closed chemical campaign, closed large-sector data; arbitrary unindexed historical schemas not certified by this census')
    (HERE/'census.json').write_text(json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n')
    print('CENSUS',len(output),'conditions',len(files),'input files',flush=True)
    for c in output:
        md=c['problem_family'];b=c['best_depth_safe'];a=c['best_any_depth']
        print(md['molecule'],md['distance_A'],md['basis'],'SAFE',
            None if b is None else (b['comparator_step'],b['ceo'],b['child'],round(b['reduction_pct']['cnot'],2),b['delta_energy_Ha'],b['cohort'],b['evidence_scope']),
            'TRADE',None if a is None or not a['depth_increased'] else (a['ceo'],a['child'],round(a['reduction_pct']['cnot'],2)),flush=True)
if __name__=='__main__':main()
