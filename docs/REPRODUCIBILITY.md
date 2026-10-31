# Reproducibility and execution

## Levels

1. **Archive integrity:** download the private data asset, verify its SHA-256 and
   each object, inspect scope and immutable code hashes. Python standard library only.
2. **Saved-result reconstruction:** re-run historical joins and current candidate /
   comparator bindings. Recompute reductions and event costs, export tables and
   nine figures. No SCF, FCI, optimization, GPU or new molecular search.
3. **Explicit policy execution:** re-run one archived uncompressed source with its
   registered settings in a new output directory. Requires numerical dependencies
   and qualified macOS sandbox isolation. This is never run by levels 1 or 2.

Original runtime: Python 3.11.14, macOS arm64, NumPy 2.4.6, SciPy 1.17.1,
SymPy 1.14.0, Qiskit 2.6.0. The saved environment also records PySCF and Numba;
compression from an exported Pauli Hamiltonian does not require new chemistry
calculations. The original complete environment is in `data/metadata/environment.json`.

Frozen policy files are copied unchanged; hashes are in `policy-files.json`.
The portable launcher changes only task/source/output paths, execution identity
and environment setup. It preserves candidate generation, ranking, W budget,
initial coefficients, optimizer settings, 600-second worker limit, 780-second outer
deadline and energy/depth guards. It does not claim bit-identical wall-time-limited
search results on another machine. macOS memory-accounting units remain those of
the recorded worker; Linux execution has not been certified.

Historical data are accessible to analysis processes but excluded from the
compression worker's filesystem permissions. The worker actively tests denial of
a historical-data canary and network access. A failed isolation check terminates
before molecular evaluation. The wrapper never retries or overwrites an attempt.

The original template registry is embedded in each frozen task, including exact
data digest. Reconstructing it is not required to run the recorded tasks. The
registry construction source and pinned upstream source are retained for inspection;
its legacy helper path is an original provenance detail, not an active worker dependency.

## Figures and Word

`tools/reproduce.py` reuses the latest report's drawing functions, extracted as
code only. Numeric inputs are selected from saved full-orbital comparisons.
The 17 displayed tables retain the revised Word's exact text and rounding; the
unrounded underlying pair values and current result bindings are independently
checked. `tools/reconstruct_census.py` recomputes all 41 case selections from raw
archived records. These are descriptive historical maxima, not pooled method performance.

The existing Word file is preserved byte-identically. Its authoring source is
provided under `report/source`. Fonts are local requirements and are not copied.
For optional reconstruction, install the `report` extra and run
`python tools/rebuild_word.py`. Output goes to `reproduced/report`; the archived
Word stays unchanged. The formula helper is a code-only extraction and the
existing report supplies layout/style measurements only.
Generated figure pixels depend on font and Pillow version. Numeric results are
the cross-platform reproduction target; the recorded original figures remain available.

## Archive version and future DOI

The fixed release is `artifact-v1.0.0`. The large data package and code-and-data
bundle are explicit assets, not assumed to be inside GitHub's automatic source ZIP.
No Zenodo integration/publication is enabled for this private repository. A future
public deposit must include all asset files, versions, licenses and checksums;
cite the version-specific DOI once it actually exists.
