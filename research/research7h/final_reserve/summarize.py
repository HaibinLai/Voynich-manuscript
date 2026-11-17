"""Fixed page-then-leaf contrasts; whole-leaf resamples are not new evidence."""
from pathlib import Path
from collections import defaultdict
import argparse
import datetime
import gzip
import hashlib
import json
import math

import numpy as np

NAMES = ('ZL_EVA', 'ZL_merged', 'IT_EVA')
CONTRASTS = (
    ('style', 'copy', 'global', 'base', 'all_words'),
    ('boundary_last', 'boundary', 'base', 'last', 'nonoverlapping_interior_pairs'),
    ('gallows_vs_position', 'paragraph', 'position_full', 'gallows_selected', 'paragraph_first_words'),
    ('gallows_vs_any_first', 'paragraph', 'any_first_selected', 'gallows_selected', 'paragraph_first_words'),
    ('copy_total', 'copy', 'base', 'edit_HV', 'all_words'),
    ('copy_edit_vs_exact', 'copy', 'exact_HV_matched', 'edit_HV', 'all_words'),
    ('copy_vertical', 'copy', 'edit_H_matched', 'edit_HV', 'all_words'),
    ('allograph_FP', 'allograph', 'base', 'FP_complete', 'all_words'),
    ('allograph_KT', 'allograph', 'base', 'KT_complete', 'all_words'),
    ('allograph_both', 'allograph', 'base', 'both_complete', 'all_words'),
)


def read(path):
    data = path.read_bytes()
    return json.loads(gzip.decompress(data) if path.suffix == '.gz' else data)


def write(path, obj):
    assert not path.exists(), ('Refusing overwrite', path)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def seed_for(name, leaves):
    key = 'final-reserve-bootstrap-v1|' + name + '|' + ','.join(leaves)
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], 'little')


def coordinate(row):
    return row['folio'], row['line'], row['slot']


def page_leaf(rows, values):
    pp, leafmap = defaultdict(list), {}
    for row, value in zip(rows, values):
        pp[row['folio']].append(float(value))
        leafmap[row['folio']] = row['leaf']
    pages = {f: math.fsum(v) / len(v) for f, v in sorted(pp.items())}
    ll = defaultdict(list)
    for folio, value in pages.items():
        ll[leafmap[folio]].append(value)
    leaves = {leaf: math.fsum(v) / len(v) for leaf, v in sorted(ll.items())}
    return pages, leaves


def holm(tails):
    bound, adjusted = 0., {}
    for i, key in enumerate(sorted(tails, key=lambda k: (tails[k], k))):
        bound = max(bound, min(1., (len(tails)-i) * tails[key]))
        adjusted[key] = bound
    return adjusted


