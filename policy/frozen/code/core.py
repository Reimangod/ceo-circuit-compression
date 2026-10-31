"""Current-run-only, deterministic, whole-CEO-block compression. No learned model.

The kernel consumes explicit native gates, not pool IDs or historical artifacts.
Little endian physical wire convention, consistent with Qiskit.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import hashlib
import itertools
import json
import math
import numpy as np
from scipy.optimize import minimize

VERSION = "current-rule-ceo-0.1"
UPSTREAM = "a3f89d03e6a03c89767d3cf8ee7657a57653dda0"
METRICS = ("cnot", "cnot_depth", "parameters", "total_depth")
ROTATIONS = {"rx", "ry", "rz"}
I = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], complex)
Y = np.array([[0, -1j], [1j, 0]], complex)
Z = np.diag([1, -1]).astype(complex)
PAULI = {"I": I, "X": X, "Y": Y, "Z": Z}
FIXED = {"x": X, "y": Y, "z": Z, "h": (X + Z) / np.sqrt(2),
         "s": np.diag([1, 1j]), "sdg": np.diag([1, -1j]),
         "t": np.diag([1, np.exp(1j * np.pi / 4)]),
         "tdg": np.diag([1, np.exp(-1j * np.pi / 4)])}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def exact_keys(obj, names):
    if not isinstance(obj, dict) or set(obj) != set(names.split()):
        raise ValueError(f"Unsupported schema keys; expected {names}")


def finite_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def validate_source(s):
    """Closed schema prevents answer fields/path imports, NOT proof of provenance."""
    canonical(s)
    exact_keys(s, "schema origin source_run_id upstream_commit problem n reference_occupied hamiltonian sector frames")
    if s["schema"] != VERSION or s["origin"] != "fresh_uncompressed_ceo_growth":
        raise ValueError("Only fresh uncompressed CEO growth input supported")
    if s["upstream_commit"] != UPSTREAM or not isinstance(s["source_run_id"], str):
        raise ValueError("Unsupported source pin/run")
    exact_keys(s["problem"], "label geometry basis mapping hamiltonian_digest")
    if s["problem"]["hamiltonian_digest"] != digest(s["hamiltonian"]):
        raise ValueError("Hamiltonian digest mismatch")
    n = s["n"]
    if type(n) is not int or not 1 <= n <= 20:
        raise ValueError("This small-statevector implementation supports 1..20 wires")
    occupied = s["reference_occupied"]
    if len(set(occupied)) != len(occupied) or any(type(q) is not int or not 0 <= q < n for q in occupied):
        raise ValueError("Invalid reference occupation")
    if not s["hamiltonian"]:
        raise ValueError("Empty Hamiltonian")
    for term in s["hamiltonian"]:
        exact_keys(term, "pauli coefficient")
        if len(term["pauli"]) != n or set(term["pauli"]) - set(PAULI) or not finite_number(term["coefficient"]):
            raise ValueError("Invalid real Hermitian Pauli term")
    # Pauli string character q acts on physical wire q (NOT printed Qiskit order).
    for constraint in s["sector"]:
        exact_keys(constraint, "wires occupation")
        qs = constraint["wires"]
        if len(set(qs)) != len(qs) or not qs or any(type(q) is not int or not 0 <= q < n for q in qs):
            raise ValueError("Invalid sector wires")
        if type(constraint["occupation"]) is not int or not 0 <= constraint["occupation"] <= len(qs):
            raise ValueError("Invalid sector occupation")
    frames = s["frames"]
    if not frames or len(frames) > 1000 or frames[0]["blocks"]:
        raise ValueError("Include HF and the uncompressed growth trajectory")
    for j, frame in enumerate(frames):
        exact_keys(frame, "growth_step blocks")
        if frame["growth_step"] != j:
            raise ValueError("Non-contiguous growth trace")
        seen = set()
        for block in frame["blocks"]:
            exact_keys(block, "occurrence_id family generator_digest theta gates")
            if block["occurrence_id"] in seen:
                raise ValueError("Duplicate occurrence ID")
            seen.add(block["occurrence_id"])
            if block["family"] not in {"QE", "OVP", "MVP"}:
                raise ValueError("Unsupported CEO block")
            p = len(block["theta"])
            if p == 0 or any(not finite_number(x) for x in block["theta"]):
                raise ValueError("Invalid independent parameter coordinates")
            if not isinstance(block["generator_digest"], str) or len(block["generator_digest"]) != 64:
                raise ValueError("Missing generator identity")
            derivatives = []
            active = set()
            for gate in block["gates"]:
                exact_keys(gate, "name wires offset weights")
                name, qs = gate["name"], gate["wires"]
                if name not in set(FIXED) | ROTATIONS | {"cx", "barrier"}:
                    raise ValueError("Unsupported native gate")
                if not qs or len(set(qs)) != len(qs) or any(type(q) is not int or not 0 <= q < n for q in qs):
                    raise ValueError("Invalid gate wires")
                if name != "barrier" and len(qs) != (2 if name == "cx" else 1):
                    raise ValueError("Gate arity mismatch")
                if len(gate["weights"]) != p or not finite_number(gate["offset"]) or any(not finite_number(x) for x in gate["weights"]):
                    raise ValueError("Invalid affine angle")
                if name not in ROTATIONS and (gate["offset"] != 0 or any(gate["weights"])):
                    raise ValueError("Non-rotation gate has angle")
                if name in ROTATIONS:
                    derivatives.append(gate["weights"])
                if name != "barrier":
                    active.update(qs)
            if not active or len(active) > 4:
                raise ValueError("Expected local CEO support of at most four wires")
            if not derivatives or np.linalg.matrix_rank(derivatives, tol=1e-10) != p:
                raise ValueError("Registered coordinates must be independent, not counted by value")
    return s


def one_gate(state, matrix, q):
    ids = np.arange(state.shape[0])
    lo = ids[(ids & (1 << q)) == 0]
    hi = lo | (1 << q)
    out = state.copy()
    out[lo] = matrix[0, 0] * state[lo] + matrix[0, 1] * state[hi]
    out[hi] = matrix[1, 0] * state[lo] + matrix[1, 1] * state[hi]
    return out


def apply_gate(state, name, wires, angle=0., inverse=False):
    if name == "barrier":
        return state
    if name == "cx":
        ids = np.arange(state.shape[0])
        permutation = ids ^ (((ids >> wires[0]) & 1) << wires[1])
        return state[permutation]
    if name in ROTATIONS:
        axis = PAULI[name[-1].upper()]
        matrix = np.cos(angle / 2) * I - 1j * np.sin(angle / 2) * axis
    else:
        matrix = FIXED[name]
    return one_gate(state, matrix.conj().T if inverse else matrix, wires[0])


def theta_of(blocks):
    return np.array([x for b in blocks for x in b["theta"]], dtype=float)


def bind(blocks, theta):
    out, offset = [], 0
    for b in blocks:
        p = len(b["theta"])
        out.append({**b, "theta": [float(x) for x in theta[offset:offset+p]]})
        offset += p
    if offset != len(theta):
        raise ValueError("Parameter binding mismatch")
    return out


def instructions(blocks, theta):
    offset = 0
    for b in blocks:
        p = len(b["theta"])
        for g in b["gates"]:
            a = float(g["offset"] + np.dot(g["weights"], theta[offset:offset+p]))
            yield g, a, offset
        offset += p


def resources(blocks, n):
    depth, cxdepth = [0]*n, [0]*n
    cx = 0
    for b in blocks:
        for g in b["gates"]:
            qs, name = g["wires"], g["name"]
            # Native barrier synchronizes depth, but is not an executed gate.
            d = max(depth[q] for q in qs) + (name != "barrier")
            for q in qs:
                depth[q] = d
            if name == "cx":
                cx += 1
                c = max(cxdepth[q] for q in qs) + 1
                for q in qs:
                    cxdepth[q] = c
    return dict(zip(METRICS, [cx, max(cxdepth), len(theta_of(blocks)), max(depth)]))


def local_distance(block):
    """Phase-invariant local unitary distance; a proxy, NOT energy bound."""
    qs = sorted({q for g in block["gates"] if g["name"] != "barrier" for q in g["wires"]})
    mapping = {q: i for i, q in enumerate(qs)}
    unitary = np.eye(1 << len(qs), dtype=complex)
    for g, a, _ in instructions([block], theta_of([block])):
        if g["name"] != "barrier":
            unitary = apply_gate(unitary, g["name"], [mapping[q] for q in g["wires"]], a)
    return max(0., float(2 - 2 * abs(np.trace(unitary)) / len(unitary)))


class BudgetExceeded(RuntimeError):
    pass


class Meter:
    def __init__(self, limit, event_sink=None):
        if type(limit) is not int or limit < 1:
            raise ValueError("Explicit positive energy-equivalent budget required")
        self.limit, self.used = limit, 0
        self.energy = self.gradient_vectors = self.gradient_components = 0
        self.events = []
        self.event_sink = event_sink

    def reserve(self, label, p=0, energy=1):
        amount = energy + 2 * p
        if self.used + amount > self.limit:
            raise BudgetExceeded("MODEL_BUDGET_EXHAUSTED")
        # Reserved before kernel invocation: even exceptions/failed optimizations count.
        self.used += amount
        self.energy += energy
        self.gradient_components += p
        self.gradient_vectors += bool(p)
        event = {"operation": label, "energy": energy, "gradient_components": p,
                 "model_units": amount, "status": "RESERVED"}
        self.events.append(event)
        if self.event_sink:
            self.event_sink({"event": "RESERVED_BEFORE_KERNEL", "sequence": len(self.events), **event})
        return event

    def report(self):
        return {"limit": self.limit, "used": self.used, "energy_evaluations": self.energy,
                "gradient_vectors": self.gradient_vectors, "gradient_components": self.gradient_components,
                "definition": "N_energy + 2*N_gradient_components; model only, not physical shots",
                "events": self.events}


class Kernel:
    def __init__(self, source, meter):
        self.source, self.meter = source, meter
        self.n = source["n"]
        self.reference = np.zeros(1 << self.n, complex)
        self.reference[sum(1 << q for q in source["reference_occupied"])] = 1

    def state(self, blocks, theta):
        state = self.reference.copy()
        for gate, angle, _ in instructions(blocks, theta):
            state = apply_gate(state, gate["name"], gate["wires"], angle)
        return state

    def h_action(self, state):
        out = np.zeros_like(state)
        for term in self.source["hamiltonian"]:
            v = state
            for q, p in enumerate(term["pauli"]):
                if p != "I":
                    v = one_gate(v, PAULI[p], q)
            out += term["coefficient"] * v
        return out

    def evaluate(self, blocks, theta, gradient=False, label="ENERGY"):
        p = len(theta) if gradient else 0
        event = self.meter.reserve(label, p)
        try:
            state = self.state(blocks, theta)
            dual = self.h_action(state)
            value = np.vdot(state, dual)
            if abs(np.vdot(state, state) - 1) > 1e-9 or abs(value.imag) > 1e-9 or not np.isfinite(value):
                raise ValueError("Nonfinite/non-Hermitian/non-normalized evaluation")
            grad = np.zeros(len(theta))
            if gradient:
                # Adjoint differentiation, reverse reconstruction: O(2**n) memory.
                for gate, angle, offset in reversed(list(instructions(blocks, theta))):
                    name, qs = gate["name"], gate["wires"]
                    if name in ROTATIONS:
                        derivative = -.5j * one_gate(state, PAULI[name[-1].upper()], qs[0])
                        partial = 2 * np.vdot(dual, derivative).real
                        weights = gate["weights"]
                        grad[offset:offset+len(weights)] += partial * np.asarray(weights)
                    state = apply_gate(state, name, qs, angle, inverse=True)
                    dual = apply_gate(dual, name, qs, angle, inverse=True)
            if not np.all(np.isfinite(grad)):
                raise ValueError("Nonfinite gradient")
            event["status"] = "COMPLETED"
            return float(value.real), grad
        except Exception:
            event["status"] = "FAILED_CHARGED"
            raise

    def certify(self, blocks, expected_energy):
        """Independent Qiskit reconstruction, charged as a fresh energy evaluation."""
        from qiskit.quantum_info import Statevector, SparsePauliOp
        event = self.meter.reserve("INDEPENDENT_CERTIFICATION")
        try:
            qc = to_qiskit(blocks, self.n, self.source["reference_occupied"])
            vector = Statevector.from_instruction(qc)
            h = SparsePauliOp.from_list([(t["pauli"][::-1], t["coefficient"])
                                       for t in self.source["hamiltonian"]])
            energy = complex(vector.expectation_value(h))
            if abs(energy.imag) > 1e-9 or abs(energy.real - expected_energy) > 1e-9:
                raise ValueError("Independent energy disagreement")
            native = self.state(blocks, theta_of(blocks))
            if np.linalg.norm(vector.data - native) > 1e-9:
                raise ValueError("Independent state disagreement")
            probabilities = abs(vector.data)**2
            ids = np.arange(len(probabilities))
            leakage = []
            for constraint in self.source["sector"]:
                counts = sum((ids >> q) & 1 for q in constraint["wires"])
                leak = float(probabilities[counts != constraint["occupation"]].sum())
                leakage.append(leak)
                if leak > 1e-10:
                    raise ValueError("Sector leakage")
            r = resources(blocks, self.n)
            ansatz = to_qiskit(blocks, self.n)
            cx_only = ansatz.copy_empty_like()
            for inst in ansatz.data:
                if inst.operation.name == "cx":
                    cx_only.append(inst.operation, [ansatz.find_bit(q).index for q in inst.qubits])
            if (ansatz.count_ops().get("cx", 0), cx_only.depth(), ansatz.depth()) != (r["cnot"], r["cnot_depth"], r["total_depth"]):
                raise ValueError("Independent native resource disagreement")
            event["status"] = "COMPLETED"
            return {"energy": energy.real, "resources": r, "sector_leakage": leakage,
                    "sector_status": "CHECKED" if leakage else "NOT_REQUESTED_NOT_CERTIFIED",
                    "method": "independent-qiskit-state-energy-native-resources", "tolerance": 1e-9}
        except Exception:
            event["status"] = "FAILED_CHARGED"
            raise


def to_qiskit(blocks, n, occupied=()):
    from qiskit import QuantumCircuit
    qc = QuantumCircuit(n)
    for q in occupied:
        qc.x(q)
    for g, a, _ in instructions(blocks, theta_of(blocks)):
        f = getattr(qc, g["name"])
        if g["name"] in ROTATIONS:
            f(a, *g["wires"])
        else:
            f(*g["wires"])
    return qc


@dataclass(frozen=True)
class Config:
    model_budget: int
    beam_width: int = 5
    screen_per_parent: int = 8
    optimize_per_parent: int = 2
    pair_pool: int = 6
    maxiter: int = 100
    gtol: float = 1e-6
    comparison_tolerance: float = 1e-9

    def validate(self):
        for field in ("model_budget", "beam_width", "screen_per_parent", "optimize_per_parent", "pair_pool", "maxiter"):
            if type(getattr(self, field)) is not int or getattr(self, field) < 1:
                raise ValueError(f"Invalid {field}")
        if self.optimize_per_parent > self.screen_per_parent:
            raise ValueError("Optimization count exceeds screens")
        # Numerical comparison tolerance must not become a hidden accuracy target.
        if not 0 < self.comparison_tolerance <= 1e-8 or not 0 < self.gtol <= 1e-2:
            raise ValueError("Invalid numerical tolerance")


def proposals(blocks, n, config):
    """Single, local pair, and geometric-size joint removals, no old masks."""
    if not blocks:
        return []
    before = resources(blocks, n)
    distances = [local_distance(b) for b in blocks]
    singles = []
    for i in range(len(blocks)):
        child = blocks[:i] + blocks[i+1:]
        after = resources(child, n)
        singles.append((i, {m: max(0., (before[m]-after[m])/max(1, before[m])) for m in METRICS}))
    masks = {(i,) for i in range(len(blocks))}
    for m in METRICS:
        order = sorted(singles, key=lambda x: (distances[x[0]] / max(x[1][m], 1e-15), x[0]))
        pool = [i for i, _ in order[:config.pair_pool]]
        masks.update(tuple(sorted(pair)) for pair in itertools.combinations(pool, 2))
        size = 2
        while size < len(blocks):
            masks.add(tuple(sorted(i for i, _ in order[:size])))
            size *= 2
    candidates = []
    for mask in sorted(masks):
        child = [b for i, b in enumerate(blocks) if i not in mask]
        after = resources(child, n)
        gains = {m: max(0., (before[m] - after[m]) / max(1, before[m])) for m in METRICS}
        proxy = sum(distances[i] for i in mask)
        candidates.append({"removed_positions": mask, "blocks": child, "resources": after,
                           "proxy": proxy, "scores": {m: proxy / max(gains[m], 1e-15) for m in METRICS}})
    # Round-robin over four current-resource rankings: no CNOT-only preference.
    rankings = [sorted(candidates, key=lambda c: (c["scores"][m], c["removed_positions"])) for m in METRICS]
    out, seen = [], set()
    for row in itertools.zip_longest(*rankings):
        for c in row:
            if c is not None and c["removed_positions"] not in seen:
                seen.add(c["removed_positions"])
                out.append(c)
    return out


def vector(record):
    return (record["energy"], *(record["resources"][m] for m in METRICS))


def frontier(records):
    unique = {digest(r["blocks"]): r for r in records}
    values = list(unique.values())
    return [r for r in values if not any(
        all(a <= b for a, b in zip(vector(other), vector(r))) and
        any(a < b for a, b in zip(vector(other), vector(r))) for other in values)]


def diverse_beam(records, width):
    # Retain approximate intermediate bridges too, not only certified improvements.
    out, seen = [], set()
    keys = [lambda r: (r["energy"], digest(r["blocks"]))]
    keys += [lambda r, m=m: (r["resources"][m], r["energy"], digest(r["blocks"])) for m in METRICS]
    rankings = [sorted(records, key=key) for key in keys]
    for row in itertools.zip_longest(*rankings):
        for r in row:
            if r is not None:
                key = digest(r["blocks"])
                if key not in seen:
                    seen.add(key)
                    out.append(r)
                    if len(out) == width:
                        return out
    return out


def comparison(candidate, originals, tol):
    """Discrete observed CEO frontier; no interpolated imaginary circuits."""
    result = {}
    for m in METRICS:
        accurate = [r for r in originals if r["energy"] <= candidate["energy"] + tol]
        if not accurate:
            result[m] = {"status": "NO_OBSERVED_EQUAL_OR_BETTER_ENERGY_COMPARATOR"}
            continue
        best = min(accurate, key=lambda r: (r["resources"][m], r["energy"]))
        baseline, child = best["resources"][m], candidate["resources"][m]
        # Supplement: can an observed CEO point with <= candidate resources match E?
        cheaper = [r for r in originals if r["resources"][m] <= child]
        gap = None if not cheaper else min(r["energy"] for r in cheaper) - candidate["energy"]
        wins = child < baseline and (gap is None or gap > tol)
        result[m] = {"status": "VERIFIED_OBSERVED_FRONTIER_GAIN" if wins else "NO_VERIFIED_GAIN",
                     "ceo_growth_step": best["growth_step"], "ceo_energy": best["energy"],
                     "ceo_resource": baseline, "candidate_resource": child,
                     "reduction_fraction": None if baseline == 0 else (baseline-child)/baseline,
                     "energy_gap_vs_observed_ceo_at_no_more_resource": gap}
    return result


def search(source, config, event_sink=None):
    validate_source(source)
    config.validate()
    meter = Meter(config.model_budget, event_sink)
    kernel = Kernel(source, meter)
    originals, trials, archive = [], [], []
    attempted = set()
    reason = "SEARCH_SPACE_EXHAUSTED"
    try:
        # Recompute only current uncompressed trajectory. Charge verification work.
        for frame in source["frames"]:
            blocks = frame["blocks"]
            e, _ = kernel.evaluate(blocks, theta_of(blocks), label="SOURCE_ENERGY")
            certificate = kernel.certify(blocks, e)
            originals.append({**frame, "energy": e, "resources": resources(blocks, source["n"]),
                              "certificate": certificate})
        beam = [originals[-1]]
        while beam:
            children = []
            for parent in beam:
                selected = []
                for proposal in proposals(parent["blocks"], source["n"], config):
                    # theta is in this key. Same topology/different initialization is NOT reuse.
                    key = digest(proposal["blocks"])
                    if key in attempted:
                        continue
                    attempted.add(key)
                    child = proposal["blocks"]
                    energy, _ = kernel.evaluate(child, theta_of(child), label="SCREEN_ENERGY")
                    record = {"parent_state_digest": digest(parent["blocks"]), "initial_blocks": child,
                              "removed_positions": list(proposal["removed_positions"]),
                              "screen_energy": energy, "proxy": proposal["proxy"],
                              "resources": proposal["resources"], "optimized": False}
                    trials.append(record)
                    selected.append(record)
                    if len(selected) == config.screen_per_parent:
                        break
                if not selected:
                    continue
                # First: policy-resource nominee even if initial E is poor. Remaining: E.
                nominations = [selected[0]] + sorted(selected[1:], key=lambda r: (r["screen_energy"], r["removed_positions"]))
                for record in nominations[:config.optimize_per_parent]:
                    blocks = record["initial_blocks"]
                    initial = theta_of(blocks)
                    best = [record["screen_energy"], initial.copy(), None]
                    start_cost = meter.used
                    calls = [0]

                    def objective(theta):
                        energy, grad = kernel.evaluate(blocks, theta, True, "OPTIMIZER_ENERGY_GRADIENT")
                        calls[0] += 1
                        if energy < best[0] or best[2] is None:
                            best[:] = [energy, np.array(theta), np.array(grad)]
                        return energy, grad

                    if len(initial):
                        result = minimize(objective, initial, jac=True, method="BFGS",
                                          options={"gtol": config.gtol, "maxiter": config.maxiter})
                        if result.nfev != calls[0] or result.njev != calls[0]:
                            raise ValueError("Optimizer/runtime accounting mismatch")
                        record.update(optimizer_success=bool(result.success), optimizer_message=str(result.message),
                                      optimizer_iterations=int(result.nit), optimizer_calls=calls[0])
                    else:
                        record.update(optimizer_success=True, optimizer_message="NO_VARIABLES",
                                      optimizer_iterations=0, optimizer_calls=0)
                    optimized = bind(blocks, best[1])
                    record.update(optimized=True, final_blocks=optimized, final_energy=float(best[0]),
                                  optimization_model_units=meter.used-start_cost,
                                  gradient_inf=None if best[2] is None else float(np.max(abs(best[2]))))
                    # Certification occurs before promotion. Budget loss is not success.
                    cert = kernel.certify(optimized, best[0])
                    child = {"blocks": optimized, "energy": best[0], "resources": record["resources"],
                             "certificate": cert, "parent_state_digest": record["parent_state_digest"]}
                    children.append(child)
                    archive.append(child)
            beam = diverse_beam(children, config.beam_width)
    except BudgetExceeded:
        reason = "MODEL_BUDGET_EXHAUSTED"
    # No comparison if original trajectory could not be fully certified.
    outputs = []
    if len(originals) == len(source["frames"]):
        for r in frontier(archive):
            c = comparison(r, originals, config.comparison_tolerance)
            outputs.append({**r, "comparison": c,
                            "gain_metrics": [m for m, v in c.items() if v["status"] == "VERIFIED_OBSERVED_FRONTIER_GAIN"]})
    return {"version": VERSION, "source_digest": digest(source), "config": asdict(config),
            "termination": reason, "originals": originals, "trials": trials, "frontier": outputs,
            "status": "VERIFIED_GAIN_FOUND" if any(r["gain_metrics"] for r in outputs) else "NO_VERIFIED_GAIN",
            "meter": meter.report(), "claims": {
                "historical_compression_input": False, "machine_learning": False,
                "optimality_guarantee": False, "matched_total_work_superiority": False,
                "hardware_shots_measured": False, "source_provenance_is_trusted_exporter_attestation": True}}
