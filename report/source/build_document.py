"""Rebuild the report from the all-orbital census, without quantum execution.

The old Word file contributes layout measurements only. No old images, tables,
experimental results, molecular kernels, optimizers, or learned models load.
"""
from pathlib import Path
import ast, collections, copy, hashlib, json, math, re, zipfile
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[2]
HERE=ROOT/'reproduced/report'
HERE.mkdir(parents=True,exist_ok=True)
CENSUS=ROOT/'data/metadata/census.json'
STUDY=ROOT/'policy/frozen'
OLD=ROOT/'report/CEO_full_orbital_policy.docx'
DEST=HERE/'CEO_full_orbital_policy_2026-10-31.docx'
FIG=HERE/'figures';FIG.mkdir(exist_ok=True)
import sys
sys.path.insert(0,str(ROOT/'tools'))
from reproduce import font_path,comparisons
from archive import Archive
FONT=font_path(None)
CURRENT='統一Policy・全軌道'
METRICS=('cnot','cnot_depth','parameters','total_depth')
JP=dict(cnot='CNOT数',cnot_depth='CNOT深さ',parameters='独立パラメータ数',total_depth='全深さ')
MOL={'LiH':'LiH','BeH2':'BeH₂','HF':'HF','N2':'N₂','H4':'H₄','H6':'H₆','H8':'H₈'}
ORDER={'LiH':0,'BeH2':1,'HF':2,'N2':3,'H4':4,'H6':5,'H8':6}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
INPUTS={str(CENSUS):sha(CENSUS),str(OLD):sha(OLD)}
census=json.loads(CENSUS.read_text())
cases=sorted(census['cases'],key=lambda c:(ORDER[c['problem_family']['molecule']],c['problem_family']['distance_A']))
_,selected=comparisons(Archive(ROOT))
main=copy.deepcopy(selected['current'])
assert len(main)==22 and len(cases)==41
for a in main:
    assert a['child_energy_Ha']<=a['ceo_energy_Ha']+1e-9
    assert a['child']['cnot_depth']<=a['common_resources']['cnot_depth']
    assert a['child']['cnot']<a['common_resources']['cnot']
for p in (STUDY/'code').glob('*.py'):INPUTS[str(p)]=sha(p)
INPUTS[str(ROOT/'docs/PROTOCOL_JA.md')]=sha(ROOT/'docs/PROTOCOL_JA.md')

def label(a):return f"{MOL[a['molecule']]} {a['distance_A']:.2f}"
def fmte(v):
    x=1000*v
    if abs(x)<1e-12:return '0'
    if abs(x)<1e-5:return f'{x:+.2e}'
    return f'{x:+.5f}'.rstrip('0').rstrip('.')
def origin(a):
    if a['cohort']==CURRENT:return '現行'
    if a['cohort'].startswith('過去統一Policy'):return '旧統一'
    if a['cohort'].startswith('Transformer'):return '生成'
    if a['cohort']=='候補順位付け・再最適化':return '順位付け'
    if a['cohort']=='大基底・部分空間計算':return '大基底'
    return '旧記録†'

# White-background scientific figures, drawn solely from the selected records.
def font(n=36):return ImageFont.truetype(FONT,n)
def tx(draw,xy,s,n=36,anchor=None,fill='black'):
    if n in (28,29,30,31,32,34):n=36
    draw.text(xy,str(s),font=font(n),fill=fill,anchor=anchor)
def canvas(w=1900,h=1260):
    im=Image.new('RGB',(w,h),'white');return im,ImageDraw.Draw(im)
def finish(im,name,records):
    p=FIG/(name+'.png');im.save(p,dpi=(300,300));FIGDATA[name]=records;return p
