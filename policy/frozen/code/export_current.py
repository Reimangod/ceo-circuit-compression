"""Adapter for LIVE, uncompressed official DVG_CEO growth objects only.

No artifact readers, dataset loaders, old-result migration or recipe interfaces.
Caller must supply frames directly from its newly executed upstream run.
Export is not by itself evidence that the caller really obeyed this restriction.
"""
import hashlib
import numpy as np
from core import VERSION, UPSTREAM, digest, validate_source, to_qiskit


def affine_template(render, theta, occurrence_id, family, generator_identity):
    """Extract affine native angles; independently check two nonzero probes.

    Nonzero probe origin avoids upstream MVP's zero-term QubitOperator issue.
    Parameter coordinates are registered independent generator coefficients.
    """
    from qiskit.quantum_info import Operator
    p = len(theta)
    origin = np.array([.317 + .113 * i for i in range(p)])

    def read(qc):
        out = []
        for inst in qc.data:
            name = inst.operation.name
            params = [complex(x) for x in inst.operation.params]
            if any(abs(x.imag) > 1e-12 for x in params) or len(params) > 1:
                raise ValueError("Non-real/non-affine native gate")
            out.append((name, [qc.find_bit(q).index for q in inst.qubits], params[0].real if params else 0.))
        return out

    base_circuit = render(origin)
    base = read(base_circuit)
    shifted = [read(render(origin + np.eye(p)[j])) for j in range(p)]
    for rows in shifted:
        if [(a,b) for a,b,_ in rows] != [(a,b) for a,b,_ in base]:
            raise ValueError("Coefficient-dependent native topology is unsupported")
    gates = []
    for k, (name, wires, angle) in enumerate(base):
        weights = [shifted[j][k][2] - angle for j in range(p)]
        weights = [0. if abs(x) < 1e-13 else x for x in weights]
        offset = float(angle - np.dot(weights, origin))
        offset = 0. if abs(offset) < 1e-13 else offset
        gates.append({"name": name, "wires": wires, "offset": offset, "weights": weights})
    block = {"occurrence_id": occurrence_id, "family": family,
             "generator_digest": digest(generator_identity), "theta": list(map(float, theta)), "gates": gates}
    # Local-unitary tests, never global-Hamiltonian energy / historical coefficients.
    active = sorted({q for g in gates if g["name"] != "barrier" for q in g["wires"]})

    def compact(qc):
        from qiskit import QuantumCircuit
        small = QuantumCircuit(len(active))
        for inst in qc.data:
            if inst.operation.name != "barrier":
                small.append(inst.operation, [active.index(qc.find_bit(q).index) for q in inst.qubits])
        return small

    for probe in (origin * 1.713 + .031, np.asarray(theta)):
        predicted = to_qiskit([{**block, "theta": probe.tolist()}], base_circuit.num_qubits)
        actual = render(probe)
        if np.linalg.norm(Operator(compact(predicted)).data - Operator(compact(actual)).data) > 1e-9:
            raise ValueError("Affine export/native unitary mismatch")
    return block


def native_groups(pool, indices):
    """Exactly mirrors the pinned native _get_mvp_ceo_circuit grouping rule."""
    group = []
    for i, index in enumerate(indices):
        group.append(int(index))
        continues = (index in pool.parent_range and i+1 < len(indices)
                     and indices[i+1] in pool.parent_range
                     and pool.get_qubits(indices[i+1]) == pool.get_qubits(index))
        if not continues:
            yield group
            group = []


def export_live_dvg_run(pool, qubit_hamiltonian, reference_occupied_physical,
                        growth_frames, source_run_id, problem, sector, code_manifest=None):
    """growth_frames: LIVE [(indices, coefficients), ...], including empty HF.

    OpenFermion logical orbital q maps to physical Qiskit wire n-1-q,
    as in the official native CEO circuits' big_endian=True convention.
    pool must be the pristine pinned DVG_CEO class, never a derived compression pool.
    """
    import inspect
    import subprocess
    from pathlib import Path
    cls = type(pool)
    if cls.__name__ != "DVG_CEO" or cls.__module__ != "adaptvqe.pools":
        raise ValueError("Only official DVG_CEO supported")
    source_file = Path(inspect.getfile(cls)).resolve()
    root = source_file.parent.parent
    if code_manifest is not None:
        # Worktree Git admin files may live alongside forbidden historical projects.
        # Host preflight freezes ONLY official tracked code hashes; worker never reads
        # shared Git storage or any historical compression object.
        if code_manifest["upstream_commit"] != UPSTREAM or not code_manifest["files"]:
            raise ValueError("Wrong/empty upstream code manifest")
        for name, sha in code_manifest["files"].items():
            path = Path(name)
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "adaptvqe" or path.suffix != ".py":
                raise ValueError("Unsupported code manifest path")
            if hashlib.sha256((root/path).read_bytes()).hexdigest() != sha:
                raise ValueError("Modified upstream scientific source")
    else:
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        if head != UPSTREAM:
            raise ValueError("Wrong upstream commit")
        # Compare tracked official Python only, never untracked reproduction results.
        names = subprocess.check_output(["git", "-C", str(root), "ls-tree", "-r", "--name-only", UPSTREAM, "adaptvqe"], text=True).splitlines()
        for name in names:
            if name.endswith(".py"):
                expected = subprocess.check_output(["git", "-C", str(root), "show", f"{UPSTREAM}:{name}"])
                if (root/name).read_bytes() != expected:
                    raise ValueError("Modified upstream scientific source")
    terms = []
    for term, coefficient in sorted(qubit_hamiltonian.terms.items()):
        if abs(complex(coefficient).imag) > 1e-12:
            raise ValueError("Non-real Pauli coefficient")
        pauli = ["I"] * pool.n
        for q, axis in term:
            pauli[pool.n-1-q] = axis
        terms.append({"pauli": "".join(pauli), "coefficient": float(complex(coefficient).real)})
    frames, previous = [], []
    for step, (indices, coefficients) in enumerate(growth_frames):
        indices = list(map(int, indices))
        if len(indices) != len(coefficients) or indices[:len(previous)] != previous:
            raise ValueError("Source must be append-only original growth, never pruning")
        if step == 0 and indices:
            raise ValueError("First frame must be HF")
        blocks, offset = [], 0
        for j, group in enumerate(native_groups(pool, indices)):
            p = len(group)
            family = "MVP" if p > 1 else ("QE" if group[0] in pool.parent_range else "OVP")
            identity = [{"index": i, "generator": str(pool.operators[i].q_operator)} for i in group]
            block = affine_template(lambda theta, ix=group: pool.get_circuit(ix, theta),
                                    coefficients[offset:offset+p], f"occurrence-{offset}-{offset+p}", family, identity)
            blocks.append(block)
            offset += p
        frames.append({"growth_step": step, "blocks": blocks})
        previous = indices
    source = {"schema": VERSION, "origin": "fresh_uncompressed_ceo_growth", "source_run_id": source_run_id,
              "upstream_commit": UPSTREAM, "problem": {**problem, "hamiltonian_digest": digest(terms)},
              "n": pool.n, "reference_occupied": list(reference_occupied_physical), "hamiltonian": terms,
              "sector": sector, "frames": frames}
    return validate_source(source)
