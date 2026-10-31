"""Preserve historical symlink names without duplicating their data objects."""
import argparse
import json
from pathlib import Path
from archive import Archive,ROOT,sha256


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);args=ap.parse_args()
    source=args.source_root.resolve();a=Archive();m=a.manifest
    index=json.loads((ROOT/'data/metadata/census.json').read_text())['inputs_sha256']
    snapshot={Archive.key(k):v for k,v in index.items()}
    assert len(snapshot)==834
    (ROOT/'data/metadata/source-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,sort_keys=True)+'\n')
    existing={x['source_path'] for x in m['files']};restored=[]
    for key,expected in snapshot.items():
        p=source/key;resolved=str(p.resolve().relative_to(source))
        if key==resolved or key in existing:continue
        entry=a.entries[resolved]
        assert sha256(p)==expected==entry['object_sha256']
        m['files'].append(dict(source_path=key,source_sha256=expected,source_bytes=p.stat().st_size,
            object_sha256=entry['object_sha256'],object_bytes=entry['object_bytes'],
            selection='BYTE_IDENTICAL_HISTORICAL_PATH_ALIAS',same_as=resolved,
            independence='SAME_SAVED_RESULT_NOT_AN_INDEPENDENT_EXPERIMENT',media_type=p.suffix,record_locators=[]))
        restored.append(dict(source_path=key,same_as=resolved,sha256=expected))
    (ROOT/'data/metadata/archive-manifest.json').write_text(json.dumps(m,ensure_ascii=False,sort_keys=True)+'\n')
    (ROOT/'data/metadata/historical-path-aliases.json').write_text(json.dumps(restored,ensure_ascii=False,sort_keys=True)+'\n')
    print(json.dumps(dict(restored=len(restored),additional_objects=0)))


if __name__=='__main__':main()
