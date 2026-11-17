"""Score fixed models on supplied pages; each family runs in a fresh process.

No tuning entry point is called. The parent is the only component allowed to
return reserved pages from the shared parser, and does so only after its gate.
"""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import inspect
import json
import math
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import corpus


def raw_bytes(path):
    path = Path(path)
    if path.exists():
        return gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    compressed = Path(str(path) + '.gz')
    assert compressed.exists(), path
    return gzip.decompress(compressed.read_bytes())


def read(path):
    return json.loads(raw_bytes(path))


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    assert not path.exists(), ('Refusing overwrite', path)
    path.write_bytes(gzip.compress(payload, mtime=0) if path.suffix == '.gz' else payload)


def coordinates(rows):
    return [(r['folio'], r['line'], r['slot']) for r in rows]


def model_origin(obj, expected):
    actual = Path(inspect.getsourcefile(obj)).resolve()
    assert actual == expected.resolve(), ('Unexpected imported implementation', actual, expected)
    return dict(path=str(actual.relative_to(ROOT.parent)), sha256=sha_bytes(actual.read_bytes()))


def same_words(left, right, right_key='word'):
    assert coordinates(left) == coordinates(right)
    assert all(tuple(a['word']) == tuple(b[right_key]) for a, b in zip(left, right))


def target_identity_cost(word, alphabet, omega):
    assert word and set(word) <= set(omega)
    unseen = len(set(omega) - set(alphabet))
    count = sum(c not in alphabet for c in word)
    assert unseen > 0 or count == 0
    return count, count * math.log2(unseen) if unseen else 0.


def eligibility(pages, rows):
    slots = sum(len(line['tokens']) for page in pages for line in page['lines'])
    missing = sum(token is None for page in pages for line in page['lines'] for token in line['tokens'])
    assert len(rows) <= slots-missing
    return dict(scope='Within parsed prose loci; non-prose labels/circles are excluded upstream by the fixed parser.',
        parsed_prose_slots=slots, missing_or_ambiguous_slots=missing, retained_known_slots=slots-missing,
        scored_target_slots=len(rows), known_slots_excluded_by_population_rule=slots-missing-len(rows),
        unknown_identity_units_are_encoded_not_omitted=True)


