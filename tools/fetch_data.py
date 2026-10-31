"""Download the private release's data asset; verify before safe extraction."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
from archive import ROOT,sha256


def extract(path,root):
    with tarfile.open(path,'r:gz') as tar:
        for m in tar.getmembers():
            if not m.isfile() or not m.name.startswith('data/raw/objects/'):
                raise ValueError('Unexpected archive member: '+m.name)
            dest=(root/m.name).resolve()
            if not dest.is_relative_to((root/'data/raw/objects').resolve()):
                raise ValueError('Unsafe archive member')
        for m in tar.getmembers():
            dest=root/m.name; dest.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(m) as f,dest.open('wb') as out:shutil.copyfileobj(f,out)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset',type=Path)
    ap.add_argument('--release',default='artifact-v1.0.0');args=ap.parse_args()
    info=json.loads((ROOT/'data/metadata/release-asset.json').read_text())
    with tempfile.TemporaryDirectory(prefix='ceo-data-') as tmp:
        path=args.asset
        if path is None:
            subprocess.run(['gh','release','download',args.release,'--repo','Reimangod/ceo-circuit-compression',
                '--pattern',info['file'],'--dir',tmp],check=True)
            path=Path(tmp)/info['file']
        if sha256(path)!=info['sha256']:raise ValueError('Release asset SHA-256 mismatch')
        extract(path,ROOT)
    print('Data package verified and extracted. No molecular computations were executed.')


if __name__=='__main__':main()
