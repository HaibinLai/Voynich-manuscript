"""Exact finite-domain bipartite bounds; no image reading or automatic scoring.

Each entry domain contains complete four-coordinate signatures. Optimizing one
coordinate independently would discard within-entry candidate constraints.
Callers must supply a frozen, defined naming branch and its integer weights.
The result is exact for the supplied algebraic domains, not for hidden geometry.
"""
from fractions import Fraction
from itertools import product


def score8(left, right):
    return 8 - sum(abs(a - b) for a, b in zip(left, right))


def checked_domains(domains):
    result = {}
    for name, values in domains.items():
        unique = sorted(set(tuple(v) for v in values))
        if not unique or any(len(v) != 4 or any(type(x) is not int or x not in (0, 1, 2) for x in v) for v in unique):
            raise ValueError('Nonempty complete ternary signatures required: ' + name)
        result[name] = unique
    return result


def evaluate8(assignment, weights):
    return sum(w * score8(assignment[a], assignment[b]) for (a, b), w in weights.items())


def optimize(domains, left, right, weights, weight_denominator):
    """Enumerate right signatures, then conditionally eliminate left entries.

    The objective is sum(w_ij * S(i,j)) / weight_denominator. No assumption
    of statistical independence is made. Entry-domain Cartesian completion
    is part of the input contract; any cross-entry constraints require another
    solver, not silent relaxation by this function.
    """
    domains = checked_domains(domains)
    left, right = tuple(left), tuple(right)
    if (not weights or not left or not right or set(left) & set(right)
            or len(set(left)) != len(left) or len(set(right)) != len(right)
            or type(weight_denominator) is not int or weight_denominator <= 0):
        raise ValueError('A defined nonempty bipartite estimand is required')
    if any(a not in left or b not in right or type(w) is not int for (a, b), w in weights.items()):
        raise ValueError('Weights must connect left entries to right entries')
    if any(name not in domains for name in left + right):
        raise ValueError('Missing entry domain')
    extrema = {'lower': None, 'upper': None}
    enumerated = 0
    for selected in product(*(domains[b] for b in right)):
        enumerated += 1
        fixed = dict(zip(right, selected))
        candidates = {}
        for side in ('lower', 'upper'):
            assignment = {name: values[0] for name, values in domains.items()}
            assignment.update(fixed)
            total = 0
            for a in left:
                scores = [(sum(weights.get((a, b), 0) * score8(value, fixed[b]) for b in right), value)
                          for value in domains[a]]
                wanted = min(v for v, _ in scores) if side == 'lower' else max(v for v, _ in scores)
                assignment[a] = next(value for v, value in scores if v == wanted)
                total += wanted
            assert total == evaluate8(assignment, weights)
            candidates[side] = {'raw_numerator': total, 'value': Fraction(total, 8 * weight_denominator),
                                'assignment': assignment}
        for side, candidate in candidates.items():
            previous = extrema[side]
            better = previous is None or (candidate['value'] < previous['value'] if side == 'lower'
                                           else candidate['value'] > previous['value'])
            if better:
                extrema[side] = candidate
    return {'bounds': extrema, 'right_assignments_enumerated': enumerated,
            'unweighted_entries': sorted(set(domains) - set(left) - set(right)),
            'scope': 'Exact supplied algebraic domains; whole signatures and shared entry states retained.'}


def pair_bounds(left_domain, right_domain):
    domains = checked_domains({'left': left_domain, 'right': right_domain})
    values = [score8(a, b) for a in domains['left'] for b in domains['right']]
    return Fraction(min(values), 8), Fraction(max(values), 8)


def contribution_at(assignment, weights, weight_denominator):
    result = [Fraction(sum(w * (2 - abs(assignment[a][k] - assignment[b][k]))
                           for (a, b), w in weights.items()), 8 * weight_denominator)
              for k in range(4)]
    assert sum(result) == Fraction(evaluate8(assignment, weights), 8 * weight_denominator)
    return result