def basic_records(pages, rep):
    rows = []
    for page in pages:
        for li, line in enumerate(page['lines']):
            for slot, token in enumerate(line['tokens']):
                if token is None:
                    continue
                rows.append(dict(folio=page['folio'], leaf=page['leaf'], line=li,
                    slot=slot, word=tuple(corpus.units(token, rep)), hand=page['metadata'].get('H', '?'),
                    position='paragraph_first' if slot == 0 and line['paragraph_start'] else
                    'line_first' if slot == 0 else 'other'))
    return rows


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def copy_scores(pages, source, rep, name, output, check):
    folder = ROOT / 'copy_prediction'
    sys.path.insert(0, str(folder))
    from copy_models import Baseline, make_records, copy_arrays, score_selected
    from reference_models import BodyLM
    origins = [model_origin(Baseline, folder / 'copy_models.py'), model_origin(BodyLM, folder / 'reference_models.py')]
    cfg = read(folder / 'configs' / (name + '.json'))
    alphabet = set(cfg['alphabet'])
    trainp = corpus.load(source, splits=['train', 'legacy'])
    train = make_records(trainp, corpus.units, rep, alphabet)
    assert {c for r in train for c in r['word']} == alphabet
    base = Baseline(train, alphabet, rep)
    base.weights = tuple(cfg['baseline_weights'])
    rows = make_records(pages, corpus.units, rep, alphabet)
    logp = base.scores(rows)
    arrays, available, hits = copy_arrays(rows, base, logp)
    scores = {k: -v for k, v in score_selected(logp, arrays, cfg['selected']).items()}
    scores['global'] = -base.components(rows)[:, 0]
    if check:
        prior = np.load(folder / 'scores' / (name + '.npz'))
        oldrows = read(folder / 'targets' / (name + '.json'))
        same_words(oldrows, rows)
        for oldrow, row in zip(oldrows, rows):
            for key in ('H', 'V'):
                canonical = lambda value: json.loads(json.dumps(value))
                assert canonical(oldrow[key]) == canonical(row[key]), (row['folio'], row['line'], row['slot'], key)
            assert oldrow['unknown_units'] == row['unknown']
        errors = {k: float(np.max(np.abs(scores[k] + prior[k]))) for k in prior.files}
        assert max(errors.values()) < 1e-11, errors
    else:
        errors = None
    dump_scores(output, 'copy', name, rows, scores, dict(preflight_errors=errors,
        target_unknown_units=sum(r['unknown'] for r in rows),
        target_escape_bits=sum(r['unknown'] for r in rows) * math.log2(base.escape_size) if base.escape_size else 0.,
        baseline_weights=list(base.weights), selected=cfg['selected'], model_origins=origins, eligibility=eligibility(pages, rows)))
    # The frozen implementation writes only into this new run's position folder.
    e = import_file('frozen_position_experiment', folder / 'position_specificity' / 'experiment.py')
    e.P = output / 'position'
    e.P.mkdir(exist_ok=True)
    choice = {k: cfg['selected'][k] for k in ('edit_HV', 'edit_H_matched')}
    state = e.Perturbation(pages, base, choice, rep)
    expected = -(scores['edit_HV'] - scores['edit_H_matched'])
    assert np.max(np.abs(state.observed_vector - expected)) < 1e-11
    conditions = {}
    for coarse in (False, True):
        label = 'coarse' if coarse else 'exact'
        seed = e.seed_for('position-specificity-confirm-v1', rep, label) if check else \
            e.seed_for('final-reserve-position-v1', name, label)
        result = state.run(coarse, 1999, seed, name + '_' + label, deep_check=True)
        if check:
            historical = np.load(folder / 'position_specificity' / 'nulls' / ('confirm_' + name + '_' + label + '.npz'))
            generated = np.load(e.P / result['null_array'])
            result['preflight_array_errors'] = {k: float(np.max(np.abs(generated[k] - historical[k]))) for k in historical.files}
            assert max(result['preflight_array_errors'].values()) < 1e-11
        conditions[label] = result
    write(output / ('position_' + name + '.json'), dict(name=name, conditions=conditions))


def allograph_scores(pages, source, rep, name, output, check):
    folder = ROOT / 'allograph_factor'
    sys.path.insert(0, str(folder))
    from models import StyleLM, Restore, mapping, quotient, transform, universe
    from reference_models import BodyLM
    origins = [model_origin(StyleLM, folder / 'models.py'), model_origin(Restore, folder / 'models.py'),
        model_origin(BodyLM, folder / 'reference_models.py')]
    rows = basic_records(pages, rep)
    cfgs = {k: read(folder / 'configs' / (name + '_' + k + '.json')) for k in ('FP', 'KT', 'both')}
    cfg0 = cfgs['FP']
    raw = raw_bytes(folder / cfg0['input_path'])
    assert sha_bytes(raw) == cfg0['input_sha256']
    train = json.loads(raw)['train']
    lm = StyleLM(train, universe(rep))
    lm.weights = tuple(cfg0['raw_weights'])
    scores = {'base': -lm.scores(rows)}
    scores['base_escape'] = lm.escape(rows)[1]
    errors = {}
    for kind, cfg in cfgs.items():
        assert cfg['raw_weights'] == cfg0['raw_weights']
        assert cfg['input_path'] == cfg0['input_path'] and cfg['input_sha256'] == sha_bytes(raw)
        mp = mapping(kind, rep)
        assert mp == cfg['map']
        qlm = StyleLM(transform(train, mp), quotient(universe(rep), mp))
        qlm.weights = tuple(cfg['quotient_weights'])
        restore = Restore(train, mp)
        qrows = transform(rows, mp)
        q = -qlm.scores(qrows)
        rr = -restore.scores(rows, **{k: cfg['restore_selected'][k] for k in ('depth', 'alpha')})
        rg = -restore.scores(rows, **{k: cfg['restore_global'][k] for k in ('depth', 'alpha')})
        arrays = dict(base=scores['base'], quotient=q, restoration=rr, restoration_global=rg,
            complete=q+rr, complete_global=q+rg, base_escape=scores['base_escape'],
            quotient_escape=qlm.escape(qrows)[1])
        for key, value in arrays.items():
            if key not in ('base', 'base_escape'):
                scores[kind + '_' + key] = value
        for r in rows:
            assert restore.decode(*restore.encode(r['word'])) == tuple(r['word'])
        if check:
            prior = np.load(folder / 'scores' / (name + '_' + kind + '.npz'))
            oldrows = read(folder / 'targets' / (name + '.json'))
            same_words(rows, oldrows)
            errors[kind] = {k: float(np.max(np.abs(value - prior[k]))) for k, value in arrays.items()}
            assert max(errors[kind].values()) < 1e-11
    dump_scores(output, 'allograph', name, rows, scores, dict(preflight_errors=errors if check else None,
        model_origins=origins, eligibility=eligibility(pages, rows)))


