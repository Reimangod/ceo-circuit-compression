"""Exact local algebra for a known computational-basis input.

Prototype, not used by execution-v16. No Hamiltonian, energy, or old result input.
One-parameter local blocks only; unsupported templates are left unchanged.
"""
from fractions import Fraction
import copy
import hashlib
import itertools
import json
import math
import sympy as sp
from sympy.polys.domains import QQ

FIELD=QQ.algebraic_field(sp.sqrt(2),sp.I)
ZERO,ONE=FIELD.zero,FIELD.one
HALF=FIELD.from_sympy(sp.Rational(1,2))
IM=FIELD.from_sympy(sp.I)
SQ=FIELD.from_sympy(sp.sqrt(2)/2)
IDENTITY=((ONE,ZERO),(ZERO,ONE))
PAULI={'x':((ZERO,ONE),(ONE,ZERO)),
       'y':((ZERO,-IM),(IM,ZERO)),
       'z':((ONE,ZERO),(ZERO,-ONE))}
FIXED=dict(PAULI,h=((SQ,SQ),(SQ,-SQ)),s=((ONE,ZERO),(ZERO,IM)),
           sdg=((ONE,ZERO),(ZERO,-IM)),t=((ONE,ZERO),(ZERO,SQ*(ONE+IM))),
           tdg=((ONE,ZERO),(ZERO,SQ*(ONE-IM))))

class Unsupported(Exception):pass

def matrix_multiply(a,b):
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in (0,1)),ZERO) for j in (0,1)) for i in (0,1))

def rotation_terms(gate):
    weight=Fraction(gate['weights'][0]);offset=float(gate['offset'])
    if weight.denominator>16:raise Unsupported('Unregistered rational rotation weight')
    # Standard fixed Clifford angles are interpreted as their exact pi multiples.
    # The numerical implementation check remains necessary for float source files.
    half_pi=round(offset/(math.pi/2))
    if offset!=half_pi*(math.pi/2):raise Unsupported('Non-Clifford fixed rotation offset')
    angle=sp.Rational(half_pi,4)*sp.pi
    cc=FIELD.from_sympy(sp.cos(angle));ss=FIELD.from_sympy(sp.sin(angle));axis=PAULI[gate['name'][-1]]
    base=tuple(tuple(cc*IDENTITY[i][j]-IM*ss*axis[i][j] for j in (0,1)) for i in (0,1))
    if not weight:return [(Fraction(0),base)]
    plus=tuple(tuple((IDENTITY[i][j]+axis[i][j])*HALF for j in (0,1)) for i in (0,1))
    minus=tuple(tuple((IDENTITY[i][j]-axis[i][j])*HALF for j in (0,1)) for i in (0,1))
    return [(-weight/2,matrix_multiply(base,plus)),(weight/2,matrix_multiply(base,minus))]

def polynomial_state(block,basis):
    """Laurent coefficients of U(theta)|basis>, using exact algebraic numbers."""
    if len(block['theta'])!=1:raise Unsupported('Only one independent coordinate is registered')
    support=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
    if not support or len(support)>4:raise Unsupported('Expected at most four local wires')
    initial=sum(int(basis[q])<<i for i,q in enumerate(support))
    state=[{} for _ in range(1<<len(support))];state[initial]={Fraction(0):ONE}
    for gate in block['gates']:
        name=gate['name']
        if name=='barrier':continue
        wires=[support.index(q) for q in gate['wires']]
        if name=='cx':
            control,target=wires
            state=[state[x^(((x>>control)&1)<<target)] for x in range(len(state))]
            continue
        if name in ('rx','ry','rz'):terms=rotation_terms(gate)
        elif name in FIXED:terms=[(Fraction(0),FIXED[name])]
        else:raise Unsupported('Unsupported fixed local gate')
        out=[{} for _ in state];wire=wires[0]
        for bits,poly in enumerate(state):
            col=(bits>>wire)&1
            for frequency,matrix in terms:
                for row in (0,1):
                    coefficient=matrix[row][col]
                    if coefficient==ZERO:continue
                    target=(bits&~(1<<wire))|(row<<wire)
                    for f,value in poly.items():
                        key=f+frequency;out[target][key]=out[target].get(key,ZERO)+coefficient*value
        state=[{f:value for f,value in poly.items() if value!=ZERO} for poly in out]
    return support,initial,state