FIGDATA={}
def paired_bars(rows,name):
    im,d=canvas();w,h=im.size
    for k,m in enumerate(METRICS):
        ox=(k%2)*950;oy=(k//2)*605
        L,R,T,B=ox+112,ox+902,oy+108,oy+492
        tx(d,(ox+475,oy+35),JP[m],42,'mt')
        vmax=max(a['ceo'][m] for a in rows)*1.12
        for j in range(5):
            val=vmax*j/4;y=B-(B-T)*j/4
            d.line((L,y,R,y),fill='#dddddd',width=2)
            tx(d,(L-16,y),f'{val:.0f}',28,'rm')
        d.line((L,T,L,B,R,B),fill='black',width=3)
        space=(R-L)/len(rows);bw=min(31,space*.28)
        for j,a in enumerate(rows):
            mid=L+(j+.5)*space
            for offset,color,key in [(-bw,'white','ceo'),(0,'#454545','child')]:
                yy=B-(a[key][m]/vmax)*(B-T)
                d.rectangle((mid+offset,yy,mid+offset+bw,B),fill=color,outline='black',width=2)
            tx(d,(mid,B+15),f"{a['distance_A']:.2f}",28,'mt')
        tx(d,((L+R)/2,B+62),'結合長 / Å',32,'mt')
    d.rectangle((470,1210,506,1242),fill='white',outline='black',width=2);tx(d,(520,1225),'比較CEO途中回路',31,'lm')
    d.rectangle((1080,1210,1116,1242),fill='#454545',outline='black',width=2);tx(d,(1130,1225),'圧縮後',31,'lm')
    return finish(im,name,[a['candidate_id'] for a in rows])
def reduction_matrix(rows,name,title='各資源の総削減率'):
    hh=180+len(rows)*62;im,d=canvas(1900,hh);xs=[680,980,1280,1580]
    tx(d,(950,18),title,42,'mt')
    for x,m in zip(xs,METRICS):tx(d,(x,90),JP[m],33,'mm')
    for i,a in enumerate(rows):
        y=150+i*62
        tx(d,(45,y+27),label(a),34,'lm')
        for x,m in zip(xs,METRICS):
            v=a['reduction_pct'][m];shade=round(255-min(100,max(0,v))*1.65)
            d.rectangle((x-128,y,x+128,y+54),fill=(shade,)*3,outline='#bbbbbb',width=1)
            tx(d,(x,y+27),f'{v:.1f}%',32,'mm',fill='white' if shade<140 else 'black')
            if v<0:d.rectangle((x-128,y,x+128,y+54),outline='black',width=2)
    return finish(im,name,[a['candidate_id'] for a in rows])
def energy_gaps(rows,name):
    im,d=canvas(1900,170+len(rows)*59);L,R=550,1670;top=115
    bound=max(-a['delta_energy_Ha']*1000 for a in rows)*1.04
    tx(d,(950,15),'比較CEOを基準とした圧縮後のエネルギー差',42,'mt')
    for j in range(5):
        x=R-(R-L)*j/4;d.line((x,top-10,x,top+59*len(rows)),fill='#cccccc',width=2)
        tx(d,(x,top-20),f'{-bound*j/4:.1f}',30,'mb')
    for i,a in enumerate(rows):
        y=top+59*i
        tx(d,(40,y+24),label(a),34,'lm');v=a['delta_energy_Ha']*1000
        x=R+(v/bound)*(R-L)
        d.rectangle((min(x,R),y+8,max(x,R),y+40),fill='#777777',outline='black',width=1)
        tx(d,(R+20,y+24),'≈0' if abs(v)<=1e-6 else f'{v:.4f}',30,'lm')
    tx(d,((L+R)/2,top+59*len(rows)+10),'ΔE / mHa',34,'mt')
    return finish(im,name,[a['candidate_id'] for a in rows])
def decomposition(rows):
    im,d=canvas(1900,180+len(rows)*59);L,R=570,1660;T=122
    tx(d,(950,15),'元分解からのCNOT削減率の内訳',42,'mt')
    for tick in (0,25,50,75,100):
        x=L+(R-L)*tick/100;d.line((x,T-10,x,T+len(rows)*59),fill='#dddddd',width=2)
        tx(d,(x,T-20),str(tick),30,'mb')
    for i,a in enumerate(rows):
        y=T+i*59;raw=a['ceo']['cnot'];common=a['common_resources']['cnot'];child=a['child']['cnot']
        v1=100*(raw-common)/raw;v2=100*(common-child)/raw
        tx(d,(35,y+24),label(a),34,'lm');x1=L+(R-L)*v1/100;x2=L+(R-L)*(v1+v2)/100
        d.rectangle((L,y+7,x1,y+42),fill='white',outline='black',width=2)
        for x in range(int(L)-30,int(x1),16):
            lo=max(L,x);hi=min(x1,x+34)
            if hi>lo:d.line((lo,y+40,hi,y+9),fill='#777777',width=1)
        d.rectangle((x1,y+7,x2,y+42),fill='#555555',outline='black',width=2)
        tx(d,(x2+13,y+24),f'{v1+v2:.1f}%',30,'lm')
    yy=T+len(rows)*59+10
    tx(d,(L,yy),'斜線: 共通簡約',31,'lt');tx(d,(L+480,yy),'灰色: 追加の探索',31,'lt')
    return finish(im,'decomposition',[a['candidate_id'] for a in rows])
def two_points(rows):
    im,d=canvas(1900,1220)
    for k,a in enumerate(rows):
        ox=(k%2)*950;oy=(k//2)*590;L,R,T,B=ox+140,ox+855,oy+115,oy+440
        tx(d,(ox+475,oy+25),label(a)+' Å',42,'mt')
        cs=[a['ceo']['cnot'],a['child']['cnot']];delta=a['delta_energy_Ha']*1000;emin=min(0,delta)
        ymin=emin-.15*max(abs(delta),.001);ymax=max(0,delta)+.15*max(abs(delta),.001)
        xmin=min(cs)*.7;xmax=max(cs)*1.1
        xx=lambda v:L+(v-xmin)/(xmax-xmin)*(R-L)
        yy=lambda v:B-(v-ymin)/(ymax-ymin)*(B-T)
        d.line((L,T,L,B,R,B),fill='black',width=3)
        for val in (emin,0):
            y=yy(val);d.line((L,y,R,y),fill='#dddddd',width=2);tx(d,(L-12,y),f'{val:.3g}',28,'rm')
        for val in cs:tx(d,(xx(val),B+13),str(val),29,'mt')
        p1=(xx(cs[0]),yy(0));p2=(xx(cs[1]),yy(delta));d.line((*p1,*p2),fill='#888888',width=2)
        d.ellipse((p1[0]-10,p1[1]-10,p1[0]+10,p1[1]+10),fill='white',outline='black',width=3)
        d.rectangle((p2[0]-10,p2[1]-10,p2[0]+10,p2[1]+10),fill='black')
        tx(d,((L+R)/2,B+52),'CNOT数',32,'mt');tx(d,(ox+45,oy+72),'ΔE / mHa',30)
    tx(d,(950,1160),'○ 比較CEO途中回路    ■ 圧縮後    線は二点の対応',32,'mt')
    return finish(im,'two-points',[a['candidate_id'] for a in rows])

for mol in ('LiH','BeH2','HF','N2'):paired_bars([a for a in main if a['molecule']==mol],mol+'-resources')
reduction_matrix(main,'current-reductions')
energy_gaps(main,'current-energy-gaps')
decomposition(main)
selected=[next(a for a in main if a['molecule']==m and a['distance_A']==r) for m,r in [('LiH',1.5),('BeH2',1.3),('HF',1.5),('N2',1.3)]]
two_points(selected)
historical_safe=[c['best_depth_safe'] for c in cases if c['best_depth_safe']]
trades=[c['best_any_depth'] for c in cases if c['best_any_depth'] and c['best_any_depth']['depth_increased']]
reduction_matrix(trades,'historical-depth-trades','過去の全軌道記録における深さ増加案')

# A tested, native editable OMML parser is reused as code only; its old data
# loading and old figure generation never execute.
helper=Path(__file__).resolve().parent/'omml_helpers.py'
helper_text=helper.read_text().replace("['ansatz','growth'", "['exp','source','sector','common','total','search','best','cont','raw','MVP','ansatz','growth'")
parsed=ast.parse(helper_text);nodes=[n for n in parsed.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in ('mr','MathParser')]
assert len(nodes)==2
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(helper)+'::OMML_helpers_only','exec'),globals())
INPUTS[str(helper)]=sha(helper)

reference=Document(OLD);doc=Document();sec=doc.sections[0];rs=reference.sections[0]
for attr in ('page_width','page_height','top_margin','bottom_margin','left_margin','right_margin','header_distance','footer_distance'):
    setattr(sec,attr,getattr(rs,attr))
for name in ('Normal','Title','Heading 1','Heading 2','Caption'):
    src=reference.styles[name];dst=doc.styles[name]
    dst.font.name='MS Mincho';dst.font.size=src.font.size;dst.font.color.rgb=RGBColor(0,0,0);dst.font.bold=src.font.bold
    for attr in ('space_before','space_after','line_spacing','keep_with_next','keep_together','widow_control'):
        setattr(dst.paragraph_format,attr,getattr(src.paragraph_format,attr))
for st in doc.styles:
    if st.type in (1,2):
        st.font.name='MS Mincho';st.font.color.rgb=RGBColor(0,0,0)
        pr=st.element.get_or_add_rPr();rf=pr.find(qn('w:rFonts'))
        if rf is None:rf=OxmlElement('w:rFonts');pr.insert(0,rf)
        for k in ('ascii','hAnsi','eastAsia','cs'):rf.set(qn('w:'+k),'MS Mincho')
    for border in list(st.element.xpath('.//w:pBdr')):border.getparent().remove(border)
doc.styles['Normal'].paragraph_format.line_spacing=1.3
doc.styles['Normal'].paragraph_format.space_after=Pt(6)
for st in ('Heading 1','Heading 2'):
    doc.styles[st].paragraph_format.keep_with_next=True
    doc.styles[st].paragraph_format.space_before=Pt(9)
    doc.styles[st].paragraph_format.space_after=Pt(6)
doc.styles['Heading 1'].font.size=Pt(12);doc.styles['Heading 2'].font.size=Pt(10.5)
footer=sec.footer.paragraphs[0];footer.alignment=WD_ALIGN_PARAGRAPH.CENTER
field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');footer._p.append(field)
doc.core_properties.title='全軌道CEO回路の圧縮と資源比較'
doc.core_properties.subject='現行の統一探索規則と全軌道の保存比較データ'
doc.core_properties.author='';doc.core_properties.last_modified_by=''
doc.core_properties.comments=''
FNO=TNO=ENO=0;TABLE_DATA=[];BODYTEXT=[];CODE_EXCERPTS=[]
def force(r,n=None):
    r.font.name='MS Mincho';r.font.color.rgb=RGBColor(0,0,0)
    rf=r._r.get_or_add_rPr().find(qn('w:rFonts'))
    if rf is None:rf=OxmlElement('w:rFonts');r._r.get_or_add_rPr().insert(0,rf)
    for k in ('ascii','hAnsi','eastAsia','cs'):rf.set(qn('w:'+k),'MS Mincho')
    if n:r.font.size=Pt(n)
def p(s,style=None):
    pp=doc.add_paragraph(style=style);pp.paragraph_format.widow_control=True;BODYTEXT.append(s)
    for part in re.split(r'(\$[^$]+\$)',s):
        if part.startswith('$') and part.endswith('$'):
            om=OxmlElement('m:oMath')
            for n in MathParser(part[1:-1]).parse():om.append(n)
            pp._p.append(om)
        else:force(pp.add_run(part))
    return pp
def head(s,level=1,newpage=False):
    pp=p(s,'Heading '+str(level))
    if newpage:pp.paragraph_format.page_break_before=True
    return pp
