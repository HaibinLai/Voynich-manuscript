"""Independently recount saved known-answer scores; never fit or decode.

Uses standard library only. Does not import the scorer, runner or adapter.
Defaults refer only to the saved artificial toy. Explicit paths may later point
at frozen main results. Output is stdout unless --out names a NEW file.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re

BASE = Path(__file__).resolve().parents[1]
# Explicit compatibility with preserved toy metadata and the frozen formal scorer.
SCORER_PROFILES = {
    '8af0cd3b91f15a04dca32a6705399c558c17ecc6e7df26d47017f80e4ef35997': 'legacy_toy_metadata',
    '1502efe86d9af5972098e9ff9678ff34834194f3157a6e8e60b2b3f8e6c00b08': 'explicit_applicability_metadata',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def safe_name(path):
    try:
        return str(path.resolve().relative_to(BASE.resolve()))
    except ValueError:
        return 'external-input/' + path.name


def histogram(word):
    result = {}
    for letter in word:
        result[letter] = result.get(letter, 0) + 1
    return result


def quotient(numerator, denominator):
    return {'correct': numerator, 'total': denominator,
            'fraction': numerator / denominator if denominator else None}


def recalculate(truth, cipher, pipe, decoded, condition, variant, vocabulary):
    """Truth is inverted from encryption, not copied from stored score counts."""
    target = truth['words']
    inverse = {encrypted: plain for plain, encrypted in truth['encryption'].items()}
    assert inverse == truth['decryption']
    assert len(target) == len(cipher)
    assert len(truth['permutations']) == len(target)
    for plain, encrypted, order in zip(target, cipher, truth['permutations']):
        assert sorted(order) == list(range(len(plain)))
        assert ''.join(truth['encryption'][plain[i]] for i in order) == encrypted
    count = histogram(''.join(cipher))
    symbols = list(count)
    vocab = set(vocabulary)
    vb = {tuple(sorted(histogram(w).items())) for w in vocab}
    target_in_vocab = [word in vocab for word in target]
    target_bag_in_vocab = [tuple(sorted(histogram(w).items())) in vb for w in target]
    model = pipe or {}
    result = {
        'truth_id': truth['id'], 'input_id': truth.get('input_id', truth['id']),
        'condition': condition, 'variant': variant, 'language': truth['language'],
        'selected_language': model.get('language'),
        'coverage_reference_language': model.get('language', truth['language']),
        'positive': truth.get('kind') != 'nonidentifiable_twin_history',
        'word_count': len(target), 'character_count': sum(map(len, cipher)),
        'observed_character_types': len(symbols),
        'mapping_types': None, 'mapping_weighted': None, 'word_bags': None,
        'exact_words': None, 'decoded_words': None,
        'training_word_coverage': quotient(sum(target_in_vocab), len(target)),
        'training_bag_coverage': quotient(sum(target_bag_in_vocab), len(target)),
        'output_training_word_hit': None, 'truth_words': target,
        'mapping_status': model.get('mapping_status', 'NOT_APPLICABLE_OR_NOT_EXECUTED'),
        'decoder_status': (decoded or {}).get('status', 'NOT_EXECUTED'),
        'reused_primary_result': model.get('reused_primary_result', False),
    }
    found_map = model.get('mapping')
    trace = {'correct_mapping_symbols': [], 'bag_correct_positions': None,
             'exact_correct_positions': None, 'truth_in_vocabulary_positions':
             [i for i, flag in enumerate(target_in_vocab) if flag]}
    if found_map is not None:
        assert model['mapping_status'] == 'PASS'
        assert set(found_map) == set(symbols)
        assert len(set(found_map.values())) == len(found_map)
        trace['correct_mapping_symbols'] = sorted(c for c in symbols if found_map[c] == inverse[c])
        nright = len(trace['correct_mapping_symbols'])
        weighted_right = sum(count[c] for c in trace['correct_mapping_symbols'])
        result['mapping_types'] = quotient(nright, len(symbols))
        result['mapping_weighted'] = quotient(weighted_right, sum(count.values()))
        mapped = [''.join(found_map[c] for c in word) for word in cipher]
        assert mapped == model['mapped_words']
        bag_flags = [histogram(mapped[i]) == histogram(target[i]) for i in range(len(target))]
        trace['bag_correct_positions'] = [i for i, flag in enumerate(bag_flags) if flag]
        result['word_bags'] = quotient(sum(bag_flags), len(target))
    if condition == 'oracle_truekey':
        supplied = [''.join(inverse[c] for c in word) for word in cipher]
        assert all(histogram(a) == histogram(b) for a, b in zip(supplied, target))
        assert decoded['input_words'] == supplied
        result['mapping_status'] = 'PROVIDED_TRUE_KEY_NOT_RECOVERED'
        result['word_bags'] = quotient(len(target), len(target))
        trace['bag_correct_positions'] = list(range(len(target)))
    if decoded and decoded['status'] == 'PASS':
        words = decoded['output_words']
        assert len(words) == len(target)
        exact_flags = [words[i] == target[i] for i in range(len(target))]
        trace['exact_correct_positions'] = [i for i, flag in enumerate(exact_flags) if flag]
        result['decoded_words'] = words
        result['exact_words'] = quotient(sum(exact_flags), len(target))
        result['output_training_word_hit'] = quotient(sum(word in vocab for word in words), len(words))
        result['in_vocabulary_exact'] = quotient(sum(exact_flags[i] for i in range(len(target)) if target_in_vocab[i]), sum(target_in_vocab))
        result['out_of_vocabulary_exact'] = quotient(sum(exact_flags[i] for i in range(len(target)) if not target_in_vocab[i]), len(target) - sum(target_in_vocab))
    return result, trace


def compare(expected, actual, pointer, mismatches):
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(expected) != set(actual):
            mismatches.append({'pointer': pointer, 'expected_keys': sorted(expected), 'actual_keys': sorted(actual)})
        for key in sorted(set(expected) & set(actual)):
            compare(expected[key], actual[key], pointer + '/' + str(key), mismatches)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            mismatches.append({'pointer': pointer, 'expected_length': len(expected), 'actual_length': len(actual)})
        for i, (a, b) in enumerate(zip(expected, actual)):
            compare(a, b, pointer + '/' + str(i), mismatches)
    elif expected != actual:
        mismatches.append({'pointer': pointer, 'expected': expected, 'actual': actual})


def rowmap(rows, key):
    result = {key(row): row for row in rows}
    assert len(result) == len(rows), 'Duplicate record identity'
    return result


def audit(data, primary, oracle, scores):
    hashes_checked = []
    for item in read(data / 'file_hashes.json'):
        path = data / item['path']
        assert digest(path) == item['sha256'], item['path']
        hashes_checked.append({'path': safe_name(path), 'sha256': item['sha256']})
    for run in (primary, oracle):
        m = read(run / 'run_manifest.json')
        assert m['data_manifest_sha256'] == digest(data / 'file_hashes.json')
        assert m['results_sha256'] == digest(run / 'results.json')
        for item in m['files']:
            path = run / item['path']
            assert digest(path) == item['sha256'], item['path']
            hashes_checked.append({'path': safe_name(path), 'sha256': item['sha256']})
    inputs = read(data / 'execution_inputs.json')
    p, o, saved = read(primary / 'results.json'), read(oracle / 'results.json'), read(scores)
    assert p['phase'] == 'primary' and o['phase'] == 'oracle'
    profile = SCORER_PROFILES[saved['bindings']['scorer_sha256']]
    contains_twins = any(c['kind'] == 'nonidentifiable_shared_input' for c in inputs['cases'])
    assert o['primary_results_sha256'] == digest(primary / 'results.json')
    for name, path in [('data_sha256', data / 'file_hashes.json'), ('primary_sha256', primary / 'results.json'), ('oracle_sha256', oracle / 'results.json')]:
        assert saved['bindings'][name] == digest(path)
    pmap, omap = rowmap(p['rows'], lambda r: r['id']), rowmap(o['rows'], lambda r: r['id'])
    assert set(pmap) == set(omap) == {case['id'] for case in inputs['cases']}
    expected, traces, language_expected, mismatches = [], [], [], []
    truth_by_input = {}
    for path in sorted((data / 'truth').glob('*.json')):
        truth = read(path)
        truth_by_input.setdefault(truth.get('input_id', truth['id']), []).append(truth)
    assert set(truth_by_input) == set(pmap)
    raw_output_checks, reused_checks = 0, 0
    for case in inputs['cases']:
        cid = case['id']
        cipher = (data / case['cipher']).read_text().split()
        assert len(cipher) == case['word_count']
        pp, oo = pmap[cid], omap[cid]
        languages = {t['language'] for t in truth_by_input[cid]}
        assert len(languages) == 1
        true_language = next(iter(languages))
        for method, route in pp['routes'].items():
            # Parse saved author RESULT only as a consistency check, not a new route.
            if route['status'] == 'PASS':
                out = (primary / 'logs' / route['run_id'] / 'stdout.txt').read_text()
                names = re.findall(r'^RESULT:\t[^\t]+\t([^\t]*)\t', out, re.M)
                assert names == [route['language']]
            language_expected.append({'id': cid, 'positive': case['kind'] != 'nonidentifiable_shared_input',
                'method': method, 'true_language': true_language, 'selected_language': route['language'],
                'status': route['status'], 'correct': (route['language'] == true_language) if route['status'] == 'PASS' else None,
                'scores': route['scores'], 'tie': route['tie']})
        for truth in truth_by_input[cid]:
            assert oo['oracle_language'] == truth['language']
            for condition, source, run in [('primary', pp, primary), ('oracle_language', oo, oracle)]:
                pipes = rowmap(source['pipelines'], lambda r: r['variant'])
                for variant in inputs['variants']:
                    pipe = pipes.get(variant)
                    language = pipe['language'] if pipe else truth['language']
                    if pipe and condition == 'primary':
                        assert pipe['language'] == pp['routes']['pattern']['language']
                    if pipe and condition == 'oracle_language':
                        assert pipe['language'] == truth['language']
                    decoder = pipe.get('decoder') if pipe else None
                    value, trace = recalculate(truth, cipher, pipe, decoder, condition, variant,
                        (data / 'train' / ('udhr-' + language + '.txt.tra')).read_text().split())
                    expected.append(value); traces.append({'truth_id': truth['id'], 'condition': condition, 'variant': variant, **trace})
                    if pipe and pipe.get('reused_primary_result'):
                        original = next(r for r in pp['pipelines'] if r['variant'] == variant)
                        for key in ('language', 'mapping', 'mapping_status', 'mapped_words', 'decoder'):
                            assert original[key] == pipe[key]
                        reused_checks += 1
                    if decoder and decoder['status'] == 'PASS':
                        logroot = primary if pipe.get('reused_primary_result') else run
                        assert (logroot / 'logs' / decoder['run_id'] / 'stdout.txt').read_text().split() == decoder['output_words']
                        raw_output_checks += 1
            decoder = oo['oracle_truekey_decoder']
            value, trace = recalculate(truth, cipher, None, decoder, 'oracle_truekey', 'shared',
                (data / 'train' / ('udhr-' + truth['language'] + '.txt.tra')).read_text().split())
            expected.append(value); traces.append({'truth_id': truth['id'], 'condition': 'oracle_truekey', 'variant': 'shared', **trace})
            if decoder['status'] == 'PASS':
                assert (oracle / 'logs' / decoder['run_id'] / 'stdout.txt').read_text().split() == decoder['output_words']
                raw_output_checks += 1
    key = lambda r: (r['truth_id'], r['condition'], r['variant'])
    a, b = rowmap(expected, key), rowmap(saved['rows'], key)
    assert set(a) == set(b)
    for identity in a:
        compare(a[identity], b[identity], '/rows/' + '|'.join(identity), mismatches)
    compare(language_expected, saved['language_rows'], '/language_rows', mismatches)
    groups = []
    for condition, variant in [('primary', 'readme_lex'), ('primary', 'code_countfirst'), ('oracle_language', 'readme_lex'), ('oracle_language', 'code_countfirst'), ('oracle_truekey', 'shared')]:
        rows = [r for r in expected if r['positive'] and r['condition'] == condition and r['variant'] == variant]
        group = {'condition': condition, 'variant': variant, 'planned_cases': len(rows), 'planned_words': sum(r['word_count'] for r in rows)}
        for metric in ('mapping_types', 'mapping_weighted', 'word_bags', 'exact_words'):
            present = [r[metric] for r in rows if r[metric] is not None]
            group[metric] = {'scored_cases': len(present), 'failed_or_unscored_cases': len(rows) - len(present),
                **quotient(sum(m['correct'] for m in present), sum(m['total'] for m in present))}
        if profile == 'explicit_applicability_metadata':
            for metric in ('mapping_types', 'mapping_weighted', 'word_bags', 'exact_words'):
                supplied = condition == 'oracle_truekey' and metric in ('mapping_types', 'mapping_weighted')
                group[metric]['applicability'] = 'NOT_APPLICABLE_PROVIDED_KEY' if supplied else 'APPLICABLE'
                group[metric]['not_applicable_cases'] = len(rows) if supplied else 0
                if supplied:
                    group[metric]['failed_or_unscored_cases'] = 0
            if condition == 'oracle_truekey':
                group['word_bags']['basis'] = 'Provided correct key and verified generation history, not recovered key performance'
        group['confirmed_exact_recovery_over_all_planned_words'] = quotient(sum(r['exact_words']['correct'] for r in rows if r['exact_words'] is not None), group['planned_words'])
        groups.append(group)
    compare(groups, saved['groups'], '/groups', mismatches)
    languages = []
    for method in sorted({r['method'] for r in language_expected}):
        rows = [r for r in language_expected if r['positive'] and r['method'] == method]
        evaluated = [r for r in rows if r['correct'] is not None]
        languages.append({'method': method, 'planned_cases': len(rows), 'scored_cases': len(evaluated),
                          **quotient(sum(r['correct'] for r in evaluated), len(evaluated))})
    files = [data / 'execution_inputs.json', data / 'file_hashes.json', primary / 'results.json', primary / 'run_manifest.json', oracle / 'results.json', oracle / 'run_manifest.json', scores, Path(__file__)]
    return {'schema': 'independent_saved_score_recount_v2', 'score_metadata_profile': profile, 'created_utc': datetime.now(timezone.utc).isoformat(),
        'all_passed': not mismatches, 'scope': 'Saved outputs and truth only; no fit, decode, manuscript or new data generation.',
        'imports_production_scoring_code': False, 'bindings': [{'path': safe_name(f), 'sha256': digest(f)} for f in files],
        'input_hash_checks': len(hashes_checked), 'truth_histories': sum(map(len, truth_by_input.values())), 'contains_twin_histories': contains_twins,
        'score_rows_checked': len(expected), 'language_rows_checked': len(language_expected), 'groups_checked': len(groups),
        'raw_output_checks': raw_output_checks, 'oracle_reused_output_checks': reused_checks,
        'mismatches': mismatches, 'recomputed_groups': groups, 'recomputed_language_denominators': languages,
        'per_row_trace': traces,
        'limitations': ['Not a fresh execution of author programs.', 'This replay verifies only saved cases; absence of process failures does not dynamically test hypothetical failure paths.', 'Counts are conditional on supplied truth histories and vocabulary. Training coverage and output vocabulary hit are not correctness.']}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, default=BASE / 'calibration/toy_data_v1')
    ap.add_argument('--primary', type=Path, default=BASE / 'calibration/toy_primary_v1')
    ap.add_argument('--oracle', type=Path, default=BASE / 'calibration/toy_oracle_v1')
    ap.add_argument('--scores', type=Path, default=BASE / 'calibration/toy_scores_v1.json')
    ap.add_argument('--out', type=Path)
    a = ap.parse_args()
    if a.out and a.out.exists():
        ap.error('--out must name a new file')
    result = audit(a.data, a.primary, a.oracle, a.scores)
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if a.out:
        with a.out.open('x') as stream:
            stream.write(payload)
        print(json.dumps({k: result[k] for k in ('all_passed', 'score_rows_checked', 'language_rows_checked', 'groups_checked')}))
    else:
        print(payload, end='')
    raise SystemExit(0 if result['all_passed'] else 1)


if __name__ == '__main__':
    main()
