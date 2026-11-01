# Continuous integration

CI checks the repository and its recorded evidence. It does not run new molecular
searches, generate FCI references, train models, or establish a new performance
claim.

## Coverage

| Job | What it checks | Release data | Molecular calculations |
| --- | --- | --- | --- |
| Documentation and workflow checks | English guides, local links and anchors, SVGs, generated views, scope metadata, frozen hashes, Actions syntax | No | None |
| Synthetic and unit tests | Python 3.11 and 3.12; candidate construction, resource counts, energy/gradient parity, budget charging, and guard behavior on small fixtures | No | None; synthetic fixtures only |
| macOS worker isolation | Worker import plus denial of historical-file and network access | No | None; zero energy calls |
| Fixed-release data and accounting audit | Release checksum, every object, all 66 current ledgers, saved-pair bindings, 41-condition reconstruction, and table export | Yes | None; saved-record arithmetic only |

The unit-test jobs intentionally skip three checks that need raw data. The
fixed-release job downloads those data and runs the archive tests with them
present. A green unit-test job alone is not a full evidence audit.

## Triggers and access

The workflow runs on pushes to `main`, pull requests, and manual dispatch.
Superseded runs on the same ref are cancelled. All jobs have timeouts and
read-only repository permissions. Checkout does not retain Git credentials.

The fixed-release job runs on main pushes, manual dispatch, and pull requests
whose source branch belongs to this repository. It is skipped for fork pull
requests, where private-release credentials are unavailable. CI never uses the
privileged `pull_request_target` event.

The download token is scoped to its single download step. Only test reports and
reconstructed tables are retained as short-lived CI artifacts; the raw data
package is not reuploaded. Private visibility, releases, and branch protections
are not changed by the workflow.

## Reproducible tools

- Every `uses:` reference is pinned to a full commit SHA.
- uv is pinned to 0.9.8 and installs from `uv.lock` with `--frozen`.
- Numerical tests cover both Python versions supported by `pyproject.toml`.
- actionlint 1.7.12 is downloaded from its official GitHub release and verified
  against a fixed SHA-256 before execution.
- One numerical thread is configured to avoid accidental thread oversubscription.

The lockfile and pinned Actions reduce environment drift. They do not promise
bit-identical wall-time-bounded molecular searches across machines.

## Reading a failure

| Failing check | What to inspect first |
| --- | --- |
| Local link or anchor | The changed Markdown path or heading |
| Generated view | Run `python3 tools/build_readme_assets.py` and review its diff |
| Frozen hash | Stop and inspect whether recorded implementation bytes changed |
| Numerical fixture | The specific state, gradient, resource, or accounting assertion |
| Isolation probe | macOS sandbox availability, runtime paths, and denied-access result |
| Release retrieval | Private repository access, asset availability, and checksum |
| Ledger or comparison | Source identity, event sequence, cost deltas, and actual pair binding |

The saved-data verification step must pass before its evidence summary is treated
as complete. Infrastructure outages and failed numerical assertions remain
distinct failure causes. Neither is silently converted into a successful research
result.

## Local equivalents

```bash
python3 tools/check_repository.py
python3 tools/build_readme_assets.py --check
uv sync --frozen --extra policy --extra report --extra test
uv run --frozen python -m pytest -q
```

For the evidence audit, retrieve the fixed release and run the three saved-data
commands in the [quick start](QUICKSTART.md). The macOS isolation probe is
`uv run --frozen python tools/check_isolation.py`.

Inspect the [workflow definition](../.github/workflows/verify.yml) for the exact
commands. Workflow checks are not a substitute for a separately configured branch
protection policy; this change does not enable or weaken such a policy.
