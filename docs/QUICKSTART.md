# Quick start

Choose between inspecting saved results and running a new compression task.
Verification and reconstruction use saved records; molecular execution is a
separate, explicit command.

## 1. Check the checkout

Requirements: Python 3.11 or 3.12. These checks need no release data or numerical
packages.

```bash
python3 tools/check_repository.py
python3 tools/build_readme_assets.py --check
```

They check local documentation links, generated result views, scope metadata,
and the hashes of the recorded implementation.

## 2. Download and verify the data

Use an authenticated [GitHub CLI](https://cli.github.com/) while the repository
is private. Allow about 174 MiB for the compressed data and 1.8 GiB for expanded
objects, with additional temporary download space.

```bash
python3 tools/fetch_data.py
python3 tools/verify.py
python3 tools/reconstruct_census.py
python3 tools/reproduce.py --tables-only
```

The fixed asset's SHA-256 is in
[release-asset.json](../data/metadata/release-asset.json). Verification checks
every object, the 66 current work ledgers, and the actual circuit/comparator
bindings. Reconstruction recomputes the 41-condition historical selection.
CSV outputs are written to `reproduced/`.

For an offline copy, use:

```bash
python3 tools/fetch_data.py --asset /path/to/ceo-full-orbital-data-v1.0.0.tar.gz
```

The same checksum and extraction checks apply. No new energies are evaluated.
Missing records retain the limitations described in the
[data dictionary](DATA_DICTIONARY.md).

## 3. Reproduce figures

The English [results page](RESULTS.md) and example SVG use only saved metadata:

```bash
python3 tools/build_readme_assets.py
```

The [original research report](../report/CEO_full_orbital_policy.docx) and its
[nine figures](../report/figures) retain their original Japanese presentation.
To regenerate those figures, install the report dependencies and provide a
locally installed Japanese font:

```bash
uv sync --frozen --extra report
uv run --frozen python tools/reproduce.py --font /path/to/Japanese-font.ttc
```

MS Mincho and Noto Serif CJK are supported. Fonts are not distributed. Font and
Pillow versions can change pixels; the selected numerical data and circuit-pair
identities are the cross-platform reproduction target. The 17 extracted report
tables retain their original wording and rounding; underlying pair arithmetic
is checked separately.

## 4. Run the tests

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use the
committed lockfile:

```bash
uv sync --frozen --extra policy --extra report --extra test
uv run --frozen python -m pytest -q
```

Without the release data, three archive-dependent tests are skipped. After step 2,
they also run. Numerical tests use small synthetic fixtures, not new molecular
benchmark experiments. A lighter archive-only environment is:

```bash
uv sync --frozen --extra test
uv run --frozen python -m pytest -q \
  tests/test_archive_tools.py tests/test_repository_quality.py
```

CI uses pinned Actions, uv 0.9.8, and frozen dependencies. It checks Python 3.11
and 3.12, documentation and workflow syntax, macOS isolation, and the fixed data
release. The data job runs on main, manual dispatch, and same-repository pull
requests; it is skipped for forks. CI has read-only permissions and retains only
short-lived test reports and reconstructed tables, not raw data packages.

## 5. Run a compression task

New execution is qualified for **macOS with `sandbox-exec`**. Linux supports
saved-data verification and reconstruction; its molecular execution layer is
not qualified. Retrieve the release data first, then run:

```bash
uv sync --frozen --extra policy
uv run --frozen python tools/check_isolation.py
uv run --frozen python tools/run_policy.py \
  --task-id lih-1.20A-all-orbitals-root006 \
  --output execution/new-attempt
```

The isolation probe imports the worker and checks access denial without evaluating
an energy. The task command is the operation that consumes a molecular budget.
Task IDs are in `inventory-v2.json` within the fixed release, resolved through
the [data manifest](../data/metadata/archive-manifest.json).

The launcher copies one uncompressed source, verifies implementation and input
hashes, and preserves the registered coefficients, candidate order, budget,
optimizer settings, and acceptance rules. Its worker cannot read historical
compression results or access the network. An existing output directory is
rejected; failed or interrupted attempts are preserved without automatic retries.

The implementation uses at most 20 physical wires. Historical H₈/32-qubit records
belong to a different experiment. Wall-time-bounded searches are not guaranteed
to follow bit-identical trajectories on other machines. See the
[method](PROTOCOL.md) for the numerical representation and execution limits.

## Environment and troubleshooting

The original numerical environment used Python 3.11.14 on macOS arm64, NumPy
2.4.6, SciPy 1.17.1, SymPy 1.14.0, and Qiskit 2.6.0. The complete saved environment
is in [environment.json](../data/metadata/environment.json). Compression uses an
exported Pauli Hamiltonian and does not require new chemistry calculations.

| Issue | Check |
| --- | --- |
| Missing data or download failure | Repository access and fixed release asset |
| Hash or ledger mismatch | Preserve the error; check source identity and event records |
| Stale result page | Regenerate with `tools/build_readme_assets.py` and review the diff |
| Missing figure font | Supply a Japanese font with `--font` |
| Isolation failure | macOS sandbox availability and runtime paths; do not bypass the probe |

Report the commit, operating system, Python version, command, and sanitized error.
Archive integrity, numerical checks, and performance evidence are distinct: a
passing test suite does not by itself establish a new scientific result.