def eq(s):
    global ENO;ENO+=1
    pp=doc.add_paragraph();pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    pp.paragraph_format.keep_together=True;pp.paragraph_format.space_before=Pt(5);pp.paragraph_format.space_after=Pt(7)
    om=OxmlElement('m:oMath')
    for n in MathParser(s).parse():om.append(n)
    pp._p.append(om);force(pp.add_run(f'  ({ENO})'),10)
def table(title,headers,rows,widths=None):
    global TNO;TNO+=1
    pp=p(f'表{TNO}. {title}','Caption');pp.paragraph_format.keep_with_next=True
    widths=widths or [6.96/len(headers)]*len(headers)
    t=doc.add_table(rows=1,cols=len(headers));t.alignment=WD_TABLE_ALIGNMENT.CENTER;t.autofit=False
    for i,w in enumerate(widths):t.columns[i].width=Inches(w)
    pr=t._tbl.tblPr
    borders=OxmlElement('w:tblBorders')
    for edge in ('top','bottom','left','right','insideH','insideV'):
        x=OxmlElement('w:'+edge);x.set(qn('w:val'),'nil');borders.append(x)
    pr.append(borders)
    for ri,row in enumerate([headers]+rows):
        cells=t.rows[0].cells if ri==0 else t.add_row().cells
        for ci,(c,v) in enumerate(zip(cells,row)):
            c.width=Inches(widths[ci]);c.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
            pp=c.paragraphs[0];pp.alignment=WD_ALIGN_PARAGRAPH.CENTER
            pp.paragraph_format.space_before=Pt(3);pp.paragraph_format.space_after=Pt(3);pp.paragraph_format.line_spacing=1.05
            r=pp.add_run(str(v));force(r,9);r.bold=ri==0
            cb=OxmlElement('w:tcBorders')
            for edge in ('top','bottom','left','right'):
                x=OxmlElement('w:'+edge);x.set(qn('w:val'),'single' if (ri==0 and edge in ('top','bottom')) or (ri==len(rows) and edge=='bottom') else 'nil')
                x.set(qn('w:color'),'000000');x.set(qn('w:sz'),'6');cb.append(x)
            c._tc.get_or_add_tcPr().append(cb)
            mar=OxmlElement('w:tcMar')
            for edge in ('left','right'):
                x=OxmlElement('w:'+edge);x.set(qn('w:w'),'60');x.set(qn('w:type'),'dxa');mar.append(x)
            c._tc.get_or_add_tcPr().append(mar)
        t.rows[ri]._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    TABLE_DATA.append(dict(number=TNO,title=title,headers=headers,rows=rows));p('')
def fig(name,title,width=6.85):
    global FNO;FNO+=1
    pp=doc.add_paragraph();pp.alignment=WD_ALIGN_PARAGRAPH.CENTER;pp.paragraph_format.keep_with_next=True
    pp.paragraph_format.space_after=Pt(2)
    sh=pp.add_run().add_picture(str(FIG/(name+'.png')),width=Inches(width));sh._inline.docPr.set('descr',title)
    cp=p(f'図{FNO}. {title}','Caption');cp.alignment=WD_ALIGN_PARAGRAPH.CENTER
    cp.paragraph_format.keep_with_next=False
def code(txt):
    original=txt
    txt=txt.replace("    child['generator_digest']=core.digest(dict(parent=block['generator_digest'],direction=v.tolist(),template=match['template_id']))",
        "    child['generator_digest']=core.digest(dict(\n        parent=block['generator_digest'],\n        direction=v.tolist(),\n        template=match['template_id']))")
    assert ast.dump(ast.parse(original))==ast.dump(ast.parse(txt))
    CODE_EXCERPTS.append(dict(original=original,display=txt,AST_equivalent=True))
    lines=txt.strip().splitlines()
    for line in lines:
        pp=p(line);pp.paragraph_format.line_spacing=1.02;pp.paragraph_format.space_after=Pt(0)
        for r in pp.runs:force(r,8.4)
    p('')
def extract(filename,start,end):
    src=(STUDY/'code'/filename).read_text();a=src.index(start);b=src.index(end,a+len(start));return src[a:b].strip()
def main_rows(rows):
    return [[f"{a['distance_A']:.2f}",f"{a['root_step']}/{a['comparator_step']}",
        f"{a['ceo']['cnot']}→{a['child']['cnot']}",f"{a['ceo']['cnot_depth']}→{a['child']['cnot_depth']}",
        f"{a['ceo']['parameters']}→{a['child']['parameters']}",f"{a['ceo']['total_depth']}→{a['child']['total_depth']}",
        f"{a['reduction_pct']['cnot']:.1f}%",fmte(a['delta_energy_Ha'])] for a in rows]

# Main text. All outcome numbers in this section refer to CURRENT only.
p('全軌道CEO回路の圧縮と資源比較','Title')
p('結合した交換演算子を用いる変分回路の統一探索規則')
p('2026年10月31日')
head('要旨')
p('本研究では, 結合した交換演算子（coupled exchange operators, CEO）を用いて成長させた量子回路からブロックの部分列と一変数の拘束回路を構成し, 残存パラメータを再最適化する圧縮手順を整理した. 本文の結果は, 全軌道のLiH, BeH₂, HF, N₂の22条件に同一の探索規則を適用した保存記録から集計した. 圧縮後のエネルギーが比較元のCEO途中回路以下となる条件を用い, CNOT数, CNOT深さ, 独立パラメータ数, 全深さを一組の実在回路で比較した.')
p('現行手順による条件別最大の総CNOT削減率は, LiHで84.4%, BeH₂で77.8%, HFで74.1%, N₂で13.1%であった. 総削減には既知の参照状態に基づく回路簡約と, その後の構造探索の両方が含まれた. 個々の比較元はCEO成長中の異なる時点であり, 条件別の最大値として扱った. 全保存入力に対する平均値や, 同じ追加費用で成長継続した場合の成績は別の評価対象であった.')
p('付録には, 過去の別版および別手法も含む7分子41条件の全軌道記録を併記した. 現行手順の結果, 過去版の結果, 比較元の独立認証が未結合の参考値を区分し, 各結果の由来を保持した.')
head('1 対象と比較条件')
p('全軌道とは, 採用した基底関数系から得られた空間軌道をすべて変分計算の対象とする設定を表した. 本文の4分子ではSTO-3Gを用い, 内殻軌道を凍結せず, 中性分子の全電子を扱った. 基底関数系の選択と, その内部での軌道凍結は別の操作として整理した.')
table('本文の計算対象',['分子','結合長 / Å','量子ビット数','電子数'],[
    ['LiH','1.20, 1.50, 1.80, 2.00, 2.20, 2.80, 3.00, 3.20','12','4'],
    ['BeH₂','1.20, 1.30, 1.40, 1.60, 2.00, 2.20, 2.80, 3.00','14','6'],
    ['HF','0.90, 1.50','12','10'],['N₂','0.90, 1.10, 1.30, 1.60','20','14']], [.75,3.55,1.25,1.25])
p('BeH₂の結合長はそれぞれのBe–H距離であった. 直鎖水素分子の付録データでは隣接原子間距離を用いた. 各比較は同じ幾何配置, 基底関数系, 電子数, ハミルトニアンに結合した記録内で行った.')

