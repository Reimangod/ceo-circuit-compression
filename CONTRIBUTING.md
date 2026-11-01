# Contributing

Start with the [quick start](docs/QUICKSTART.md) and
[CI coverage](docs/CI.md). Keep changes small enough to review against their
stated purpose.

## Development checks

```bash
uv sync --frozen --extra policy --extra report --extra test
uv run --frozen python tools/check_repository.py
uv run --frozen python tools/build_readme_assets.py --check
uv run --frozen python -m pytest -q
```

The raw-data tests need the fixed release asset. A checkout without it skips
three data-dependent tests; state that explicitly in a pull request. Full archive
verification is a separate CI job on trusted branches.

## Preserve the research record

- Treat `policy/frozen/`, `third_party/`, `data/`, the original `report/`, and
  existing release assets as recorded evidence. Documentation changes should not
  modify them.
- Propose algorithm, budget, acceptance-rule, or data-schema changes separately.
  Describe their scientific implications before any new experiment is launched.
- Preserve exact IDs, coefficients, missingness, and historical outcome labels.
  Never substitute a new optimization result for an old record.
- Keep verification, saved-result reconstruction, and explicit molecular execution
  separate. Tests use synthetic fixtures or saved evidence.
- Keep current-policy and historical collections distinct. Report total resource
  reduction separately from additional reduction after common simplification.

## Documentation and figures

Maintained documentation, comments added to new tooling, and new overview graphics
use English. Historical strings and frozen files retain their recorded bytes.

Edit the generated results table and example SVG through
`tools/build_readme_assets.py`, then run it and commit its outputs. The workflow
diagram is directly editable SVG in `docs/assets/`. Keep labels short, provide
descriptive image alt text, and verify the diagram against the frozen code.

## Pull requests and reports

Use the pull-request checklist to describe the change, commands tested, skipped
checks, and any evidence that remains unavailable. A passing documentation check
does not establish a scientific performance claim.

Do not commit virtual environments, raw object packages, caches, authentication
material, proprietary fonts, or private correspondence. Do not change repository
visibility, branch protection, tags, or published release assets as part of an
unrelated fix. See [security guidance](SECURITY.md) for sensitive reports.
