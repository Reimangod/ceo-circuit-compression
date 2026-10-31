"""Deterministic gzip/tar data asset; original sources are never modified."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from archive import ROOT, sha256


def pack(files,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    with dest.open('wb') as raw,gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=6) as gz:
        with tarfile.open(fileobj=gz,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for p in sorted(files):
                info=tar.gettarinfo(str(p),arcname=str(p.relative_to(ROOT)))
                info.mtime=0;info.uid=info.gid=0;info.uname=info.gname='';info.mode=0o644
                with p.open('rb') as f:tar.addfile(info,f)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--include-code',action='store_true');args=ap.parse_args()
    files=list((ROOT/'data/raw').rglob('*'));files=[p for p in files if p.is_file()]
    if args.include_code:
        import subprocess
        tracked=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z']).split(b'\0')
        files += [ROOT/p.decode() for p in tracked if p]
    name='ceo-code-and-data-v1.0.0.tar.gz' if args.include_code else 'ceo-full-orbital-data-v1.0.0.tar.gz'
    p=ROOT/'dist'/name;pack(set(files),p)
    report=dict(file=name,bytes=p.stat().st_size,sha256=sha256(p),members=len(set(files)),format='tar.gz',
                scope='code-and-data' if args.include_code else 'data',visibility='PRIVATE',doi=None)
    (ROOT/'dist'/(name+'.json')).write_text(json.dumps(report,indent=2)+'\n')
    if not args.include_code:
        (ROOT/'data/metadata/release-asset.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