head('2 電子状態とCEO回路',newpage=True)
head('2 1 量子ビット上の電子状態',2)
p('一つの空間軌道には上向きスピンと下向きスピンの二つのスピン軌道が対応した. 本文では, スピン軌道の占有を1, 非占有を0とする計算基底を用いた. 例えば12量子ビットのLiHでは6空間軌道を扱い, 4電子のHartree–Fock参照状態から変分回路を作用させた. 元の電子ハミルトニアンをJordan–Wigner変換し, Pauli演算子の和として表した.')
eq(r'H=∑_{ℓ}α_{ℓ}P_{ℓ},  P_{ℓ}∈\{I,X,Y,Z\}^{⊗n}')
p('$n$は量子ビット数, $P_{ℓ}$はPauli演算子の積, $α_{ℓ}$は実係数であった. 核間反発などの定数は恒等演算子の係数に含め, 元記録と同じエネルギー原点を用いた.')
eq('|ψ(θ)⟩=U_{m}(θ_{m})⋯U_{1}(θ_{1})|Φ⟩')
eq('E(θ)=⟨ψ(θ)|H|ψ(θ)⟩')
p('$|Φ⟩$は参照状態, $U_{i}$は回路の第$i$ブロックであった. 式の右側から演算を作用させた. 一つのブロックが複数の独立変数を持つ場合, $θ_{i}$をベクトルとして扱った. ブロック数, 独立変数数, 成長反復数は別々に記録した.')
head('2 2 交換演算子と演算子プール',2)
p('量子ビットの生成消滅演算子を次式で表した. これらは一つの量子ビットの占有を変える演算であり, 異なる量子ビット間のフェルミオン符号列を伴う生成消滅演算子とは区別した.')
eq(r'Q_{p}=\frac{X_{p}+iY_{p}}{2},  Q_{p}^{†}=\frac{X_{p}−iY_{p}}{2}')
eq('A_{pq}=Q_{p}^{†}Q_{q}−Q_{q}^{†}Q_{p}')
eq('A_{pqrs}=Q_{p}^{†}Q_{q}^{†}Q_{r}Q_{s}−(Q_{p}^{†}Q_{q}^{†}Q_{r}Q_{s})^{†}')
p('$p,q,r,s$はスピン軌道の番号であった. $A^{†}=−A$を満たす生成子に実数の回転角を掛けて指数化すると, ユニタリ演算を得た. 占有配置間の交換を表すこれらの演算をQEと呼び, 元のCEO実装で定めた番号順序, 符号, 正規化を保存した.')
p('演算子プールは, 参照状態へ追加できる候補演算の集合であった. プールの番号は候補の識別子であり, 完成回路における出現位置とは別の情報であった. 同じ候補演算が回路中に複数回現れる場合も, それぞれの位置とパラメータを保持した.')

head('2 3 CEOの一変数形と多変数形',newpage=True)
p('CEOは, 同じ量子ビット集合に作用する交換生成子を組み合わせた演算であった. 一変数形をOVP, 多変数形をMVPとする原著の名称を用いた. 二つの構成生成子を$A_{1},A_{2}$とすると, 代表的な一変数形を次式で表せた. 実際の生成子と角度の係数は, 元実装に登録された回路定義を用いた.')
eq('U_{±}(φ)=exp[φ(A_{1}±A_{2})]')
p('多変数形では, 構成する交換演算の角度を独立に調整した. 回路を登録された順序の指数演算の積として表すと, 次式となった. $k$はそのブロック内の独立変数の数であり, プール全体の演算数とは異なった.')
eq('U_{MVP}(θ)=∏_{a=1}^{k}exp(θ_{a}A_{a})')
p('同じ量子ビット集合を共有する構成要素を共通の素ゲート構造で実現することがCEOの特徴であった. そのため, 角度を一つ消去したときのCNOT削減量は一律でなかった. 本研究では, 変更後の実際の素ゲート列を構築して資源を計数した.')
p('一つの独立パラメータが, 複数の素ゲートの回転角に現れる場合もあった. 素ゲート$g$の回転角を次式で表し, 登録された定数$b_{g}$と重み$w_{gk}$をそのまま引き継いだ. 回転ゲートの本数と独立パラメータ数をこの写像で区別した.')
eq('α_{g}=b_{g}+∑_{k}w_{gk}θ_{k}')
head('2 4 CEO回路の成長と圧縮の位置づけ',2)
p('元のCEO-ADAPT-VQEでは, 現在の状態に候補演算を追加したときのエネルギー変化を勾配から調べ, 元実装の選択規則に従って演算を追加した. 既存パラメータと追加パラメータを再最適化し, その回路を成長途中の保存点として残した. 一度の反復で複数の構成演算が登録される場合があり, 反復番号とブロック数を分けた.')
eq(r'g_{A}=\frac{∂}{∂t}⟨ψ|exp(−tA)Hexp(tA)|ψ⟩|_{t=0}=⟨ψ|[H,A]|ψ⟩')
p('今回の圧縮は, ここまでに得られた未圧縮のCEO保存回路を入力とした. 演算子プール全体の追加勾配を測り直す代わりに, 保存回路のブロックの削除と登録済みの拘束変換を候補とした. 学習器, 過去の圧縮回路, 過去に成功した削除位置は今回の候補生成に用いなかった.')
p('入力はハミルトニアン, 参照状態, 素ゲート定義, 元の全保存回路と各係数であった. 出力は, 適格な圧縮回路の素ゲート列, 全独立係数, 比較元の反復番号, 検証記録であった. 構造の選択と係数の最適化は, 明示した規則とBFGS法によって行った.')

head('3 圧縮回路の構成',newpage=True)
head('3 1 出発回路と比較回路',2)
p('元の成長軌跡の最終反復を$R$とし, その約3分の1, 約3分の2, 最終の3点を出発点に選んだ. 同じ反復番号となる点は重複を除いて扱う規則とし, 本文の実行では22条件について66入力を固定した. 一つの入力にはHartree–Fock状態と反復0から出発反復$r$までの保存回路が含まれた.')
p('出発反復$r$は, 広い部分列候補を構成する元であった. 別の保存反復$a$も, その時点の係数を使う局所削除候補の元となった. 採否判定の比較反復$j$は, 候補のエネルギーと資源を比較する基準であった. 表では出発点と比較点を別々に示した.')
eq('U_{S}(φ)=U_{i_{s}}(φ_{i_{s}})⋯U_{i_{1}}(φ_{i_{1}}),  i_{1}<⋯<i_{s}')
p('$S$は保持するブロック位置の集合であった. 削除後も元の相対順序を保った. 残したブロックの係数を元の保存点から引き継ぎ, その後の最適化で全残存変数を調整した. ブロックを削除しても, 軌道数とハミルトニアンは元の全軌道問題を維持した.')
head('3 2 部分列と拘束変換',2)
p('出発回路が12ブロック以下の場合は, 元の完全な集合を除く全部分集合を構成した. 候補数は最大4095であった. それより大きい回路では, 少数ブロックを保持する集合, 一つまたは二つを削除する集合, 元順序や局所変化の大きさで分散させた集合から, 有限個の候補を構成した. 出発回路の登録上限は96ブロックであった.')
p('出発点以前の各保存回路についても, 一つまたは二つのブロックを削除する候補を作った. その候補数は保持ブロック数ごとに制限し, 全保存点から交互に候補を取り出した. これにより, 最終回路の一部だけに候補を集中させることを避けた.')
p('MVPをOVPへ置き換える候補では, 登録された拘束方向$v$へ元の係数を射影して初期値を定めた. ここで$v$は符号と係数の結び付けを表す固定ベクトルであった.')
eq('min_{φ}‖θ_{source}−vφ‖^{2},  −2v^{T}θ_{source}+2(v^{T}v)φ=0')
eq(r'θ=vφ,  φ_{init}=\frac{v^{T}θ_{source}}{v^{T}v}')
p('この射影は探索の初期化であった. 元のMVPと拘束後のOVPが同じ状態を作るかどうかは, 係数と参照状態に依存した. したがって置換候補のエネルギーを再評価し, 後述の条件で採否を判定した.')

