"""Exact named definitions extracted from the recorded author source; no corpus imports."""
from collections import Counter, defaultdict
from functools import lru_cache
import numpy as np
UNK="<UNK>"


def contexts(row, feature=None, value=None):
    h, s = row['hand'], row['section']
    tl, pl = min(row['length'], 10), min(row['previous_length'], 10)
    keys = [(), ('hs', h, s), ('tl', h, s, tl), ('pl', h, s, tl, pl),
            ('position', h, s, tl, pl, row['position_bin'], row['paragraph_line'])]
    if feature:
        v = row[feature] if value is None else value
        keys = [()] + [('context', v)] + [key+(v,) for key in keys[1:]]
    return tuple(keys)

class Conditional:
    def __init__(self, rows, alphabet, alpha, feature=None):
        self.vocab = tuple(sorted(set(alphabet)|{UNK}))
        self.lookup = {c:i for i,c in enumerate(self.vocab)}
        self.alpha = alpha
        self.feature = feature
        self.counts = defaultdict(Counter)
        self.totals = Counter()
        for row in rows:
            for key in contexts(row, feature):
                self.counts[key][row['target']] += 1
                self.totals[key] += 1

    @lru_cache(maxsize=200000)
    def distribution(self, keys):
        out = np.full(len(self.vocab), 1/len(self.vocab))
        for key in keys:
            count = self.counts.get(key, {})
            if not count:
                continue
            arr = np.array([count.get(c, 0) for c in self.vocab], dtype=float)
            out = (arr+self.alpha*out)/(self.totals[key]+self.alpha)
        out.flags.writeable = False
        return out

    def prob(self, row, value=None):
        return self.distribution(contexts(row, self.feature, value))[self.lookup[row['target']]]

    def scores(self, rows):
        return np.log2(np.array([self.prob(row) for row in rows]))
