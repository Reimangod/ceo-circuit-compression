# Quick start

Choose the level that matches your task. Inspecting a checkout, reconstructing
saved results, and running a new compression search are separate operations.

## 1. Inspect the checkout

Requirements: Python 3.11 or 3.12. No numerical packages or release data are needed.

```bash
python3 tools/check_repository.py
python3 tools/build_readme_assets.py --check
```

These commands check documentation links, frozen file identities, scope metadata,
and the English overview assets. They do not validate the full raw-data package.

## 2. Retrieve and verify the fixed data

Requirements: access to the private repository and release, an authenticated
GitHub CLI, and about 1.8 GiB for expanded objects plus temporary download space.
Do not paste tokens into scripts or command-line URLs.

```bash
python3 tools/fetch_data.py
python3 tools/verify.py
python3 tools/reconstruct_census.py
python3 tools/reproduce.py --tables-only
```

The data asset is about 174 MiB compressed. The expected SHA-256 is stored in
[release-asset.json](../data/metadata/release-asset.json). Verification checks all
objects and reconciles the 66 current work ledgers. Reconstruction redoes the
saved-data joins for the 41-condition census. Tables are written to `reproduced/`.

An offline copy of the fixed release asset can be used instead of a download:

```bash
python3 tools/fetch_data.py --asset /path/to/ceo-full-orbital-data-v1.0.0.tar.gz
```

The same checksum and extraction checks apply. Missing data produce a failure;
they are not replaced with invented values or new calculations.

## 3. Run the tests with locked dependencies

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) and use the
committed lockfile. CI pins uv to 0.9.8.

```bash
uv sync --frozen --extra policy --extra report --extra test
uv run --frozen python -m pytest -q
```

Without the release data, three archive-dependent tests are intentionally skipped.
After step 2, those tests also run. The numerical tests use small synthetic
fixtures, not new molecular benchmark runs.

For a lighter metadata-and-documentation test environment:

```bash
uv sync --frozen --extra test
uv run --frozen python -m pytest -q \
  tests/test_archive_tools.py tests/test_repository_quality.py
```

Use `python3 -m pip install -e '.[policy,report,test]'` only when a locked uv
environment is unavailable. A fresh pip resolution can differ from `uv.lock`;
record that environment when reporting reproducibility.

## 4. Reconstruct the original report figures

The English repository overview and [results table](RESULTS.md) use lightweight
SVG and Markdown assets. Rebuild them without numerical dependencies:

```bash
python3 tools/build_readme_assets.py
```

The preserved report figures reproduce the original Japanese presentation.
They require the report extra and a locally installed Japanese font:

```bash
uv sync --frozen --extra report
uv run --frozen python tools/reproduce.py --font /path/to/Japanese-font.ttc
```

MS Mincho and Noto Serif CJK are supported; fonts are not distributed. Different
fonts can alter pixels while leaving the selected numerical data unchanged.
The nine original figures remain in [report/figures](../report/figures).

## 5. Run an explicitly requested compression task

New execution requires the policy extra and the qualified macOS isolation layer.
It consumes an experimental budget, unlike the preceding inspection commands.

```bash
uv sync --frozen --extra policy
uv run --frozen python tools/check_isolation.py
uv run --frozen python tools/run_policy.py \
  --task-id lih-1.20A-all-orbitals-root006 \
  --output execution/new-attempt
```

The isolation probe checks access and imports without evaluating an energy.
The task runner then executes one recorded uncompressed source with its registered
settings. It rejects existing output directories and preserves failures without
automatic retries. See [reproducibility and execution](REPRODUCIBILITY.md).

## Expected outputs

| Operation | Output | Molecular work |
| --- | --- | --- |
| Repository check | PASS/FAIL report on the checkout | None |
| Fetch fixed data | Verified `data/raw/objects/` files | None |
| Verify and reconstruct | Hash, cost-ledger, and comparison checks | None |
| Reproduce tables and figures | Derived files in `reproduced/` | None |
| Explicit task runner | New circuit, coefficients, events, and terminal status | Yes |

If a command fails, preserve its output and report the command, Python version,
commit, and error through the [contribution process](../CONTRIBUTING.md).
