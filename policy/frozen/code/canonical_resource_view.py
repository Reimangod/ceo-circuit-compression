"""Common source/candidate resource convention for a future single deletion queue.

This is a classical cache and resource adapter, not a new molecular experiment.
The topology's resource realization is independent of numerical source theta.
No results, Hamiltonian, old masks, optimizer state, or energy enter this API.
"""
from collections import OrderedDict
import copy
import core
import cached_reference_input_simplification as algebra


class CanonicalResourceView:
    def __init__(self,n,reference_occupied,resource_cache_limit=2048,certificate_cache_limit=4096):
        self.n=n;self.reference=tuple(reference_occupied)
        self.resource_cache_limit=resource_cache_limit;self.certificate_cache_limit=certificate_cache_limit
        self.resource_cache=OrderedDict();self.certificate_cache=OrderedDict()
        self.resource_hits=self.certificate_hits=self.certificate_misses=0

    def template_key(self,block):
        return core.digest(dict(gates=block['gates'],independent_coordinates=len(block['theta'])))

    def certificate(self,block,basis):
        support=sorted({q for g in block['gates'] if g['name']!='barrier' for q in g['wires']})
        key=(self.template_key(block),tuple(basis[q] for q in support))
        if key in self.certificate_cache:
            self.certificate_hits+=1;self.certificate_cache.move_to_end(key)
            item=self.certificate_cache[key]
        else:
            self.certificate_misses+=1
            try:item=(True,algebra.two_level_certificate(block,basis))
            except algebra.Unsupported as error:item=(False,str(error))
            self.certificate_cache[key]=item
            if len(self.certificate_cache)>self.certificate_cache_limit:self.certificate_cache.popitem(last=False)
        if not item[0]:raise algebra.Unsupported(item[1])
        return copy.deepcopy(item[1])

    def compile(self,blocks):
        return algebra.simplify_frame(blocks,self.n,self.reference,certificate_lookup=self.certificate)

    def resources(self,blocks,n):
        if n!=self.n:raise ValueError('Resource view bound to another physical wire register')
        key=tuple(self.template_key(block) for block in blocks)
        if key in self.resource_cache:
            self.resource_hits+=1;self.resource_cache.move_to_end(key)
            return dict(self.resource_cache[key])
        result=core.resources(self.compile(blocks)['blocks'],n)
        self.resource_cache[key]=result
        if len(self.resource_cache)>self.resource_cache_limit:self.resource_cache.popitem(last=False)
        return dict(result)

    def report(self):
        return dict(resource_hits=self.resource_hits,resource_entries=len(self.resource_cache),
            certificate_hits=self.certificate_hits,certificate_misses=self.certificate_misses,
            certificate_entries=len(self.certificate_cache),resource_cache_limit=self.resource_cache_limit,
            certificate_cache_limit=self.certificate_cache_limit,quantum_energy_queries=0,gradient_queries=0,
            key_scope='template and registered basis input, never numeric equality of coefficients')
