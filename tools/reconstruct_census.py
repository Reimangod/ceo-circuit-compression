"""Re-run the original saved-data joins against archived full-orbital records.

Virtual paths resolve archive objects in memory. No author paths need to exist,
no historical compressor is executed, and no molecular/optimizer code is imported.
"""
import ast
import csv
import fnmatch
import io
import json
from pathlib import Path as RealPath, PurePosixPath
from archive import Archive,ROOT


def reconstruct():
    a=Archive()
    entries=set(a.entries)
    nodes=set(entries)
    for key in entries:
        nodes.update(str(p) for p in PurePosixPath(key).parents)
    class Path:
        def __init__(self,value=''):
            self.key=a.key(value) if not isinstance(value,Path) else value.key
            if self.key=='.':self.key=''
        def __str__(self):return 'archive://'+self.key
        def __repr__(self):return str(self)
        def __hash__(self):return hash(self.key)
        def __eq__(self,other):return isinstance(other,Path) and self.key==other.key
        def __truediv__(self,value):
            key=a.key(value)
            return Path(key if key.startswith('outputs/') else '/'.join(x for x in (self.key,key) if x))
        @property
        def name(self):return PurePosixPath(self.key).name
        @property
        def parent(self):return Path(str(PurePosixPath(self.key).parent))
        @property
        def parents(self):return [Path(str(p)) for p in PurePosixPath(self.key).parents]
        def exists(self):return self.key in nodes
        def read_bytes(self):return a.file(self.key).read_bytes()
        def open(self,*args,**kwargs):return io.StringIO(self.read_bytes().decode())
        def glob(self,pattern):
            prefix=self.key+'/'
            for key in sorted(nodes):
                if key.startswith(prefix):
                    rest=key[len(prefix):]
                    if len(rest.split('/'))==len(pattern.split('/')) and fnmatch.fnmatchcase(rest,pattern):yield Path(key)
        def __lt__(self,other):return self.key<other.key

    def rebase(x):
        if isinstance(x,dict):return {k:rebase(v) for k,v in x.items()}
        if isinstance(x,list):return [rebase(v) for v in x]
        if isinstance(x,str) and '/outputs/' in x and x.startswith('/'):
            return 'archive://'+a.key(x)
        return x
    tree=ast.parse((ROOT/'tools/collect_saved_source.py').read_text())
    # Extract only definitions and numerical constants, not original top-level I/O.
    definitions=[n for n in tree.body if isinstance(n,ast.FunctionDef)]
    ns=dict(Path=Path,__name__='saved_record_join',__file__='collect_saved_source.py')
    import collections,hashlib,math
    ns.update(collections=collections,hashlib=hashlib,json=json,math=math,TAU=1e-9,
        M=('cnot','cnot_depth','parameters','total_depth'),Z={'H':1,'Li':3,'Be':4,'C':6,'N':7,'O':8,'F':9},
        AO={'H':1,'Li':5,'Be':5,'C':5,'N':5,'O':5,'F':5},HERE=Path('outputs/ceo-all-orbital-historical-census-2026-10-31'),
        ROOT=Path(),OUT=Path('outputs'),files={},missing=[],cases={},candidates_seen=collections.Counter(),seen_pairs=set(),histories={})
    exec(compile(ast.Module(body=definitions,type_ignores=[]),'saved-record-functions','exec'),ns)
    def read(path):
        p=Path(path);b=p.read_bytes();ns['files'][str(p)]=hashlib.sha256(b).hexdigest()
        return rebase(json.loads(b))
    def lines(path):
        p=Path(path);b=p.read_bytes();ns['files'][str(p)]=hashlib.sha256(b).hexdigest()
        return rebase([json.loads(x) for x in b.splitlines() if x.strip()])
    ns['read']=read;ns['lines']=lines
    for name in ('portable','canonical','compressed_bank','old_policy','campaign','neural','large'):
        ns[name]()
    cases=[]
    for _,c in sorted(ns['cases'].items()):
        c['cohorts']=sorted(c['cohorts']);cases.append(c)
    expected=json.loads((ROOT/'data/metadata/census.json').read_text())['cases']
    if cases!=expected:
        diffs=[]
        for i,(c,e) in enumerate(zip(cases,expected)):
            if c!=e:diffs.append(dict(index=i,problem=c['problem_family'],different_keys=[k for k in c if c[k]!=e[k]],
                pair_counts=[c['pair_count'],e['pair_count']],cohort_differences={k:dict(actual=c['cohort_best'].get(k),expected=e['cohort_best'].get(k)) for k in set(c['cohort_best'])|set(e['cohort_best']) if c['cohort_best'].get(k)!=e['cohort_best'].get(k)}))
        raise AssertionError(json.dumps(dict(expected=len(expected),actual=len(cases),differences=diffs[:8]),ensure_ascii=False))
    return dict(status='PASS',conditions=len(cases),all_historical_case_values_and_bindings='EXACT_MATCH',
                archived_sources_read=len(ns['files']),new_molecular_calls=0,new_optimization_calls=0)


if __name__=='__main__':print(json.dumps(reconstruct(),ensure_ascii=False))
