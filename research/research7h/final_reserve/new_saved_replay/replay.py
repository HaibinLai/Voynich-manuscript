#!/usr/bin/env python3
"""Independent complete-probability and position replay of a saved final packet.

No corpus/worker imports or new target selection. Output must be new. The caller
authorizes --run; initial validation uses preflight_v1 only. Reusable for a later
explicitly authorized reserve packet without changing models or fitting choices.
"""
from collections import Counter, defaultdict
from pathlib import Path
from functools import lru_cache
import argparse
import ast
import copy
import datetime
import gzip
import hashlib
import importlib.util
import json
import math
import re
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TRACKED = {}


def sha(path):
    path = Path(path).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path in TRACKED:
        assert TRACKED[path] == digest, ('Input changed', path.name)
    else:
        TRACKED[path] = digest
    return digest


def read(path):
    path = Path(path)
    sha(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def npz(path):
    sha(path)
    with np.load(path, allow_pickle=False) as stream:
        return {key: stream[key] for key in stream.files}


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')


def module(name, path):
    sha(path)
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def metadata_scalar_helpers():
    """Extract pure independent functions, avoiding metadata's corpus import."""
    path = ROOT/'metadata_sensitivity/replay.py'
    sha(path)
    names = {'word', 'train_rows', 'compare', 'copy_replay', 'allograph_replay', 'boundary_replay'}
    parsed = ast.parse(path.read_text(), filename=str(path))
    definitions = [n for n in parsed.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in definitions} == names
    namespace = dict(ROOT=ROOT, read=read, Counter=Counter, defaultdict=defaultdict,
        lru_cache=lru_cache, math=math, re=re, np=np, UNK='<UNK>', BOS='<BOS>', EOS='<EOS>',
        scalar=module('saved_packet_allograph_scalar', ROOT/'allograph_factor/replay.py'))
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), 'exec'), namespace)
    return namespace, sorted(names)


def packet_family(run, family, name):
    receipt = read(run/f'{family}_{name}.json')
    rows_path, scores_path = run/receipt['rows_path'], run/receipt['scores_path']
    assert rows_path.parent.resolve() == run and scores_path.parent.resolve() == run
    assert sha(rows_path) == receipt['rows_sha256']
    assert sha(scores_path) == receipt['scores_sha256']
    rows, saved = read(rows_path), npz(scores_path)
    assert len(rows) == receipt['targets'] and all(len(a) == len(rows) for a in saved.values())
    return rows, saved


def old_hand_training(source, rep, name, helpers):
    pages = read(ROOT/'metadata_sensitivity/inputs'/f'{source}_train_legacy.json.gz')
    pages = copy.deepcopy(pages)
    assert all(p['split'] in ('train', 'legacy') for p in pages)
    for page in pages:
        for line in page['lines']:
            line['effective_hands'] = [page['metadata'].get('H', '?')] * len(line['tokens'])
    train = helpers['train_rows'](pages, rep)
    frozen = read(ROOT/'allograph_factor/inputs'/f'{name}_train_dev.json.gz')['train']
    projection = lambda row: (tuple(row['word']), row['hand'], row['position'])
    assert list(map(projection, train)) == list(map(projection, frozen))
    return pages, train


def extra_escape_checks(name, rows, saved):
    errors = {}
    for kind in ('FP', 'KT', 'both'):
        cfg = read(ROOT/'allograph_factor/configs'/f'{name}_{kind}.json')
        mapping = cfg['map']
        for field, alphabet, size, mapper in [
            ('base_escape', set(cfg['original_alphabet']), cfg['raw_escape_size'], lambda c:c),
            (kind+'_quotient_escape', set(cfg['quotient_alphabet']), cfg['quotient_escape_size'], lambda c:mapping.get(c,c))]:
            calculated = np.asarray([sum(mapper(c) not in alphabet for c in r['word']) * math.log2(size) for r in rows])
            errors[field] = max(errors.get(field, 0.), float(np.max(np.abs(calculated-saved[field]))))
    assert max(errors.values()) < 1e-10
    return errors