def summarize(run):
    for filename in ('summary.json', 'bootstrap_draws.npz', 'bootstrap_means.npz'):
        assert not (run / filename).exists(), ('Refusing overwrite', filename)
    receipt = read(run / 'execution_receipt.json')
    execution_hash = hashlib.sha256((run / 'execution_receipt.json').read_bytes()).hexdigest()
    expected_split = 'confirm' if receipt['mode'] == 'preflight' else 'reserve'
    assert receipt['mode'] in ('preflight', 'reserve')
    for item in receipt['input_pages']:
        assert hashlib.sha256((run / item['path']).read_bytes()).hexdigest() == item['sha256']
    draws, boots, results, supplementary, positions = {}, {}, [], [], {}
    for name in NAMES:
        data = {}
        for family in ('copy', 'allograph', 'paragraph', 'boundary'):
            meta = read(run / (family + '_' + name + '.json'))
            rowpath = run / meta['rows_path']
            scorepath = run / meta['scores_path']
            assert hashlib.sha256(rowpath.read_bytes()).hexdigest() == meta['rows_sha256']
            assert hashlib.sha256(scorepath.read_bytes()).hexdigest() == meta['scores_sha256']
            rows = read(rowpath)
            scores = np.load(scorepath)
            assert len(rows) == meta['targets']
            assert all(len(scores[k]) == len(rows) and np.all(np.isfinite(scores[k])) for k in scores.files)
            assert len({coordinate(r) for r in rows}) == len(rows)
            data[family] = rows, scores
        cr, cs = data['copy']
        ar, ass = data['allograph']
        assert [coordinate(r) for r in cr] == [coordinate(r) for r in ar]
        assert np.max(np.abs(cs['base'] - ass['base'])) < 1e-11, 'Raw baseline changed between families'
        source = 'IT2a-n' if name == 'IT_EVA' else 'ZL3b-n'
        pages = read(run / (source + '_pages.json.gz'))
        assert all(p['split'] == expected_split for p in pages)
        allpages = {p['folio'] for p in pages}
        allleaves = {p['leaf'] for p in pages}
        extras = [(f'allograph_{k}_global_restore', 'allograph', 'base', k + '_complete_global', 'all_words') for k in ('FP', 'KT', 'both')]
        for cid, family, a, b, population in CONTRASTS + tuple(extras):
            rows, arrays = data[family]
            gain = arrays[a] - arrays[b]
            pp, ll = page_leaf(rows, gain)
            leaves = sorted(ll)
            values = np.asarray([ll[k] for k in leaves])
            eligiblepages = set(pp)
            excluded = {'pages': sorted(allpages-eligiblepages), 'leaves': sorted(allleaves-set(leaves))}
            obj = dict(id=cid, representation=name, family=family, model_before=a, model_after=b,
                population=population, words=len(rows), eligible_pages=len(pp), eligible_leaves=len(ll),
                ineligible=excluded, per_page_gain=pp, per_leaf_gain=ll,
                mean_leaf_bits_saved=float(values.mean()) if len(values) else None,
                pooled_bits_saved=float(gain.mean()) if len(gain) else None,
                pooled_before_bits=float(arrays[a].mean()) if len(rows) else None,
                pooled_after_bits=float(arrays[b].mean()) if len(rows) else None,
                no_target_selection_by_score=True)
            if len(values) >= 2:
                key = name + '_' + hashlib.sha256(','.join(leaves).encode()).hexdigest()[:12]
                if key not in draws:
                    rng = np.random.default_rng(seed_for(name, leaves))
                    draws[key] = rng.integers(0, len(leaves), size=(99999, len(leaves)))
                samples = values[draws[key]].mean(axis=1)
                boots[name + '__' + cid] = samples
                quantiles = lambda levels: np.quantile(samples, levels, method='linear').tolist()
                loo = [(float(values.sum()) - float(v)) / (len(values)-1) for v in values]
                obj.update(bootstrap95=quantiles([.025, .975]),
                    bootstrap99_5_primary10=quantiles([.0025, .9975]) if name == 'ZL_EVA' and not cid.endswith('_global_restore') else None,
                    bootstrap99_833_all30=quantiles([.05/60, 1-.05/60]) if not cid.endswith('_global_restore') else None,
                    bootstrap_replicates=99999, bootstrap_draw_key=key, bootstrap_seed=seed_for(name, leaves),
                    quantile_method='linear', leave_one_leaf_out_range=[min(loo), max(loo)],
                    leave_one_leaf_out={leaf: v for leaf, v in zip(leaves, loo)})
            else:
                obj.update(bootstrap95=None, bootstrap99_5_primary10=None, bootstrap99_833_all30=None,
                    uncertainty_unavailable='Fewer than two eligible leaf groups; do not manufacture an interval.')
            sensitivity = {k: v for k, v in ll.items() if k not in ('f15', 'f103')}
            obj['exposure_sensitivity'] = dict(omitted_leaves=['f15', 'f103'], eligible_leaves=len(sensitivity),
                per_leaf=sensitivity, mean_leaf_bits_saved=math.fsum(sensitivity.values()) / len(sensitivity) if sensitivity else None,
                interpretation='Descriptive only; not a replacement primary analysis or a second significance opportunity.')
            (supplementary if cid.endswith('_global_restore') else results).append(obj)
        positions[name] = read(run / ('position_' + name + '.json'))
    assert len(results) == 30 and len(supplementary) == 9
    tails = {name + '_' + label: value['monte_carlo_reference_p'] for name, item in positions.items() for label, value in item['conditions'].items()}
    adjusted = holm(tails)
    for name, item in positions.items():
        for label, value in item['conditions'].items():
            value['holm_reference_p_family6'] = adjusted[name + '_' + label]
    np.savez_compressed(run / 'bootstrap_draws.npz', **draws)
    np.savez_compressed(run / 'bootstrap_means.npz', **boots)
    payload = dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        mode=receipt['mode'], split=expected_split, freeze_sha256=receipt['freeze_sha256'], execution_receipt_sha256=execution_hash,
        primary_representation='ZL_EVA', primary_contrasts=10, all_combinations=30,
        aggregation='mean word loss within each eligible page, equal eligible-page mean within leaf, equal eligible-leaf mean',
        results=results, global_restoration_sensitivity=supplementary, position_specificity=positions,
        caveats=['At most eleven reserved leaf groups; resampling count is not independent sample size.',
            'Percentile intervals are approximate under a whole-leaf sampling model; possible between-leaf dependence remains.',
            'Metadata/layout is supplied, not compressed; positional labels can partly reflect visible initial glyphs.',
            'Representations share source evidence and are not independent replications.',
            'Positive predictive gains are not semantic decoding or proof of historical generation mechanisms.'])
    write(run / 'summary.json', payload)
    print(json.dumps(dict(contrasts=len(results), sensitivity=len(supplementary), position_conditions=len(tails), passed=True)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', type=Path, required=True)
    summarize(parser.parse_args().run)