head('3 3 参照状態に基づく共通回路簡約',newpage=True)
p('既知の計算基底入力に作用する一変数の局所ブロックについて, その状態準備を二つの基底状態の重ね合わせとして表せる場合があった. このとき, 回転ゲートと少数のCNOTによる状態準備へ置き換えた. どの量子ビットが既知の0または1を保つかを回路の先頭から追跡した.')
eq('U(φ)|b⟩=exp(iχ)[cos(ωφ)|b⟩+s sin(ωφ)|b′⟩]')
p('$b,b′$は局所の計算基底配置, $ω$は登録角度の係数, $s$は符号, $χ$は全体位相であった. 有理数係数と$√2,i$からなる厳密な代数計算で, この関係を一変数の全値に対して確認した. 得られた短い回路が, 各量子ビット上で元のCNOT深さと全深さを超えない実現だけを採用した.')
p('この簡約は, 登録された参照状態から作る状態族の等価性を根拠とした. 適用できる局所入力が確定したブロックを順に置き換え, その他のブロックは元の素ゲート列を保った. 比較元CEOとすべての候補に同じ簡約を適用し, 構造探索の追加効果を分けた.')
eq(r'η_{total}=100\frac{C_{raw}−C_{child}}{C_{raw}}')
eq(r'η_{search}=100\frac{C_{common}−C_{child}}{C_{common}}')
p('$C_{raw}$は元のCEO分解のCNOT数, $C_{common}$は比較元へ共通簡約を施した後のCNOT数, $C_{child}$は圧縮後のCNOT数であった. 分母が異なるため, 総削減率と追加削減率は単純に足し合わせる量ではなかった. 内訳を一つの棒グラフで表す際は, 両成分を共通の$C_{raw}$で割った.')
p('例えばBeH₂ 1.30 Åの現行比較では, CNOT数は27から共通簡約によって9へ, 探索後に6へ減少した. 総削減率は77.8%, 共通簡約後に対する追加削減率は33.3%であった. 元分解の27に対して表す内訳は, 共通簡約66.7ポイントと追加探索11.1ポイントであった.')

head('4 候補の初期評価と計算配分',newpage=True)
head('4 1 局所変化と資源水準',2)
p('候補生成時には, 削除または置換による局所ユニタリの変化を, 全体位相に依存しない行列距離で表した. 生成子や係数の大きさだけでブロックを判断する代わりに, 登録された局所回路の行列を使った. 局所行列の次元を$d$とした.')
p('この距離は, 全体位相$χ$を変えた二つの行列のFrobeniusノルムを展開することから導いた. ユニタリ行列では$U^{†}U=V^{†}V=I$であるため, 二つの二乗項の跡はともに$d$となった. 跡の偏角に合わせて$χ$を選ぶと交差項が最大となった.')
eq('min_{χ}‖U−exp(iχ)V‖_{F}^{2}=2d−2|tr(V^{†}U)|')
eq(r'δ(U,V)=2−\frac{2}{d}|tr(V^{†}U)|')
p('削除候補では$V=I$とし, 複数ブロックを削除する候補の初期順位には対応する局所距離の和を用いた. 置換候補では元MVPと置換先OVPの距離を計算した. これは候補生成時の近似的な順位量であり, エネルギー損失の計算はハミルトニアンを用いて別に行った.')
p('各保存点の候補を, 局所距離の和をCNOT削減数で割った量と資源で整列した. 初期評価対象が上限を超えたときは, 保存点とCNOT数の水準を分散させて選んだ. 最初の128候補の規則を保った列に別の分散列を継ぎ足し, 重複を除いた最大256候補を一つの列として用いた. 実際の初期評価数は残予算にも依存した.')
head('4 2 初期エネルギーに基づく配分',2)
p('各候補の引き継いだ初期係数でエネルギーを一度評価した. その値を比較元のエネルギーと組み合わせ, 到達までに必要な改善量と, 一回の係数調整に要する換算費用を順位付けへ反映した.')
eq(r'q_{aj}=\frac{max(0,E_{a,init}−E_{j}−τ)(1+2P_{a})}{C_{j}−C_{a}}')
p('ここで$a$は候補, $j$は比較元, $P_{a}$は候補の独立変数数, $τ=10^{−9}$ Haはエネルギー比較の許容差であった. 分母が正で, 候補のCNOT深さが比較元以下である組だけを順位付けの対象とした. $q_{aj}$は測定後の初期値を使う配分規則であり, 到達に必要な評価回数の予測値そのものとしては扱わなかった.')
p('初回の待ち行列では, 保存点ごとの代表候補, CNOT数ごとの代表候補, 比較点ごとの候補列を組み合わせた. そのため実行順序は, 単純にCNOT数の最小候補だけを繰り返す手順とは異なった. 低資源の回路を重視しながら, 構造と初期値の違う複数候補へ最適化の機会を配分した.')

head('4 3 BFGSによる係数最適化',newpage=True)
p('選んだ構造の独立係数を$φ$とし, そのエネルギーと全成分の勾配を同時に計算した. BFGS法では, これまでの係数更新と勾配変化から近似逆ヘッセ行列$M$を更新し, 次の探索方向を決めた. 現行手順では, 同じ候補構造の現在の採用点に結合した行列だけを再利用した.')
p('探索方向は, 現在の係数の近傍でエネルギーを二次式として近似することから定まった. 勾配を$g$, ヘッセ行列を$H_{E}$, 係数の変化を$z$とすると, 近似式の停留条件は$g+H_{E}z=0$となった. BFGS法ではその逆行列を$M$で近似し, 直線探索によって実際の更新幅を選んだ.')
eq(r'E(φ+z)≈E(φ)+g^{T}z+\frac{1}{2}z^{T}H_{E}z,  z=−Mg')
eq('s=φ_{k+1}−φ_{k},  y=∇E(φ_{k+1})−∇E(φ_{k})')
eq(r'M_{k+1}=(I−ρsy^{T})M_{k}(I−ρys^{T})+ρss^{T},  ρ=\frac{1}{y^{T}s}')
p('行列の対称性, 正定値性, 係数点との対応を検査した. 最適化区間の境界で最良観測点へ戻るときは, その点に対応しない行列を初期化し直した. 異なる構造間へ逆ヘッセ行列を移す処理や, その対角成分から削除損失を予測する処理は, 今回の候補順位付けには含まれなかった.')
p('一候補へ最大8回の新しいエネルギー・勾配同時評価を配分して待ち行列へ戻した. これはBFGSの8反復と同じ回数ではなく, 直線探索内の評価も含む回数であった. 同じ構造に対する累積上限は100同時評価であった. 最大反復数は100, 勾配停止値は10⁻⁸に設定した.')
p('初回配分後には, まだ到達していないエネルギー差, ここまでの改善量, 使用評価回数, CNOTの利益から追加配分の順位を決めた. 次式は実装の順位量を表した. $n_{a}$は同時評価の累積回数, $Δ_{a}$は初期値からの観測改善量であった.')
eq(r'q_{a,cont}=\frac{G_{aj}}{max(Δ_{a},10^{−12})}\frac{(1+2P_{a})(1+n_{a})}{max(1,C_{j}−C_{a})}')
p('$G_{aj}=max(0,E_{a,best}−E_{j}−τ)$とした. 再配分の順位は厳しい側の未改善比較点で評価し, 各最適化区間では到達しやすい側の未改善比較点を停止目標とした. 適格な点を得た後も, 残予算と候補集合に応じて, より低エネルギーの比較点への到達を調べた.')

