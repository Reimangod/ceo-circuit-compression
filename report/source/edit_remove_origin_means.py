"""Narrow OOXML edit; preserve all other package parts and result numbers."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
import hashlib,json
from docx import Document

HERE=Path(__file__).resolve().parents[2]/'reproduced/report'
SOURCE=HERE/'CEO_full_orbital_policy_2026-10-31.docx'
DEST=HERE/'CEO_full_orbital_policy_2026-10-31_revised.docx'
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'm':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
W='{'+NS['w']+'}'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
original_hash=sha(SOURCE)
with ZipFile(SOURCE) as z:
    parts={i.filename:z.read(i.filename) for i in z.infolist()}
    infos=z.infolist()
root=etree.fromstring(parts['word/document.xml'])
before_math=[etree.tostring(x,method='c14n') for x in root.xpath('//m:oMath',namespaces=NS)]
def text(el):return ''.join(el.xpath('.//w:t/text()',namespaces=NS))
before_tables=[];removed=[];edits=[]
tables=root.xpath('/w:document/w:body/w:tbl',namespaces=NS)
for i,t in enumerate(tables,1):
    rows=t.xpath('./w:tr',namespaces=NS)
    values=[[text(c) for c in r.xpath('./w:tc',namespaces=NS)] for r in rows]
    before_tables.append(values)
    if '由来' not in values[0]:continue
    column=values[0].index('由来')
    assert column==len(values[0])-1
    for row in rows:
        cells=row.xpath('./w:tc',namespaces=NS)
        assert len(cells)==len(values[0])
        row.remove(cells[column])
    grid=t.find(W+'tblGrid');assert grid is not None
    grid.remove(list(grid)[column])
    removed.append(i)
assert removed==[7,8,9,10,11,12,13]

def replace_once(old,new):
    hits=[]
    for p in root.xpath('/w:document/w:body/w:p',namespaces=NS):
        if old in text(p):hits.append(p)
    assert len(hits)==1,(old,len(hits))
    p=hits[0];ts=p.xpath('.//w:t',namespaces=NS)
    # The targeted prose is a single regular run, with no inline math.
    assert len(ts)==1 and not p.xpath('.//m:oMath',namespaces=NS)
    before=ts[0].text;ts[0].text=before.replace(old,new)
    edits.append(dict(before=before,after=ts[0].text))

replace_once('全保存入力に対する平均値や, 同じ追加費用で成長継続した場合の成績は別の評価対象であった.',
             '同じ追加費用で成長継続した場合の成績は別の評価対象であった.')
replace_once('条件別最大例の比較元は異なる成長反復であり, 行の平均を全入力に対する平均圧縮率として扱うことを避けた.',
             '条件別最大例の比較元は異なる成長反復であった.')
replace_once('「現行」は本文の統一手順, 「旧統一」は過去版の統一手順, 「順位付け」は候補順位付けと再最適化, 「生成」はTransformerが生成した構造と係数の最適化, 「大基底」はH₈の別実験を表した. 「旧記録†」では比較元各点の独立認証が本集計へ未結合であり, 参考比較として扱った. 欠測や未確認を0%の結果へ置き換えず, 該当する条件を残した.',
             '本付録には現行手順, 過去版の統一手順, 候補順位付けや生成回路の再最適化, 大基底の別実験による保存記録が含まれた. 一部の旧記録は比較元各点の独立認証が本集計へ未結合の参考値として扱った. 欠測や未確認は該当条件に明記した.')

# Keep the certification qualification identifiable after deleting its column.
notes='この表の最大値は複数版の探索から得た事後最大例であった. 本文の現行手順の再現成績とは区別した. 矢印は同じ比較組の四資源であった.'
hits=[p for p in root.xpath('/w:document/w:body/w:p',namespaces=NS) if text(p)==notes]
assert len(hits)==2
for p,add in zip(hits,[
    ' 1.00, 1.50, 3.50 Åの比較元の独立認証は本集計に未結合であり, これらを参考値として扱った.',
    ' 1.50, 1.80, 2.50 Åの比較元の独立認証は本集計に未結合であり, これらを参考値として扱った.'
]):
    ts=p.xpath('.//w:t',namespaces=NS);assert len(ts)==1
    old=ts[0].text;ts[0].text=old+add;edits.append(dict(before=old,after=ts[0].text))
replace_once('H₆は12量子ビット・6電子の直鎖であった. 深さ増加を伴う行には↑を付けた. 1.25 Åと1.50 Åには, 今回の向きのエネルギー比較を満たすCNOT削減例を保存範囲で確認できなかった.',
    'H₆は12量子ビット・6電子の直鎖であった. 深さ増加を伴う行には↑を付けた. 表の削減例は比較元の独立認証が本集計に未結合の参考値であった. 1.25 Åと1.50 Åには, 今回の向きのエネルギー比較を満たすCNOT削減例を保存範囲で確認できなかった.')

assert '平均' not in text(root)
after_math=[etree.tostring(x,method='c14n') for x in root.xpath('//m:oMath',namespaces=NS)]
assert before_math==after_math
for i,t in enumerate(tables,1):
    expected=before_tables[i-1]
    if i in removed:expected=[r[:-1] for r in expected]
    actual=[[text(c) for c in r.xpath('./w:tc',namespaces=NS)] for r in t.xpath('./w:tr',namespaces=NS)]
    assert actual==expected,i
    assert len(t.find(W+'tblGrid'))==len(expected[0])
    assert '由来' not in actual[0]
parts['word/document.xml']=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
with ZipFile(DEST,'w') as z:
    for info in infos:z.writestr(info,parts[info.filename])
with ZipFile(DEST) as z,ZipFile(SOURCE) as old:
    assert z.testzip() is None
    for name in parts:
        if name!='word/document.xml':assert z.read(name)==old.read(name),name
assert sha(SOURCE)==original_hash
d=Document(DEST);assert len(d.tables)==17 and len(d.inline_shapes)==9
assert not any('平均' in p.text for p in d.paragraphs)
report=dict(source=str(SOURCE),source_sha256=original_hash,source_unchanged=True,
    destination=str(DEST),destination_sha256=sha(DEST),removed_origin_tables=removed,
    average_reduction_mentions_remaining=0,remaining_numeric_cells_unchanged=True,
    math_unchanged=True,figures_unchanged=True,other_package_parts_byte_identical=True,
    paragraph_edits=edits,visual_review='PENDING')
(HERE/'revision-no-origin-means.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='paragraph_edits'},ensure_ascii=False))
