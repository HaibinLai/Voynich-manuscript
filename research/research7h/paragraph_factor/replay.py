"""Independent arithmetic replay from frozen counts and saved target strings.

Does not import the fitting/scoring implementation, or reopen manuscript corpora.
"""
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import gzip
import hashlib
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parent


def read(path):
    b = path.read_bytes()
    return json.loads(gzip.decompress(b) if path.suffix == '.gz' else b)


def instantiate(saved):
    vocab = saved['vocab']
    allowed, known = set(saved['omega']), set(saved['alphabet'])
    k = len(allowed-known)
    counts = {tuple(row['history']): dict(zip(vocab, row['counts'])) for row in saved['contexts']}
    totals = {tuple(row['history']): row['total'] for row in saved['contexts']}
    alpha, order = saved['alpha'], saved['order']

    @lru_cache(None)
    def transition(history, next_symbol):
        prior = transition(history[1:], next_symbol) if history else 1/len(vocab)
        return (counts.get(history, {}).get(next_symbol, 0)+alpha*prior)/(totals.get(history, 0)+alpha)

    start = ('<BOS>',)*(order-1)
    def raw_log(word):
        state, total = start, 0.
        for c in word:
            assert c in allowed
            mapped = c if c in known else '<UNK>'
            probability = transition(state, mapped)
            if c not in known:
                probability /= k
            total += math.log2(probability)
            state = (state+(mapped,))[-(order-1):] if order > 1 else ()
        return total+math.log2(transition(state, '<EOS>'))

    nonempty = 1-transition(start, '<EOS>')
    first = {c: transition(start, c if c in known else '<UNK>')/(k if c not in known else 1)/nonempty for c in allowed}
    worst_table_error = 0.
    for row in saved['contexts']:
        h = tuple(row['history'])
        assert sum(row['counts']) == row['total']
        observed = [transition(h, c) for c in vocab]
        worst_table_error = max(worst_table_error, max(abs(a-b) for a, b in zip(observed, row['probabilities'])))
        assert abs(sum(observed)-1) < 1e-11
    assert abs(sum(first.values())-1) < 1e-11
    assert worst_table_error < 1e-12
    return dict(raw_log=raw_log, nonempty=nonempty, first=first, known=known,
        escape_size=k, table_max_error=worst_table_error,
        full_log=lambda w: raw_log(w)-math.log2(nonempty))


def mix(a, b, fraction):
    if fraction == 0:
        return a
    if fraction == 1:
        return b
    high = max(a, b)
    return high+math.log2((1-fraction)*2**(a-high)+fraction*2**(b-high))