def paragraph_scores(pages, source, rep, name, output, check):
    folder = ROOT / 'paragraph_factor'
    sys.path.insert(0, str(folder))
    from models import BodyLM, PrefixFactor, logmix
    origins = [model_origin(BodyLM, folder / 'models.py'), model_origin(PrefixFactor, folder / 'models.py')]
    cfg = read(folder / name / 'frozen_config.json')
    assert sha_bytes((folder / name / 'probability_tables.json.gz').read_bytes()) == cfg['probability_tables_sha256']
    tables = read(folder / name / 'probability_tables.json.gz')
    body = BodyLM.from_payload(tables['body'])
    pos = BodyLM.from_payload(tables['position'])
    factors = {k: PrefixFactor.from_payload(body, v) for k, v in tables['factors'].items()}
    rows = [r for r in basic_records(pages, rep) if r['position'] == 'paragraph_first']
    scores = {k: [] for k in ('body_full', 'position_full', 'gallows_selected', 'any_first_selected')}
    for r in rows:
        w = r['word']
        base = body.logp_full(w)
        scores['body_full'].append(-base)
        scores['position_full'].append(-logmix(base, pos.logp_full(w), cfg['selected']['position']['weight']))
        for kind in ('gallows', 'any_first'):
            chosen = cfg['selected']['factors'][kind]['mixture']
            factor = factors[kind + '_beta' + str(chosen['beta'])]
            scores[kind + '_selected'].append(-logmix(base, factor.logp(w), chosen['weight']))
    scores = {k: np.asarray(v) for k, v in scores.items()}
    errors = None
    if check:
        oldrows = [json.loads(line) for line in raw_bytes(folder / name / 'confirm_word_scores.jsonl.gz').splitlines()]
        oldrows = [r for r in oldrows if r['position'] == 'paragraph_first']
        same_words(rows, oldrows)
        errors = {k: float(np.max(np.abs(values - np.asarray([r['bits'][k] for r in oldrows])))) for k, values in scores.items()}
        assert max(errors.values()) < 1e-11
    dump_scores(output, 'paragraph', name, rows, scores, dict(preflight_errors=errors, model_origins=origins,
        eligibility=eligibility(pages, rows)))


