"""Expose SciPy's existing joint memoization; reconcile requests vs evaluations."""
from scipy.optimize._optimize import MemoizeJac

class JointBFGSCounters:
    def __init__(self,objective):
        self.objective_calls=0;self.objective_requests=0;self.rejected_or_failed=0
        self.fun_requests=0;self.jac_requests=0
        def evaluate(x,*args):
            self.objective_requests+=1
            try:
                value=objective(x,*args)
            except BaseException:
                self.rejected_or_failed+=1
                raise
            self.objective_calls+=1
            return value
        self.memo=MemoizeJac(evaluate)

    def fun(self,x,*args):
        self.fun_requests+=1
        return self.memo(x,*args)

    def jac(self,x,*args):
        self.jac_requests+=1
        return self.memo.derivative(x,*args)

    def reconcile(self,result,external_objective_calls):
        if result.nfev!=self.fun_requests or result.njev!=self.jac_requests:
            raise ValueError('Optimizer request counter mismatch')
        if external_objective_calls!=self.objective_calls:
            raise ValueError('Optimizer physical evaluation counter mismatch')
        return self.report()

    def report(self):
        return dict(scipy_function_requests=self.fun_requests,scipy_gradient_requests=self.jac_requests,
            joint_objective_calls=self.objective_calls,
            joint_objective_requests=self.objective_requests,failed_or_rejected_joint_requests=self.rejected_or_failed,
            definition='Requests may use memoized values. Live ledger distinguishes actual charged calls from pre-cap refusals; completed joint calls reconcile with optimizer_calls.')
