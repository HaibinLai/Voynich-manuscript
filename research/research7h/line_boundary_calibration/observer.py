"""Closed-four-symbol adaptation of boundary.py Conditional, no corpus imports."""
from collections import Counter, defaultdict
import math
import numpy as np

ALPHAS = (1, 5, 20, 100, 500)
WEIGHTS = (0, .25, .5, .75, 1)
SYMBOLS = (0, 1, 2, 3)


def contexts(row, feature=False, value=None):
    h, s = row['hand'], row['section']
    assert row['length'] == 0
    keys = [(), ('hs', h, s), ('tl', h, s, 0), ('pl', h, s, 0, min(row['previous_length'], 10)),
            ('position', h, s, 0, min(row['previous_length'], 10), row['position_bin'], row['paragraph_line'])]
    if feature:
        v = row['x'] if value is None else value
        keys = [(), ('context', v)] + [key + (v,) for key in keys[1:]]
    return tuple(keys)


class Conditional:
    def __init__(self, rows, alpha, feature=False):
        self.alpha = alpha; self.feature = feature
        self.counts = defaultdict(Counter); self.totals = Counter()
        self.cache = {}
        for row in rows:
            assert row['x'] in SYMBOLS and row['y'] in SYMBOLS
            for key in contexts(row, feature):
                self.counts[key][row['y']] += 1; self.totals[key] += 1

    def distribution(self, keys):
        if keys in self.cache:
            return self.cache[keys]
        out = np.full(4, .25)
        for key in keys:
            if key not in self.counts:
                continue
            arr = np.array([self.counts[key].get(y, 0) for y in SYMBOLS], dtype=float)
            out = (arr + self.alpha * out) / (self.totals[key] + self.alpha)
        out.flags.writeable = False
        self.cache[keys] = out
        return out

    def probs(self, rows):
        return np.array([self.distribution(contexts(r, self.feature))[r['y']] for r in rows])


def select(train, fold_map):
    """All target data stay outside selection; pooled held-fold NLL is fixed."""
    base_oof = {a: np.empty(len(train)) for a in ALPHAS}
    child_oof = {a: np.empty(len(train)) for a in ALPHAS}
    fold = np.array([fold_map[r['leaf']] for r in train])
    for k in range(3):
        fit = [r for r, f in zip(train, fold) if f != k]
        ids = np.flatnonzero(fold == k); held = [train[i] for i in ids]
        assert fit and held and {r['leaf'] for r in fit}.isdisjoint(r['leaf'] for r in held)
        for a in ALPHAS:
            base_oof[a][ids] = Conditional(fit, a).probs(held)
            child_oof[a][ids] = Conditional(fit, a, True).probs(held)
    base_grid = [(float(-np.log2(base_oof[a]).mean()), a) for a in ALPHAS]
    _, ba = min(base_grid, key=lambda pair: (pair[0], -pair[1]))
    grid = []
    for a in ALPHAS:
        for w in WEIGHTS:
            loss = float(-np.log2((1-w)*base_oof[ba] + w*child_oof[a]).mean())
            grid.append(dict(loss=loss, alpha=a, weight=w))
    best = min(grid, key=lambda item: (item['loss'], item['weight'], -item['alpha']))
    cfg = dict(base_alpha=ba, alpha=best['alpha'], weight=best['weight'],
               base_grid=base_grid, feature_grid=grid, folds=3, candidates_base=5, candidates_feature=25)
    return cfg, Conditional(train, ba), Conditional(train, best['alpha'], True)


def truth(rho, permutation):
    p = np.array([.55, .25, .15, .05])
    channel = (1-rho)*np.tile(p, (4, 1)) + rho*np.eye(4)
    moved = np.empty_like(channel)
    moved[:, permutation] = channel
    joint = p[:, None]*moved
    marginal = joint.sum(axis=0)
    mi = math.fsum(float(joint[x,y])*math.log2(float(moved[x,y]/marginal[y]))
                   for x in SYMBOLS for y in SYMBOLS if joint[x,y] > 0)
    if rho == 0:
        assert abs(mi) < 1e-14
        mi = 0.0  # Analytic independence; remove only roundoff around exact zero.
    return joint, marginal, mi


def evaluate(rows, base, child, weight, joint):
    marginal = joint.sum(axis=0)
    eb = []; em = []; xb = []; xm = []
    for row in rows:
        b = base.distribution(contexts(row))
        q = np.array([(1-weight)*b + weight*child.distribution(contexts(row, True, x)) for x in SYMBOLS])
        assert abs(float(b.sum())-1) < 1e-12 and np.max(np.abs(q.sum(axis=1)-1)) < 1e-12
        eb.append(-math.log2(float(b[row['y']])))
        em.append(-math.log2(float(q[row['x'],row['y']])))
        xb.append(-math.fsum(float(marginal[y])*math.log2(float(b[y])) for y in SYMBOLS))
        xm.append(-math.fsum(float(joint[x,y])*math.log2(float(q[x,y])) for x in SYMBOLS for y in SYMBOLS))
    return dict(base_bits=np.asarray(eb), model_bits=np.asarray(em),
                expected_base_bits=np.asarray(xb), expected_model_bits=np.asarray(xm))