def boundary_scores(pages, source, rep, name, output, check):
    from boundary_word import pair_records, continuation_logp
    from boundary import Conditional
    from predictive import CharLM
    sys.path.insert(0, str(ROOT / 'paragraph_factor'))
    from models import universe
    origins = [model_origin(Conditional, ROOT / 'boundary.py'), model_origin(CharLM, ROOT / 'predictive.py'),
        model_origin(universe, ROOT / 'paragraph_factor/models.py')]
    suffix = {'ZL_EVA': '', 'ZL_merged': '_merged', 'IT_EVA': '_IT'}[name]
    stem = 'boundary_word_confirm' + suffix
    cfg = read(ROOT / 'results' / (stem + '_frozen_config.json'))
    alphabet = set(cfg['alphabet'])
    trainp = corpus.load(source, splits=['train', 'legacy'])
    words = [tuple(corpus.units(t, rep)) for p in trainp for line in p['lines'] for t in line['tokens'] if t]
    assert {c for word in words for c in word} == alphabet
    selected = cfg['selected']
    lm = CharLM(words, alphabet, selected['char_order'], selected['char_alpha'])
    train = pair_records(trainp, rep, alphabet)
    base = Conditional(train, alphabet, selected['base_alpha'])
    setting = selected['features']['last']
    last = Conditional(train, alphabet, setting['alpha'], 'last')
    rows = pair_records(pages, rep, alphabet)
    lookup = {(r['folio'], r['line'], r['slot']): r for r in basic_records(pages, rep)}
    escape_size = len(universe(rep) - alphabet)
    assert escape_size > 0
    scores = {k: [] for k in ('base', 'last', 'target_escape')}
    for row in rows:
        actual = lookup[(row['folio'], row['line'], row['slot'])]['word']
        target_unknown, escape = target_identity_cost(actual, alphabet, universe(rep))
        continuation = continuation_logp(lm, row['word'])
        bp = base.prob(row)
        mp = (1-setting['weight']) * bp + setting['weight'] * last.prob(row)
        scores['base'].append(-math.log2(bp) - continuation + escape)
        scores['last'].append(-math.log2(mp) - continuation + escape)
        scores['target_escape'].append(escape)
        row['mapped_word'] = row['word']
        row['word'] = actual
        row['target_unknown_units'] = target_unknown
    scores = {k: np.asarray(v) for k, v in scores.items()}
    errors = None
    if check:
        oldrows = read(ROOT / 'results' / (stem + '_pairs.json'))
        assert coordinates(rows) == coordinates(oldrows)
        assert all(tuple(r['mapped_word']) == tuple(o['word']) for r, o in zip(rows, oldrows))
        old = np.load(ROOT / 'results' / (stem + '_scores.npz'))
        errors = {k: float(np.max(np.abs(scores[k] - scores['target_escape'] + old[k]))) for k in ('base', 'last')}
        assert max(errors.values()) < 1e-11
    dump_scores(output, 'boundary', name, rows, scores, dict(preflight_errors=errors,
        target_escape_size=escape_size, target_escape_bits=float(scores['target_escape'].sum()), target_length_input=False,
        model_origins=origins, eligibility=eligibility(pages, rows)))


def dump_scores(output, family, name, rows, scores, extra):
    prefix = family + '_' + name
    npz = output / (prefix + '.npz')
    assert not npz.exists()
    for key, value in scores.items():
        assert len(value) == len(rows) and np.all(np.isfinite(value)), key
    np.savez_compressed(npz, **scores)
    rp = output / (prefix + '_rows.json.gz')
    write(rp, rows)
    write(output / (prefix + '.json'), dict(family=family, name=name, targets=len(rows),
        rows_path=rp.name, scores_path=npz.name, rows_sha256=sha_bytes(rp.read_bytes()),
        scores_sha256=sha_bytes(npz.read_bytes()), completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), **extra))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('family', choices=['copy', 'allograph', 'paragraph', 'boundary'])
    parser.add_argument('--name', choices=['ZL_EVA', 'ZL_merged', 'IT_EVA'], required=True)
    parser.add_argument('--pages', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    pages = read(args.pages)
    expected = 'confirm' if args.preflight else 'reserve'
    assert pages and all(p['split'] == expected for p in pages)
    args.output.mkdir(exist_ok=True, parents=True)
    source = 'IT2a-n.txt' if args.name == 'IT_EVA' else 'ZL3b-n.txt'
    rep = 'merged' if args.name == 'ZL_merged' else 'eva'
    functions = dict(copy=copy_scores, allograph=allograph_scores, paragraph=paragraph_scores, boundary=boundary_scores)
    functions[args.family](pages, source, rep, args.name, args.output, args.preflight)
    print(json.dumps(dict(family=args.family, name=args.name, preflight=args.preflight, passed=True)), flush=True)


if __name__ == '__main__':
    main()
