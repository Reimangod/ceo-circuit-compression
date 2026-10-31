"""Exact-file bootstrap; replaces only the qualified numerical kernel."""
from pathlib import Path
import hashlib,importlib.util,json,sys,time,resource
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE/'code'),str(HERE)]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m
task=json.loads(Path(sys.argv[sys.argv.index('--task')+1]).read_text())
out=Path(sys.argv[sys.argv.index('--output')+1])
for name,digest in task['executor_files'].items():
    path=HERE/name if name in ('bootstrap_v2.py','sector_kernel.py') else HERE/'code'/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Executor drift '+name)
for name in ('cached_reference_input_simplification','canonical_resource_view','prefix_canonical_resource_view',
             'native_policy','candidate_screen_coverage','nested_candidate_screen_coverage','edit_policy'):
    load(name,HERE/'code'/(name+'.py'))
worker=load('worker_native_edit',HERE/'code/worker.py')
BlockKernel=load('sector_kernel',HERE/'sector_kernel.py').BlockKernel
started=time.monotonic()
def guard():
    if time.monotonic()-started>=task['settings']['wall_seconds']:raise worker.StopWork('TIME_CENSORED')
    if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss>int(1.5*2**30):raise worker.StopWork('MEMORY_CENSORED')
class GuardedKernel(BlockKernel):
    def __init__(self,*a,**k):super().__init__(*a,**k);self.guard=guard
class GuardedView(worker.PrefixCanonicalResourceView):
    def resources(self,*a,**k):guard();return super().resources(*a,**k)
worker.BlockKernel=GuardedKernel;worker.PrefixCanonicalResourceView=GuardedView
(out/'executor-identity.json').write_text(json.dumps(dict(files=task['executor_files'],
    unchanged_worker=True,numerical_kernel='exact-complex-occupation-sector',max_blocks=96))+'\n')
raise SystemExit(worker.main())

