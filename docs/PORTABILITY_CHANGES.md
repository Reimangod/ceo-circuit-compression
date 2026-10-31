# Portability changes

## Immutable implementation

The 17 latest-policy Python modules, exact-sector kernel and original bootstrap
are copied unchanged. Every file is bound by `data/metadata/policy-files.json`.
The wrapper verifies those hashes and each task's executor and source digests.
The registered per-task settings and embedded native template registry remain intact.

## New entry points

- `run_policy.py` locates the installed Python/runtime, copies one allowed native
  uncompressed source into a new output directory, rebinds task paths and execution
  identity, then executes the immutable bootstrap under the same qualified macOS
  sandbox baseline. Worker limits and counters are unchanged. The filesystem and
  network denial/import probe runs without an energy call (`check_isolation.py`).
- Archive/reconstruction tools resolve logical historical paths through a manifest.
  They do not require the author's absolute paths. Two symlinked historical result
  names are preserved without duplicating object bytes or claiming independence.
- The latest report's figure functions are AST-extracted without its top-level I/O.
  Their nine PNG outputs were byte-identical to the existing figures using the
  original local font/runtime. Other fonts can change pixels, not numeric data.
- Word authoring uses archived selections and the existing report's layout settings;
  its code-only OMML helper is distributed separately. Original research files
  and the archived revised Word are not rewritten.

## Limits

The currently qualified execution sandbox is macOS. Linux can verify/reconstruct
the archive; compression-worker execution there is not claimed as qualified.
Wall-clock bounded searches are not promised bit-identical across platforms.
The latest policy supports at most 20 physical wires; H8/32-qubit records belong
to the separate historical collection and are not represented as current executions.
