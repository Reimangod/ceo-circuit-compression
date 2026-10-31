# Repository instructions

Every shell command starts with `rtk` (use `rtk proxy` for unfiltered commands).
Use apply_patch for source and documentation edits. Do not delegate to agents.
Keep this repository private; publication, DOI registration, and visibility changes
require a separate request. Never modify the original research directories.

Scope: 41 indexed full-orbital conditions, with current-policy evidence explicitly
limited to 22 conditions / 66 tasks. Historical data retain their original method,
budget, acceptance, missingness, and verification scope. Only the latest compressor
and its shared dependencies are distributed as executable policy code. No model
weights or historical compression algorithms belong in the release.

Verification, table/figure reconstruction, and compression execution are separate
commands. Verification/reconstruction never launch molecular searches. Research
execution must be explicit and source-only, with unchanged registered budget,
candidate order, energy/depth guards and accounting. Never use archived compressed
circuits, masks, fitted coefficients, or historical results as search inputs.

Preserve raw numeric precision and original IDs. Missing/unknown/unverified values
are not zero or false. Changes to portability do not retroactively modify recorded
experiments. Report the W model separately from grouped measurement cost and shots.
