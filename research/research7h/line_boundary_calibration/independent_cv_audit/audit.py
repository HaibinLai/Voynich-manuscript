#!/usr/bin/env python3
"""Independent scalar replay of the preselected seed's nine CV searches.

Reads saved synthetic arrays and glyph-free geometry only. It does not import
observer/select, generate randomness, or open any manuscript input or split.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import math
import numpy as np

SEED = 2026111700
ALPHAS = (1, 5, 20, 100, 500)
WEIGHTS = (0.0, 0.25, 0.5, 0.75, 1.0)
RHOS = (0.0, 0.15, 0.5)
SHIFT = (2, 3, 0, 1)
ROW_FIELDS = {'folio', 'leaf', 'line', 'slot', 'hand', 'section', 'previous_length',
              'length', 'position_bin', 'paragraph_line'}
ROUNDING_AUDIT_LIMIT = 5e-13  # Audit equality only, never a selection tolerance.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path):
    return json.loads(path.read_text())


def save_json(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def geometry_audit(skeleton):
    report = {}
    for split in ('train_legacy', 'dev'):
        rebuilt = []
        pages = skeleton[split]['pages']
        for page in pages:
            assert page['split'] in ({'train', 'legacy'} if split == 'train_legacy' else {'dev'})
            for i in range(1, len(page['lines'])):
                previous, current = page['lines'][i-1:i+1]
                if not previous['paragraph_known'] or not current['paragraph_known']:
                    continue
                if previous['paragraph_end'] or current['paragraph_start']:
                    continue
                if previous['block'] != current['block'] or previous['paragraph'] != current['paragraph']:
                    continue
                if previous['aligned_to_excluded_locus'] or current['aligned_to_excluded_locus']:
                    continue
                pl, cl = previous['lengths'], current['lengths']
                if not pl or not cl or pl[-1] is None or cl[0] is None:
                    continue
                rebuilt.append(dict(folio=page['folio'], leaf=page['leaf'], line=i, slot=0,
                    hand=current['effective_hands'][0], section=page['section'],
                    previous_length=pl[-1], length=0, position_bin=0, paragraph_line=0))
        assert rebuilt == skeleton[split]['rows']
        assert all(set(r) == ROW_FIELDS for r in rebuilt)
        assert all(r['length'] == r['position_bin'] == r['paragraph_line'] == 0 for r in rebuilt)
        report[split] = {'rows': len(rebuilt), 'pages': len({r['folio'] for r in rebuilt}),
                         'leaves': len({r['leaf'] for r in rebuilt}), 'reconstructed_exactly': True}
    train = skeleton['train_legacy']['rows']
    leaves = {r['leaf'] for r in train}
    ordered = sorted(leaves, key=lambda leaf: hashlib.sha256(('line-calibration-fold-v1|' + leaf).encode()).digest())
    folds = {leaf: i % 3 for i, leaf in enumerate(ordered)}
    assert folds == skeleton['inner_leaf_fold']
    assert leaves.isdisjoint(r['leaf'] for r in skeleton['dev']['rows'])
    assert (len(train), len(leaves)) == (1548, 57)
    assert (report['dev']['rows'], report['dev']['leaves']) == (647, 17)
    fold_report = []
    for k in range(3):
        fit_leaves = {leaf for leaf in leaves if folds[leaf] != k}
        held_leaves = leaves - fit_leaves
        assert fit_leaves.isdisjoint(held_leaves)
        fold_report.append({'fold': k, 'fit_leaves': sorted(fit_leaves), 'held_leaves': sorted(held_leaves),
            'fit_rows': sum(folds[r['leaf']] != k for r in train),
            'held_rows': sum(folds[r['leaf']] == k for r in train), 'no_leaf_overlap': True})
    report['folds'] = fold_report
    report['train_dev_leaf_disjoint'] = True
    return report, folds


def level_keys(row, x, conditioned):
    # Levels stay distinct even when constant geometry makes counts coincide.
    h, i, length = row['hand'], row['section'], min(10, row['previous_length'])
    base = [(), (h, i), (h, i, 0), (h, i, 0, length),
            (h, i, 0, length, row['position_bin'], row['paragraph_line'])]
    if conditioned:
        return [(), (x,)] + [key + (x,) for key in base[1:]]
    return base


def fit_levels(rows, xs, ys, fit_indices, conditioned):
    levels = [dict() for _ in range(6 if conditioned else 5)]
    for j in fit_indices:
        for level, key in zip(levels, level_keys(rows[j], xs[j], conditioned)):
            if key not in level:
                level[key] = [0, 0, 0, 0]
            level[key][ys[j]] += 1
    return levels


def scalar_distribution(levels, row, x, alpha, conditioned):
    out = []
    for y in range(4):
        probability = 0.25
        for level, key in zip(levels, level_keys(row, x, conditioned)):
            counts = level.get(key)
            if counts is not None:
                probability = (counts[y] + alpha * probability) / (sum(counts) + alpha)
        assert 0 < probability < 1
        out.append(probability)
    return out


def mean_nll(probabilities):
    return math.fsum(-math.log2(p) for p in probabilities) / len(probabilities)


def replay_search(rows, xs, ys, folds, saved, label, saved_oof):
    n = len(rows)
    oof = {kind: {alpha: [None] * n for alpha in ALPHAS} for kind in ('base', 'feature')}
    normalization_error = 0.0
    for fold in range(3):
        fit = [j for j, r in enumerate(rows) if folds[r['leaf']] != fold]
        held = [j for j, r in enumerate(rows) if folds[r['leaf']] == fold]
        assert fit and held
        assert {rows[j]['leaf'] for j in fit}.isdisjoint(rows[j]['leaf'] for j in held)
        for kind, conditioned in [('base', False), ('feature', True)]:
            counts = fit_levels(rows, xs, ys, fit, conditioned)
            for alpha in ALPHAS:
                for j in held:
                    distribution = scalar_distribution(counts, rows[j], xs[j], alpha, conditioned)
                    normalization_error = max(normalization_error, abs(math.fsum(distribution) - 1))
                    oof[kind][alpha][j] = distribution[ys[j]]
    assert all(all(p is not None for p in probabilities) for group in oof.values() for probabilities in group.values())
    base_grid = [{'alpha': a, 'loss': mean_nll(oof['base'][a])} for a in ALPHAS]
    base_choice = min(base_grid, key=lambda r: (r['loss'], -r['alpha']))
    assert len(saved['base_grid']) == 5 and {a for _, a in saved['base_grid']} == set(ALPHAS)
    saved_base = {a: loss for loss, a in saved['base_grid']}
    base_error = max(abs(r['loss'] - saved_base[r['alpha']]) for r in base_grid)
    # Use the actually recorded baseline to audit the recorded mixture grid.
    # An independently chosen different baseline is separately reported as a tie.
    selected_base = saved['base_alpha']
    feature_grid = []
    for alpha in ALPHAS:
        for weight in WEIGHTS:
            probabilities = [(1-weight)*b + weight*c for b, c in zip(oof['base'][selected_base], oof['feature'][alpha])]
            feature_grid.append({'alpha': alpha, 'weight': weight, 'loss': mean_nll(probabilities)})
    choice = min(feature_grid, key=lambda r: (r['loss'], r['weight'], -r['alpha']))
    assert len(saved['feature_grid']) == 25
    saved_grid = {(r['alpha'], r['weight']): r['loss'] for r in saved['feature_grid']}
    assert set(saved_grid) == {(a, w) for a in ALPHAS for w in WEIGHTS}
    feature_error = max(abs(r['loss'] - saved_grid[(r['alpha'], r['weight'])]) for r in feature_grid)
    recorded_base = min(saved['base_grid'], key=lambda p: (p[0], -p[1]))[1]
    recorded_feature = min(saved['feature_grid'], key=lambda r: (r['loss'], r['weight'], -r['alpha']))
    assert recorded_base == saved['base_alpha']
    assert (recorded_feature['alpha'], recorded_feature['weight']) == (saved['alpha'], saved['weight'])
    tie_notes = []
    base_matches = base_choice['alpha'] == saved['base_alpha']
    if not base_matches:
        gap = next(r['loss'] for r in base_grid if r['alpha'] == saved['base_alpha']) - base_choice['loss']
        assert abs(gap) <= ROUNDING_AUDIT_LIMIT
        tie_notes.append({'grid': 'base', 'independent': base_choice, 'recorded_alpha': saved['base_alpha'], 'independent_loss_gap': gap})
    feature_matches = (choice['alpha'], choice['weight']) == (saved['alpha'], saved['weight'])
    if not feature_matches:
        selected_loss = next(r['loss'] for r in feature_grid if (r['alpha'], r['weight']) == (saved['alpha'], saved['weight']))
        gap = selected_loss - choice['loss']
        assert abs(gap) <= ROUNDING_AUDIT_LIMIT
        tie_notes.append({'grid': 'feature', 'independent': choice,
                          'recorded_alpha': saved['alpha'], 'recorded_weight': saved['weight'], 'independent_loss_gap': gap})
    assert base_error <= ROUNDING_AUDIT_LIMIT and feature_error <= ROUNDING_AUDIT_LIMIT
    assert normalization_error <= ROUNDING_AUDIT_LIMIT
    for kind in oof:
        for alpha, probabilities in oof[kind].items():
            saved_oof[f'{label}__{kind}__alpha{alpha}'] = np.asarray(probabilities)
    zero_weight_losses = [r['loss'] for r in feature_grid if r['weight'] == 0]
    assert len(set(zero_weight_losses)) == 1
    return {'name': label, 'base_grid': base_grid, 'feature_grid': feature_grid,
            'maximum_base_grid_error_bits': base_error, 'maximum_feature_grid_error_bits': feature_error,
            'maximum_normalization_error': normalization_error, 'base_selection_matches': base_matches,
            'feature_selection_matches': feature_matches, 'independent_base_selection': base_choice,
            'independent_feature_selection': choice,
            'recorded_selection': {k: saved[k] for k in ('base_alpha', 'alpha', 'weight')},
            'recorded_exact_tie_rule_passed': True, 'zero_weight_alpha_invariance_exact': True,
            'rounding_tie_notes': tie_notes, 'folds': 3, 'targets_used_in_cv': n,
            'mixture_grid_uses_recorded_base_oof': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, out = args.source.resolve(), args.output.resolve()
    assert not out.exists(), 'Independent audit output must be a new directory'
    complete_path = root/'run_v1/complete.json'
    complete = load_json(complete_path)
    assert complete['all_passed'] is True and len(complete['cases']) == 60
    assert sha(root/'run_v1/summary.json') == complete['summary_sha256']
    skeleton_path = root/'skeleton.json.gz'
    receipt = load_json(root/'skeleton_receipt.json')
    assert sha(skeleton_path) == receipt['sha256']
    skeleton = json.loads(gzip.decompress(skeleton_path.read_bytes()))
    geometry, folds = geometry_audit(skeleton)
    rows = skeleton['train_legacy']['rows']
    inputs = [complete_path, root/'run_v1/summary.json', skeleton_path,
              root/'skeleton_receipt.json', root/'protocol.txt', root/'observer.py', root/'freeze.json']
    reports, all_oof = [], {}
    cases_by_path = {r['path']: r['sha256'] for r in complete['cases']}
    for ri, rho in enumerate(RHOS):
        case_path = root/f'run_v1/cases/seed{SEED}_rho{ri}.json'
        assert sha(case_path) == cases_by_path[str(case_path.relative_to(root/'run_v1'))]
        case = load_json(case_path)
        assert case['seed'] == SEED and case['rho'] == rho
        array_path = root/f'run_v1/cases/seed{SEED}_rho{ri}_synthetic.npz'
        assert sha(array_path) == case['synthetic_sha256']
        assert case['synthetic_path'] == str(array_path.relative_to(root/'run_v1'))
        inputs.extend([case_path, array_path])
        with np.load(array_path, allow_pickle=False) as arrays:
            for fit, stream, permutation in [('source', 'A', (0, 1, 2, 3)),
                    ('target_identity', 'B', (0, 1, 2, 3)), ('target_shift', 'B', SHIFT)]:
                # T_* arrays are never accessed. All CV observations belong to A/B.
                xs = [int(x) for x in arrays[stream+'_x']]
                original_ys = [int(y) for y in arrays[stream+'_y']]
                assert len(xs) == len(original_ys) == len(rows)
                assert set(xs) <= set(range(4)) and set(original_ys) <= set(range(4))
                ys = [permutation[y] for y in original_ys]
                reports.append(replay_search(rows, xs, ys, folds, case['configs'][fit],
                    f'seed{SEED}_rho{ri}_{fit}', all_oof))
    out.mkdir(parents=True)
    array_output = out/'scalar_oof_probabilities.npz'
    np.savez_compressed(array_output, **all_oof)
    result = {'all_passed': True, 'completed_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'scope': 'Independent scalar CV replay; nine preselected searches, not all 180 selection grids',
        'seed': SEED, 'rhos': list(RHOS), 'searches': len(reports), 'base_grid_points': 45,
        'mixture_grid_points': 225, 'folds': 3, 'geometry': geometry, 'search_results': reports,
        'maximum_base_grid_error_bits': max(r['maximum_base_grid_error_bits'] for r in reports),
        'maximum_feature_grid_error_bits': max(r['maximum_feature_grid_error_bits'] for r in reports),
        'maximum_normalization_error': max(r['maximum_normalization_error'] for r in reports),
        'exact_selection_matches': sum(r['base_selection_matches'] and r['feature_selection_matches'] for r in reports),
        'rounding_tie_notes': [dict(search=r['name'], **note) for r in reports for note in r['rounding_tie_notes']],
        'audit_only_rounding_tolerance': ROUNDING_AUDIT_LIMIT,
        'selection_tolerance_added': False, 'observed_selections_changed': False,
        'new_random_samples_generated': False, 'real_manuscript_text_loaded': False,
        'confirm_loaded': False, 'reserve_loaded': False, 'synthetic_evaluation_T_accessed': False,
        'imports_observer_or_select': False,
        'inputs': [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in inputs],
        'script_sha256': sha(Path(__file__)),
        'independent_oof': {'path': array_output.name, 'sha256': sha(array_output), 'arrays': len(all_oof)}}
    save_json(out/'verification.json', result)
    print(json.dumps({k: result[k] for k in ['all_passed', 'searches', 'maximum_base_grid_error_bits',
        'maximum_feature_grid_error_bits', 'maximum_normalization_error', 'exact_selection_matches', 'rounding_tie_notes']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
