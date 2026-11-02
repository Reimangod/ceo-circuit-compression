# Data dictionary

## Collections

| Molecule | Current-policy conditions | Historical conditions | Historical basis |
| --- | ---: | ---: | --- |
| LiH | 8 | 12 | STO-3G |
| HF | 2 | 2 | STO-3G |
| BeH₂ | 8 | 12 | STO-3G |
| N₂ | 4 | 4 | STO-3G |
| H₄ | — | 2 | STO-3G |
| H₆ | — | 7 | STO-3G |
| H₈ | — | 2 | 6-31G |

The 41 historical conditions include the 22 current conditions. Each current
condition has three registered starting circuits, giving 66 tasks. Historical
methods, budgets, starts, and verification coverage differ; the collections are
not pooled as a single benchmark. All current conditions use full-orbital STO-3G.

## Storage and identities

`data/metadata/archive-manifest.json` maps the original workspace-relative
`source_path` to a SHA-256-addressed object. `archive://outputs/...` is a logical
identifier, resolved by `tools/archive.py`, not a URL or an absolute author path.
Objects are distributed in the release asset. They retain the original format.

Each entry records original bytes/hash, published object bytes/hash, extraction
status and available record locators. An extracted object is a derived subset,
not falsely labeled as the original whole file. `EXCLUDED` entries document material
outside the full-orbital scope. Byte-identical final progress/result pairs use aliases.
Alias paths identify files; they do not merge separate physical evaluation events.
Two historical completion paths refer to existing saved result files. These logical
paths are retained (`historical-path-aliases.json`) for exact reconstruction, while
their bytes are stored once. They are not independent experiments. Historical
`pair_count` counts eligible saved comparison records, not independent samples.

## Conditions, circuits, comparisons

- A condition includes molecule, full coordinates (angstrom), basis, electron and
  qubit counts. Physical matching also requires the original Hamiltonian/problem
  binding; a geometry-only family is not permission to reuse an energy.
- Native source JSON includes `hamiltonian`, `reference_occupied`, `sector`,
  `upstream_commit` and ordered `frames`. Each frame has `growth_step` and `blocks`.
- Blocks retain their family, ordered gates, coefficient vector, occurrence and
  generator identity. Affine gate `offset` and `weights` specify how independent
  coordinates enter rotations. Parameter counts follow registered bindings, not
  accidental equality of floating-point coefficients.
- Current result `archive` entries retain accepted circuit coefficients,
  kept/removed positions, registered replacements and certification. `trials`
  include initial screens and optimization states; those are not all certified endpoints.
- `originals` contains actual comparator checkpoints, raw native resources,
  common-simplified resources and energy. `candidate_id` plus `comparator_step`
  identifies a pair inside one source run.
- Historical canonical records preserve ProblemID, StatePreparationID,
  MeasurementContextID and EvaluationID. Different Hamiltonians/observables or
  incompatible evaluation settings do not authorize cache reuse.

## Units and resources

Energies are total molecular energies in Hartree under the recorded Hamiltonian
convention. `delta_energy_Ha = E_child - E_CEO` retains its sign, including tiny
positive differences allowed by the 1e-9 Ha comparison tolerance. References are
not reconstructed from a molecule name. Unknown reference errors remain unknown.

`cnot`, `cnot_depth`, `parameters`, `total_depth` are logical integer resources
under the recorded decomposition/simplification convention. Reduction percent is
`100*(CEO-child)/CEO`, undefined if the baseline is zero. Raw, common-simplified,
and child resources are distinct. These are not hardware-routed resource counts.

## Costs, outcomes and missingness

Recorded current search cost is 117,745 W. Qualification (77 W) and post-search
validation (24 W) are separate entries in
[cost-breakdown.json](../data/metadata/cost-breakdown.json). Original CEO generation
cost is separate and is not fully known for every source. W measures modeled
evaluation effort, not shots or the CEO paper's grouped Measurement Cost.

The current event ledger charges at STARTED: `delta_W = 1 + 2*p` for an energy
evaluation with `p` requested scalar gradient components. A terminal record and
exact compatible reuse have zero delta. Sum the deltas once; do not sum STARTED
and terminal copies of cumulative totals. Counters include started failed work.

`MODEL_CAP_TERMINAL`, time censoring, engineering failure, algorithmic rejection,
no improvement and missing output are different outcomes. The missing list describes
unavailable records; it is not a list of independent failed molecular experiments.
Null/UNKNOWN/not-checked carry their recorded meaning. Unavailable old counters
are not replaced with zero and old costs are not pooled as a matched-work experiment.

Verification evidence records method, code identity, tolerance and scope. A selected
endpoint's full-state Qiskit check does not certify every candidate. Historical
`STORED_HISTORY_ONLY_INDIVIDUAL_BASELINE_CERTIFICATE_NOT_JOINED` remains a limited
reference comparison. H8 sector certification is not relabeled as global Qiskit validation.
