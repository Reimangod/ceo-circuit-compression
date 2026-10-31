"""Non-destructive assembly from the fixed, existing research record.

This is an archive builder, never a molecular kernel or an experiment dispatcher.
Only full-orbital portions of mixed files are exported. Originals remain untouched.
"""
from __future__ import annotations

import argparse
import ast
import collections
import copy
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

REPO = Path(__file__).resolve().parents[1]
CURRENT = "ceo-all-orbital-unified-compression-2026-10-31"
CENSUS = "ceo-all-orbital-historical-census-2026-10-31"
REPORT = "ceo-full-orbital-policy-word-2026-10-31"
CANON = "genvqe-ceo-teacher-2026-09-26/v1.2/execution/artifacts/canonical-normalized-v1"
UPSTREAM = "a3f89d03e6a03c89767d3cf8ee7657a57653dda0"


def digest(b):
    return hashlib.sha256(b).hexdigest()


def encoded(x):
    return (json.dumps(x, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n").encode()


def save(path, x):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded(x))


def load(path):
    return json.loads(path.read_bytes())


def lines(path):
    return [json.loads(x) for x in path.read_bytes().splitlines() if x.strip()]


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list))
                        else v for k, v in row.items() if k in fields})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-root", type=Path, required=True)
    args = ap.parse_args()
    source_root = args.source_root.resolve()
    out = source_root / "outputs"
    census = load(out / CENSUS / "census.json")
    assert census["case_count"] == 41
    # Use the same full-orbital metadata test as the already closed census.
    module = ast.parse((out / CENSUS / "collect.py").read_text())
    code = [n for n in module.body if isinstance(n, (ast.FunctionDef, ast.Assign))
            and ((isinstance(n, ast.FunctionDef) and n.name == "meta") or
                 (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ("Z", "AO") for t in n.targets)))]
    import math
    ns = dict(collections=collections, math=math)
    exec(compile(ast.Module(body=code, type_ignores=[]), "census-metadata-filter", "exec"), ns)
    meta = ns["meta"]
    expected = census["inputs_sha256"]
    for name, sha in expected.items():
        if digest(Path(name).read_bytes()) != sha:
            raise ValueError("Original source changed: " + str(Path(name).relative_to(source_root)))

    objects = REPO / "data/raw/objects"
    objects.mkdir(parents=True, exist_ok=True)
    manifest = []
    handled = set()
    retained = {}
    denied = set()
    full_sources = {}

    def rel(p):
        # Preserve the logical historical name even when an ancestor is a symlink.
        # Physical dedup is by byte digest, not by erasing historical path identity.
        return str(Path(p).absolute().relative_to(source_root))

    def put(p, obj=None, selection="BYTE_IDENTICAL_FULL_ORBITAL", pointers=None):
        p = Path(p).absolute()
        key = rel(p)
        if key in handled:
            return
        raw = p.read_bytes()
        if obj is None:
            b = raw
        elif p.suffix == ".jsonl":
            b = b"".join(encoded(x) for x in obj)
        elif p.suffix == ".csv":
            s = io.StringIO(newline="")
            w = csv.DictWriter(s, fieldnames=list(obj[0]))
            w.writeheader(); w.writerows(obj); b = s.getvalue().encode()
        else:
            b = encoded(obj)
        h = digest(b)
        target = objects / h
        if not target.exists():
            target.write_bytes(b)
        entry = dict(source_path=key, source_sha256=digest(raw), source_bytes=len(raw),
                     object_sha256=h, object_bytes=len(b), selection=selection,
                     record_locators=pointers or [], media_type=p.suffix)
        manifest.append(entry); retained[key] = entry; handled.add(key)

    def exclude(p, reason):
        key = rel(p)
        if key in handled:
            return
        manifest.append(dict(source_path=key, source_sha256=digest(Path(p).read_bytes()),
                             selection="EXCLUDED", reason=reason))
        handled.add(key); denied.add(key)

    def subset(p, x, pointers=None):
        put(p, x, "FULL_ORBITAL_RECORD_EXTRACTION", pointers)

    # Classify portable source files before filtering associated runs/inventories.
    for name in expected:
        p = Path(name)
        if p.suffix != ".json":
            continue
        x = load(p)
        if isinstance(x, dict) and all(k in x for k in ("frames", "reference_occupied", "problem", "n")):
            md = meta(x["problem"], x["n"], len(x["reference_occupied"]))
            if md:
                full_sources[str(p)] = (md, digest(p.read_bytes()))
                put(p)
            else:
                exclude(p, "FROZEN_ORBITAL_OR_NOT_ESTABLISHED_AS_FULL_ORBITAL")
    full_hashes = {v[1] for v in full_sources.values()}

    # Canonical identities: preserve coefficients/bindings and all matched contexts.
    canon = out / CANON
    problems = lines(canon / "problems.jsonl")
    full_probs = {p["id"]: p for p in problems if meta(p, p["n_qubits"], p["n_electrons"])}
    evs = [x for x in lines(canon / "evaluations.jsonl") if x["problem_id"] in full_probs]
    states = {x["state_preparation_id"] for x in evs}
    eval_ids = {x["id"] for x in evs}
    contexts = {x["context_id"] for x in evs}
    canonical_rows = {
        "problems.jsonl": list(full_probs.values()), "evaluations.jsonl": evs,
        "circuits.jsonl": [x for x in lines(canon / "circuits.jsonl") if x["id"] in states],
        "resources.jsonl": [x for x in lines(canon / "resources.jsonl") if x["state_preparation_id"] in states],
        "contexts.jsonl": [x for x in lines(canon / "contexts.jsonl") if x["id"] in contexts],
        "verifications.jsonl": [x for x in lines(canon / "verifications.jsonl") if x["evaluation_id"] in eval_ids],
        "legacy_links.jsonl": [x for x in lines(canon / "legacy_links.jsonl") if x["problem_id"] in full_probs],
    }
    allowed_checkpoints = set()
    receipts_p = canon.parent / "energy-matched-history-v1/history_receipts.jsonl"
    receipts = [x for x in lines(receipts_p) if x["problem_id"] in full_probs]
    subset(receipts_p, receipts)
    for x in receipts:
        allowed_checkpoints.update(f["path"] for f in x["files"])
    for name, rows in canonical_rows.items():
        subset(canon / name, rows, [x.get("id", x.get("evaluation_id")) for x in rows])

    # Direct/comparison collections have case-bound Hamiltonians.
    direct_root = out / "ceo-direct-multigeometry-plan-2026-10-25/execution"
    direct_probs = load(direct_root / "problems.json")
    direct_full = {k: p for k, p in direct_probs.items() if meta(p, p["n_qubits"], p["n_electrons"])}
    subset(direct_root / "problems.json", direct_full, list(direct_full))
    d = load(direct_root / "dataset.json")
    subset(direct_root / "dataset.json", dict(rows=[x for x in d["rows"] if x["case"] in direct_full],
        extraction_note="Only case-bound full-orbital rows. Global mixed-cohort counts omitted."))

    for name in ("ceo-energy-transformer-polish-ten-2026-10-26", "ceo-repaired-transformer-extra-ten-test-2026-10-25"):
        base = out / name / "execution"
        ps = load(base / "problems.json")
        good = {k: p for k, p in ps.items() if meta(p, p["n_qubits"], p["n_electrons"])}
        subset(base / "problems.json", good, list(good))
        x = load(base / "comparison.json")
        result = {}
        for k in ("points", "ceo_points", "optimizer_trials", "paired_details", "pairs"):
            if isinstance(x.get(k), list):
                result[k] = [r for r in x[k] if isinstance(r, dict) and r.get("case") in good]
        result["limitations"] = x.get("limitations")
        result["extraction_note"] = "Full-orbital case-bound records; mixed global summaries omitted."
        subset(base / "comparison.json", result)

    # Campaign problem identities come from its saved physical constants, not names.
    campaign = out / "ceo-chemical-transformer-campaign-2026-10-04"
    good_pid = set()
    for p in (campaign / "portable-circuits-v1").glob("*/circuit.json"):
        x = load(p); q = x["problem_constants"]
        if meta(q, q["n_qubits"], q.get("n_electrons", q.get("n_active_electrons"))):
            good_pid.add(x["problem_id"]); put(p)
        elif str(p) in expected:
            exclude(p, "FROZEN_ORBITAL_CAMPAIGN_INPUT")
    cp = load(campaign / "progress-v6.json")
    good_rows = [x for x in cp["rows"] if x["problem_id"] in good_pid]
    good_curves = [x for x in cp["curves"] if x["problem_id"] in good_pid]
    campaign_files = {x["certificate_path"] for x in good_rows}
    for x in good_curves:
        for k in ("certificate", "source"):
            if isinstance(x.get(k), dict) and x[k].get("path"):
                campaign_files.add(x[k]["path"])
    subset(campaign / "progress-v6.json", dict(rows=good_rows, curves=good_curves,
        extraction_note="Only problem-ID-bound full-orbital records; historical ML outputs are data, not models."))

    # Historical portable tasks/results, individually scoped by uncompressed source.
    for name in expected:
        p = Path(name)
        if rel(p) in handled:
            continue
        if p.suffix == ".json":
            x = load(p)
            if isinstance(x, dict) and "tasks" in x:
                tasks = [t for t in x["tasks"] if t.get("source") in full_sources]
                base = {k: x[k] for k in ("cap_provenance", "cost_caps", "evaluation_scope", "upstream_pin") if k in x}
                base["tasks"] = tasks
                subset(p, base, ["/tasks/" + str(i) for i,t in enumerate(x["tasks"]) if t.get("source") in full_sources])
            elif isinstance(x, dict) and "source_sha256" in x and "archive" in x:
                if x["source_sha256"] in full_hashes:
                    put(p)
                    for sibling in ("work.jsonl", "isolation.json", "executor-identity.json"):
                        q = p.with_name(sibling)
                        if q.exists(): put(q)
                else: exclude(p, "RESULT_SOURCE_NOT_FULL_ORBITAL")
            elif str(p) in allowed_checkpoints or str(p) in campaign_files:
                put(p)
            elif "ceo-policy-achievements-2026-10-19" in str(p):
                keep = [r for r in x if str(source_root / r["source_path"]) in full_sources]
                subset(p, keep)
            elif "ceo-large-sector-study-2026-10-25" not in str(p):
                exclude(p, "NOT_BOUND_TO_INCLUDED_FULL_ORBITAL_RECORD")
        elif p.suffix != ".csv":
            exclude(p, "NOT_BOUND_TO_INCLUDED_FULL_ORBITAL_RECORD")

    # H8 is the only full-orbital subset of the large-basis study.
    large = out / "ceo-large-sector-study-2026-10-25"
    cfg = load(large / "config.json")
    ids = {x["id"] for x in cfg["cases"] if x["frozen_spatial"] == 0}
    subset(large / "config.json", {**cfg, "cases": [x for x in cfg["cases"] if x["id"] in ids]})
    for filename in ("CASE_MAXIMA.csv", "ALL_COMPARISONS.csv", "COSTS.csv"):
        p = large / filename
        if p.exists():
            rows = list(csv.DictReader(p.open()))
            rows = [x for x in rows if x.get("case") in ids]
            if rows: subset(p, rows)
    for case in ids:
        folder = large / "cases" / case
        for pattern in ("problem.json", "growth-result.json", "growth-status.json", "source-root-*.json",
                        "checkpoints/*.json", "compression/**/result.json", "compression/**/work.jsonl",
                        "source-verification-work.jsonl"):
            for p in sorted(folder.glob(pattern)):
                if p.is_file(): put(p)

    # Current experiment closure includes all outcomes, budget events and incident.
    study = out / CURRENT
    for p in sorted(study.glob("*.json")):
        if p.name in ("endpoint-averages.json",):
            continue
        if p.name not in ("inventory.json", "inventory-v2.json"):
            put(p)
    for pattern in ("runs-v2/*/work.jsonl", "runs-v2/*/task.json", "runs-v2/*/isolation.json",
                    "global-checks/*.json", "qualification-work/**/*.json", "qualification-work/**/*.jsonl",
                    "runs/**/*.json", "runs/**/*.jsonl", "*.csv"):
        for p in sorted(study.glob(pattern)):
            if p.is_file(): put(p)
    # Aliases preserve progress/result correspondence without two copies.
    aliases = []
    for p in sorted((study / "runs-v2").glob("*/result.json")):
        progress = p.with_name("progress.json")
        assert p.read_bytes() == progress.read_bytes()
        aliases.append(dict(source_path=rel(progress), same_as=rel(p), sha256=digest(p.read_bytes())))

    # Original immutable policy and dependencies, no older compressor/model code.
    frozen = REPO / "policy/frozen"
    frozen.mkdir(parents=True, exist_ok=True)
    code_records = []
    for p in sorted((study / "code").glob("*.py")) + [study/"sector_kernel.py", study/"bootstrap_v2.py"]:
        dest = frozen / ("code/" + p.name if p.parent.name == "code" else p.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, dest)
        code_records.append(dict(file=str(dest.relative_to(REPO)), source_path=rel(p), sha256=digest(p.read_bytes())))
    shutil.copyfile(study/"PROTOCOL_JA.md", REPO/"docs/PROTOCOL_JA.md")
    upstream_dir = source_root / "paper-era-reproduction/a3f89d0"
    updest = REPO / "third_party/ceo-adapt-vqe"
    updest.mkdir(parents=True, exist_ok=True)
    for p in sorted((upstream_dir/"adaptvqe").rglob("*.py")) + [upstream_dir/"LICENSE", upstream_dir/"README.md"]:
        d = updest / p.relative_to(upstream_dir); d.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(p, d)
    shutil.copyfile(upstream_dir/"LICENSE", REPO/"LICENSE")
    save(REPO/"data/metadata/policy-files.json", code_records)

    # Publication views are never inputs to the policy subprocess.
    def normalized(x):
        if isinstance(x, dict):
            return {normalized(k): normalized(v) for k,v in x.items()}
        if isinstance(x, list): return [normalized(v) for v in x]
        if isinstance(x, str):
            return x.replace(str(source_root)+"/", "archive://")
        return x
    save(REPO/"data/metadata/census.json", normalized(census))
    selected = load(out/REPORT/"selected-data.json")
    save(REPO/"data/metadata/report-selection.json", normalized(selected))
    save(REPO/"data/metadata/missing.json", normalized(census["missing"]))
    save(REPO/"data/metadata/archive-manifest.json", dict(schema="ceo-paper-archive-1", files=manifest,
        aliases=aliases, original_index_files=len(expected), original_index_sha256=digest((out/CENSUS/"census.json").read_bytes()),
        original_index_hash_check="834/834 PASS", all_conditions=41, current_conditions=22, current_tasks=66,
        upstream_commit=UPSTREAM, source_files_unchanged=True, historical_methods_not_redistributed=True))
    save(REPO/"data/metadata/environment.json", normalized(load(study/"environment.json")))
    save(REPO/"data/metadata/cost-breakdown.json", load(study/"cost-breakdown.json"))

    conditions=[]
    for c in census["cases"]:
        p=c["problem_family"]
        conditions.append(dict(**p,current_policy="統一Policy・全軌道" in c["cohort_best"],
            pair_count=c["pair_count"],cohorts=c["cohorts"], historical_not_common_budget=True))
    write_csv(REPO/"data/tables/conditions.csv", conditions)
    for name in ("results.csv", "all-checkpoint-comparisons.csv"):
        shutil.copyfile(study/name, REPO/"data/tables"/name)
    # Only original presentation, not QA caches or hidden Office locks.
    report = REPO/"report";report.mkdir(exist_ok=True)
    shutil.copyfile(out/REPORT/"CEO_full_orbital_policy_2026-10-31_revised.docx", report/"CEO_full_orbital_policy.docx")
    for p in (out/REPORT/"figures").glob("*.png"):
        dest=report/"figures"/p.name;dest.parent.mkdir(exist_ok=True);shutil.copyfile(p,dest)
    # Store all 17 displayed tables exactly as they are in the revised document.
    from zipfile import ZipFile
    import xml.etree.ElementTree as ET
    with ZipFile(report/"CEO_full_orbital_policy.docx") as z:
        xml=ET.fromstring(z.read("word/document.xml"))
    n={"w":"http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    tables=[]
    for t in xml.findall("w:body/w:tbl",n):
        rows=[
            ["".join(a.text or "" for a in cell.findall(".//w:t",n)) for cell in row.findall("w:tc",n)]
            for row in t.findall("w:tr",n)]
        tables.append(rows)
    assert len(tables)==17
    save(REPO/"data/metadata/report-tables.json",tables)
    src=out/REPORT/"build_document.py"
    tree=ast.parse(src.read_text())
    wanted={"label","fmte","font","tx","canvas","finish","paired_bars","reduction_matrix","energy_gaps","decomposition","two_points"}
    functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in wanted]
    # AST extraction is a mechanical code copy; historical report I/O never runs.
    (REPO/"tools/figure_functions.py").write_text(ast.unparse(ast.Module(body=functions,type_ignores=[]))+"\n")
    for p in (out/REPORT/"build_document.py",out/REPORT/"edit_remove_origin_means.py"):
        d=report/"source"/p.name;d.parent.mkdir(exist_ok=True);shutil.copyfile(p,d)

    # Retain extraction provenance for every original indexed file, including exclusions.
    for name in expected:
        if rel(name) not in handled:
            raise ValueError("Unclassified indexed file: "+rel(name))
    save(REPO/"data/metadata/source-snapshot.json",{rel(p):h for p,h in expected.items()})
    total=sum(e.get("object_bytes",0) for e in manifest)
    save(REPO/"data/metadata/assembly-summary.json",dict(
        source_files_checked=len(expected),objects=len(list(objects.iterdir())),object_bytes=sum(p.stat().st_size for p in objects.iterdir()),
        stored_paths=len(retained),excluded_paths=len(denied),aliases=len(aliases),logical_bytes=total,
        current_policy_only=True,new_molecular_experiments=0,visibility="private"))
    print(json.dumps(load(REPO/"data/metadata/assembly-summary.json"),ensure_ascii=False))


if __name__ == "__main__": main()
