"""Synthetic-only direct-enumeration checks; never imports K/F observations."""
from fractions import Fraction
from itertools import product
from random import Random
from bounds import optimize, contribution_at


def direct_value(assignment, weights, denominator):
    total = Fraction(0)
    for (a, b), weight in weights.items():
        similarity = Fraction(1) - sum(Fraction(abs(x-y), 8) for x, y in zip(assignment[a], assignment[b]))
        total += Fraction(weight, denominator) * similarity
    return total


def check(domains, left, right, weights, denominator):
    ids = list(domains)
    direct = [direct_value(dict(zip(ids, values)), weights, denominator)
              for values in product(*(domains[x] for x in ids))]
    fast = optimize(domains, left, right, weights, denominator)
    assert fast['bounds']['lower']['value'] == min(direct)
    assert fast['bounds']['upper']['value'] == max(direct)
    for endpoint in fast['bounds'].values():
        assert direct_value(endpoint['assignment'], weights, denominator) == endpoint['value']
        assert sum(contribution_at(endpoint['assignment'], weights, denominator)) == endpoint['value']


if __name__ == '__main__':
    left, right = ['a0', 'a1', 'a2'], ['b1', 'b2']
    weights = {('a0', 'b1'): -1, ('a0', 'b2'): -1,
               ('a1', 'b1'): 2, ('a1', 'b2'): -1,
               ('a2', 'b1'): -1, ('a2', 'b2'): 2}
    rng = Random(614119)
    alphabet = list(product(range(3), repeat=4))
    for _ in range(24):
        domains = {name: rng.sample(alphabet, rng.randint(1, 3)) for name in left + right}
        check(domains, left, right, weights, 4)
    common = (2, 2, 2, 2)
    domains = {name: [common, alphabet[i]] for i, name in enumerate(left + right)}
    check(domains, left, right, weights, 4)
    result = optimize(domains, left, right, weights, 4)
    assert result['bounds']['lower']['value'] <= 0 <= result['bounds']['upper']['value']
    tied = {name: [(0, 0, 0, 0)] for name in left + right}
    check(tied, left, right, weights, 4)
    assert optimize(tied, left, right, weights, 4)['bounds']['upper']['value'] == 0
    print('26 synthetic joint-domain cases match full enumeration; no manuscript data scored.')
