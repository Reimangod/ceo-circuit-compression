"""Exact complex fixed-occupation numerical adapter for the unchanged policy.

No wavefunction truncation. Raw CEO unitaries are used for gradients; compiled
state-preparation circuits are only reconstructed forward and certified.
"""
from collections import OrderedDict
import time
import numpy as np
from scipy.sparse import coo_matrix
import core
from fast_kernel import operator_matrix

def pauli_masks(source):
    words=[];groups={}
    for t in source['hamiltonian']:
        x=z=ny=0
        for q,a in enumerate(t['pauli']):
            if a in 'XY':x|=1<<q
            if a in 'YZ':z|=1<<q
            ny+=a=='Y'
        c=t['coefficient']*(1j**ny)
        words.append((x,z,c));groups.setdefault(x,[]).append((z,c))
    return words,groups

class BlockKernel:
    def __init__(self,source,meter):
        self.source=source;self.meter=meter;self.n=source['n'];self.guard=lambda:None
        all_ids=np.arange(1<<self.n,dtype=np.uint64);valid=np.ones(len(all_ids),bool)
        for c in source['sector']:
            count=sum((all_ids>>np.uint64(q))&1 for q in c['wires'])
            valid&=count==c['occupation']
        self.ids=all_ids[valid]
        if len(self.ids)>25000000 or not len(self.ids):raise ValueError('Invalid exact occupation sector')
        self.lookup=np.full(1<<self.n,-1,np.int32);self.lookup[self.ids.astype(int)]=np.arange(len(self.ids))
        ref=sum(1<<q for q in source['reference_occupied']);i=int(self.lookup[ref])
        if i<0:raise ValueError('Reference outside requested sector')
        self.reference=np.zeros(len(self.ids),complex);self.reference[i]=1
        self.words,groups=pauli_masks(source);rows=[];cols=[];data=[]
        for x,terms in groups.items():
            diagonal=np.zeros(len(self.ids),complex)
            for z,c in terms:
                parity=np.bitwise_count(self.ids & np.uint64(z))&1
                diagonal+=c*(1.-2.*parity.astype(float))
            destination=self.lookup[(self.ids ^ np.uint64(x)).astype(int)]
            ok=destination>=0
            if np.linalg.norm(diagonal[~ok])>1e-9:raise ValueError('Hamiltonian does not preserve requested occupation sector')
            nonzero=ok & (diagonal!=0)
            if np.any(nonzero):
                rows.append(destination[nonzero]);cols.append(np.flatnonzero(nonzero).astype(np.int32));data.append(diagonal[nonzero])
        self.hs=coo_matrix((np.concatenate(data),(np.concatenate(rows),np.concatenate(cols))),
                           shape=(len(self.ids),len(self.ids))).tocsr();self.hs.eliminate_zeros()
        anti=self.hs-self.hs.getH()
        if anti.nnz and np.max(abs(anti.data))>1e-10:raise ValueError('Non-Hermitian exact-sector Hamiltonian')
        self.layouts=OrderedDict();self.layout_bytes=0;self.cache_limit=32*2**20
        self.cert_matrices=OrderedDict();self.seconds=0.;self.evaluations=0

    def layout(self,qs):
        key=tuple(qs)
        if key in self.layouts:self.layouts.move_to_end(key);return self.layouts[key]
        mask=sum(1<<q for q in qs)
        _,column=np.unique(self.ids & np.uint64(((1<<self.n)-1)^mask),return_inverse=True)
        column=column.astype(np.int32);pattern=np.zeros(len(self.ids),np.uint8)
        for j,q in enumerate(qs):pattern|=(((self.ids>>np.uint64(q))&1)<<j).astype(np.uint8)
        valid=np.zeros((1<<len(qs),int(column.max())+1),bool);valid[pattern,column]=True
        size=column.nbytes+pattern.nbytes+valid.nbytes
        while self.layouts and self.layout_bytes+size>self.cache_limit:
            _,old=self.layouts.popitem(last=False);self.layout_bytes-=sum(a.nbytes for a in old)
        result=(pattern,column,valid)
        if size<=self.cache_limit:self.layouts[key]=result;self.layout_bytes+=size
        return result

    def apply_local(self,state,u,qs,check=True):
        pattern,column,valid=self.layout(qs)
        panel=np.zeros(valid.shape,complex);panel[pattern,column]=state
        out=u@panel
        if check and np.linalg.norm(out[~valid])>1e-9:raise ValueError('Local block leaks outside exact occupation sector')
        return out[pattern,column].copy()

    def state(self,blocks,theta):
        v=self.reference.copy();off=0
        for b in blocks:
            self.guard();p=len(b['theta']);qs,u,_=operator_matrix(b,theta[off:off+p]);off+=p
            v=self.apply_local(v,u,qs)
        return v

    def h_action(self,state):return self.hs@state

    def evaluate(self,blocks,theta,gradient=False,label='ENERGY'):
        started=time.monotonic();event=self.meter.reserve(label,len(theta) if gradient else 0)
        try:
            if gradient and any(b['family'] not in ('QE','OVP','MVP') for b in blocks):
                raise ValueError('Use raw particle-preserving CEO blocks for gradients, not state-only rewrites')
            v=self.state(blocks,theta);dual=self.h_action(v);e=np.vdot(v,dual);g=np.zeros(len(theta))
            if abs(np.vdot(v,v)-1)>1e-9 or abs(e.imag)>1e-9:raise ValueError('State/energy invalid')
            if gradient:
                off=len(theta)
                for b in reversed(blocks):
                    self.guard();p=len(b['theta']);off-=p;qs,u,du=operator_matrix(b,theta[off:off+p],True)
                    before=self.apply_local(v,u.conj().T,qs)
                    for j in range(p):g[off+j]=2*np.vdot(dual,self.apply_local(before,du[j],qs)).real
                    dual=self.apply_local(dual,u.conj().T,qs);v=before
            if not np.isfinite(e) or not np.isfinite(g).all():raise ValueError('Nonfinite objective')
            event['status']='COMPLETED';return float(e.real),g
        except BaseException:
            event['status']='FAILED_CHARGED';raise
        finally:self.seconds+=time.monotonic()-started;self.evaluations+=1

    def qiskit_local_matrix(self,b):
        from qiskit import QuantumCircuit
        from qiskit.quantum_info import Operator
        key=core.digest(b)
        if key in self.cert_matrices:self.cert_matrices.move_to_end(key);return self.cert_matrices[key]
        qs=sorted({q for g in b['gates'] if g['name']!='barrier' for q in g['wires']})
        if len(qs)>4:raise ValueError('Registered CEO support exceeds four wires')
        qc=QuantumCircuit(len(qs))
        for g,a,_ in core.instructions([b],core.theta_of([b])):
            if g['name']=='barrier':continue
            fn=getattr(qc,g['name']);w=[qs.index(q) for q in g['wires']]
            if g['name'] in core.ROTATIONS:fn(a,*w)
            else:fn(*w)
        result=(qs,Operator(qc).data);self.cert_matrices[key]=result
        if len(self.cert_matrices)>512:self.cert_matrices.popitem(last=False)
        return result

    def independent_state(self,blocks):
        # Independent embedding by explicit destination bits, not panel multiplication.
        v=self.reference.copy()
        for b in blocks:
            self.guard();qs,u=self.qiskit_local_matrix(b);pattern=np.zeros(len(self.ids),np.uint8)
            support=sum(1<<q for q in qs)
            for j,q in enumerate(qs):pattern|=(((self.ids>>np.uint64(q))&1)<<j).astype(np.uint8)
            rest=self.ids & np.uint64(((1<<self.n)-1)^support);out=np.zeros_like(v)
            for col in range(len(u)):
                src=np.flatnonzero(pattern==col)
                if not len(src):continue
                for row in np.flatnonzero(u[:,col]!=0):
                    bits=sum(((int(row)>>j)&1)<<q for j,q in enumerate(qs))
                    dst=self.lookup[(rest[src]|np.uint64(bits)).astype(int)];good=dst>=0
                    if np.linalg.norm(v[src[~good]])*abs(u[row,col])>1e-9:raise ValueError('Independent state reconstruction leaks')
                    out[dst[good]]+=u[row,col]*v[src[good]]
            v=out
        return v

    def independent_energy(self,state):
        # Term-wise expectation; no use of the grouped sparse Hamiltonian above.
        e=0j
        for x,z,c in self.words:
            dst=self.lookup[(self.ids ^ np.uint64(x)).astype(int)];valid=dst>=0
            parity=np.bitwise_count(self.ids & np.uint64(z))&1
            e+=c*np.vdot(state[dst[valid]],(1.-2.*parity[valid].astype(float))*state[valid])
        return e

    def certify(self,blocks,expected_energy):
        event=self.meter.reserve('INDEPENDENT_CERTIFICATION')
        try:
            v=self.independent_state(blocks);e=self.independent_energy(v)
            native=self.state(blocks,core.theta_of(blocks));err=float(np.linalg.norm(v-native))
            if err>1e-9 or abs(np.vdot(v,v)-1)>1e-9 or abs(e.imag)>1e-9 or abs(e.real-expected_energy)>1e-9:
                raise ValueError('Independent state/Pauli energy disagreement')
            from qiskit import QuantumCircuit
            qc=core.to_qiskit(blocks,self.n);cx=QuantumCircuit(self.n)
            for inst in qc.data:
                if inst.operation.name=='cx':cx.append(inst.operation,[qc.find_bit(q).index for q in inst.qubits])
            rr=core.resources(blocks,self.n)
            if (qc.count_ops().get('cx',0),cx.depth(),qc.depth())!=(rr['cnot'],rr['cnot_depth'],rr['total_depth']):
                raise ValueError('Resource recount disagrees')
            event['status']='COMPLETED'
            return dict(energy=float(e.real),resources=rr,sector_leakage=[0.]*len(self.source['sector']),
                sector_status='EXACT_OCCUPATION_BASIS_AND_LOCAL_LEAKAGE_CHECKED',
                method='independent-qiskit-local-unitaries/explicit-bit-embedding/termwise-Pauli-energy',
                tolerance=1e-9,state_error=err,independent_global_Qiskit_statevector=False,
                sector_dimension=len(self.ids),global_wavefunction_truncation=False)
        except BaseException:
            event['status']='FAILED_CHARGED';raise