head('5 適格性と費用',newpage=True)
head('5 1 エネルギーと資源の判定',2)
p('比較元$j$に対して, 次の三条件を満たす候補を適格なCNOT削減例として保存した. 資源の判定には, 比較元と候補へ同じ共通簡約を施した素ゲート列を用いた.')
eq('E_{child}≤E_{CEO,j}+τ,  C_{child}<C_{common,j},  D_{child}≤D_{common,j}')
p('$C$はCNOT数, $D$はCNOT深さであった. 独立パラメータ数$P$と全深さ$T$は併せて記録し, 候補の選択にはCNOT数, 全深さ, 独立変数数, エネルギーの順序を用いた. 元の比較回路も選択肢に保ち, 条件を満たす削減例が得られなかった場合は元回路を基準出力とした.')
p('本文の条件別表では, 保存された適格な比較組から総CNOT削減率が最大の一組を表示した. 探索開始点自身に対する改善と, より短い以前の途中回路に対する改善は別の比較であった. また, 比較元のエネルギーが圧縮後より高い関係を用いたため, より低エネルギーのCEO回路との比較表とは選ばれる反復が異なった.')
p('数値許容差内で正となったエネルギー差も元の符号で保存した. 基底状態に対する絶対誤差の閾値は今回の表の採用条件に用いず, 同じ物理問題の二回路間の差を示した. 元軌跡の収束状況と, 最適化後の停留性は, この比較条件と別の属性であった.')
head('5 2 論理回路資源の計数',2)
p('CNOT数は変分回路に含まれるcx命令の個数であった. CNOT深さはCNOTだけを残し, 共有する量子ビット上で演算順序を保ったときの層数であった. 全深さは単一量子ビットゲートも含む元の素ゲート列で数え, 登録された同期命令による時点の調整を保持した. 同期命令自身は実行ゲートの一層へ加算しなかった.')
p('各量子ビット$q$の終了層$t_{q}$を0から開始し, 作用する量子ビット集合を$S_{g}$とすると, 一つのゲートの終了層を次式で更新した. CNOT深さではCNOTだけをこの更新に通し, 全深さではすべての素ゲートを通した. 最後の最大終了層を深さとした.')
eq('t_{new}=1+max_{q∈S_{g}}t_{q},  t_{q}←t_{new}  (q∈S_{g}),  D=max_{q}t_{q}')
p('資源は参照状態を準備した後の変分ゲート列を対象とした. したがってHartree–Fockの占有を作る初期Xゲートはこの資源比較に含めず, 比較する二回路で同じ扱いとした. 実機の結合図に沿った経路探索やゲート誤り率の重み付けは今回の論理資源とは別の設定であった.')
head('5 3 評価費用の換算規則',2)
eq('W=N_{E}+2N_{g},  B=2F+128+20(1+2P_{root})')
p('$N_{E}$は実行したエネルギー評価数, $N_{g}$は実行したスカラー勾配成分の数であった. 一回のエネルギーと$P$成分の勾配の同時計算を$1+2P$と換算した. $F$は参照状態を含む元保存点数であり, 先頭の$2F$は保存点の再評価と検証に対応した. 同じ式をすべての分子に用いたため, 数値の予算上限は元の回路サイズに応じて変わった.')
p('同一試行内で状態, 係数, 評価種別が完全に一致する評価を再利用した場合は, 元評価への参照を記録した. 共通簡約の代数計算と資源計数は量子エネルギーの追加評価を伴わず, 古典処理として扱った. この$W$は実機の測定ショット数や, CEO原著で測定グループを用いて算出したMeasurement Costとは別の換算量であった.')

head('6 数値計算と検証')
p('全軌道問題の量子状態は, 指定した上向き・下向きスピンの電子数を保つ全配置の部分空間で計算した. この部分空間は電子数保存則を用いた表現であり, 状態の振幅が小さい配置を切り捨てる近似とは異なった. 本文の閉殻系では, 空間軌道数を$n/2$, 各スピンの電子数を$N_{α}=N_{β}$として, 配置数を次式で表した.')
eq(r'd_{sector}=\binom{n/2}{N_{α}}\binom{n/2}{N_{β}}')
table('全軌道の計算空間',['分子','空間軌道数','各スピン電子数','保持した配置数'],[
    ['LiH','6','2, 2','225'],['BeH₂','7','3, 3','1225'],['HF','6','5, 5','36'],['N₂','10','7, 7','14400']], [1.0,1.8,1.9,2.1])
p('ハミルトニアンは同じビット反転を与えるPauli項をまとめて疎行列へ変換した. 係数の大きさによる項の削除は行わず, 元の定数項と軌道順序を保持した. 勾配は元CEOブロックの作用を用いて計算し, 参照状態上だけの等価性を持つ簡約回路を任意入力に対する等価ユニタリとして逆伝播へ流用することを避けた.')
p('エネルギーの係数微分は, 状態の微分を用いて次式で計算した. 積の微分では, 対応するブロックだけを微分した状態を作った. 実装は最終状態からブロックを逆順にたどり, 同じ順伝播とハミルトニアン作用から全成分を得る随伴法を用いた.')
eq(r'\frac{∂E}{∂φ_{k}}=2Re⟨\frac{∂ψ}{∂φ_{k}}|H|ψ⟩')
p('候補の検証では, 保存された素ゲートからQiskitで局所行列を構成し, 状態を別経路で再構成した. エネルギーはPauli項別の期待値から再計算した. 状態の規格化, 全体位相を合わせた状態差, 電子数とスピン別電子数の保存, 資源の再計数を確認した. 状態差の許容値は10⁻⁹, 部分空間からの逸脱の許容値は10⁻¹⁰であった.')
p('今回の22条件の最大例には, 元分解からの資源削減に共通簡約の効果が含まれた. 以下の図表では, 元分解と共通簡約後の比較元を区別した. 過去版の結果については保存済みの検証範囲を引き継ぎ, 付録でその範囲を示した.')

head('7 現行の統一探索規則による結果',newpage=True)
p('図1は22条件について, 比較元CEOの元分解に対する四資源の総削減率を示した. 各行は同じ一組の回路に対応した. 条件別最大例の比較元は異なる成長反復であり, 行の平均を全入力に対する平均圧縮率として扱うことを避けた.')
fig('current-reductions','現行手順の条件別最大例における四資源の総削減率',6.7)

descriptions={
'LiH':('LiHの結果','8条件のCNOT数は, 元分解の比較元に対して8.3%から84.4%減少した. 最大例は3.20 Åの45から7 CNOTへの削減であった. 1.50 Åでは112から65へ減少し, エネルギー差は−0.07070 mHaであった. 比較反復が2である複数の伸長条件では, 短い初期回路を基準にした大きな総削減が得られた.'),
'BeH2':('BeH₂の結果','1.20, 1.30, 1.40, 1.60 Åの最大例は, いずれも比較反復1に対する27から6 CNOTへの削減であった. 2.00, 2.20, 3.00 Åの最大例では比較元がより長い回路であり, 総削減率はそれぞれ7.6%, 7.1%, 8.8%であった. これらの値は共通簡約と追加探索の内訳と併せて評価した.'),
'HF':('HFの結果','0.90 Åでは85から50 CNOTへ, 1.50 Åでは27から7 CNOTへ減少した. どちらも圧縮後のエネルギーは比較元より低かった. 1.50 Åの独立パラメータ数は3を維持し, CNOT数と深さの改善は主に回路の実現方法と構造の変化に現れた.'),
'N2':('N₂の結果','4条件の総CNOT削減率は5.7%から13.1%であった. 最大例は1.30 Åの168から146 CNOTへの削減であった. すべての条件でCNOT深さと独立変数数も減少した. 微小な正のエネルギー差は, 登録した10⁻⁹ Haの許容差内として符号付きで保存した.')}
for mol in ('LiH','BeH2','HF','N2'):
    title,desc=descriptions[mol];head(title,newpage=True)
    rows=[a for a in main if a['molecule']==mol]
    p(desc)
    table('現行手順による'+MOL[mol]+'の比較',['結合長\nÅ','出発/\n比較反復','CNOT数','CNOT\n深さ','独立\n変数数','全深さ','CNOT\n削減率','ΔE\nmHa'],
        main_rows(rows),[.55,.70,1.02,.85,.65,1.02,.75,1.22])
    p('矢印は比較CEOの元分解から圧縮後への変化を表した. 出発反復と比較反復は別の番号であった. 表示したエネルギー差は一組の保存値から算出した.')
    fig(mol+'-resources',MOL[mol]+'の比較回路と圧縮回路の論理資源')

