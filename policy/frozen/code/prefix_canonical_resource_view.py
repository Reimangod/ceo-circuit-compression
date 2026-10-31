"""Exact resource-only prefix dynamic programming for the same fixed compiler.

Actual delivered gates/proofs still come from the unchanged algebraic compiler.
This adapter avoids deep-copying every complete candidate just to obtain counts.
"""
from collections import OrderedDict
import itertools
from canonical_resource_view import CanonicalResourceView
import cached_reference_input_simplification as algebra


class PrefixCanonicalResourceView(CanonicalResourceView):
    def __init__(self,*args,prefix_cache_limit=4096,**kwargs):
        super().__init__(*args,**kwargs)
        self.prefix_cache=OrderedDict();self.prefix_cache_limit=prefix_cache_limit
        self.prefix_hits=0;self.transitions=0

    def initial_state(self):
        return ({q:int(q in self.reference) for q in range(self.n)},[0]*self.n,[0]*self.n,
                [0]*self.n,[0]*self.n,0,0)

    def transition(self,block,state):
        known,original_cnot,original_depth,compiled_cnot,compiled_depth,cx,p=state
        known=dict(known);support=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
        original_cnot=algebra.end_times(block['gates'],original_cnot,True)
        original_depth=algebra.end_times(block['gates'],original_depth,False)
        certificate=None;choices=[]
        native_cx=sum(g['name']=='cx' for g in block['gates'])
        if all(q in known for q in support):
            try:
                certificate=self.certificate(block,known)
                a=certificate['initial_local_bits'];b=certificate['other_local_bits']
                flip=[q for j,q in enumerate(support) if ((a^b)>>j)&1]
                for pivot in flip:
                    for targets in itertools.permutations(q for q in flip if q!=pivot):
                        child=algebra.realize(block,certificate,pivot,targets)
                        child_cx=sum(g['name']=='cx' for g in child['gates'])
                        if child_cx>=native_cx:continue
                        nc=algebra.end_times(child['gates'],compiled_cnot,True)
                        nd=algebra.end_times(child['gates'],compiled_depth,False)
                        if all(x<=y for x,y in zip(nc,original_cnot)) and all(x<=y for x,y in zip(nd,original_depth)):
                            choices.append(((max(nc),max(nd),sum(nc),sum(nd),pivot,targets),nc,nd,child_cx))
            except algebra.Unsupported:pass
        if choices:
            _,compiled_cnot,compiled_depth,added_cx=min(choices,key=lambda choice:choice[0])
        else:
            compiled_cnot=algebra.end_times(block['gates'],compiled_cnot,True)
            compiled_depth=algebra.end_times(block['gates'],compiled_depth,False)
            added_cx=native_cx
        if certificate is not None:
            a=certificate['initial_local_bits'];b=certificate['other_local_bits']
            for j,q in enumerate(support):
                if ((a^b)>>j)&1:known.pop(q,None)
                else:known[q]=(a>>j)&1
        else:
            for q in support:known.pop(q,None)
        assert all(x<=y for x,y in zip(compiled_cnot,original_cnot))
        assert all(x<=y for x,y in zip(compiled_depth,original_depth))
        self.transitions+=1
        return known,original_cnot,original_depth,compiled_cnot,compiled_depth,cx+added_cx,p+len(block['theta'])

    def resources(self,blocks,n):
        if n!=self.n:raise ValueError('Resource view bound to another physical wire register')
        key=tuple(self.template_key(block) for block in blocks)
        state=self.initial_state();start=0
        for length in range(len(key),0,-1):
            prefix=key[:length]
            if prefix in self.prefix_cache:
                self.prefix_hits+=1;self.prefix_cache.move_to_end(prefix);state=self.prefix_cache[prefix];start=length;break
        for index in range(start,len(blocks)):
            state=self.transition(blocks[index],state);prefix=key[:index+1]
            self.prefix_cache[prefix]=state
            if len(self.prefix_cache)>self.prefix_cache_limit:self.prefix_cache.popitem(last=False)
        return dict(cnot=state[5],cnot_depth=max(state[3]),parameters=state[6],total_depth=max(state[4]))

    def report(self):
        return dict(super().report(),prefix_hits=self.prefix_hits,prefix_entries=len(self.prefix_cache),
                    prefix_cache_limit=self.prefix_cache_limit,computed_transitions=self.transitions,
                    counter_scope='exact same native barriers, known-input proof conditions, and per-wire rank as the full compiler')
