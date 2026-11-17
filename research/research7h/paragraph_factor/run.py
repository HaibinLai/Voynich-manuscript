"""Train/develop first, persist all distributions, then score frozen confirm once."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import datetime
import gzip
import hashlib
import json
import math
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import corpus
from models import BodyLM, PrefixFactor, POSITIONS, universe, logmix, verify_models

VARIANTS = [('ZL_EVA', 'ZL3b-n.txt', 'eva', 2026111718),
            ('ZL_merged', 'ZL3b-n.txt', 'merged', 2026111719),
            ('IT_EVA', 'IT2a-n.txt', 'eva', 2026111720)]
ORDERS, ALPHAS, BETAS, WEIGHTS = [1, 2, 3, 4], [1, 5, 20, 100], [1, 5, 20, 100], [0, .25, .5, .75, 1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, obj):
    path = HERE/path
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()
    if path.suffix == '.gz':
        path.write_bytes(gzip.compress(raw, mtime=0))
    else:
        path.write_bytes(raw)


def read(path):
    p = HERE/path
    raw = gzip.decompress(p.read_bytes()) if p.suffix == '.gz' else p.read_bytes()
    return json.loads(raw)


def get_records(source, representation, splits):
    assert splits and set(splits) <= {'legacy', 'train', 'dev', 'confirm'}
    pages = corpus.load(source=source, splits=splits)
    result, missing = [], 0
    for page in pages:
        assert page['split'] in splits and page['split'] != 'reserve'
        for line_index, line in enumerate(page['lines']):
            for j, token in enumerate(line['tokens']):
                if token is None:
                    missing += 1
                    continue
                position = 'paragraph_first' if j == 0 and line['paragraph_start'] else ('line_first' if j == 0 else 'other')
                result.append(dict(folio=page['folio'], leaf=page['leaf'], line=line_index,
                    slot=j, loci=line['loci'], position=position, word=corpus.units(token, representation),
                    original_token=token, hand=page['metadata'].get('H', '?'), split=page['split']))
    return result, dict(pages=len(pages), leaves=len({p['leaf'] for p in pages}), tokens=len(result),
        missing_slots=missing, positions=dict(Counter(r['position'] for r in result)))


def mean_bits(records, score):
    return sum(-score(r['word']) for r in records)/len(records)


def input_hashes(source):
    return {name: sha(path) for name, path in {
        'protocol.txt': HERE/'protocol.txt', 'models.py': HERE/'models.py', 'run.py': HERE/'run.py',
        'split_manifest.json': HERE.parent/'split_manifest.json', 'corpus.py': HERE.parent/'corpus.py',
        'build_corpus.py': corpus.BASE/'build_corpus.py', 'study20/analyze.py': corpus.BASE/'study20/analyze.py',
        source: corpus.BASE/'sources'/source}.items()}


def prepare(name, source, representation, seed):
    start = time.time()
    receipt = read('protocol_receipt.json')
    assert receipt['protocol_sha256'] == sha(HERE/'protocol.txt')
    assert receipt['split_sha256'] == sha(HERE.parent/'split_manifest.json')
    assert receipt['unit_universes'][representation] == sorted(universe(representation))
    assert not (HERE/name/'frozen_config.json').exists(), 'Do not overwrite frozen configurations'
    train, train_summary = get_records(source, representation, ['train', 'legacy'])
    dev, dev_summary = get_records(source, representation, ['dev'])
    alphabet = {c for r in train for c in r['word']}
    omega = universe(representation)
    assert alphabet <= omega and all(set(r['word']) <= omega for r in dev)
    train_body = [r for r in train if r['position'] != 'paragraph_first']
    dev_body = [r for r in dev if r['position'] != 'paragraph_first']
    train_first = [r for r in train if r['position'] == 'paragraph_first']
    dev_first = [r for r in dev if r['position'] == 'paragraph_first']
    body_tuning, best = [], None
    for order in ORDERS:
        for alpha in ALPHAS:
            lm = BodyLM([r['word'] for r in train_body], alphabet, omega, order, alpha)
            score = mean_bits(dev_body, lm.logp_full)
            body_tuning.append(dict(order=order, alpha=alpha, dev_body_bits_per_word=score))
            if best is None or (score, order, alpha) < best[:3]:
                best = (score, order, alpha, lm)
    _, order, alpha, body = best
    position = BodyLM([r['word'] for r in train_first], alphabet, omega, order, alpha)
    base_first = [body.logp_full(r['word']) for r in dev_first]
    pos_first = [position.logp_full(r['word']) for r in dev_first]
    position_tuning = [dict(weight=w, dev_paragraph_bits_per_word=-sum(logmix(a, b, w) for a, b in zip(base_first, pos_first))/len(dev_first)) for w in WEIGHTS]
    position_selected = min(position_tuning, key=lambda t: (t['dev_paragraph_bits_per_word'], t['weight']))
    factor_tuning, selected, factor_payloads = {}, {}, {}
    for kind in ['gallows', 'any_first']:
        candidates = []
        for beta in BETAS:
            factor = PrefixFactor(body, train, beta, kind)
            scores = [factor.logp(r['word']) for r in dev_first]
            factor_payloads[f'{kind}_beta{beta}'] = factor.payload()
            for w in WEIGHTS:
                loss = -sum(logmix(a, b, w) for a, b in zip(base_first, scores))/len(dev_first)
                candidates.append(dict(beta=beta, weight=w, dev_paragraph_bits_per_word=loss))
        direct = min([c for c in candidates if c['weight'] == 1], key=lambda t: (t['dev_paragraph_bits_per_word'], t['beta']))
        mixture = min(candidates, key=lambda t: (t['dev_paragraph_bits_per_word'], t['weight'], t['beta']))
        factor_tuning[kind] = candidates
        selected[kind] = dict(direct=direct, mixture=mixture)
    tables = dict(body=body.payload(), position=position.payload(), factors=factor_payloads)
    assert tables['body']['conditional_sum_max_error'] < 1e-11
    assert tables['position']['conditional_sum_max_error'] < 1e-11
    for v in factor_payloads.values():
        assert max(v['probability_sum_error'].values()) < 1e-11
    save(f'{name}/probability_tables.json.gz', tables)
    selection = dict(body_order=order, body_alpha=alpha, position=position_selected, factors=selected)
    config = dict(name=name, source=source, representation=representation, seed=seed, selected=selection,
        frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        train_summary=train_summary, dev_summary=dev_summary,
        training_alphabet=sorted(alphabet), universe_size=len(omega), escape_size=len(omega-alphabet),
        dev_escaped_units=sum(c not in alphabet for r in dev for c in r['word']),
        body_tuning=body_tuning, position_tuning=position_tuning, factor_tuning=factor_tuning,
        input_hashes=input_hashes(source), probability_tables_sha256=sha(HERE/name/'probability_tables.json.gz'),
        scope='All configurations and conditional probabilities are persisted before loading confirm. Reserve is not used.',
        preparation_seconds=time.time()-start)
    save(f'{name}/frozen_config.json', config)
    print(json.dumps(dict(phase='prepared', name=name, selected=selection, train=train_summary, dev=dev_summary), ensure_ascii=False), flush=True)


def summarize(rows, score_keys, scope):
    selected = [r for r in rows if scope == 'all' or r['position'] == 'paragraph_first']
    result = {}
    for model in score_keys:
        pages, leaves = defaultdict(lambda: [0., 0]), defaultdict(lambda: [0., 0])
        for r in selected:
            b = r['bits'][model]
            for group, key in [(pages, r['folio']), (leaves, r['leaf'])]:
                group[key][0] += b
                group[key][1] += 1
        result[model] = dict(tokens=len(selected), bits_per_word=sum(r['bits'][model] for r in selected)/len(selected),
            page_mean_bits_per_word=float(np.mean([v[0]/v[1] for v in pages.values()])),
            leaf_mean_bits_per_word=float(np.mean([v[0]/v[1] for v in leaves.values()])),
            per_page={k: dict(bits=v[0], tokens=v[1], bits_per_word=v[0]/v[1]) for k, v in pages.items()},
            per_leaf={k: dict(bits=v[0], tokens=v[1], bits_per_word=v[0]/v[1]) for k, v in leaves.items()})
    return result


def bootstrap(results, seed):
    base = 'body_full'
    comparisons = [(base, k) for k in results if k != base]
    comparisons += [('position_full', 'gallows_selected'), ('any_first_selected', 'gallows_selected')]
    leaves = sorted(results[base]['per_leaf'])
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(leaves), size=(9999, len(leaves)))
    out = {}
    for a, b in comparisons:
        values = np.array([results[a]['per_leaf'][leaf]['bits_per_word']-results[b]['per_leaf'][leaf]['bits_per_word'] for leaf in leaves])
        samples = values[indices].mean(axis=1)
        out[a+'__minus__'+b] = dict(mean_leaf_bits_saved=float(values.mean()),
            bootstrap95=np.quantile(samples, [.025, .975]).tolist(),
            per_leaf=dict(zip(leaves, values.tolist())), replicates=9999, raw_bootstrap=samples.tolist(),
            interpretation='Positive saves bits with the second model. Descriptive conditional leaf-bootstrap interval; not semantic evidence or a multiple-testing-adjusted significance claim.')
    return out


def evaluate(name, source, representation, seed):
    assert not (HERE/name/'confirm_results.json').exists(), 'Confirm may not be silently rescored'
    config = read(f'{name}/frozen_config.json')
    assert config['input_hashes'] == input_hashes(source), 'Inputs/code must match frozen development configuration'
    assert config['probability_tables_sha256'] == sha(HERE/name/'probability_tables.json.gz')
    tables = read(f'{name}/probability_tables.json.gz')
    body, pos = BodyLM.from_payload(tables['body']), BodyLM.from_payload(tables['position'])
    factors = {k: PrefixFactor.from_payload(body, v) for k, v in tables['factors'].items()}
    selected = config['selected']
    opened = datetime.datetime.now(datetime.timezone.utc).isoformat()
    test, test_summary = get_records(source, representation, ['confirm'])
    assert all(set(r['word']) <= body.omega for r in test)
    rows = []
    score_keys = ['body_full', 'position_full', 'gallows_direct', 'gallows_selected', 'any_first_direct', 'any_first_selected']
    for r in test:
        w = r['word']
        base = body.logp_full(w)
        scores = {k: -base for k in score_keys}
        costs = {}
        if r['position'] == 'paragraph_first':
            scores['position_full'] = -logmix(base, pos.logp_full(w), selected['position']['weight'])
            for kind in ['gallows', 'any_first']:
                for mode in ['direct', 'mixture']:
                    setting = selected['factors'][kind][mode]
                    key = f"{kind}_beta{setting['beta']}"
                    factor = factors[key]
                    costs[key] = factor.cost(w)
                    name_mode = 'direct' if mode == 'direct' else 'selected'
                    scores[kind+'_'+name_mode] = -logmix(base, -costs[key]['total_bits'], setting['weight'])
        rows.append({**r, 'word': list(w), 'bits': scores,
            'body_raw_bits': -body.logp_raw(w), 'body_nonempty_normalization_bits': math.log2(body.nonempty_mass),
            'escaped_units': sum(c not in body.alphabet for c in w),
            'escape_bits': sum(c not in body.alphabet for c in w)*math.log2(body.escape_size) if body.escape_size else 0,
            'factor_costs': costs})
    raw = ''.join(json.dumps(r, ensure_ascii=False, allow_nan=False)+'\n' for r in rows).encode()
    (HERE/name/'confirm_word_scores.jsonl.gz').write_bytes(gzip.compress(raw, mtime=0))
    summaries = {scope: summarize(rows, score_keys, scope) for scope in ['paragraph_first', 'all']}
    contrasts = {scope: bootstrap(result, seed) for scope, result in summaries.items()}
    out = dict(name=name, source=source, representation=representation, confirm_opened_utc=opened,
        config_sha256=sha(HERE/name/'frozen_config.json'), protocol_sha256=sha(HERE/'protocol.txt'),
        test_summary=test_summary, confirm_escaped_units=sum(r['escaped_units'] for r in rows),
        observed_units_within_frozen_universe=True, reserve_used=False,
        summaries=summaries, comparisons=contrasts, selected=selected,
        limitations=['Confirm outcomes from the prior stage were already seen; this is not fully blind.',
        'Position is supplied by transcription layout markers, which may partly depend on initial glyphs.',
        'Unit-string prediction is not language identification, pronunciation, or meaning.',
        'Model parameter transmission costs are not included; costs are fixed-model held-out predictions.'])
    save(f'{name}/confirm_results.json', out)
    print(json.dumps(dict(phase='evaluated', name=name, confirm=test_summary,
        paragraph_bits={k: v['bits_per_word'] for k, v in summaries['paragraph_first'].items()},
        primary_comparisons={k: {kk: vv for kk, vv in v.items() if kk != 'raw_bootstrap'} for k, v in contrasts['paragraph_first'].items() if k.startswith(('position_full', 'any_first_selected'))}), ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'evaluate'])
    args = parser.parse_args()
    if args.phase == 'prepare':
        save('preflight_verification.json', verify_models())
        for variant in VARIANTS:
            prepare(*variant)
    else:
        assert all((HERE/v[0]/'frozen_config.json').exists() for v in VARIANTS)
        for variant in VARIANTS:
            evaluate(*variant)


if __name__ == '__main__':
    main()