head('7 1 共通簡約と追加探索の内訳',newpage=True)
p('図6の棒全体は元分解に対する総CNOT削減率であった. 斜線部分は比較元へ共通簡約を適用した効果, 灰色部分は共通簡約後から圧縮後までの追加効果を表した. 両部分は元分解のCNOT数で割ったため, 同じ棒の中で加算できた. この区分によって, 簡約器の効果と構造探索の効果をそれぞれ読み取れる形にした.')
fig('decomposition','CNOT総削減率における共通簡約と追加探索の内訳',6.2)

head('7 2 エネルギーの対応',newpage=True)
p('図7は比較元を0としたエネルギー差を示した. 負の値は圧縮後がより低エネルギーであることを表した. 「≈0」は表示上の区分であり, 正の微小値を含む元の数値は表と付録に保持した. 3.20 ÅのLiHの差が大きいのは, 初期の比較反復2を基準とする組が選ばれたためであった.')
fig('current-energy-gaps','現行手順の最大例における比較元からのエネルギー差',6.2)

head('7 3 資源とエネルギーの二点比較',newpage=True)
p('図8では四条件について, 比較元と圧縮後の二点をCNOT数と相対エネルギーの平面へ配置した. 線は同じ比較組の対応を表した. 各二点の間に追加の回路や計算結果を補間せず, 保存された二つの状態だけを示した. この図は, CEO成長中の全軌跡や最適化の経過を描いた曲線とは役割を分けた.')
fig('two-points','CNOT数と相対エネルギーによる四条件の二点比較')
p('元のCEO軌跡における全点との関係を調べる場合には, その軌跡に結合した追加の比較が必要であった. 本図で直接確認できるのは, 表示した比較点に対して圧縮後のCNOT数が小さく, エネルギーが数値許容差内で同等または低いという関係であった.')

head('8 結果の解釈',newpage=True)
p('現行の22条件では, 共通簡約と有限予算の構造探索を組み合わせることで, 保存されたCEO途中回路に対する資源削減例を得た. 初期の短い比較回路に対して大きな割合が現れる条件と, より長い回路に対して数%から十数%の改善が現れる条件があった. その違いを比較反復と絶対CNOT数から読み取る構成とした.')
p('CNOT深さは, 同時に実行できるゲートの配置に依存した. CNOTの個数が減っても, 残るゲートが同じ量子ビットへ集中すると深さが増える場合があった. 現行手順は候補生成時と採否判定時の両方で深さを確認し, 比較元へ同じ共通簡約を施した後の深さ以下となる候補を保存した. 過去の深さ増加案は, この現行条件と分けて付録に保存した.')
p('独立パラメータ数は回路族の自由度を表した. 保存された数値が偶然一致したことや, 最終係数を固定して書き出したことを理由に自由度を減らさず, 登録された係数の結び付けから数えた. 一変数への拘束は自由度を減らす操作であり, 実際のゲート数の変化は変更後の素ゲート列から確認した.')
p('本比較のエネルギー条件は二回路間の関係を定めたものであった. 絶対的な化学精度, 厳密な基底状態への収束, すべての出発回路に対する大幅な圧縮をそれぞれ評価するには, 対応する別の基準と記録が必要であった. 本文の条件別最大例は, これらを代替する値として扱わなかった.')
p('測定費用については, 今回の換算量Wがエネルギーと勾配成分の評価回数を表した. 実機で必要な測定回数は, 測定演算子の分散, グループ化, 必要精度, 回路実行時間などにも依存した. 本文のデータ図から直接示せる結論は論理資源の削減と二回路間のエネルギー関係であり, 実機ショット数や同費用の成長継続に対する優位性は別に検証する範囲であった.')

head('付録1 全41条件の保存記録',newpage=True)
p('以下は本文の現行22条件に限定した集計とは別に, 全軌道と確認できた過去の保存結果を含む索引であった. 各条件でCNOT深さ非増加の最大例を優先し, その例が見つからなかった場合は深さ増加案を記載した. エネルギー条件は本文と同じ向きで再計算した.')
p('「現行」は本文の統一手順, 「旧統一」は過去版の統一手順, 「順位付け」は候補順位付けと再最適化, 「生成」はTransformerが生成した構造と係数の最適化, 「大基底」はH₈の別実験を表した. 「旧記録†」では比較元各点の独立認証が本集計へ未結合であり, 参考比較として扱った. 欠測や未確認を0%の結果へ置き換えず, 該当する条件を残した.')
for mol in ('LiH','BeH2','HF','N2','H4','H6','H8'):
    group=[c for c in cases if c['problem_family']['molecule']==mol]
    if mol!='LiH':head(MOL[mol]+'の保存比較',level=2,newpage=mol in ('BeH2','HF','H6'))
    else:head('LiHの保存比較',level=2)
    rows=[]
    for c in group:
        md=c['problem_family'];a=c['best_depth_safe'] or c['best_any_depth']
        if a is None:
            rows.append([f"{md['distance_A']:.2f}",'—','未確認','—','—','—','—','—']);continue
        rows.append([f"{md['distance_A']:.2f}",str(a['comparator_step']),
            f"{a['ceo']['cnot']}→{a['child']['cnot']}",f"{a['ceo']['cnot_depth']}→{a['child']['cnot_depth']}"+('↑' if a['depth_increased'] else ''),
            f"{a['ceo']['parameters']}→{a['child']['parameters']}",f"{a['ceo']['total_depth']}→{a['child']['total_depth']}",
            f"{a['reduction_pct']['cnot']:.1f}%",origin(a)])
    if mol=='H8':p('H₈は6-31Gの32量子ビット・8電子で, 凍結軌道を用いない別実験であった. 指定電子数の全配置を保持した計算であり, 元の成長計算は収束未達であった. 他の付録条件はSTO-3Gであった.')
    table(MOL[mol]+'の全軌道保存記録',['結合長\nÅ','比較\n反復','CNOT数','CNOT\n深さ','独立\n変数数','全深さ','CNOT\n削減率','由来'],rows,[.55,.5,1.02,.95,.68,1.05,.72,1.27])
    if mol=='H4':p('H₄は8量子ビット・4電子の直鎖であった. 表の未確認は, 保存範囲で指定条件のCNOT削減例を得ていないという状態を表した.')
    if mol=='H6':p('H₆は12量子ビット・6電子の直鎖であった. 深さ増加を伴う行には↑を付けた. 1.25 Åと1.50 Åには, 今回の向きのエネルギー比較を満たすCNOT削減例を保存範囲で確認できなかった.')
    if mol in ('LiH','BeH2'):p('この表の最大値は複数版の探索から得た事後最大例であった. 本文の現行手順の再現成績とは区別した. 矢印は同じ比較組の四資源であった.')

head('付録2 深さ増加案とエネルギー',newpage=True)
p('過去記録のうち, CNOT数をさらに減らす代わりにCNOT深さが増えた12比較組を次表にまとめた. BeH₂ 2.00 ÅとH₈ 2.00 Åには, 深さ非増加の例と別にこの案が存在した. 現行手順の深さ非増加条件の成功件数へは加えなかった.')
table('全軌道の深さ増加案',['条件 / Å','比較\n反復','CNOT数','CNOT\n深さ','独立\n変数数','全深さ','ΔE\nmHa'],[
    [label(a),str(a['comparator_step']),f"{a['ceo']['cnot']}→{a['child']['cnot']}",f"{a['ceo']['cnot_depth']}→{a['child']['cnot_depth']}",
     f"{a['ceo']['parameters']}→{a['child']['parameters']}",f"{a['ceo']['total_depth']}→{a['child']['total_depth']}",fmte(a['delta_energy_Ha'])] for a in trades],
    [1.15,.5,1.05,1.02,.72,1.1,1.22])
fig('historical-depth-trades','過去の深さ増加案における四資源の削減率',6.6)