def two_level_certificate(block,basis):
    first_barrier=next((i for i,g in enumerate(block['gates']) if g['name']=='barrier'),len(block['gates']))
    if any(g['name']!='barrier' for g in block['gates'][first_barrier:]):
        raise Unsupported('Only trailing native scheduling barriers can be preserved')
    support,initial,state=polynomial_state(block,basis)
    nonzero=[i for i,poly in enumerate(state) if poly]
    if len(nonzero)!=2 or initial not in nonzero:raise Unsupported('Not a two-level basis-input family')
    other=next(i for i in nonzero if i!=initial);poly=state[initial]
    if len(poly)!=2:raise Unsupported('Not a cosine family')
    frequencies=sorted(poly)
    if frequencies[0]!=-frequencies[1] or frequencies[1]<=0:raise Unsupported('Unregistered common theta phase')
    omega=frequencies[1];phase=poly[omega]/HALF
    if poly[-omega]!=phase*HALF:raise Unsupported('Unequal cosine coefficients')
    phase_expr=sp.simplify(FIELD.to_sympy(phase))
    if sp.simplify(phase_expr*sp.conjugate(phase_expr))!=1:raise Unsupported('Not a unit-modulus fixed phase')
    sine=state[other]
    sign=None
    for candidate in (1,-1):
        expected={omega:-IM*HALF*phase*candidate,-omega:IM*HALF*phase*candidate}
        if sine==expected:sign=candidate
    if sign is None:raise Unsupported('Not a real signed sine family')
    return dict(method='exact Laurent coefficients over Q(sqrt(2),i)',
        source_support=support,input_basis_bits=[int(basis[q]) for q in support],
        initial_local_bits=initial,other_local_bits=other,frequency=[omega.numerator,omega.denominator],
        sine_sign=sign,constant_global_phase=str(phase_expr),
        scope='all theta for this fixed basis input; not an identity on arbitrary inputs',
        exact_angle_convention='source fixed Clifford offsets interpreted as exact pi/2 multiples')

