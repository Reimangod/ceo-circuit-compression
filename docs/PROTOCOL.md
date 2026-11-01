# Compression policy specification

This is the English description of the full-orbital application registered on
2026-10-31. The frozen implementation and task settings, not a translated field
name, define the executable experiment. The original protocol remains in the
immutable `artifact-v1.0.0` Git history and the original research record.

## Inputs and registered starts

The current application covers 22 full-orbital conditions. Each trajectory supplies
three starts at `ceil(R/3)`, `ceil(2R/3)`, and the final step `R`. The resulting
66 inputs were fixed before execution. Existing frozen-core records, earlier
full-orbital trajectories, and source-generation results remain unchanged.

Only uncompressed CEO records enter candidate construction. Previously compressed
circuits, deletion positions, successful fitted coefficients, and learned models
are excluded from the worker's inputs.

## Candidate construction and allocation

The application preserves the registered candidate generator, common circuit
simplifier, resource-aware initial order, and single candidate queue.

- Ordered block subsequences are constructed from the starting circuit. Up to
  4,095 proper subsets are considered for small circuits; larger circuits use the
  bounded construction implemented in the frozen generator.
- One- and two-block deletions are also constructed from earlier checkpoints.
- Registered MVP-to-OVP coordinate constraints provide additional candidates.
- A nested, diversified list permits at most 256 initial energy screens.
- Short BFGS allocations use at most eight new joint energy/gradient evaluations
  before a candidate returns to the queue. Line-search evaluations count toward
  that limit. Each topology has a cap of 100 joint evaluations.
- Recycled inverse-Hessian information is bound to the accepted point of the same
  topology. It is reset when its coefficient-point correspondence is lost.
- Initial-energy-qualified candidates can be certified without BFGS refinement.

The common maximum circuit size is 96 blocks. The preceding implementation used
64; this application extends that size bound without using historical solutions
to choose deletion positions.

## Common budget rule

```text
W = N_energy + 2 * N_scalar_gradient_components
B = 2*F + 128 + 20*(1 + 2*P)
```

`F` is the number of source checkpoints including Hartree–Fock. `P` is the number
of independent coefficients in the starting circuit. The constant 128 is a base
allocation, distinct from the maximum of 256 initial screens. Compression does
not remeasure the full operator-pool gradient. Original CEO generation cost is
recorded separately, with unknown historical values left unknown.

The same formula applies to all molecules; its numerical limit scales with the
input. W is an evaluation model, not physical shots or the original paper's
grouped Measurement Cost.

## Acceptance and resource conventions

Both comparator and candidate use the same reference-input circuit simplification.
A saved eligible compression pair satisfies:

```text
E_child <= E_raw_CEO + 1e-9 Ha
CNOT_child < CNOT_common_CEO
CNOT_depth_child <= CNOT_depth_common_CEO
```

Eligible outputs are ordered by CNOT count, total depth, independent coefficient
count, and energy. The original comparator remains a fallback when no eligible
improvement is found. Tiny positive energy differences within tolerance retain
their original signs.

Report total reductions from the raw decomposition separately from additional
reductions after common simplification. Keep starting-point comparisons separate
from comparisons against earlier checkpoints. Four resource metrics must be
taken from one actual pair, not assembled from different best candidates.

## Numerical implementation and verification

The numerical representation retains every configuration in the specified
particle-number and spin-resolved-number sector. It applies no amplitude or
configuration truncation. Hamiltonian terms with the same bit-flip pattern are
combined before the sector sparse matrix is built, without coefficient-threshold
truncation. This avoids materializing redundant sparse triplets for N₂.

Gradient propagation uses the original number-conserving CEO blocks.
Reference-state-only circuit identities are used for state preparation and
resource accounting, not substituted as arbitrary-input unitaries in the adjoint
gradient calculation.

Independent checks reconstruct states from Qiskit local gate matrices, compute
energy through a separate Pauli-term expectation path, and recount logical
resources. Qualification checks compare states, energies, and gradients on small
fixtures. Additional final source-point statevector checks are distinguished from
the compression search and its classical runtime.

Changing the numerical backend and supported size does not promise bit-identical
search trajectories relative to the preceding version. Numerical ties in gradients
or rankings and wall-time termination can change the executed path.

## Execution limits and preserved outcomes

The recorded execution uses one numerical worker and one BLAS thread, a
600-second worker limit, a 780-second outer deadline, an approximate 1.5 GiB RSS
limit, a 1 GiB output bound, and a 512 MiB free-space floor. Time and memory checks
also run during candidate construction.

The qualified sandbox excludes historical research files and network access.
There are no automatic extensions, retries, deletions, GPU jobs, FCI calculations,
training jobs, or external submissions. Interrupted work remains interrupted;
it is not recoded as completion or no improvement.

The archived completion records cover all 66 terminal tasks, ledger reconciliation,
source identities, circuit coefficients, comparison tables, and missingness.
Compression success means that an output passed the registered checks; the
protocol does not guarantee a nonzero reduction for every possible input.