head('付録3 比較組の絶対エネルギー',newpage=True)
p('表のエネルギーは元のハミルトニアンに含まれる定数項を保持した値であった. 表示桁で同じ値となる組についても, エネルギー差は保存された倍精度値から計算した. 現行22条件と過去最大例を分け, 資源の比較行を識別できる形にした.')
table('現行22条件の絶対エネルギー',['条件 / Å','比較\n反復','比較CEO / Ha','圧縮後 / Ha','ΔE / mHa'],[
    [label(a),a['comparator_step'],f"{a['ceo_energy_Ha']:.12f}",f"{a['child_energy_Ha']:.12f}",fmte(a['delta_energy_Ha'])] for a in main],
    [1.05,.5,1.8,1.8,1.25])
extras=[]
for c in cases:
    a=c['best_depth_safe'] or c['best_any_depth']
    if a and a['cohort']!=CURRENT:extras.append(a)
head('過去最大例の絶対エネルギー',2,newpage=True)
table('付録の過去最大例の絶対エネルギー',['条件 / Å','比較\n反復','比較CEO / Ha','圧縮後 / Ha','ΔE / mHa'],[
    [label(a),a['comparator_step'],f"{a['ceo_energy_Ha']:.12f}",f"{a['child_energy_Ha']:.12f}",fmte(a['delta_energy_Ha'])] for a in extras],
    [1.05,.5,1.8,1.8,1.25])
p('この記録集合には, 全軌道と確認できた41条件のうち26条件で深さ非増加のCNOT削減例があり, 深さ増加を許した場合は36条件にCNOT削減例があった. これらは参考値を含む保存記録の条件数であり, 独立な無作為標本数や成功確率の推定値とは分けた. 残る5条件はBeH₂ 1.00 Å, H₄ 1.00 Åと2.00 Å, H₆ 1.25 Åと1.50 Åであった.')
p('過去版には結果ファイルのない294試行枠があり, その枠は欠測として保持した. 同じ物理条件が複数版に現れるため, 294を独立な分子条件数や失敗条件数へ読み替えなかった. H₂OとNH₃の確認した旧記録は凍結軌道または活性空間の設定であり, 全軌道表の対象外であった.')

head('付録4 実装と再現情報',newpage=True)
table('現行の処理と実装の対応',['処理','ファイルと関数'],[
    ['部分列の有限生成','descriptors.py / descriptors'],
    ['保存点と拘束変換','native_policy.py / source_candidates, replacement'],
    ['最大256初期候補の列','edit_policy.py, nested_candidate_screen_coverage.py'],
    ['初回の最適化配分','native_policy.py / coverage_order'],
    ['観測改善に基づく再配分','native_policy.py / continuation_key'],
    ['一待ち行列とBFGSの区間','worker.py / main'],
    ['適格回路の独立検証と保存','worker.py / admit, certify'],
    ['参照状態に基づく共通簡約','cached_reference_input_simplification.py / simplify_frame'],
    ['共通簡約後の資源計数','prefix_canonical_resource_view.py / resources'],
    ['エネルギーと勾配','sector_kernel.py / BlockKernel'],
], [2.6,4.2])
p('以下は現行コードから取り出した拘束変換の抜粋であった. vが登録された座標方向, phiが一変数形の初期値であった. 候補の構築後にエネルギーと資源を評価する順序は本文と対応した.')
code(extract('native_policy.py','def replacement(block,match):','\ndef blocks_for'))
p('追加配分の順位量は次の関数であった. 比較元との残差, 初期値からの改善, 同時評価回数, パラメータ数, CNOTの利益が一つの値に現れた. 同点時には資源と候補識別子を用いた.')
code(extract('native_policy.py','def continuation_key(probe,target,tol):','\ndef easiest_target_for'))
head('データの結合と数値の再現',2,newpage=True)
p('結果の集計元はceo-all-orbital-historical-census-2026-10-31/census.jsonであった. このファイルは比較回路, 圧縮回路, 比較元エネルギー, 出力エネルギー, 各資源, 元結果ファイル, 検証範囲を保存した. 現行手順の結果はcohort_best内の「統一Policy・全軌道」だけを本文へ取り出した.')
p('本文の図表に用いた比較組は, 元result.jsonの候補識別子と比較反復へ再結合した. 元分解の資源, 共通簡約後の資源, 圧縮後の資源を同じ組で照合した. 本文と付録の数値は新しい分子計算や追加の最適化で補わず, 保存値から計算した.')
p('出典と数値結合の機械可読記録には, 比較元識別子, 候補識別子, 使用元ファイルのSHA-256を含めた. 同一物理問題への結合と数値の再現を確認する根拠として用いた.')
head('参考資料',2)
p('[1] M. Ramôa, P. G. Anastasiou, L. P. Santos, N. J. Mayhall, E. Barnes, S. E. Economou, Reducing the resources required by ADAPT-VQE using coupled exchange operators and improved subroutines, npj Quantum Information 11, 86 (2025). DOI: 10.1038/s41534-025-01039-4. CEO, OVP, MVPおよび原著の資源分解の出典.')
p('[2] CEO原著公開コード, mafaldaramoa/ceo-adapt-vqe, 固定コミットa3f89d03e6a03c89767d3cf8ee7657a57653dda0. 回路構成と素ゲート規約の参照元.')
p('[3] 全軌道CEO回路への統一圧縮Policyの適用, 2026年10月31日. PROTOCOL_JA.mdおよびcode内の凍結済み実装. 本文の候補生成, 待ち行列, 予算, 採否規則の出典.')
p('[4] 全軌道保存データの照合集計, 2026年10月31日. census.json. 本文22条件と付録41条件の数値および比較関係の出典.')

# OOXML theme font, fields and package hygiene.
settings=doc.settings.element;upd=settings.find(qn('w:updateFields'))
if upd is None:upd=OxmlElement('w:updateFields');settings.append(upd)
upd.set(qn('w:val'),'true')
for rel in doc.part.rels.values():
    if rel.reltype.endswith('/theme'):
        from lxml import etree
        root=etree.fromstring(rel.target_part.blob)
        ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        for n in root.xpath('//a:fontScheme/a:majorFont/*|//a:fontScheme/a:minorFont/*',namespaces=ns):
            if n.tag in ('{'+ns['a']+'}latin','{'+ns['a']+'}ea','{'+ns['a']+'}cs') or n.get('script')=='Jpan':n.set('typeface','MS Mincho')
        rel.target_part._blob=etree.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
doc.save(DEST)
assert sha(OLD)==INPUTS[str(OLD)] and sha(CENSUS)==INPUTS[str(CENSUS)]
with zipfile.ZipFile(DEST) as z:
    assert z.testzip() is None
    assert len([x for x in z.namelist() if x.startswith('word/media/')])==FNO
    for name in [n for n in z.namelist() if n.endswith('.xml')]:
        from lxml import etree
        etree.fromstring(z.read(name))
receipt=dict(document=str(DEST),document_sha256=sha(DEST),source_files=INPUTS,
    results_source=str(CENSUS),current_conditions=22,all_full_orbital_conditions=41,
    new_molecular_evaluations=0,new_optimization_calls=0,new_model_training=0,
    figures=FNO,tables=TNO,equations=ENO,figure_record_ids=FIGDATA,table_data=TABLE_DATA,code_excerpts=CODE_EXCERPTS,
    old_media_reused=0,old_document_unchanged=True,limitations=['historical maxima mix methods and budgets',
    'old-record baseline certificates not individually joined','only selected matched points, no interpolated CEO trajectory',
    'logical resources and W model, not actual shot or matched-growth superiority'])
(HERE/'build-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
(HERE/'selected-data.json').write_text(json.dumps(dict(current=main,historical_cases=cases),ensure_ascii=False,sort_keys=True)+'\n')
print(json.dumps(dict(path=str(DEST),figures=FNO,tables=TNO,equations=ENO,bytes=DEST.stat().st_size),ensure_ascii=False))
