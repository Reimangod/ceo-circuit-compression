"""Actual macOS worker-isolation/import probe, with no energy or optimization."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from run_policy import profile,ROOT


def main():
    if sys.platform!='darwin':raise SystemExit('This probe qualifies the macOS execution layer only.')
    py=Path(sys.executable).absolute()
    runtime=json.loads(subprocess.check_output([str(py),'-I','-c',
        'import sys,site,json;print(json.dumps([sys.base_prefix]+site.getsitepackages()))'],text=True))
    runtime += [str(py.parent),str(py.parent.parent/'pyvenv.cfg'),str(py.resolve().parent)]
    frozen=ROOT/'policy/frozen'
    with tempfile.TemporaryDirectory(prefix='ceo-isolation-') as temp:
        out=Path(temp).resolve();p=out/'sandbox.sb';p.write_text(profile(out,runtime,frozen))
        program=('import sys,socket,json;from pathlib import Path;'
            'sys.path[:0]='+repr([str(frozen/'code'),str(frozen)])+';'
            'import worker,sector_kernel;denied=[]\n'
            'for f in [lambda:Path('+repr(str(ROOT/'data/metadata/census.json'))+').read_bytes(),'
            'lambda:socket.create_connection(("127.0.0.1",9),timeout=.1)]:\n'
            ' try:f();denied.append(False)\n'
            ' except PermissionError:denied.append(True)\n'
            'assert denied==[True,True],denied\n'
            'print(json.dumps(dict(historical_read_denied=True,network_denied=True,worker_import=True,new_energy_calls=0)))')
        env={k:v for k,v in os.environ.items() if k in ('PATH','LANG','LC_ALL')}
        env.update(PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',
            MKL_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',NUMBA_NUM_THREADS='1',TMPDIR=str(out))
        subprocess.run(['/usr/bin/sandbox-exec','-f',str(p),str(py),'-I','-c',program],cwd='/',env=env,check=True)


if __name__=='__main__':main()
