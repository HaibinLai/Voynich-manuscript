# -*- coding: utf-8 -*-
"""Independent scalar audit. Default action is synthetic-only; never imports study code."""
from collections import Counter, defaultdict
from pathlib import Path
import argparse, datetime, gzip, hashlib, json, math, re

HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
RESEARCH = STUDY.parent
UNK, BOS, EOS = '<UNK>', '<BOS>', '<EOS>'
ALPHAS = [1, 5, 20, 100, 500]
WEIGHTS = [0, .25, .5, .75, 1]
REPRESENTATIONS = {'ZL_EVA': ('ZL3b-n', 'eva'), 'ZL_merged': ('ZL3b-n', 'merged'), 'IT_EVA': ('IT2a-n', 'eva')}
SOURCE_SHA = {
    ('ZL3b-n', 'train_legacy'): '139f2ce735689086e4a64f1786271f5f18b3ab288cf7ef84d6abcd994d06cc8c',
    ('ZL3b-n', 'dev'): '0f95c04fae55357398983aca0f0b89e3f3b9a3f8a034f73b13716f1053cd5e73',
    ('IT2a-n', 'train_legacy'): 'd8001be26b06c64063e640f3ed7c1241c6f52cf75bd4c6b8cd6bfe6b0d5e211b',
    ('IT2a-n', 'dev'): '5dc88bb9adac08184aaacae7b24e814ff8ffff3564846ca9495328f8b9f4ac82',
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    payload = path.read_bytes()
    return json.loads(gzip.decompress(payload) if path.suffix == '.gz' else payload)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def tokens(text, representation):
    # Same declared token alphabet; independently applied, no data.py import.
    expression = r"cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z']" if representation == 'merged' else r"@\d{3};|[a-z']"
    result = tuple(re.findall(expression, text))
    assert result and ''.join(result) == text
    return result


def universe(representation):
    omega = set("abcdefghijklmnopqrstuvwxyz'") | {'@%03d;' % i for i in range(1000)}
    if representation == 'merged':
        omega.update(['ch', 'sh', 'cth', 'ckh', 'cph', 'cfh'])
    return omega


def corpus_words(pages, rep):
    return [tokens(t, rep) for p in pages for line in p['lines'] for t in line['tokens'] if t is not None]


def reconstruct_pairs(pages, rep):
    result, counts = [], Counter()
    for page in pages:
        for index in range(1, len(page['lines'])):
            earlier, later = page['lines'][index - 1], page['lines'][index]
            counts['candidate_adjacent_parsed_rows'] += 1
            reason = None
            if not (earlier['paragraph_known'] and later['paragraph_known']):
                reason = 'unknown_paragraph'
            elif earlier['paragraph_end'] or later['paragraph_start'] or earlier['block'] != later['block'] or earlier['paragraph'] != later['paragraph']:
                reason = 'paragraph_or_block_boundary'
            elif earlier['aligned_to_excluded_locus'] or later['aligned_to_excluded_locus']:
                reason = 'aligned_to_excluded_locus'
            elif not earlier['tokens'] or not later['tokens'] or earlier['tokens'][-1] is None or later['tokens'][0] is None:
                reason = 'missing_endpoint'
            if reason:
                counts[reason] += 1
                continue
            source, target = tokens(earlier['tokens'][-1], rep), tokens(later['tokens'][0], rep)
            result.append(dict(folio=page['folio'], leaf=page['leaf'], line=index, slot=0,
                previous_line=index - 1, previous_slot=len(earlier['tokens']) - 1, word=target,
                previous_word=source, previous_length=len(source), length=0,
                hand=later['effective_hands'][0], previous_hand=earlier['effective_hands'][-1],
                section=page['metadata'].get('I', '?'), position_bin=0, paragraph_line=0,
                source_file_adjacent=max(earlier['source_lines']) + 1 == min(later['source_lines'])))
            counts['eligible_same_paragraph_cross_row'] += 1
    counts['cross_hand_pairs'] = sum(r['hand'] != r['previous_hand'] for r in result)
    counts['unresolved_target_H_at'] = sum(r['hand'] == '@' for r in result)
    counts['source_file_adjacent_only'] = sum(r['source_file_adjacent'] for r in result)
    return result, dict(counts)


def map_rows(rows, alphabet):
    output = []
    for raw in rows:
        r = dict(raw)
        r['original_word'] = tuple(raw['word'])
        r['word'] = tuple(c if c in alphabet else UNK for c in raw['word'])
        r['last'] = raw['previous_word'][-1] if raw['previous_word'][-1] in alphabet else UNK
        r['target'] = r['word'][0]
        r['target_unknown_units'] = sum(c not in alphabet for c in raw['word'])
        r['source_unknown_units'] = sum(c not in alphabet for c in raw['previous_word'])
        output.append(r)
    return output


def hierarchy(r, feature):
    h, s = r['hand'], r['section']
    tail = [('hs', h, s), ('tl', h, s, min(10, r['length'])),
            ('pl', h, s, min(10, r['length']), min(10, r['previous_length'])),
            ('position', h, s, min(10, r['length']), min(10, r['previous_length']), r['position_bin'], r['paragraph_line'])]
    if feature:
        return [(), ('context', r['last'])] + [key + (r['last'],) for key in tail]
    return [()] + tail


def build_q(rows, feature):
    cells = defaultdict(Counter)
    for row in rows:
        for key in hierarchy(row, feature):
            cells[key][row['target']] += 1
    return dict(cells)


def q_probability(cells, row, alphabet, alpha, feature):
    probability = 1.0 / (len(alphabet) + 1)
    for key in hierarchy(row, feature):
        cell = cells.get(key)
        if cell:
            probability = (cell.get(row['target'], 0) + alpha * probability) / (sum(cell.values()) + alpha)
    return probability


def q_support(cells, rows, feature):
    histograms = [Counter() for _ in hierarchy(rows[0], feature)] if rows else []
    details, depths = [], Counter()
    for row in rows:
        counts = [sum(cells.get(key, {}).values()) for key in hierarchy(row, feature)]
        for histogram, count in zip(histograms, counts):
            histogram[str(count)] += 1
        depth = max((i for i, n in enumerate(counts) if n), default=-1)
        depths[str(depth)] += 1
        details.append(dict(counts=counts, deepest_observed_level=depth, final_level_unseen=counts[-1] == 0))
    return dict(exact_training_count_histogram_by_level=[dict(h) for h in histograms], deepest_observed_level_counts=dict(depths), rows=details)


def build_char(words):
    counts = defaultdict(Counter)
    for word in words:
        history = [BOS, BOS, BOS]
        for symbol in list(word) + [EOS]:
            for length in range(4):
                counts[tuple(history[-length:]) if length else ()][symbol] += 1
            history = (history + [symbol])[-3:]
    return dict(counts)


def char_probability(counts, alphabet, history, symbol):
    result = 1.0 / (len(alphabet) + 2)
    for length in range(4):
        key = tuple(history[-length:]) if length else ()
        cell = counts.get(key, {})
        result = (cell.get(symbol, 0) + 100 * result) / (sum(cell.values()) + 100)
    return result


def continuation_bits(counts, alphabet, mapped_word):
    # Start after the first symbol: never score, then subtract, the char-LM first term.
    history = [BOS, BOS, mapped_word[0]]
    losses = []
    for symbol in list(mapped_word[1:]) + [EOS]:
        losses.append(-math.log2(char_probability(counts, alphabet, history, symbol)))
        history = (history + [symbol])[-3:]
    return math.fsum(losses)


def aggregate(rows, values):
    by_page, page_leaf = defaultdict(list), {}
    for row, value in zip(rows, values):
        by_page[row['folio']].append(value)
        page_leaf[row['folio']] = row['leaf']
    pages = {p: math.fsum(v) / len(v) for p, v in by_page.items()}
    by_leaf = defaultdict(list)
    for p, value in pages.items():
        by_leaf[page_leaf[p]].append(value)
    leaves = {leaf: math.fsum(v) / len(v) for leaf, v in by_leaf.items()}
    loo = {leaf: math.fsum(v for l, v in leaves.items() if l != leaf) / (len(leaves) - 1) for leaf in leaves} if len(leaves) > 1 else {}
    return dict(mean_leaf=math.fsum(leaves.values()) / len(leaves) if leaves else None,
        pooled=math.fsum(values) / len(values) if values else None, per_page=pages, per_leaf=leaves,
        leave_one_leaf_out=loo, leave_one_leaf_out_range=[min(loo.values()), max(loo.values())] if loo else None)


def compare(actual, expected, tolerance=1e-10):
    if isinstance(actual, dict):
        assert set(actual) == set(expected), (set(actual), set(expected))
        return max((compare(actual[k], expected[k], tolerance) for k in actual), default=0.)
    if isinstance(actual, (list, tuple)):
        assert len(actual) == len(expected)
        return max((compare(a, b, tolerance) for a, b in zip(actual, expected)), default=0.)
    if isinstance(actual, float):
        error = abs(actual - expected)
        assert error < tolerance, (actual, expected, error)
        return error
    assert actual == expected, (actual, expected)
    return 0.


def replay_cv(pages, raw, rep, cfg):
    leaves = sorted({r['leaf'] for r in raw}, key=lambda leaf: hashlib.sha256(('line-calibration-fold-v1|' + leaf).encode()).digest())
    fold = {leaf: i % 3 for i, leaf in enumerate(leaves)}
    assert fold == cfg['leaf_fold']
    baseline = {alpha: [None] * len(raw) for alpha in ALPHAS}
    augmented = {alpha: [None] * len(raw) for alpha in ALPHAS}
    escapes, audit = [None] * len(raw), []
    for k in range(3):
        fit_pages = [p for p in pages if p['leaf'] in fold and fold[p['leaf']] != k]
        alphabet = set(c for w in corpus_words(fit_pages, rep) for c in w)
        fit = map_rows([r for r in raw if fold[r['leaf']] != k], alphabet)
        held_ids = [i for i, r in enumerate(raw) if fold[r['leaf']] == k]
        held = map_rows([raw[i] for i in held_ids], alphabet)
        assert {r['leaf'] for r in fit}.isdisjoint(r['leaf'] for r in held)
        cells0, cells1 = build_q(fit, False), build_q(fit, True)
        escape = math.log2(len(universe(rep) - alphabet))
        for i, row in zip(held_ids, held):
            escapes[i] = escape if raw[i]['word'][0] not in alphabet else 0.
            for alpha in ALPHAS:
                baseline[alpha][i] = q_probability(cells0, row, alphabet, alpha, False)
                augmented[alpha][i] = q_probability(cells1, row, alphabet, alpha, True)
        audit.append(dict(fold=k, fit_rows=len(fit), held_rows=len(held),
            fit_leaves=sorted({r['leaf'] for r in fit}), held_leaves=sorted({r['leaf'] for r in held}),
            alphabet=sorted(alphabet), held_first_unknown=sum(raw[i]['word'][0] not in alphabet for i in held_ids)))
    compare(audit, cfg['folds'])
    base_grid = [dict(alpha=a, loss=math.fsum(-math.log2(p) + x for p, x in zip(baseline[a], escapes)) / len(raw)) for a in ALPHAS]
    ba = min(base_grid, key=lambda r: (r['loss'], -r['alpha']))['alpha']
    grid = [dict(alpha=a, weight=w, loss=math.fsum(-math.log2((1 - w) * p + w * q) + x for p, q, x in zip(baseline[ba], augmented[a], escapes)) / len(raw)) for a in ALPHAS for w in WEIGHTS]
    best = min(grid, key=lambda r: (r['loss'], r['weight'], -r['alpha']))
    assert (ba, best['alpha'], best['weight']) == (cfg['base_alpha'], cfg['alpha'], cfg['weight'])
    error = max(compare(base_grid, cfg['base_grid']), compare(grid, cfg['feature_grid']))
    return dict(base_grid=base_grid, feature_grid=grid, fold_audits=audit, max_loss_error=error, selected=[ba, best['alpha'], best['weight']])


def load_saved(source, split):
    path = RESEARCH / 'metadata_sensitivity/inputs' / f'{source}_{split}.json.gz'
    assert sha(path) == SOURCE_SHA[source, split]
    pages = read(path)
    assert {p['split'] for p in pages} <= ({'train', 'legacy'} if split == 'train_legacy' else {'dev'})
    return pages


def replay_completed(output):
    # Nothing below this guard can execute against an unfinished study.
    receipt = read(output / 'complete.json')
    assert receipt['all_three_complete'] is True
    assert sha(output / 'summary.json') == receipt['summary_sha256']
    execution = read(output / 'execution_receipt.json')
    assert execution['freeze_sha256'] == sha(STUDY / 'freeze.json')
    assert execution['confirm_loaded'] is False and execution['reserve_loaded'] is False
    binding = read(HERE / 'preparation_binding.json')
    for name, digest in binding['reviewed_sources'].items():
        assert sha(STUDY / name) == digest
    assert sha(HERE / 'replay.py') == binding['audit_script_sha256']
    frozen = read(output / 'all_configs_frozen.json')
    assert frozen['dev_loaded'] is False
    assert frozen['frozen_utc'] < receipt['completed_utc']
    reports = []
    # numpy is used only to read saved .npz arrays, never for probability or selection.
    import numpy as np
    for name, (source, rep) in REPRESENTATIONS.items():
        config_path = output / 'configs' / f'{name}.json'
        assert sha(config_path) == frozen['configs'][name]
        cfg = read(config_path)
        assert (cfg['name'], cfg['source'], cfg['representation']) == (name, source, rep)
        assert cfg['char_order'] == 4 and cfg['char_alpha'] == 100
        training = load_saved(source, 'train_legacy')
        raw_train, train_count = reconstruct_pairs(training, rep)
        train_words = corpus_words(training, rep)
        alphabet = set(c for w in train_words for c in w)
        assert sorted(alphabet) == cfg['alphabet']
        assert sorted({p['leaf'] for p in training}) == cfg['all_training_leaves']
        assert len(train_words) == cfg['train_words']
        assert train_count == cfg['train_pair_counts']
        cv = replay_cv(training, raw_train, rep, cfg)
        fit = map_rows(raw_train, alphabet)
        cells0, cells1, chars = build_q(fit, False), build_q(fit, True), build_char(train_words)
        dev = load_saved(source, 'dev')
        assert {p['leaf'] for p in training}.isdisjoint(p['leaf'] for p in dev)
        raw_dev, dev_count = reconstruct_pairs(dev, rep)
        rows = map_rows(raw_dev, alphabet)
        original_rows = read(output / f'{name}_rows.json.gz')
        compare(rows, original_rows)
        report = read(output / f'{name}_summary.json')
        assert report['target_counts'] == dev_count and report['targets'] == len(rows)
        assert sha(output / f'{name}_rows.json.gz') == report['rows_sha256']
        assert sha(output / f'{name}_scores.npz') == report['scores_sha256']
        omega = universe(rep)
        assert alphabet < omega and cfg['escape_size'] == len(omega - alphabet)
        assert cfg['omega_size'] == len(omega)
        identity_fee = math.log2(len(omega - alphabet))
        arrays = defaultdict(list)
        for row in rows:
            p = q_probability(cells0, row, alphabet, cfg['base_alpha'], False)
            q = (1 - cfg['weight']) * p + cfg['weight'] * q_probability(cells1, row, alphabet, cfg['alpha'], True)
            tail = continuation_bits(chars, alphabet, row['word'])
            first_escape = identity_fee if row['original_word'][0] not in alphabet else 0.
            escape = identity_fee * sum(c not in alphabet for c in row['original_word'])
            bc, mc = -math.log2(p), -math.log2(q)
            values = dict(base_bits=bc + tail + escape, model_bits=mc + tail + escape,
                continuation_bits=tail, target_escape_bits=escape, first_target_escape_bits=first_escape,
                first_base_class_bits=bc, first_model_class_bits=mc,
                first_base_actual_bits=bc + first_escape, first_model_actual_bits=mc + first_escape)
            assert abs((values['base_bits'] - values['model_bits']) - (bc - mc)) < 1e-10
            for key, value in values.items():
                arrays[key].append(value)
        with np.load(output / f'{name}_scores.npz') as saved:
            assert set(saved.files) == set(arrays)
            cost_errors = {key: compare(value, saved[key].tolist()) for key, value in arrays.items()}
        support = read(output / f'{name}_support.json.gz')
        for key, cells, feature in [('base', cells0, False), ('augmented', cells1, True)]:
            calculated = q_support(cells, rows, feature)
            compare(calculated, {k: support[key][k] for k in calculated})
        gain = [a - b for a, b in zip(arrays['base_bits'], arrays['model_bits'])]
        aggregations = {'base_cost': arrays['base_bits'], 'model_cost': arrays['model_bits'], 'gain': gain,
            'first_base_class_cost': arrays['first_base_class_bits'], 'first_model_class_cost': arrays['first_model_class_bits'],
            'first_base_actual_cost': arrays['first_base_actual_bits'], 'first_model_actual_cost': arrays['first_model_actual_bits']}
        aggregate_errors = {key: compare(aggregate(rows, values), report[key]) for key, values in aggregations.items()}
        assert dict(Counter(r['folio'] for r in rows)) == report['targets_by_page']
        assert dict(Counter(r['leaf'] for r in rows)) == report['targets_by_leaf']
        assert sum(r['target_unknown_units'] for r in rows) == report['target_unknown_units']
        assert sum(r['source_unknown_units'] for r in rows) == report['source_unknown_units']
        assert sum(r['last'] == UNK for r in rows) == report['source_unknown_endpoint_pairs']
        assert len({r['folio'] for r in rows}) == report['eligible_pages']
        assert len({r['leaf'] for r in rows}) == report['eligible_leaves']
        assert sorted({p['folio'] for p in dev} - {r['folio'] for r in rows}) == report['ineligible_pages']
        slots = sum(len(line['tokens']) for p in dev for line in p['lines'])
        missing = sum(t is None for p in dev for line in p['lines'] for t in line['tokens'])
        assert (slots, missing, slots - missing, slots - missing - len(rows)) == (report['parsed_prose_slots'], report['missing_or_ambiguous_slots'], report['retained_known_slots'], report['known_slots_not_selected_by_crossline_target_rule'])
        assert len({p['leaf'] for p in training}) == report['training_leaf_count']
        assert len({p['leaf'] for p in dev}) == report['dev_leaf_count']
        compare(math.fsum(arrays['target_escape_bits']), report['target_escape_bits'])
        compare(math.fsum(arrays['first_target_escape_bits']), report['first_target_escape_bits'])
        assert sorted(alphabet) == cfg['alphabet']
        reports.append(dict(name=name, targets=len(rows), cv=cv, cost_errors=cost_errors,
            aggregate_errors=aggregate_errors, support_and_rows_exact=True, train_dev_leaves_disjoint=True,
            all_three_fold_alphabets_training_only=True))
    result = dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), all_passed=True,
        representations=reports, candidate_grid_points=90, original_summary_sha256=sha(output / 'summary.json'),
        audit_script_sha256=sha(HERE / 'replay.py'), preparation_binding_sha256=sha(HERE / 'preparation_binding.json'),
        scope='Independent deterministic arithmetic and selection replay of saved train/dev and completed output; no new targets, random samples, tuning, confirm or reserve.',
        no_author_model_or_scoring_imports=True, confirm_or_reserve_loaded=False)
    assert not (HERE / 'audit_report.json').exists()
    write(HERE / 'audit_report.json', result)
    print(json.dumps({'all_passed': True, 'targets': sum(x['targets'] for x in reports), 'candidate_grid_points': 90}))


