"""Synthetic numerical tests, not new molecular search or dataset generation."""
import copy
import importlib.util
from pathlib import Path
import sys
import pytest

np=pytest.importorskip('numpy')
pytest.importorskip('scipy');pytest.importorskip('sympy');pytest.importorskip('qiskit')
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'policy/frozen/code'))
import core
import edit_policy
import native_policy
from prefix_canonical_resource_view import PrefixCanonicalResourceView
from fast_kernel import BlockKernel as FullKernel
from engine import Meter


def fixture():
    # A controlled-RY sandwich rotates |01> and |10>; every block conserves N.
    def b(i,t):
        return dict(occurrence_id=f'fixture-{i}',family='QE',generator_digest=core.digest(['synthetic',i]),theta=[t],
            gates=[dict(name='cx',wires=[0,1],offset=0.,weights=[0.]),
                   dict(name='ry',wires=[0],offset=0.,weights=[1.]),
                   dict(name='cx',wires=[1,0],offset=0.,weights=[0.]),
                   dict(name='ry',wires=[0],offset=0.,weights=[-1.]),
                   dict(name='cx',wires=[1,0],offset=0.,weights=[0.]),
                   dict(name='cx',wires=[0,1],offset=0.,weights=[0.])])
    h=[dict(pauli='ZI',coefficient=.7),dict(pauli='IZ',coefficient=-.3)]
    return dict(schema=core.VERSION,origin='fresh_uncompressed_ceo_growth',source_run_id='SYNTHETIC_NOT_MOLECULAR',
        upstream_commit=core.UPSTREAM,problem=dict(label='synthetic',geometry=[['H',[0,0,0]]],basis='synthetic',
        mapping='Jordan-Wigner',hamiltonian_digest=core.digest(h)),n=2,reference_occupied=[0],hamiltonian=h,
        sector=[dict(wires=[0,1],occupation=1)],frames=[dict(growth_step=0,blocks=[]),
        dict(growth_step=1,blocks=[b(0,.21)]),dict(growth_step=2,blocks=[b(0,.22),b(1,-.17)])])


def test_source_schema_rejects_answer_fields():
    s=fixture();core.validate_source(s);s['historical_recipe']=[1]
    with pytest.raises(ValueError):core.validate_source(s)


def test_candidate_generation_and_nested_screen_deterministic():
    s=fixture();cfg=dict(max_blocks=96,max_screen_topologies=4095)
    one,flag=edit_policy.source_candidates(s,cfg,{},core.resources)
    two,flag2=edit_policy.source_candidates(copy.deepcopy(s),cfg,{},core.resources)
    assert len(one)>0
    assert core.canonical(one)==core.canonical(two) and flag==flag2
    for limit in (1,2,128,256):
        assert core.canonical(edit_policy.select_anchor_screens(one,limit))==core.canonical(edit_policy.select_anchor_screens(two,limit))


def test_resource_counter_matches_qiskit():
    s=fixture();bs=s['frames'][-1]['blocks'];r=core.resources(bs,s['n']);q=core.to_qiskit(bs,s['n'])
    assert r['cnot']==q.count_ops().get('cx',0) and r['parameters']==2 and r['total_depth']==q.depth()


def test_sector_kernel_state_energy_gradient_and_certificate_parity(tmp_path):
    s=fixture();bs=s['frames'][-1]['blocks'];theta=core.theta_of(bs)
    spec=importlib.util.spec_from_file_location('exact_sector_fixture',ROOT/'policy/frozen/sector_kernel.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    meter1=Meter(100,tmp_path/'full.jsonl');meter2=Meter(100,tmp_path/'sector.jsonl')
    full=FullKernel(s,meter1);sector=m.BlockKernel(s,meter2)
    e,g=full.evaluate(bs,theta,True);meter1.close()
    f,h=sector.evaluate(bs,theta,True);meter2.close()
    assert abs(e-f)<1e-12 and np.max(abs(g-h))<1e-10
    assert np.max(abs(g))>1e-3
    delta=1e-6;plus=theta.copy();minus=theta.copy();plus[0]+=delta;minus[0]-=delta
    ep,_=sector.evaluate(bs,plus);meter2.close();em,_=sector.evaluate(bs,minus);meter2.close()
    assert abs((ep-em)/(2*delta)-h[0])<1e-7
    cert=sector.certify(bs,f);meter2.close()
    assert abs(cert['energy']-f)<1e-12 and cert['resources']==core.resources(bs,s['n'])


def test_energy_and_depth_guard_selection():
    originals=[dict(growth_step=0,energy=1.,resources=dict(cnot=0,cnot_depth=0)),
               dict(growth_step=1,energy=0.,resources=dict(cnot=10,cnot_depth=3))]
    p=dict(resources=dict(cnot=5,cnot_depth=4))
    assert native_policy.target_for(p,originals,[],1e-9) is None
    p['resources']['cnot_depth']=3
    assert native_policy.target_for(p,originals,[],1e-9)['growth_step']==1


def test_reservation_failure_and_reuse_are_counted_once(tmp_path):
    meter=Meter(5,tmp_path/'ledger.jsonl');e=meter.reserve('SYNTHETIC',2)
    e['status']='FAILED_CHARGED';meter.close();meter.reuse(1,'EXACT_COMPATIBLE')
    assert meter.used==5 and meter.failed==1 and meter.cache_hits==1
    with pytest.raises(core.BudgetExceeded):meter.reserve('BEYOND_CAP')


def test_parameter_binding_not_inferred_from_equal_values():
    s=fixture();bs=s['frames'][-1]['blocks'];bs[1]['theta']=bs[0]['theta'][:]
    assert core.resources(bs,2)['parameters']==2
