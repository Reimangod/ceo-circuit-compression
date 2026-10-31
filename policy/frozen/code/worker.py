"""A bounded single-queue subset search; no historical result access."""
from pathlib import Path
import argparse
import hashlib
import json
import resource
import socket
import time
import traceback
import numpy as np
from scipy.optimize import minimize
import core
from fast_kernel import BlockKernel
from engine import Meter,atomic
from fronts import rows
from optimizer_accounting import JointBFGSCounters
from prefix_canonical_resource_view import PrefixCanonicalResourceView
from edit_policy import source_candidates,target_for,blocks_for,resource_first_key,coverage_order,continuation_key,easiest_target_for,select_anchor_screens

class StopWork(Exception):pass

class EventMeter(Meter):
    def reuse(self,source_id,kind):
        self.cache_hits+=1
        self.append(dict(status='REUSED',kind=kind,source_evaluation_id=source_id,delta_W=0,W=self.used,**self.context))
    def close(self):
        if self.event is not None:
            self.failed+=self.event['status']!='COMPLETED'
            self.append(dict(self.event,delta_W=0,W=self.used,terminal=True))
            self.event=None

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--task',required=True);parser.add_argument('--output',required=True)
    args=parser.parse_args();task=json.loads(Path(args.task).read_text());out=Path(args.output);cfg=task['settings']
    execution_id=task.get('execution_id','synthetic-fixture')
    denied=[]
    def network():
        with socket.socket() as s:s.settimeout(.1);s.connect(('127.0.0.1',9))
    for fn in (lambda:Path(task['forbidden_read_canary']).read_bytes(),network):
        try:fn();denied.append(False)
        except PermissionError:denied.append(True)
    if denied!=[True,True]:raise ValueError('Source-only sandbox missing')
    atomic(out/'isolation.json',dict(historical_read_denied=True,network_denied=True))
    raw=Path(task['source']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=task['source_sha256']:raise ValueError('Source drift')
    source=json.loads(raw);core.validate_source(source)
    if core.digest(task['native_registry_data'])!=task['native_registry_sha256']:raise ValueError('Native registry drift')
    registry=task['native_registry_data']['templates']
    start=time.monotonic();cpu=time.process_time();tol=cfg['comparison_tolerance']
    meter=EventMeter(cfg['model_budget'],out/'work.jsonl');kernel=BlockKernel(source,meter)
    view=PrefixCanonicalResourceView(source['n'],source['reference_occupied'])
    originals=[];trials=[];archive=[];segments=[];cache={};topology_calls={};status='COMPLETED';termination='QUEUE_EXHAUSTED';allocation_phase='SOURCE_VALIDATION';coverage_ids=None;coverage_cursor=0;continuation_id=None;coverage_round=0

    def check(amount=0):
        if time.monotonic()-start>=cfg['wall_seconds']:raise StopWork('TIME_CENSORED')
        if meter.used+meter.reserved+amount>meter.limit:raise StopWork('MODEL_CAP_TERMINAL')

    def context(blocks,probe=None):
        meter.resource=view.resources(blocks,source['n'])
        meter.context=dict(execution_id=execution_id,task_id=task['task_id'],allocation_phase='SOURCE_VALIDATION' if probe is None else allocation_phase,phase='SOURCE' if probe is None else 'SEARCH',
            source_anchor_step=probe['anchor_step'] if probe else None,
            kept_positions=probe['kept_positions'] if probe else None,
            replacements=probe.get('replacements',[]) if probe else None,
            candidate_id=probe['probe_id'] if probe else None)

    def evaluate(blocks,theta,gradient=False,label='ENERGY',probe=None):
        check();context(blocks,probe)
        meter.context.update(theta_digest=core.digest(list(map(float,theta))),request_label=label,gradient_requested=gradient)
        key=(core.digest([frame for frame in blocks]),tuple(float(x).hex() for x in theta),gradient)
        if key in cache:
            e,g,eid=cache[key];meter.reuse(eid,'EXACT_CURRENT_TASK_EVALUATION_REUSE');return e,g.copy(),eid
        amount=1+2*len(theta) if gradient else 1;check(amount)
        try:
            e,g=kernel.evaluate(blocks,theta,gradient,label)
            eid=f"{execution_id}/{task['task_id']}:E{meter.energy}"
            meter.event.update(energy=e,theta_digest=core.digest(list(map(float,theta))),
                gradient_inf=float(max(abs(g))) if gradient and len(g) else None)
            cache[key]=(e,g.copy(),eid)
            return e,g,eid
        finally:meter.close()

    def certify(blocks,theta,e,probe=None):
        check(1);context(blocks,probe)
        try:
            bound=core.bind(blocks,theta);compiled=view.compile(bound)
            c=kernel.certify(compiled['blocks'],e)
            phase=complex(__import__('sympy').N(__import__('sympy').sympify(compiled['source_to_compiled_global_phase'])))
            alignment=float(np.linalg.norm(kernel.state(bound,theta)-phase*kernel.state(compiled['blocks'],theta)))
            if alignment>1e-9:raise ValueError('Canonical source-family state disagreement')
            if c['resources']!=view.resources(bound,source['n']):raise ValueError('Prefix resource cache disagrees with actual compiled gates')
            c.update(raw_native_resources=core.resources(bound,source['n']),canonical_blocks=compiled['blocks'],
                source_native_blocks=bound,algebraic_proofs=compiled['records'],
                source_to_compiled_global_phase=compiled['source_to_compiled_global_phase'],
                canonical_state_alignment_error=alignment,
                equivalence_scope='registered-reference state family, not arbitrary-input unitary')
            c.update(evaluation_id=f"{execution_id}/{task['task_id']}:E{meter.energy}",state_vector_check='PASSED',
                state_vector_tolerance=1e-9,energy_check='PASSED',resource_recount='PASSED',sector_tolerance=1e-10)
            meter.event.update(energy=c['energy'],theta_digest=core.digest(list(map(float,theta))))
            return c
        finally:meter.close()

    def save():
        states=[]
        for t in trials:
            states.append({k:v for k,v in t.items() if k not in ('_cache','_resume')})
        result=dict(schema='FRONTIER-COVER-CEO-8',execution_id=execution_id,task_id=task['task_id'],case_id=task['case_id'],group=task['group'],
            root_step=task['root_step'],source_sha256=task['source_sha256'],settings=cfg,status=status,termination=termination,
            originals=originals,trials=states,archive=archive,segments=segments,meter=dict(meter.report(),pool_gradient_components=0),
            comparisons={str(w):rows(originals,archive,min(w,meter.used),tol) for w in sorted(set(cfg['snapshots']+[meter.used]))},
            physical_shots=0,machine_learning=False,historical_compression_inputs=False,native_registry_sha256=task['native_registry_sha256'],
            cpu_seconds=time.process_time()-cpu,wall_seconds=time.monotonic()-start,
            max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            optimized_topologies=len(topology_calls),previous_actual_W_cap=task['previous_actual_W_cap'],
            optimizer_hessians='CURRENT_TASK_ACCEPTED_POINT_ONLY',measurement_cost_scope='W_MODEL_NOT_GROUPED_SHOTS',
            resource_convention='SOURCE_AND_CANDIDATES_SAME_REFERENCE_COMPILER',canonical_resource_cache=view.report(),
            source_only_uniform_budget_rule=task.get('uniform_budget_rule'))
        atomic(out/'progress.json',result);return result

    def admit(probe,state):
        if not any(state['energy']<=o['energy']+tol and probe['resources']['cnot']<o['resources']['cnot']
                   and probe['resources']['cnot_depth']<=o['resources']['cnot_depth'] for o in originals[1:]):return
        sid=core.digest(dict(probe=probe['probe_id'],theta=state['theta']))
        if any(a['candidate_id']==sid for a in archive):return
        blocks=blocks_for(source,probe,registry)
        c=certify(blocks,state['theta'],state['energy'],probe)
        probe['last_certificate']=c
        if not any(c['energy']<=o['energy']+tol and c['resources']['cnot']<o['resources']['cnot']
                   and c['resources']['cnot_depth']<=o['resources']['cnot_depth'] for o in originals[1:]):
            probe['certification_status']='CERTIFIED_BUT_NO_REGISTERED_COMPARATOR_MATCH';return
        archive.append(dict(candidate_id=sid,kind='COMPRESSED',probe_id=probe['probe_id'],
            kept_positions=probe['kept_positions'],removed_positions=probe['removed_positions'],source_anchor_step=probe['anchor_step'],
            theta=state['theta'],initial_coefficients=probe['initial_theta'],replacements=probe.get('replacements',[]),topology_id=probe['topology_id'],energy=c['energy'],resources=c['resources'],
            certificate=c,available_W=meter.used,gradient_inf=state.get('gradient_inf'),phase='SINGLE_QUEUE',
            optimizer_initial_state='CURRENT_TASK_ONLY' if state['slices'] else 'NOT_USED',theta_origin='ORIGINAL_CHECKPOINT_WITH_REGISTERED_CONSTRAINT'))
        probe['accepted']=True

    try:
        for frame in source['frames']:
            bs=frame['blocks'];theta=core.theta_of(bs);e,_,_=evaluate(bs,theta,label='SOURCE_REVALIDATION')
            c=certify(bs,theta,e)
            originals.append(dict(growth_step=frame['growth_step'],energy=c['energy'],resources=c['resources'],
                                  raw_native_resources=c['raw_native_resources'],raw_native_energy=e,
                                  certificate=c,kind='NO_ACTION',available_W=meter.used))
        # Reserve most W for parameter optimization instead of exhaustive screens.
        probes,full_small=source_candidates(source,cfg,registry,view.resources)
        limit=min(cfg['screen_limit'],len(probes),max(0,(meter.limit-meter.used-1)//2))
        # CNOT-level coverage is retained if the full source catalog cannot fit.
        if len(probes)>limit:
            probes=select_anchor_screens(probes,limit)
        probes=probes[:limit]
        allocation_phase='INITIAL_SCREEN'
        for probe in probes:
            probe['probe_id']=core.digest(dict(task=task['task_id'],anchor=probe['anchor_step'],topology=probe['topology_id'],initial=probe['initial_theta']))
            bs=blocks_for(source,probe,registry)
            e,_,eid=evaluate(bs,probe['initial_theta'],label='SCREEN',probe=probe)
            state=dict(theta=probe['initial_theta'],energy=e,current_theta=probe['initial_theta'],current_energy=e,
                       hessian=None,hessian_point_digest=None,calls=0,slices=0,iterations=0,last_drop=0.,gradient_inf=None,done=not len(probe['initial_theta']))
            trial=dict(probe,screen_energy=e,screen_evaluation_id=eid,state=state,accepted=False)
            trials.append(trial);admit(trial,state)
        save()
        while True:
            check();pending=[]
            for t in trials:
                s=t['state'];key=t['topology_id'];target=target_for(t,originals,archive,tol)
                if s['done'] or target is None or topology_calls.get(key,0)>=cfg['max_joint_calls_per_topology']:continue
                if key not in topology_calls and len(topology_calls)>=cfg['max_optimized_topologies']:continue
                pending.append((resource_first_key(t),t,target))
            if not pending:break
            remaining=meter.limit-meter.used
            pending=[x for x in pending if 2+2*x[1]['resources']['parameters']<=remaining]
            if not pending:raise StopWork('MODEL_CAP_TERMINAL')
            byid={t['probe_id']:(t,target) for _,t,target in pending}
            if coverage_ids is None:coverage_ids=coverage_order(trials,originals,tol)
            chosen=None
            if continuation_id in byid:
                chosen=continuation_id;continuation_id=None;allocation_phase='COVERAGE_PROGRESS'
            else:
                while coverage_cursor<len(coverage_ids):
                    cid=coverage_ids[coverage_cursor];coverage_cursor+=1
                    if cid in byid:chosen=cid;break
                allocation_phase='COVERAGE_FIRST_PASS'
            if chosen is not None:
                trial,target=byid[chosen]
                selection_rank=(1,coverage_cursor,trial['resources']['cnot'],trial['probe_id'])
            else:
                # Only after the finite first pass, revisit measured progress.
                _,trial,target=min(pending,key=lambda x:continuation_key(x[1],x[2],tol))
                selection_rank=(2,*continuation_key(trial,target,tol));allocation_phase='COVERAGE_REFINEMENT'
            rank_target_step=target['growth_step'] if allocation_phase=='COVERAGE_REFINEMENT' else None
            # Seek the easiest still-unimproved comparator first; a later
            # segment can target a more accurate point on the same frontier.
            eligible=[]
            for o in originals[1:]:
                rr=trial['resources']
                if rr['cnot']>=o['resources']['cnot'] or rr['cnot_depth']>o['resources']['cnot_depth']:continue
                incumbents=[a['resources']['cnot'] for a in archive if a['energy']<=o['energy']+tol
                            and a['resources']['cnot_depth']<=o['resources']['cnot_depth']]
                if incumbents and rr['cnot']>=min(incumbents):continue
                eligible.append(o)
            target=max(eligible,key=lambda o:(o['energy'],-o['growth_step']))
            coverage_round+=1
            state=trial['state'];key=trial['topology_id']
            bs=blocks_for(source,trial,registry)
            p=len(state['theta']);check(2+2*p)
            repair_allowance=None
            meter.reserved=1
            before=state['energy'];before_W=meter.used;calls0=topology_calls.get(key,0);reason=None;result=None;pending_stop=None;accepted_steps=[];point_values={};initial_gradient=None
            attempt_initial=list(state['current_theta']);hreason='RESET';H=state['hessian']
            if H is not None:
                H=np.array(H,dtype=float);H=(H+H.T)/2
                if state['hessian_point_digest']!=core.digest(attempt_initial):raise ValueError('BFGS statepoint mismatch')
                try:np.linalg.cholesky(H);hreason='CURRENT_TASK_ACCEPTED_POINT'
                except np.linalg.LinAlgError:H=None;hreason='RESET_NON_SPD'
            def objective(theta):
                nonlocal reason,initial_gradient
                if topology_calls.get(key,0)>=cfg['max_joint_calls_per_topology']:raise StopWork('TOPOLOGY_CALL_CAP')
                # Reuse only exact current-task values; real calls count across all source anchors.
                if topology_calls.get(key,0)-calls0>=8:raise StopWork('COVERAGE_JOINT_SLICE')
                n0=meter.energy;e,g,eid=evaluate(bs,theta,True,'OPTIMIZER',trial)
                new=meter.energy-n0;topology_calls[key]=topology_calls.get(key,0)+new
                state['calls']+=new
                point_values[tuple(float(v).hex() for v in theta)]=g.tolist()
                if np.array_equal(theta,np.asarray(attempt_initial)):initial_gradient=g.tolist()
                if e<state['energy']:
                    state.update(energy=e,theta=np.asarray(theta).tolist(),gradient_inf=float(max(abs(g))),best_evaluation_id=eid)
                return e,g
            counter=JointBFGSCounters(objective)
            def callback(intermediate_result):
                nonlocal reason
                gg=point_values[tuple(float(v).hex() for v in intermediate_result.x)]
                accepted_steps.append(dict(theta=intermediate_result.x.tolist(),energy=float(intermediate_result.fun),gradient=gg))
                if intermediate_result.fun<=target['energy']+tol:
                    reason='TARGET_ACCEPTED_ITERATE';raise StopIteration
            try:
                options=dict(gtol=cfg['gtol'],maxiter=cfg['maxiter']-state['iterations'])
                if H is not None:options['hess_inv0']=H
                result=minimize(counter.fun,np.asarray(attempt_initial),jac=counter.jac,method='BFGS',callback=callback,options=options)
                counter.reconcile(result,counter.objective_calls)
                if int(result.nit)!=len(accepted_steps):raise ValueError('Accepted-iteration counter mismatch')
                reason=reason or ('STATIONARY' if result.success else ('ITERATION_SLICE' if result.status==1 else 'OPTIMIZER_STOPPED'))
                state['current_theta']=result.x.tolist();state['current_energy']=float(result.fun)
                hh=np.asarray(result.hess_inv);hh=(hh+hh.T)/2
                state['hessian']=hh.tolist();state['hessian_point_digest']=core.digest(state['current_theta'])
                if reason in ('STATIONARY','OPTIMIZER_STOPPED') or state['iterations']+len(accepted_steps)>=cfg['maxiter']:state['done']=True
            except StopWork as err:
                reason=str(err);state['done']=reason!='COVERAGE_JOINT_SLICE'
                if reason=='COVERAGE_JOINT_SLICE':
                    state.update(current_theta=list(state['theta']),current_energy=state['energy'],hessian=None,hessian_point_digest=None,
                        resume_reset_reason='PHASE_BOUNDARY_RETURN_TO_BEST_OBSERVED_POINT')
                elif reason!='TOPOLOGY_CALL_CAP':pending_stop=err
            finally:
                meter.reserved=0;state['iterations']+=len(accepted_steps);state['slices']+=1;state['last_drop']=max(0.,before-state['energy'])
                trial['optimizer_accounting']=counter.report()
                trial['initialization']=hreason;trial['stop_reason']=reason
                segments.append(dict(probe_id=trial['probe_id'],anchor_step=trial['anchor_step'],
                    allocation_phase=allocation_phase,requested_iteration_limit=options['maxiter'],source_repair_allowance_W=repair_allowance,
                    accepted_iterations=len(accepted_steps),accepted_steps=accepted_steps,initial_gradient=initial_gradient,
                    attempt_initial_theta=attempt_initial,hessian_initialization=hreason,selection_rank=list(selection_rank),
                    selection_rank_target_comparator_step=rank_target_step,post_update_rank=None,
                    target_comparator_step=target['growth_step'],target_energy=target['energy'],
                    actual_joint_calls=topology_calls.get(key,0)-calls0,request_accounting=counter.report(),
                    W_start=before_W,W_end=meter.used,reason=reason,gradient_inf=state['gradient_inf']))
            admit(trial,state)
            trial['accepted']=any(a['probe_id']==trial['probe_id'] for a in archive)
            next_target=easiest_target_for(trial,originals,archive,tol)
            post_target=target_for(trial,originals,archive,tol) if not state['done'] and topology_calls.get(key,0)<cfg['max_joint_calls_per_topology'] else None
            segments[-1].update(best_energy_after_segment=state['energy'],best_theta_after_segment=list(state['theta']),
                current_theta_after_segment=list(state['current_theta']),cumulative_joint_calls_after_segment=state['calls'],
                post_update_rank=list(continuation_key(trial,post_target,tol)) if post_target is not None else None,
                post_update_rank_target_comparator_step=post_target['growth_step'] if post_target is not None else None,
                post_update_rank_basis='ADAPTIVE_CONTINUATION_FOR_HARDEST_REMAINING_COMPARATOR_OR_NOT_PENDING')
            gap=max(0.,state['energy']-next_target['energy']-tol) if next_target is not None else 0.
            trial['next_frontier_comparator']=next_target['growth_step'] if next_target is not None else None
            drop=max(0.,trial['screen_energy']-state['energy'])
            if allocation_phase=='COVERAGE_FIRST_PASS' and not state['done'] and gap>0 and gap<=drop:
                continuation_id=trial['probe_id']
            if pending_stop is not None:raise pending_stop
            if len(segments)%8==0:save()
    except StopWork as err:status=str(err);termination=str(err)
    except BaseException as err:
        status='ENGINEERING_FAILURE';termination=type(err).__name__+': '+str(err)
        atomic(out/'engineering-traceback.json',dict(error=termination,traceback=traceback.format_exc()))
    result=save();atomic(out/'result.json',result)
    print(json.dumps(dict(task=task['task_id'],status=status,W=meter.used,screens=len(trials),accepted=len(archive))),flush=True)
    return int(status=='ENGINEERING_FAILURE')

if __name__=='__main__':raise SystemExit(main())
