"""Deterministic adapter checks without manuscript targets or reserve loading."""
from pathlib import Path
import itertools
import json
import math
import sys

P = Path(__file__).resolve().parent
sys.path.insert(0, str(P))
from worker import target_identity_cost
sys.path.insert(0, str(P.parent))
from predictive import CharLM, BOS, EOS
from boundary import UNK
from boundary_word import continuation_logp


def verify():
    alphabet, omega = set('ab'), set('abxy')
    lm = CharLM([tuple('ab'), tuple('aab'), tuple('b')], alphabet, 4, 5)
    q0 = {'a': .5, 'b': .3, UNK: .2}
    q1 = {'a': .2, 'b': .3, UNK: .5}
    cases = []
    for context, target, expected in [('x', 'a', 0.), ('a', 'x', 1.), ('a', 'ax', 1.), ('x', 'xy', 2.)]:
        word = tuple(target)
        mapped = tuple(c if c in alphabet else UNK for c in word)
        count, identity = target_identity_cost(word, alphabet, omega)
        assert identity == expected
        tail = continuation_logp(lm, mapped)
        before = math.log2(q0[mapped[0]]) + tail
        after = math.log2(q1[mapped[0]]) + tail
        assert abs(((after-identity) - (before-identity)) - (after-before)) < 1e-12
        cases.append(dict(context=context, target=target, target_unknown=count, identity_bits=identity, contrast_unchanged=True))
    total = remaining = max_factor_error = 0.
    for length in range(1, 7):
        for word in itertools.product(sorted(omega), repeat=length):
            mapped = tuple(c if c in alphabet else UNK for c in word)
            _, identity = target_identity_cost(word, alphabet, omega)
            factor = math.log2(q0[mapped[0]]) + continuation_logp(lm, mapped) - identity
            h = (BOS,) * 3
            prefix = q0[mapped[0]] / (2 if mapped[0] == UNK else 1)
            h = (h + (mapped[0],))[-3:]
            for c in mapped[1:]:
                prefix *= lm.prob(h, c) / (2 if c == UNK else 1)
                h = (h + (c,))[-3:]
            direct = prefix * lm.prob(h, EOS)
            max_factor_error = max(max_factor_error, abs(math.log2(direct)-factor))
            total += direct
            if length == 6:
                remaining += prefix * (1-lm.prob(h, EOS))
    assert max_factor_error < 1e-11
    assert abs(total + remaining - 1) < 1e-11
    no_escape = target_identity_cost(tuple('ab'), alphabet, alphabet)
    assert no_escape == (0, 0.)
    return dict(target_only_cases=cases, nonempty_expanded_word_mass_through_6=total,
        remaining_mass=remaining, total_mass=total+remaining, no_double_nonempty_condition=True,
        max_independent_probability_error=max_factor_error, closed_alphabet_zero_escape_checked=True,
        manuscript_records_loaded=False, passed=True)


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2))