def realize(block,certificate,pivot,targets):
    """Prepare cos(omega theta)|a> +/- sin(omega theta)|b> on the known input."""
    support=certificate['source_support'];a=certificate['initial_local_bits'];b=certificate['other_local_bits']
    flip=[q for i,q in enumerate(support) if ((a^b)>>i)&1]
    if pivot not in flip or set(targets)!=set(flip)-{pivot}:raise ValueError('Bad fanout support')
    ones=[q for i,q in enumerate(support) if q in flip and (a>>i)&1]
    fixed=lambda name,wires:dict(name=name,wires=wires,offset=0.,weights=[0.])
    omega=Fraction(*certificate['frequency']);gates=[fixed('x',[q]) for q in ones]
    gates.append(dict(name='ry',wires=[pivot],offset=0.,weights=[float(2*omega*certificate['sine_sign'])]))
    gates.extend(fixed('cx',[pivot,q]) for q in targets)
    gates.extend(fixed('x',[q]) for q in ones)
    gates.extend(copy.deepcopy(g) for g in block['gates'] if g['name']=='barrier')
    identity=hashlib.sha256(json.dumps(dict(family='REFERENCE_INPUT_STATE_PREPARATION',gates=gates),
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return dict(occurrence_id=block['occurrence_id']+':reference-input',family='REFERENCE_INPUT_STATE_PREPARATION',
        generator_digest=identity,theta=list(block['theta']),gates=gates)

def end_times(gates,start,cnot_only):
    times=list(start)
    for gate in gates:
        if cnot_only and gate['name']!='cx':continue
        when=max(times[q] for q in gate['wires'])+(gate['name']!='barrier')
        for q in gate['wires']:times[q]=when
    return times

def simplify_frame(blocks,n,reference_occupied,certificate_lookup=None):
    """One deterministic algebraic policy, with per-wire depth dominance.

    Known bits describe an entire parameterized family, not a numerical theta
    coincidence. A non-basis input is conservatively left unchanged.
    """
    known={q:int(q in reference_occupied) for q in range(n)}
    original_cnot=[0]*n;original_depth=[0]*n
    compiled_cnot=[0]*n;compiled_depth=[0]*n
    output=[];records=[];phase=sp.Integer(1)
    for index,block in enumerate(blocks):
        support=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
        original_cnot=end_times(block['gates'],original_cnot,True)
        original_depth=end_times(block['gates'],original_depth,False)
        certificate=None;reason='INPUT_NOT_PROVEN_COMPUTATIONAL_BASIS';choices=[]
        if all(q in known for q in support):
            try:
                certificate=(certificate_lookup or two_level_certificate)(block,known)
                a=certificate['initial_local_bits'];b=certificate['other_local_bits']
                flip=[q for j,q in enumerate(support) if ((a^b)>>j)&1]
                for pivot in flip:
                    for targets in itertools.permutations(q for q in flip if q!=pivot):
                        child=realize(block,certificate,pivot,targets)
                        nc=end_times(child['gates'],compiled_cnot,True)
                        nd=end_times(child['gates'],compiled_depth,False)
                        if (sum(g['name']=='cx' for g in child['gates'])<sum(g['name']=='cx' for g in block['gates'])
                                and all(x<=y for x,y in zip(nc,original_cnot))
                                and all(x<=y for x,y in zip(nd,original_depth))):
                            choices.append(((max(nc),max(nd),sum(nc),sum(nd),pivot,targets),child,nc,nd))
                reason='NO_PER_WIRE_DOMINATING_REALIZATION'
            except Unsupported as error:reason=str(error)
        if choices:
            _,child,compiled_cnot,compiled_depth=min(choices,key=lambda x:x[0]);output.append(child)
            phase=sp.simplify(phase*sp.sympify(certificate['constant_global_phase']))
            records.append(dict(source_block_position=index,original_generator_digest=block['generator_digest'],
                compiled_template_digest=child['generator_digest'],certificate=certificate,
                cnot_before=sum(g['name']=='cx' for g in block['gates']),
                cnot_after=sum(g['name']=='cx' for g in child['gates']),
                original_cnot_end_times=list(original_cnot),compiled_cnot_end_times=list(compiled_cnot),
                original_depth_end_times=list(original_depth),compiled_depth_end_times=list(compiled_depth)))
        else:
            output.append(copy.deepcopy(block))
            compiled_cnot=end_times(block['gates'],compiled_cnot,True)
            compiled_depth=end_times(block['gates'],compiled_depth,False)
        if certificate is not None:
            a=certificate['initial_local_bits'];b=certificate['other_local_bits']
            for j,q in enumerate(support):
                if ((a^b)>>j)&1:known.pop(q,None)
                else:known[q]=(a>>j)&1
        else:
            for q in support:known.pop(q,None)
        assert all(x<=y for x,y in zip(compiled_cnot,original_cnot))
        assert all(x<=y for x,y in zip(compiled_depth,original_depth))
    return dict(blocks=output,records=records,source_to_compiled_global_phase=str(phase),
        cnot_depth=max(compiled_cnot),total_depth=max(compiled_depth),
        energy_or_gradient_queries=0,selection='fixed reference bits and exact local operator algebra only',
        parameter_binding='same independent source coordinates; no fixed-coefficient parameter count of zero',
        scope='same state family on the registered reference; arbitrary-input unitary and noisy-channel equality not claimed')
