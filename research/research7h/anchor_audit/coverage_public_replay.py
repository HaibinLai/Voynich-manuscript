"""Recheck saved Bax coverage counts in a fresh directory; never load a corpus."""
from pathlib import Path
from collections import defaultdict
import argparse
import datetime
import gzip
import hashlib
import json
import re


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def audit(input_dir, registry):
    mappings = json.loads(registry.read_text())['bax']['mapping']
    rows = json.loads(gzip.decompress((input_dir/'coverage_words.json.gz').read_bytes()))
    results = json.loads((input_dir/'coverage_results.json').read_text())
    assert len(mappings) == 14
    tables = {}
    for name, allow_m in [('conservative_m_excluded', False), ('optimistic_m_allowed', True)]:
        table = []
        for rule in mappings:
            if not allow_m and rule['eva'] == 'm':
                continue
            pattern = tuple(re.findall(r"@\d{3};|[a-z']", rule['eva']))
            assert pattern and ''.join(pattern) == rule['eva']
            candidates = rule['phonetic_candidates']
            assert candidates and len(set(candidates)) == len(candidates)
            table.append((pattern, len(candidates)))
        tables[name] = table
    aggregates = defaultdict(lambda: defaultdict(int))
    row_checks = 0
    seen = set()
    for row in rows:
        group = row['representation'], row['split_group']
        assert group[0] in ('ZL_EVA', 'IT_EVA') and group[1] in ('train_legacy', 'dev')
        word = tuple(row['word'])
        count = row['count']
        assert word and isinstance(count, int) and count > 0 and (group, word) not in seen
        seen.add((group, word))
        g = aggregates[group]
        g['types'] += 1
        g['tokens'] += count
        g['units'] += len(word)*count
        checks = {}
        for name, table in tables.items():
            # Forward path propagation differs from the original backward
            # recurrence. A unit-skip edge is allowed only in minimum cost.
            n = len(word)
            segmentation = [0]*(n+1)
            symbolic = [0]*(n+1)
            min_missing = [n+1]*(n+1)
            segmentation[0] = symbolic[0] = 1
            min_missing[0] = 0
            for start in range(n):
                min_missing[start+1] = min(min_missing[start+1], min_missing[start]+1)
                for pattern, branching in table:
                    end = start+len(pattern)
                    if word[start:end] != pattern:
                        continue
                    segmentation[end] += segmentation[start]
                    symbolic[end] += branching*symbolic[start]
                    min_missing[end] = min(min_missing[end], min_missing[start])
            checked = dict(segmentation_paths=segmentation[n], symbolic_paths=symbolic[n],
                min_unexplained_units=min_missing[n])
            assert checked == {k:int(v) for k,v in row['bounds'][name].items()}, (group, word, name)
            checks[name] = checked
            g[name+'_full'] += count*bool(segmentation[n])
            g[name+'_single'] += count*(symbolic[n] == 1)
            g[name+'_types'] += bool(segmentation[n])
            g[name+'_missing'] += count*min_missing[n]
            row_checks += 1
        low, high = [checks[name] for name in tables]
        assert low['symbolic_paths'] <= high['symbolic_paths']
        assert low['min_unexplained_units'] >= high['min_unexplained_units']
    assert len(aggregates) == len(results['groups']) == 4
    for result in results['groups']:
        g = aggregates[result['representation'], result['split_group']]
        assert all(g[k] == result[k] for k in ('types', 'tokens', 'units'))
        for name in tables:
            full, single, types, missing = (g[name+'_'+k] for k in ('full', 'single', 'types', 'missing'))
            expected = dict(full_coverable_tokens=full, full_coverable_fraction=full/g['tokens'],
                single_symbolic_path_tokens=single, single_symbolic_path_fraction=single/g['tokens'],
                multiple_symbolic_path_tokens=full-single, full_coverable_types=types,
                min_unexplained_units=missing, min_unexplained_unit_fraction=missing/g['units'])
            assert expected == result['bounds'][name]
    return dict(passed=True, saved_word_rows=len(rows), row_bound_checks=row_checks,
        aggregate_groups=len(aggregates), raw_corpus_loaded=False, confirm_loaded=False,
        reserve_loaded=False, frozen_result_modified=False,
        method='Independent forward path propagation and exact aggregation of saved word rows',
        interpretation='Only fixed partial-table coverage among retained prose words; not distinct pronunciations, translation accuracy, or a statistical bound on the full hypothesis.')


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input-dir', type=Path, default=here)
    ap.add_argument('--registry', type=Path)
    ap.add_argument('--out-dir', type=Path, required=True)
    args = ap.parse_args()
    input_dir = args.input_dir.resolve()
    registry = (args.registry or input_dir.parent/'literature/candidate_claims.json').resolve()
    out = args.out_dir.resolve()
    assert not out.exists(), 'Use a fresh output directory; no overwrite or automatic resume.'
    assert out != input_dir and out != here
    sources = {'coverage_words.json.gz':input_dir/'coverage_words.json.gz',
        'coverage_results.json':input_dir/'coverage_results.json',
        'candidate_claims.json':registry, 'replay_code':Path(__file__).resolve()}
    source_hashes = {name:sha(path) for name,path in sources.items()}
    out.mkdir(parents=True)
    receipt = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_sha256=source_hashes, output_mode='fresh saved-result replay',
        no_corpus_loader=True, no_new_corpus_scoring=True)
    (out/'execution_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    result = audit(input_dir, registry)
    assert source_hashes == {name:sha(path) for name,path in sources.items()}
    result.update(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_sha256=source_hashes, execution_receipt_sha256=sha(out/'execution_receipt.json'))
    (out/'verification.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