def paragraph_replay(name, rows, saved, helper):
    folder = ROOT/'paragraph_factor'/name
    config = read(folder/'frozen_config.json')
    path = folder/'probability_tables.json.gz'
    assert sha(path) == config['probability_tables_sha256']
    tables = read(path)
    body, position = helper.instantiate(tables['body']), helper.instantiate(tables['position'])
    factors = {}
    prefix_error = 0.
    for kind in ('gallows', 'any_first'):
        setting = config['selected']['factors'][kind]['mixture']
        factor = tables['factors'][f"{kind}_beta{setting['beta']}"]
        if kind == 'gallows':
            prior = {c:body['first'][c] for c in 'ktpf'}
            prior['<NONE>'] = math.fsum(p for c,p in body['first'].items() if c not in 'ktpf')
            z = prior['<NONE>'] * body['nonempty']
            assert abs(z-factor['z_none']) < 1e-11
        else:
            prior, z = body['first'], None
        count = factor['training_counts']['paragraph_first']
        total = sum(count.values())
        assert total == factor['training_totals']['paragraph_first']
        pi = {c:(count.get(c,0)+factor['beta']*p)/(total+factor['beta']) for c,p in prior.items()}
        assert abs(math.fsum(pi.values())-1) < 1e-11
        prefix_error = max(prefix_error, max(abs(p-factor['prefix_probabilities']['paragraph_first'][c]) for c,p in pi.items()))
        factors[kind] = (setting, pi, z)
    arrays = {k:[] for k in ('body_full', 'position_full', 'gallows_selected', 'any_first_selected')}
    for row in rows:
        assert row['position'] == 'paragraph_first' and row['slot'] == 0
        word = tuple(row['word'])
        base = body['full_log'](word)
        arrays['body_full'].append(-base)
        arrays['position_full'].append(-helper.mix(base, position['full_log'](word), config['selected']['position']['weight']))
        for kind, (setting, pi, z) in factors.items():
            prefix = word[0] if kind == 'any_first' or word[0] in 'ktpf' else '<NONE>'
            root = word[1:] if prefix != '<NONE>' else word
            assert (root if prefix == '<NONE>' else (prefix,)+root) == word
            full_factor = math.log2(pi[prefix]) + body['raw_log'](root) - (math.log2(z) if prefix == '<NONE>' else 0.)
            arrays[kind+'_selected'].append(-helper.mix(base, full_factor, setting['weight']))
    errors = {k:float(np.max(np.abs(np.asarray(v)-saved[k]))) for k,v in arrays.items()}
    assert max(errors.values()) < 1e-10
    return dict(errors=errors, prefix_probability_max_error=prefix_error,
        table_max_error=max(body['table_max_error'], position['table_max_error']),
        original_word_identity_and_none_support_checked=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    run, out = args.run.resolve(), args.output.resolve()
    assert run.is_dir() and not out.exists()
    complete = read(run/'complete.json')
    assert complete['all_passed'] is True and complete['mode'] in ('preflight', 'reserve')
    assert complete['freeze_sha256'] == sha(HERE.parent/'freeze.json')
    assert len(complete['completed']) == 12 and not complete['failures']
    assert not any('corpus' in key or key.endswith('worker') for key in sys.modules)
    helpers, names = metadata_scalar_helpers()
    paragraph = module('saved_packet_paragraph_scalar', ROOT/'paragraph_factor/replay.py')
    position = module('saved_packet_position_adapter', HERE/'position_adapter.py')
    out.mkdir(parents=True)
    started = time.monotonic()
    save(out/'execution_receipt.json', {'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'mode':complete['mode'], 'input_run_name':run.name, 'complete_sha256':sha(run/'complete.json'),
        'script_sha256':sha(Path(__file__)), 'raw_corpus_reopened':False, 'target_selection_performed':False})
    findings, positions = [], []
    try:
        for name in ('ZL_EVA', 'ZL_merged', 'IT_EVA'):
            rep = 'merged' if name == 'ZL_merged' else 'eva'
            source = 'IT2a-n' if name == 'IT_EVA' else 'ZL3b-n'
            pages, train = old_hand_training(source, rep, name, helpers)
            for family in ('copy', 'allograph', 'boundary', 'paragraph'):
                rows, scores = packet_family(run, family, name)
                alias = {'inline__'+k:v for k,v in scores.items()}
                if family == 'copy':
                    errors = helpers['copy_replay'](train, rows, alias, read(ROOT/'copy_prediction/configs'/f'{name}.json'))
                    detail = {'errors':errors}
                elif family == 'allograph':
                    errors = helpers['allograph_replay'](train, rows, alias, name)
                    errors.update(extra_escape_checks(name, rows, scores))
                    detail = {'errors':errors}
                elif family == 'boundary':
                    detail = {'errors':helpers['boundary_replay'](pages, rep, train, rows, alias, name)}
                else:
                    detail = paragraph_replay(name, rows, scores, paragraph)
                finding = dict(name=name, family=family, targets=len(rows), **detail)
                findings.append(finding)
                save(out/f'{family}_{name}.json', finding)
                print(json.dumps({'name':name, 'family':family, 'max_error':max(detail['errors'].values())}), flush=True)
            item = position.replay_position(name, run, read, npz, ROOT, sha)
            positions.append(item)
            save(out/f'position_{name}.json', item)
            print(json.dumps({'name':name, 'position_permutations':sum(r['all_permutations'] for r in item['findings'])}), flush=True)
        assert not any('corpus' in key or key.endswith('worker') for key in sys.modules)
        for path, before in list(TRACKED.items()):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        files = []
        for path, digest in sorted(TRACKED.items()):
            try: relative = str(path.relative_to(ROOT))
            except ValueError: relative = 'supplied_run/'+str(path.relative_to(run))
            files.append({'path':relative, 'bytes':path.stat().st_size, 'sha256':digest})
        result = {'all_passed':True, 'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'mode':complete['mode'], 'input_run_name':run.name, 'complete_sha256':sha(run/'complete.json'),
            'probability_tasks':findings, 'position_tasks':positions,
            'maximum_probability_cost_error':max(max(f['errors'].values()) for f in findings),
            'position_permutations':sum(f['all_permutations'] for p in positions for f in p['findings']),
            'maximum_position_gain_error':max(f['max_gain_difference'] for p in positions for f in p['findings']),
            'maximum_position_movement_error':max(f['max_movement_difference'] for p in positions for f in p['findings']),
            'reused_metadata_scalar_functions':names, 'input_and_helper_hashes':files,
            'all_input_bytes_unchanged':True, 'elapsed_seconds':time.monotonic()-started,
            'raw_corpus_reopened':False, 'new_targets_selected':False, 'models_or_parameters_selected':False,
            'corpus_or_worker_imported':False,
            'saved_reserve_packet_read':complete['mode']=='reserve',
            'position_null_summation':'math.fsum for all 11994 draws; edit paths independently enumerated',
            'scope':'Full probability and position replay only; aggregation/bootstrap/Holm checked separately by saved_output_audit.py.'}
        assert result['position_permutations'] == 11994
        save(out/'verification.json', result)
        print(json.dumps({k:result[k] for k in ['all_passed','mode','maximum_probability_cost_error','position_permutations','maximum_position_gain_error','maximum_position_movement_error','elapsed_seconds']}), flush=True)
    except Exception as exc:
        save(out/'incomplete.json', {'error':str(exc), 'completed_probability_tasks':len(findings),
            'completed_position_tasks':len(positions), 'elapsed_seconds':time.monotonic()-started})
        raise


if __name__ == '__main__':
    main()
