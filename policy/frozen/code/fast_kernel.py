"""Exact local block evaluation + selected-sector sparse Hamiltonian. No result data."""
import time
import numpy as np
from scipy.sparse import coo_matrix
import core

def operator_matrix(block,theta,derivatives=False):
    qs=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
    lookup={q:i for i,q in enumerate(qs)}; d=1<<len(qs)
    u=np.eye(d,dtype=complex); du=np.zeros((len(theta),d,d),dtype=complex)
    for g,a,_ in core.instructions([block],theta):
        if g['name']=='barrier':continue
        wires=[lookup[q] for q in g['wires']]
        u=core.apply_gate(u,g['name'],wires,a)
        if derivatives:
            for j in range(len(theta)):du[j]=core.apply_gate(du[j],g['name'],wires,a)
            if g['name'] in core.ROTATIONS:
                z=-.5j*core.one_gate(u,core.PAULI[g['name'][-1].upper()],wires[0])
                for j,w in enumerate(g['weights']):
                    if w:du[j]+=w*z
    return qs,u,du

class BlockKernel(core.Kernel):
    def __init__(self,source,meter):
        super().__init__(source,meter)
        self.indices={};ids=np.arange(1<<self.n,dtype=np.int64);valid=np.ones(len(ids),bool)
        for c in source['sector']:
            counts=sum((ids>>q)&1 for q in c['wires']);valid&=counts==c['occupation']
        self.sector_ids=ids[valid]
        if not len(self.sector_ids):raise ValueError('Empty sector')
        inv=np.full(len(ids),-1,dtype=np.int64);inv[self.sector_ids]=np.arange(len(self.sector_ids))
        rows=[];cols=[];data=[];x=self.sector_ids
        for term in source['hamiltonian']:
            flip=ny=0;parity=np.zeros(len(x),np.int8)
            for q,p in enumerate(term['pauli']):
                if p in 'XY':flip|=1<<q
                if p in 'YZ':parity^=((x>>q)&1).astype(np.int8)
                ny+=p=='Y'
            yy=inv[x^flip];ok=yy>=0
            rows.extend(yy[ok]);cols.extend(np.flatnonzero(ok))
            data.extend((term['coefficient']*(1j**ny)*(1-2*parity[ok])))
        self.hs=coo_matrix((data,(rows,cols)),shape=(len(x),len(x))).tocsr();self.hs.eliminate_zeros()
        diff=self.hs-self.hs.getH()
        if diff.nnz and np.max(abs(diff.data))>1e-10:raise ValueError('Projected H non-Hermitian')
        self.seconds=0.;self.evaluations=0

    def apply_local(self,state,u,qs):
        key=tuple(qs)
        if key not in self.indices:
            rest=[q for q in range(self.n) if q not in qs]
            active=sum(((np.arange(1<<len(qs))>>j)&1)<<q for j,q in enumerate(qs))
            inactive=sum(((np.arange(1<<len(rest))>>j)&1)<<q for j,q in enumerate(rest)) if rest else np.array([0])
            self.indices[key]=active[:,None]|inactive[None,:]
        idx=self.indices[key];out=np.empty_like(state);out[idx]=u@state[idx];return out

    def state(self,blocks,theta):
        state=self.reference.copy();offset=0
        for block in blocks:
            p=len(block['theta']);qs,u,_=operator_matrix(block,theta[offset:offset+p]);offset+=p
            state=self.apply_local(state,u,qs)
        return state

    def h_action(self,state):
        leak=float(np.vdot(state,state).real-np.vdot(state[self.sector_ids],state[self.sector_ids]).real)
        if leak>1e-9:raise ValueError('State outside validated occupation sector')
        out=np.zeros_like(state);out[self.sector_ids]=self.hs@state[self.sector_ids];return out

    def evaluate(self,blocks,theta,gradient=False,label='ENERGY'):
        started=time.monotonic();event=self.meter.reserve(label,len(theta) if gradient else 0)
        try:
            states=[self.reference.copy()];ops=[];offset=0
            for b in blocks:
                p=len(b['theta']);qs,u,du=operator_matrix(b,theta[offset:offset+p],gradient)
                ops.append((qs,u,du,offset,p));offset+=p
                states.append(self.apply_local(states[-1],u,qs))
            state=states[-1];dual=self.h_action(state);value=np.vdot(state,dual)
            if abs(np.vdot(state,state)-1)>1e-9 or abs(value.imag)>1e-9:raise ValueError('Invalid state/energy')
            grad=np.zeros(len(theta))
            if gradient:
                for i in range(len(ops)-1,-1,-1):
                    qs,u,du,start,p=ops[i]
                    for j in range(p):grad[start+j]=2*np.vdot(dual,self.apply_local(states[i],du[j],qs)).real
                    dual=self.apply_local(dual,u.conj().T,qs)
            if not np.isfinite(value) or not np.isfinite(grad).all():raise ValueError('Nonfinite outcome')
            event['status']='COMPLETED';return float(value.real),grad
        except BaseException:
            event['status']='FAILED_CHARGED';raise
        finally:self.seconds+=time.monotonic()-started;self.evaluations+=1