def replay(name):
    folder = ROOT/name
    config, results = read(folder/'frozen_config.json'), read(folder/'confirm_results.json')
    saved = read(folder/'probability_tables.json.gz')
    assert hashlib.sha256((folder/'probability_tables.json.gz').read_bytes()).hexdigest() == config['probability_tables_sha256']
    assert hashlib.sha256((folder/'frozen_config.json').read_bytes()).hexdigest() == results['config_sha256']
    body, position = instantiate(saved['body']), instantiate(saved['position'])
    factors = {}
    max_prefix_error = 0.
    for key, f in saved['factors'].items():
        if f['kind'] == 'gallows':
            prior = {c: body['first'][c] for c in 'ktpf'}
            prior['<NONE>'] = sum(p for c, p in body['first'].items() if c not in 'ktpf')
            z = prior['<NONE>']*body['nonempty']
            assert abs(z-f['z_none']) < 1e-11
        else:
            prior, z = body['first'], None
        tables = {}
        for label, counts in f['training_counts'].items():
            n = sum(counts.values())
            assert n == f['training_totals'][label]
            tables[label] = {c: (counts.get(c, 0)+f['beta']*p)/(n+f['beta']) for c, p in prior.items()}
            assert abs(sum(tables[label].values())-1) < 1e-11
            max_prefix_error = max(max_prefix_error, max(abs(p-f['prefix_probabilities'][label][c]) for c, p in tables[label].items()))
        factors[key] = dict(kind=f['kind'], z=z, tables=tables)

    rows = [json.loads(line) for line in gzip.decompress((folder/'confirm_word_scores.jsonl.gz').read_bytes()).decode().splitlines()]
    max_word_error, max_component_error = 0., 0.
    aggregate = {scope: defaultdict(lambda: defaultdict(lambda: [0., 0])) for scope in ['all', 'paragraph_first']}
    escaped_targets = 0
    for row in rows:
        w = tuple(row['word'])
        assert ''.join(w) == row['original_token']
        base = body['full_log'](w)
        predicted = {k: -base for k in row['bits']}
        assert abs(-body['raw_log'](w)-row['body_raw_bits']) < 1e-11
        if row['position'] == 'paragraph_first':
            predicted['position_full'] = -mix(base, position['full_log'](w), config['selected']['position']['weight'])
            for kind in ['gallows', 'any_first']:
                for mode in ['direct', 'mixture']:
                    setting = config['selected']['factors'][kind][mode]
                    key = f"{kind}_beta{setting['beta']}"
                    factor = factors[key]
                    prefix = w[0] if kind == 'any_first' or w[0] in 'ktpf' else '<NONE>'
                    root = w[1:] if prefix != '<NONE>' else w
                    components = [-math.log2(factor['tables']['paragraph_first'][prefix]), -body['raw_log'](root),
                        math.log2(factor['z']) if prefix == '<NONE>' else 0.]
                    original = row['factor_costs'][key]
                    expected = [original['prefix_bits'], original['body_raw_bits'], original['support_normalization_bits']]
                    max_component_error = max(max_component_error, max(abs(a-b) for a, b in zip(components, expected)))
                    assert (root if prefix == '<NONE>' else (prefix,)+root) == w
                    assert sum(components) >= 0
                    output = kind+('_direct' if mode == 'direct' else '_selected')
                    predicted[output] = -mix(base, -sum(components), setting['weight'])
        escaped_targets += sum(c not in body['known'] for c in w)
        max_word_error = max(max_word_error, max(abs(predicted[k]-v) for k, v in row['bits'].items()))
        for scope in ['all']+(['paragraph_first'] if row['position'] == 'paragraph_first' else []):
            for key, bits in predicted.items():
                aggregate[scope][key][row['leaf']][0] += bits
                aggregate[scope][key][row['leaf']][1] += 1
    assert max_word_error < 1e-10 and max_component_error < 1e-10
    assert escaped_targets == results['confirm_escaped_units']
    max_boot_error, max_aggregate_error = 0., 0.
    for scope, models in aggregate.items():
        for model, leaves in models.items():
            total_bits, total_tokens = sum(v[0] for v in leaves.values()), sum(v[1] for v in leaves.values())
            original = results['summaries'][scope][model]
            max_aggregate_error = max(max_aggregate_error, abs(total_bits/total_tokens-original['bits_per_word']))
            for leaf, (bits, n) in leaves.items():
                assert n == original['per_leaf'][leaf]['tokens']
                assert abs(bits/n-original['per_leaf'][leaf]['bits_per_word']) < 1e-10
        order = sorted(next(iter(models.values())))
        rng = np.random.default_rng(config['seed'])
        indices = rng.integers(0, len(order), size=(9999, len(order)))
        for comparison, saved_comparison in results['comparisons'][scope].items():
            a, b = comparison.split('__minus__')
            values = np.array([models[a][leaf][0]/models[a][leaf][1]-models[b][leaf][0]/models[b][leaf][1] for leaf in order])
            samples = values[indices].mean(axis=1)
            error = float(np.max(np.abs(samples-np.array(saved_comparison['raw_bootstrap']))))
            max_boot_error = max(max_boot_error, error)
            assert error < 1e-10
    return dict(variant=name, tokens=len(rows), paragraph_tokens=sum(r['position'] == 'paragraph_first' for r in rows),
        escaped_units=escaped_targets, probability_table_max_error=max(body['table_max_error'], position['table_max_error']),
        prefix_posterior_max_error=max_prefix_error, individual_word_max_error=max_word_error,
        factor_cost_component_max_error=max_component_error, aggregate_bits_per_word_max_error=max_aggregate_error,
        bootstrap_array_max_error=max_boot_error, independent_replay_passed=True,
        source_corpus_reopened=False, reserve_used=False)


if __name__ == '__main__':
    outcomes = [replay(name) for name in ['ZL_EVA', 'ZL_merged', 'IT_EVA']]
    (ROOT/'replay_verification.json').write_text(json.dumps(outcomes, indent=2)+'\n')
    print(json.dumps(outcomes, indent=2))