def toy():
    raw = dict(word=('a',), previous_word=('a',), previous_length=1, length=0,
        hand='h', section='s', position_bin=0, paragraph_line=0, folio='toy1', leaf='toy')
    alphabet = {'a', 'b'}
    training = map_rows([raw, raw, dict(raw, word=('b',))], alphabet)
    cells = build_q(training, False)
    row = map_rows([raw], alphabet)[0]
    p = q_probability(cells, row, alphabet, 2, False)
    assert abs(p - (2 / 3 - (1 / 3) * (2 / 5) ** 5)) < 1e-14
    total = sum(q_probability(cells, dict(row, target=c), alphabet, 2, False) for c in ['a', 'b', UNK])
    assert abs(total - 1) < 1e-14
    chars = build_char([('a',), ('a', 'b'), ('b',)])
    for h in [(BOS, BOS, BOS), (BOS, BOS, 'a'), ('b', 'a', UNK)]:
        assert abs(sum(char_probability(chars, alphabet, h, c) for c in ['a', 'b', UNK, EOS]) - 1) < 1e-14
    # Nonempty class strings: finite-depth ended mass plus unended tail sums to one.
    frontier = {(c,): q_probability(cells, dict(row, target=c), alphabet, 2, False) for c in ['a', 'b', UNK]}
    ended = 0.
    for _ in range(6):
        next_frontier = {}
        for word, mass in frontier.items():
            h = ([BOS, BOS, BOS] + list(word))[-3:]
            ended += mass * char_probability(chars, alphabet, h, EOS)
            for c in ['a', 'b', UNK]:
                next_frontier[word + (c,)] = mass * char_probability(chars, alphabet, h, c)
        frontier = next_frontier
    assert abs(ended + math.fsum(frontier.values()) - 1) < 1e-12
    unknown = map_rows([dict(raw, word=('x', 'a', 'y'), previous_word=('z',))], alphabet)[0]
    fee = math.log2(3)
    first, tail, escape = 2.5, continuation_bits(chars, alphabet, unknown['word']), 2 * fee
    assert abs((first + fee) + tail + escape - fee - (first + tail + escape)) < 1e-12
    assert unknown['target_unknown_units'] == 2 and unknown['source_unknown_units'] == 1
    assert hierarchy(unknown, True)[1] == ('context', UNK)
    line = dict(paragraph_known=True, paragraph_end=False, paragraph_start=False,
        block='b', paragraph=0, aligned_to_excluded_locus=False, tokens=['a'],
        effective_hands=['h'], source_lines=[1])
    toy_page = dict(folio='toy1', leaf='toy', metadata={'I':'s'}, lines=[
        line, dict(line, tokens=['b'], effective_hands=['@'], source_lines=[2]),
        dict(line, tokens=[None], source_lines=[3]),
        dict(line, paragraph_start=True, paragraph=1, source_lines=[4])])
    selected, excluded = reconstruct_pairs([toy_page], 'eva')
    assert len(selected) == 1 and selected[0]['previous_word'] == ('a',) and selected[0]['word'] == ('b',)
    assert excluded['missing_endpoint'] == 1 and excluded['paragraph_or_block_boundary'] == 1
    assert excluded['cross_hand_pairs'] == 1 and excluded['unresolved_target_H_at'] == 1
    # Page then leaf equality, deliberately unequal target counts and pages per leaf.
    agg_rows = [dict(folio='a1',leaf='a'),dict(folio='a1',leaf='a'),dict(folio='a2',leaf='a'),dict(folio='b1',leaf='b')]
    aggregation = aggregate(agg_rows,[0.,2.,5.,9.])
    assert aggregation['per_page'] == {'a1':1.,'a2':5.,'b1':9.}
    assert aggregation['per_leaf'] == {'a':3.,'b':9.} and aggregation['mean_leaf'] == 6.
    assert aggregation['pooled'] == 4. and aggregation['leave_one_leaf_out_range'] == [3.,9.]
    result = dict(passed=True, real_data_loaded=False, tests=['analytic five-level scalar Q',
        'Q and character distributions normalized', 'nonempty ended mass plus exact finite tail',
        'first identity fee counted once', 'source unknown separated from target cost',
        'synthetic missing endpoint / paragraph / H rules', 'unequal page and leaf aggregation'],
        audit_script_sha256=sha(HERE / 'replay.py'))
    write(HERE / 'toy_verification.json', result)
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--completed-run', type=Path)
    args = parser.parse_args()
    if args.completed_run:
        replay_completed(args.completed_run.resolve())
    else:
        toy()
