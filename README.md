# CEO Circuit Compression

[![Research artifact CI](https://github.com/Reimangod/ceo-circuit-compression/actions/workflows/verify.yml/badge.svg?branch=main)](https://github.com/Reimangod/ceo-circuit-compression/actions/workflows/verify.yml)

Code and data for reducing the size of saved **CEO-ADAPT-VQE** circuits.
CEO-ADAPT-VQE builds a quantum state-preparation circuit by adding coupled
exchange operators. This method compresses its saved checkpoints through
block removal and parameter constraints, with optional coefficient reoptimization.
Every reported pair includes its energy, logical resources, and search cost.

**[Results](docs/RESULTS.md)** · **[Quick start](docs/QUICKSTART.md)** ·
**[Method](docs/PROTOCOL.md)** · **[Data format](docs/DATA_DICTIONARY.md)**

## Method

![Saved CEO checkpoints pass through candidate construction, bounded screening and refinement, independent validation, and recorded outputs.](docs/assets/compression-workflow.svg)

The search uses uncompressed CEO checkpoints, without learned models or previous
compression solutions. The same reference-input simplification is applied to
the candidate and its CEO comparator. A verified compression pair satisfies:

```text
E_compressed <= E_CEO + 1e-9 Ha
CNOT_compressed < CNOT_common_simplified_CEO
CNOT_depth_compressed <= CNOT_depth_common_simplified_CEO
```

The comparison checkpoint can be earlier than the search's starting checkpoint.
Both are identified in each result. Total reduction from the raw CEO decomposition
and additional reduction after common simplification have different denominators.

## Results and data

| Collection | Scope | Role |
| --- | --- | --- |
| Current policy | 22 conditions, 66 starting circuits; LiH, HF, BeH₂, N₂ | One policy with a common budget rule |
| Historical archive | 41 full-orbital conditions across seven molecules | Includes the current conditions; methods and budgets differ |

The historical collection also contains H₄, H₆, and H₈. Full-orbital means that
all orbitals in the specified basis are retained, with no frozen-core exclusion.
Exact geometries and basis sets are listed in
[conditions.csv](data/tables/conditions.csv).

![One saved LiH pair: 112 raw CEO CNOTs, 100 after common simplification, and 65 after compression.](docs/assets/lih-example.svg)

For this LiH 1.50 Å pair, the energy change is **−0.07070 mHa**. CNOT reduction
is **42.0%** from the raw comparator and **35.0%** after common simplification;
the common-simplified and compressed CNOT depths are both 31.
[All 22 selected comparisons](docs/RESULTS.md) are descriptive saved results,
not guarantees for every input.

Resources are logical, under the recorded decomposition. The cost model
`W = N_energy + 2 * N_scalar_gradient_components` is separate from physical shots
and the CEO paper's grouped Measurement Cost. These data alone do not establish
matched-work superiority over continued CEO growth, hardware advantage, or
generalization to unseen molecules. Source convergence and comparator energy
non-worsening are separate properties.

## Reproduce the saved results

Use Python 3.11 or 3.12 and the [GitHub CLI](https://cli.github.com/).
Authentication is required while the repository is private.

```bash
gh repo clone Reimangod/ceo-circuit-compression
cd ceo-circuit-compression
python3 tools/check_repository.py
python3 tools/fetch_data.py
python3 tools/verify.py
python3 tools/reconstruct_census.py
python3 tools/reproduce.py --tables-only
```

These commands verify and reconstruct saved records; they launch no molecular
search, optimization, or FCI calculation. The fixed
[data release](https://github.com/Reimangod/ceo-circuit-compression/releases/tag/artifact-v1.0.0)
requires about 1.8 GiB when expanded, plus temporary download space.
The [quick start](docs/QUICKSTART.md) covers locked dependencies, figure
reproduction, tests, and the separate macOS compression command.

## Contents

```text
policy/frozen/    Recorded compressor and exact-sector kernel
third_party/     Pinned upstream CEO implementation and license
data/            Conditions, results, provenance, and release-data manifest
docs/            Usage, method, results, data dictionary, and overview figures
report/          Original research report and figures
tools/           Data retrieval, verification, reconstruction, and execution
tests/           Saved-data checks and synthetic numerical tests
```

The guides and overview figures are in English. Original report artifacts and
historical data retain their source language and recorded values. Research
provenance is preserved separately from the presentation.

## Tests and support

```bash
uv sync --frozen --extra policy --extra report --extra test
uv run --frozen python -m pytest -q
```

CI checks documentation, locked Python 3.11/3.12 numerical tests, macOS worker
isolation, and fixed-release data on trusted branches. Three raw-data tests are
skipped when the release data are absent; the data-audit job runs them after
download. CI never launches molecular experiments.

For an issue, include the commit, operating system, Python version, command,
and sanitized error. Keep credentials and private correspondence out of issues.
Code and data changes should retain original identities, uncertainty, and
comparison definitions.

## Citation and license

Cite the code and data through [CITATION.cff](CITATION.cff), and cite the CEO paper:

Ramôa, M. et al. *Reducing the resources required by ADAPT-VQE using coupled
exchange operators and improved subroutines*. **npj Quantum Information 11**,
86 (2025). [DOI: 10.1038/s41534-025-01039-4](https://doi.org/10.1038/s41534-025-01039-4).

Original code: [Apache-2.0](LICENSE). Original data and documentation:
[CC BY 4.0](LICENSE-DATA). Third-party attribution is retained in [NOTICE](NOTICE).
The upstream implementation is pinned to
`a3f89d03e6a03c89767d3cf8ee7657a57653dda0`.
