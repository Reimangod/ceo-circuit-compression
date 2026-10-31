"""Classical source-only audit of pinned OVP subfamilies inside MVP blocks.

No Hamiltonian expectation, parameter optimization or compressed outcome input.
This is a candidate-representation feasibility check, not compression performance.
"""
import copy
import itertools
import sys
import types
import numpy as np
from common import HERE,ROOT,BASE,read,atomic
sys.path.insert(0,str(BASE/'code'))
import core
from fast_kernel import operator_matrix

def localize(block):
    qs=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
    b=copy.deepcopy(block)
    b['gates']=[dict(g,wires=[qs.index(q) for q in g['wires']]) for g in block['gates'] if g['name']!='barrier']
    return qs,b

def distance_up_to_phase(a,b):
    phase=np.angle(np.trace(b.conj().T@a))
    return float(np.linalg.norm(a-np.exp(1j*phase)*b))

def registered_templates():
    if 'adaptvqe' not in sys.modules:
        package=types.ModuleType('adaptvqe');package.__path__=[str(ROOT/'paper-era-reproduction/a3f89d0/adaptvqe')]
        sys.modules['adaptvqe']=package
    from adaptvqe.circuits import ovp_ceo_circuit
    sys.path.insert(0,str(ROOT/'outputs/ceo-current-rule-policy-2026-10-06'))
    import export_current as ex
    templates=[];seen=set()
    for a,b,c,d in itertools.permutations(range(4)):
        source=[sorted([a,c]),sorted([b,c])];target=[sorted([b,d]),sorted([a,d])]
        for kind in ('sum','diff'):
            block=ex.affine_template(lambda x,s=source,t=target,k=kind:ovp_ceo_circuit(s,t,4,x[0],k),
                [.1],'local-registered-OVP','OVP',dict(source=source,target=target,type=kind))
            _,u0,du=operator_matrix(block,np.zeros(1),True);h=du[0]@u0.conj().T
            identity=tuple(np.round(np.r_[h.real.ravel(),h.imag.ravel()],12))
            if identity in seen:continue
            seen.add(identity);templates.append((block,h))
    return templates

def restrictions(local,templates):
    p=len(local['theta']);_,u0,du=operator_matrix(local,np.zeros(p),True)
    generators=np.array([d@u0.conj().T for d in du])
    comm=max((np.linalg.norm(a@b-b@a) for a,b in itertools.combinations(generators,2)),default=0.)
    if comm>1e-9:raise ValueError('MVP generators not commuting')
    matrix=np.stack([g.ravel() for g in generators],axis=1);found=[]
    for block,h in templates:
        coeff,_,_,_=np.linalg.lstsq(matrix,h.ravel(),rcond=1e-12)
        residual=float(np.linalg.norm(matrix@coeff-h.ravel()))
        if residual>1e-9 or max(abs(coeff.imag))>1e-10:continue
        coeff=coeff.real;coeff[abs(coeff)<1e-12]=0
        if np.count_nonzero(coeff)<2:continue
        errors=[]
        for phi in (-.271,.193,.517):
            _,a,_=operator_matrix(local,coeff*phi);_,b,_=operator_matrix(block,[phi])
            errors.append(distance_up_to_phase(a,b))
        if max(errors)>1e-9:raise ValueError('Native OVP subfamily disagreement')
        found.append(dict(local_template=block,coordinate_direction=coeff.tolist(),generator_residual=residual,
            generator_commutator_norm=float(comm),unitary_probe_errors=errors,
            containment_scope='registered CEO subfamily, numerically checked up to global phase',
            source_state_preservation='NOT_ASSERTED_AFTER_COEFFICIENT_PROJECTION'))
    return found

def main():
    templates=registered_templates();inv=read(HERE/'inventory.json');last={}
    for task in inv['tasks']:
        if task['case_id'] not in last or task['root_step']>last[task['case_id']]['root_step']:last[task['case_id']]=task
    cache={};cases=[]
    for case,task in sorted(last.items()):
        source=read(task['source']);blocks=source['frames'][-1]['blocks'];matches=[]
        for position,block in enumerate(blocks):
            if len(block['theta'])<2:continue
            qs,local=localize(block)
            identity=core.digest(dict(gates=local['gates'],arity=len(local['theta'])))
            if identity not in cache:cache[identity]=restrictions(local,templates)
            variants=[]
            for match in cache[identity]:
                v=np.asarray(match['coordinate_direction']);phi=float(v@np.asarray(block['theta'])/(v@v))
                variants.append(dict(direction=v.tolist(),projected_initial_phi=phi,
                    coefficient_projection_residual=float(np.linalg.norm(np.asarray(block['theta'])-v*phi)),
                    local_template_digest=core.digest(match['local_template']),
                    native_CNOT=core.resources([match['local_template']],4)['cnot']))
            matches.append(dict(block_position=position,independent_parameters=len(block['theta']),
                source_CNOT=core.resources([block],source['n'])['cnot'],qubits=qs,variants=variants))
        cases.append(dict(case_id=case,source_sha256=task['source_sha256'],root_step=task['root_step'],
                          multi_parameter_blocks=len(matches),blocks_with_OVP_subfamily=sum(bool(m['variants']) for m in matches),blocks=matches))
        print('BLOCK_AUDIT',case,len(matches),sum(bool(m['variants']) for m in matches),flush=True)
    atomic(HERE/'block-restriction-feasibility.json',dict(status='CLASSICAL_FEASIBILITY_ONLY',cases=cases,
        unique_local_source_templates=len(cache),registered_local_OVP_templates=len(templates),
        numerical_checks=list(cache.values()),candidate_energy_evaluations=0,new_FCI=0,
        note='Projection proposes a smaller family. Full-circuit energy acceptance remains to be tested within unchanged W.'))

if __name__=='__main__':main()
