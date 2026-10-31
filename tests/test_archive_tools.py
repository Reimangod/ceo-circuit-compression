import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from archive import Archive,sha256
from fetch_data import extract


def test_scope_and_current_subset():
    c=json.loads((ROOT/'data/metadata/census.json').read_text())
    assert len(c['cases'])==41
    current=[x for x in c['cases'] if '統一Policy・全軌道' in x['cohort_best']]
    assert len(current)==22
    assert {x['problem_family']['molecule'] for x in current}=={'LiH','BeH2','HF','N2'}
    assert all(x['problem_family']['full_orbital'] for x in c['cases'])


def test_no_mean_or_origin_column_in_word():
    with ZipFile(ROOT/'report/CEO_full_orbital_policy.docx') as z:
        assert z.testzip() is None
        root=ET.fromstring(z.read('word/document.xml'))
        assert len([x for x in z.namelist() if x.startswith('word/media/')])==9
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    assert '平均' not in ''.join(x.text or '' for x in root.findall('.//w:t',ns))
    tables=root.findall('w:body/w:tbl',ns)
    assert len(tables)==17
    for t in tables:
        assert '由来' not in ''.join(x.text or '' for x in t.find('w:tr',ns).findall('.//w:t',ns))


def test_frozen_hashes():
    for x in json.loads((ROOT/'data/metadata/policy-files.json').read_text()):
        assert sha256(ROOT/x['file'])==x['sha256']


def test_individual_parameter_and_unknown_values_preserved():
    a=Archive()
    x=a.jsonl('outputs/genvqe-ceo-teacher-2026-09-26/v1.2/execution/artifacts/canonical-normalized-v1/circuits.jsonl') if (ROOT/'data/raw/objects').exists() else None
    if x is None:
        import pytest;pytest.skip('Release data required for canonical-circuit test')
    assert x and all('parameter_binding_map' in row and 'coefficients' in row for row in x)
    assert any(row['energy_error_reference'] is None for row in a.jsonl('outputs/genvqe-ceo-teacher-2026-09-26/v1.2/execution/artifacts/canonical-normalized-v1/evaluations.jsonl'))


def test_no_historical_compressor_or_model_files():
    assert not list((ROOT/'policy').rglob('*.pt'))
    assert not list((ROOT/'policy').rglob('*.pkl'))
    assert not list((ROOT/'policy').rglob('*.safetensors'))
    assert set(p.name for p in (ROOT/'policy/frozen/code').glob('*.py'))=={
        Path(x['file']).name for x in json.loads((ROOT/'data/metadata/policy-files.json').read_text()) if '/code/' in x['file']}


def test_aliases_do_not_drop_evaluations():
    a=Archive()
    assert len(a.manifest['aliases'])==66
    assert all(x['source_path'].endswith('/progress.json') and x['same_as'].endswith('/result.json') for x in a.manifest['aliases'])


def test_archive_rejects_traversal(tmp_path):
    p=tmp_path/'bad.tar.gz'
    with tarfile.open(p,'w:gz') as t:
        i=tarfile.TarInfo('data/raw/objects/../../../../outside');i.size=1;t.addfile(i,io.BytesIO(b'x'))
    import pytest
    with pytest.raises(ValueError):extract(p,tmp_path/'dest')


def test_archive_rejects_symlink(tmp_path):
    p=tmp_path/'bad.tar.gz'
    with tarfile.open(p,'w:gz') as t:
        i=tarfile.TarInfo('data/raw/objects/link');i.type=tarfile.SYMTYPE;i.linkname='/etc/passwd';t.addfile(i)
    import pytest
    with pytest.raises(ValueError):extract(p,tmp_path/'dest')


def test_pair_arithmetic_and_actual_current_binding():
    if not (ROOT/'data/raw/objects').exists():
        import pytest;pytest.skip('Release asset required')
    from reproduce import comparisons
    c,s=comparisons(Archive());assert len(c['cases'])==41 and len(s['current'])==22


def test_all_raw_objects_and_ledger():
    if not (ROOT/'data/raw/objects').exists():
        import pytest;pytest.skip('Release asset required')
    from verify import verify
    r=verify();assert r['status']=='PASS' and r['ledger_search_W']==117745


def test_policy_launch_rejects_existing_output(tmp_path,monkeypatch):
    import run_policy
    monkeypatch.setattr(run_policy.sys,'platform','darwin')
    # Existing directory is checked before any molecular execution.
    if Path('/usr/bin/sandbox-exec').exists():
        import pytest
        with pytest.raises(FileExistsError):run_policy.launch('invalid',tmp_path)


def test_no_fabricated_doi_or_coauthors():
    text=(ROOT/'CITATION.cff').read_text()
    assert '\ndoi:' not in text
    assert text.count('family-names:')==1
