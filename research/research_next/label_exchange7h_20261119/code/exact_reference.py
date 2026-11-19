"""W8 exact scalar finite-reference arithmetic; no I/O or manuscript runs on import."""
from bisect import bisect_left, bisect_right
from fractions import Fraction
from itertools import permutations, product
from math import prod, comb

MODELS = ('exact', 'fk', 'fp', 'ft', 'kp', 'kt', 'pt')

def q(n, d=1):
    f = Fraction(n, d)
    return {'numerator': str(f.numerator), 'denominator': str(f.denominator), 'decimal': float(f)}

def fraction(x):
    if isinstance(x, dict):
        return Fraction(int(x['numerator']), int(x['denominator']))
    return Fraction(x)

class ScalarReference:
    """Uniform Cartesian product of group integer scores, including identity/ties."""
    def __init__(self, arrays, denominator):
        assert arrays and denominator > 0
        self.arrays = [list(map(int, a)) for a in arrays]
        assert all(self.arrays)
        ordered = sorted(self.arrays, key=len)
        self.last = sorted(ordered[-1])
        self.prefix = [sum(x) for x in product(*ordered[:-1])] if len(ordered) > 1 else [0]
        self.total = prod(map(len, self.arrays))
        self.denominator = int(denominator)
        self.observed = sum(a[0] for a in self.arrays)
        self.minimum = sum(min(a) for a in self.arrays)
        self.maximum = sum(max(a) for a in self.arrays)
        self.mean_integer = sum((Fraction(sum(a), len(a)) for a in self.arrays), Fraction(0))

    def tail(self, score):
        return sum(len(self.last) - bisect_left(self.last, score - x) for x in self.prefix)

    def tails(self, score):
        ge = gt = 0
        for p in self.prefix:
            lo = bisect_left(self.last, score - p)
            hi = bisect_right(self.last, score - p)
            ge += len(self.last) - lo
            gt += len(self.last) - hi
        return ge, gt, ge - gt

    def summary(self):
        ge, gt, ties = self.tails(self.observed)
        return {'assignments': self.total, 'observed': q(self.observed, self.denominator),
                'mean': q(self.mean_integer / self.denominator),
                'excess_over_mean': q((self.observed - self.mean_integer) / self.denominator),
                'min': q(self.minimum, self.denominator), 'max': q(self.maximum, self.denominator),
                'observed_integer': str(self.observed), 'score_denominator': str(self.denominator),
                'tail_ge': ge, 'tail_gt': gt, 'ties': ties, 'p_upper': q(ge, self.total),
                'reject_1_20': ge * 20 <= self.total,
                'reject_1_120': ge * 120 <= self.total}

    def rejection_size(self, alpha_denominator):
        """Smallest integer threshold with exact upper tail <= 1/alpha_denominator."""
        assert alpha_denominator >= 1
        lo, hi = self.minimum, self.maximum + 1
        while lo < hi:
            mid = (lo + hi) // 2
            if self.tail(mid) * alpha_denominator <= self.total:
                hi = mid
            else:
                lo = mid + 1
        count = self.tail(lo)
        assert count * alpha_denominator <= self.total
        assert lo == self.minimum or self.tail(lo - 1) * alpha_denominator > self.total
        return {'threshold_integer': str(lo), 'score_denominator': str(self.denominator),
                'threshold_may_lie_between_attainable_scores': True,
                'rejected_assignments': count, 'assignments': self.total,
                'size': q(count, self.total), 'nominal_alpha': q(1, alpha_denominator)}

def permutation_scores(matrix):
    """Rows/columns already in frozen order; identity is lexicographic index zero."""
    n = len(matrix)
    assert n >= 1 and all(len(r) == n for r in matrix)
    return [sum(int(matrix[i][p[i]]) for i in range(n)) for p in permutations(range(n))]

def all_summaries(group_arrays, denominator, leaves_by_group):
    total = {}; increments = {}; groups = []
    for model in MODELS:
        total[model] = ScalarReference([g[model] for g in group_arrays], denominator).summary()
    for model in MODELS[1:]:
        arrays = [[int(a)-int(b) for a,b in zip(g[model], g['exact'])] for g in group_arrays]
        increments[model] = ScalarReference(arrays, denominator).summary()
    # Group-scale denominator derived from the same common integer matrix scale.
    n = sum(len(ll) for ll in leaves_by_group)
    assert denominator % n == 0
    scale = denominator // n
    for arrays, leaves in zip(group_arrays, leaves_by_group):
        groups.append({'leaves': leaves, 'no_exchange_information': len(leaves) == 1,
                       'models': {m: ScalarReference([arrays[m]], len(leaves)*scale).summary() for m in MODELS},
                       'increments': {m: ScalarReference([[int(a)-int(b) for a,b in zip(arrays[m],arrays['exact'])]],len(leaves)*scale).summary() for m in MODELS[1:]}})
    return {'models':total, 'increments':increments, 'groups':groups,
            'max_increment_global_null':'NOT_RECOMPUTED; do not derive from independent marginal tails'}

def binomial_cdf(k, n, p):
    return sum(comb(n, j)*p**j*(1-p)**(n-j) for j in range(k+1))

def clopper_pearson(k, n):
    """Nominal 95% interval under ideal iid Bernoulli generator repetitions, not simultaneous."""
    assert n > 0 and 0 <= k <= n
    if k == 0:
        lower = 0.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo+hi)/2
            # P(X >= k) increases in p.
            if 1-binomial_cdf(k-1,n,mid) < .025: lo=mid
            else: hi=mid
        lower = (lo+hi)/2
    if k == n:
        upper = 1.0
    else:
        lo, hi = 0.0, 1.0
        for _ in range(80):
            mid = (lo+hi)/2
            if binomial_cdf(k,n,mid) > .025: lo=mid
            else: hi=mid
        upper = (lo+hi)/2
    return {'lower':lower,'upper':upper,'level':.95,'n':n,'rejections':k,
            'assumption':'Nominal under ideal iid generator repetitions; fixed PRNG seeds alone do not guarantee coverage; not simultaneous or a manuscript interval.'}
