"""Explicit source-only macOS execution of the immutable latest policy.

Saved comparisons, historical circuits and model artifacts are NOT readable by the
worker. This command never runs from verify/reproduce and never retries a task.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from archive import Archive,ROOT,sha256


def profile(output,runtime,frozen):
    reads=['/System','/usr','/bin','/sbin','/Library','/opt/homebrew','/dev',*runtime,str(frozen),str(output)]
    q=json.dumps
    # Same qualified system-access baseline as the original macOS dispatcher.
    # Denying all platform services aborts dyld before Python; user data and all
    # writes remain denied except the explicit numerical/input/output allowlist.
    return ('(version 1)\n(allow default)\n(deny network*)\n'
        '(deny file-read* (subpath "/Users") (subpath "/Volumes") '
        '(subpath "/private/var/folders") (subpath "/private/tmp"))\n'
        '(deny file-write*)\n(allow file-read-metadata)\n(allow file-read* '+
        ' '.join('(subpath '+q(p)+')' for p in reads)+')\n'
        '(allow file-write* (subpath '+q(str(output))+') (literal "/dev/null"))\n')


def launch(task_id,output,python=sys.executable):
    if sys.platform!='darwin' or not Path('/usr/bin/sandbox-exec').exists():
        raise RuntimeError('Compression execution is qualified for macOS sandbox-exec only. Archive verification/reconstruction are portable.')
    output=Path(output).resolve()
    if output.exists():raise FileExistsError('Use a new output directory; automatic retries/overwrites are disabled.')
    # Verify copied policy identity before copying the ONLY allowed physical input.
    for r in json.loads((ROOT/'data/metadata/policy-files.json').read_text()):
        if sha256(ROOT/r['file'])!=r['sha256']:raise ValueError('Frozen policy drift')
    a=Archive();inv=a.json('outputs/ceo-all-orbital-unified-compression-2026-10-31/inventory-v2.json')
    task=copy.deepcopy(next(t for t in inv['tasks'] if t['task_id']==task_id))
    source=a.file(task['source'])
    assert sha256(source)==task['source_sha256']
    output.mkdir(parents=True);shutil.copyfile(source,output/'source.json')
    task['source']=str(output/'source.json')
    task['forbidden_read_canary']=str(ROOT/'data/metadata/census.json')
    task['execution_id']='portable-reexecution/'+task['execution_id']
    # Frozen executor checks are preserved byte for byte.
    frozen=ROOT/'policy/frozen'
    for name,expected in task['executor_files'].items():
        f=frozen/name if name in ('bootstrap_v2.py','sector_kernel.py') else frozen/'code'/name
        if sha256(f)!=expected:raise ValueError('Task/executor mismatch: '+name)
    (output/'task.json').write_text(json.dumps(task,sort_keys=True)+'\n')
    py=Path(python).absolute()
    runtime=json.loads(subprocess.check_output([str(py),'-I','-c',
        'import sys,site,json;print(json.dumps([sys.base_prefix]+site.getsitepackages()))'],text=True))
    runtime += [str(py.parent),str(py.parent.parent/'pyvenv.cfg'),str(py.resolve().parent)]
    (output/'sandbox.sb').write_text(profile(output,runtime,frozen))
    env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL')}
    env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
        VECLIB_MAXIMUM_THREADS='1',NUMBA_NUM_THREADS='1',TMPDIR=str(output))
    cmd=['/usr/bin/sandbox-exec','-f',str(output/'sandbox.sb'),str(py),'-I',str(frozen/'bootstrap_v2.py'),
         '--task',str(output/'task.json'),'--output',str(output)]
    with (output/'worker.log').open('w') as log:
        p=subprocess.Popen(cmd,env=env,cwd='/',stdout=log,stderr=subprocess.STDOUT)
        try:code=p.wait(timeout=780)
        except subprocess.TimeoutExpired:
            p.terminate();p.wait(timeout=30)
            (output/'supervisor-failure.json').write_text(json.dumps(dict(status='TIME_CENSORED',reason='PROCESS_DEADLINE'))+'\n')
            raise RuntimeError('Preserved timeout; no automatic retry')
    if code or not (output/'result.json').is_file():
        raise RuntimeError('Preserved failed attempt; inspect worker.log. No automatic retry.')
    print(str(output/'result.json'))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--task-id',required=True);ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--python',default=sys.executable);args=ap.parse_args()
    launch(args.task_id,args.output,args.python)


if __name__=='__main__':main()
