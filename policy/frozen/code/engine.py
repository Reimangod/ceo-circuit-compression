from pathlib import Path
import json
import os
import numpy as np
from scipy.optimize import minimize
import core
from optimizer_accounting import JointBFGSCounters

class PhaseStop(Exception):pass
class SliceStop(Exception):pass
class WallStop(Exception):pass

def atomic(path,obj):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n');os.replace(tmp,path)

class Meter:
    def __init__(self,limit,path):
        self.limit=limit;self.path=path;self.used=0;self.energy=0;self.components=0;self.vectors=0
        self.failed=0;self.reserved=0;self.event=None;self.context={};self.resource={};self.phases={}
        self.sequence=0;self.cache_hits=0;self.cnot_proxy=0;self.depth_proxy=0
    def append(self,event):
        self.sequence+=1
        with self.path.open('a') as f:f.write(json.dumps(dict(event,sequence=self.sequence),sort_keys=True)+'\n')
    def reserve(self,label,p=0):
        amount=1+2*p
        if self.used+amount+self.reserved>self.limit:raise core.BudgetExceeded('IMMUTABLE_B200')
        if self.event is not None:raise ValueError('Unclosed primitive')
        self.used+=amount;self.energy+=1;self.components+=p;self.vectors+=bool(p)
        self.phases[label]=self.phases.get(label,0)+amount
        self.cnot_proxy+=amount*self.resource.get('cnot',0);self.depth_proxy+=amount*self.resource.get('total_depth',0)
        self.event=dict(id=self.energy,label=label,p=p,delta_W=amount,W=self.used,status='STARTED',
            cnot=self.resource.get('cnot',0),total_depth=self.resource.get('total_depth',0),**self.context)
        self.append(self.event);return self.event
    def close(self):
        if self.event is not None:
            self.failed+=self.event['status']!='COMPLETED'
            self.append(dict(id=self.event['id'],status=self.event['status'],delta_W=0,W=self.used));self.event=None
    def reuse(self,source_id,kind):
        self.cache_hits+=1;self.append(dict(kind=kind,source_evaluation_id=source_id,delta_W=0,W=self.used))
    def report(self):
        return dict(limit=self.limit,W=self.used,energy_evaluations=self.energy,gradient_components=self.components,
            gradient_vectors=self.vectors,failed_started=self.failed,cache_hits=self.cache_hits,by_phase=self.phases,
            W_weighted_CNOT_proxy=self.cnot_proxy,W_weighted_total_depth_proxy=self.depth_proxy,
            actual_hardware_shots=0,definition='N_energy+2*N_scalar_gradient_components; not actual shots')

def optimize(objective,initial,initial_energy,remaining_calls,target_energy,cfg):
    calls=0;accepted=0;best=[initial_energy,np.array(initial),None];reason=None;stopped=None;result=None
    def counted(theta):
        nonlocal calls
        if calls>=remaining_calls:raise SliceStop('TOPOLOGY_JOINT_CALL_CAP')
        energy,grad=objective(theta);calls+=1
        if energy<best[0]:best[:]=[energy,np.array(theta),np.array(grad)]
        elif np.array_equal(theta,best[1]):best[2]=np.array(grad)
        return energy,grad
    counter=JointBFGSCounters(counted)
    def callback(intermediate_result):
        nonlocal accepted,reason
        accepted+=1
        if intermediate_result.fun<=target_energy+cfg['comparison_tolerance']:
            reason='TARGET_ACCEPTED_ITERATE';raise StopIteration
    try:
        result=minimize(counter.fun,np.array(initial),jac=counter.jac,method='BFGS',callback=callback,
            options=dict(gtol=cfg['gtol'],maxiter=cfg['maxiter']))
        counter.reconcile(result,calls)
        if reason is None:reason='OPTIMIZER_FINISHED' if result.success else 'OPTIMIZER_RETURNED_NOT_CONVERGED'
    except (PhaseStop,core.BudgetExceeded,WallStop,SliceStop) as err:reason=type(err).__name__;stopped=err
    if not calls and stopped:raise stopped
    if not calls:raise ValueError('Optimizer returned no evaluation')
    return dict(energy=best[0],theta=best[1].tolist(),gradient_inf=float(np.max(abs(best[2]))) if best[2] is not None and len(initial) else None,
        calls=calls,accepted_iterations=accepted,reason=reason,stopped=stopped,accounting=counter.report(),
        optimizer_success=bool(result.success) if result is not None else False)
