"""Reconstruct saved comparisons and the report's nine figures; no molecular calls."""
import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from archive import Archive, ROOT

CURRENT = '統一Policy・全軌道'
METRICS = ('cnot', 'cnot_depth', 'parameters', 'total_depth')


def comparisons(archive):
    census = json.loads((archive.root/'data/metadata/census.json').read_text())
    selected = json.loads((archive.root/'data/metadata/report-selection.json').read_text())
    for c in census['cases']:
        for key in ('best_depth_safe', 'best_any_depth'):
            row = c[key]
            if row is None:
                continue
            assert row['child_energy_Ha'] <= row['ceo_energy_Ha'] + 1e-9
            assert row['delta_energy_Ha'] == row['child_energy_Ha'] - row['ceo_energy_Ha']
            for m in METRICS:
                expected = 100*(row['ceo'][m]-row['child'][m])/row['ceo'][m] if row['ceo'][m] else None
                assert expected == row['reduction_pct'][m]
            archive.file(row['evidence_path'])
    # Bind each current table row back to one actual archived result and comparator.
    for row in selected['current']:
        r = archive.json(row['evidence_path'])
        a = next(x for x in r['archive'] if x['candidate_id'] == row['candidate_id'])
        b = next(x for x in r['originals'] if x['growth_step'] == row['comparator_step'])
        assert a['energy'] == row['child_energy_Ha'] and a['resources'] == row['child']
        assert b['raw_native_energy'] == row['ceo_energy_Ha'] and b['raw_native_resources'] == row['ceo']
        assert b['resources'] == row['common_resources']
        assert a['resources']['cnot_depth'] <= b['resources']['cnot_depth']
    assert len(selected['current']) == 22 and len(census['cases']) == 41
    return census, selected


def font_path(explicit):
    candidates = [explicit, os.environ.get('CEO_REPORT_FONT'),
        '/Applications/Microsoft Word.app/Contents/Resources/DFonts/msmincho.ttc',
        '/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc',
        '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc']
    for p in candidates:
        if p and Path(p).is_file(): return p
    raise RuntimeError('Install a Japanese font (e.g. Noto Serif CJK) or pass --font. No font is redistributed.')


def figures(selected, destination, font):
    from PIL import Image, ImageDraw, ImageFont
    spec=importlib.util.spec_from_file_location('report_figures', ROOT/'tools/figure_functions.py')
    m=importlib.util.module_from_spec(spec)
    m.__dict__.update(Image=Image, ImageDraw=ImageDraw, ImageFont=ImageFont,
        FIG=destination, FONT=font, FIGDATA={}, METRICS=METRICS,
        JP=dict(cnot='CNOT数',cnot_depth='CNOT深さ',parameters='独立パラメータ数',total_depth='全深さ'),
        MOL={'LiH':'LiH','BeH2':'BeH₂','HF':'HF','N2':'N₂','H4':'H₄','H6':'H₆','H8':'H₈'})
    spec.loader.exec_module(m);destination.mkdir(parents=True,exist_ok=True)
    rows=selected['current']
    for mol in ('LiH','BeH2','HF','N2'):
        m.paired_bars([a for a in rows if a['molecule']==mol],mol+'-resources')
    m.reduction_matrix(rows,'current-reductions')
    m.energy_gaps(rows,'current-energy-gaps')
    m.decomposition(rows)
    chosen=[next(a for a in rows if a['molecule']==mol and a['distance_A']==r)
            for mol,r in [('LiH',1.5),('BeH2',1.3),('HF',1.5),('N2',1.3)]]
    m.two_points(chosen)
    trades=[c['best_any_depth'] for c in selected['historical_cases']
            if c['best_any_depth'] and c['best_any_depth']['depth_increased']]
    m.reduction_matrix(trades,'historical-depth-trades','過去の全軌道記録における深さ増加案')
    return m.FIGDATA


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=ROOT/'reproduced')
    ap.add_argument('--font');ap.add_argument('--tables-only',action='store_true')
    args=ap.parse_args();a=Archive();c,s=comparisons(a)
    args.output.mkdir(parents=True,exist_ok=True)
    for name,rows in [('current-pairs',s['current']),('historical-depth-safe',
            [x['best_depth_safe'] for x in c['cases'] if x['best_depth_safe']])]:
        fields=['molecule','distance_A','basis','cohort','candidate_id','comparator_step',
                'ceo_energy_Ha','child_energy_Ha','delta_energy_Ha']
        fields += [f'{side}_{m}' for side in ('ceo','child','reduction_pct') for m in METRICS]
        with (args.output/(name+'.csv')).open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
            for x in rows:
                r={k:x.get(k) for k in fields if k in x}
                r.update({f'{side}_{m}':x[side][m] for side in ('ceo','child','reduction_pct') for m in METRICS})
                w.writerow(r)
    # Displayed tables retain the revised Word's exact wording/rounding; raw pair
    # arithmetic and current candidate bindings above are reconstructed separately.
    tables=json.loads((ROOT/'data/metadata/report-tables.json').read_text())
    for i,rows in enumerate(tables,1):
        with (args.output/f'table-{i:02}.csv').open('w',newline='',encoding='utf-8') as f:
            csv.writer(f).writerows(rows)
    ids=None
    if not args.tables_only: ids=figures(s,args.output/'figures',font_path(args.font))
    report=dict(current_conditions=22,historical_conditions=41,display_tables=len(tables),
                figures=0 if ids is None else len(ids),figure_record_ids=ids,
                pair_binding='PASS',new_molecular_evaluations=0,new_optimization_calls=0,
                displayed_tables='lossless extracted presentation cells; pair arithmetic independently reconstructed')
    (args.output/'reproduction.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='figure_record_ids'},ensure_ascii=False))


if __name__=='__main__': main()
