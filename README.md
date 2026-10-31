# CEO circuit compression

Code, circuits, and full-orbital research data for a bounded post-growth CEO circuit
compression study. This is a **private research repository**. There is no DOI or
public archival deposit yet.

The latest policy was applied to **22 conditions / 66 starting circuits** of LiH,
HF, BeH2 and N2. The historical collection contains **41 conditions / 7 molecules**,
including those 22 conditions. Historical records use different methods and budgets;
they are not additional executions of the latest policy.

See [日本語の説明](docs/README_JA.md), [policy specification](docs/PROTOCOL_JA.md),
[data dictionary](docs/DATA_DICTIONARY.md), and [reproducibility guide](docs/REPRODUCIBILITY.md).

## Retrieve and inspect the fixed data

Python 3.11 and the GitHub CLI are sufficient for the offline numeric checks.
Access to this private repository/release is required. Never put authentication
tokens in scripts, URLs, notebooks or commits.

```bash
gh repo clone Reimangod/ceo-circuit-compression
cd ceo-circuit-compression
python3 tools/fetch_data.py
python3 tools/verify.py
python3 tools/reconstruct_census.py
python3 tools/reproduce.py --tables-only
```

These commands **do not execute a molecular search, optimization or FCI**.
The data asset is checksum-verified before extraction. The historical joins are
reconstructed directly from the full-orbital subset of saved records.

## Reproduce the report figures

```bash
python3 -m pip install -e '.[report,test]'
python3 tools/reproduce.py --font /path/to/Japanese-font.ttc
python3 -m pytest -q
```

A Japanese font must be installed locally. MS Mincho and Noto Serif CJK are supported;
no font is distributed. Tables use the revised Word's displayed cells, while pair
arithmetic and current candidate/comparator bindings are checked from original
result records. Figure data and drawing functions reproduce all nine report figures.
Font differences can change pixels without changing data.

The existing, unchanged Word report is in `report/CEO_full_orbital_policy.docx`.
Its presentation omits the origin column and mean-reduction discussion. Provenance
remains in the machine-readable archive.

## Explicit compression execution

Install `.[policy]` in a separate environment. Read the execution documentation
first. The worker is qualified for macOS `sandbox-exec`; data verification and
reconstruction are platform-independent.

```bash
python3 tools/run_policy.py --task-id lih-1.20A-all-orbitals-root006 --output execution/new-attempt
```

This is an **explicit new execution**, not part of data retrieval or verification.
It retains the registered task budget/settings and does not overwrite or retry an
existing attempt. The worker can read only its uncompressed source, frozen policy,
numerical runtime and new output directory. Historical compression results are
excluded from its read permissions. Wall-clock termination can vary by machine.

## Contents

- `policy/frozen`: immutable latest implementation, verified against original hashes.
- `third_party`: pinned CEO source and its original Apache-2.0 license.
- `data/metadata`, `data/tables`: identities, full-precision data, provenance and conditions.
- `data/raw`: retrieved content-addressed objects; distributed as a private release asset.
- `tools`: archive readers, saved-data joins, table/figure reconstruction and explicit execution.
- `report`: revised Word, figures and their authoring sources.

## Interpretation and limitations

The comparison is to an actual saved CEO checkpoint whose energy is equal to or
higher than the compressed circuit's energy, within the registered 1e-9 Ha tolerance.
Some source trajectories did not meet growth convergence criteria. Relative energy
non-worsening is distinct from absolute ground-state accuracy.

Logical resource counts separate raw native decomposition, common reference-input
simplification, and further pruning. The W model is `N_energy + 2*N_scalar_gradient_components`;
it is neither actual shots nor the grouped Measurement Cost of the CEO paper.
Source-generation costs are separate and not known for every source. No matched-work
growth superiority, hardware advantage or unknown-molecule generalization is inferred
from this archive. Historical missing records and limited certification remain labeled.

## Citation and licenses

See `CITATION.cff`. Code is Apache-2.0; original study data and documentation are
CC BY 4.0 (`LICENSE-DATA`). Third-party materials keep their own notices and terms.
The CEO paper and pinned implementation must also be credited:

Ramôa et al., *Reducing the resources required by ADAPT-VQE using coupled exchange
operators and improved subroutines*, npj Quantum Information (2025),
[doi:10.1038/s41534-025-01039-4](https://doi.org/10.1038/s41534-025-01039-4).
[Official source](https://github.com/mafaldaramoa/ceo-adapt-vqe), commit
`a3f89d03e6a03c89767d3cf8ee7657a57653dda0`.
