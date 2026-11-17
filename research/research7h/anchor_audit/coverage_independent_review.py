"""Audit saved coverage rows without importing or loading any manuscript corpus."""
from pathlib import Path
from collections import defaultdict
from functools import lru_cache
import datetime
import gzip
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    registry = HERE.parent / 'literature/candidate_claims.json'
    mapping = json.loads(registry.read_text())['bax']['mapping']
    rows = json.loads(gzip.decompress((HERE/'coverage_words.json.gz').read_bytes()))
    result = json.loads((HERE/'coverage_results.json').read_text())
    tables = {}
    for bound, allow_m in [('conservative_m_excluded', False), ('optimistic_m_allowed', True)]:
        table = []
        for rule in mapping:
            if rule['eva'] == 'm' and not allow_m:
                continue
            pattern = tuple(re.findall(r"@\d{3};|[a-z']", rule['eva']))
            assert ''.join(pattern) == rule['eva'] and pattern
            values = rule['phonetic_candidates']
            assert values and len(set(values)) == len(values)
            table.append((pattern, len(values)))
        tables[bound] = table
    groups = defaultdict(list)
    checks = 0
    for row in rows:
        word = tuple(row['word'])
        assert word and isinstance(row['count'], int) and row['count'] > 0
        groups[(row['representation'], row['split_group'])].append(row)
        assert row['split_group'] in ('train_legacy', 'dev')
        for bound, table in tables.items():
            # Independently expand a polynomial in z, with z marking one
            # unexplained unit. Its constant coefficient counts full paths;
            # its least nonzero degree is the minimum unexplained-unit count.
            @lru_cache(None)
            def paths(pos, branch):
                if pos == len(word):
                    return (1,)
                fallback = paths(pos+1, branch)
                coefficients = [0] + list(fallback)
                for pattern, nvalues in table:
                    end = pos + len(pattern)
                    if word[pos:end] != pattern:
                        continue
                    tail = paths(end, branch)
                    for missing, count in enumerate(tail):
                        coefficients[missing] += count * (nvalues if branch else 1)
                return tuple(coefficients)
            segment_polynomial = paths(0, False)
            symbol_polynomial = paths(0, True)
            independently = dict(segmentation_paths=segment_polynomial[0],
                symbolic_paths=symbol_polynomial[0],
                min_unexplained_units=next(i for i,n in enumerate(segment_polynomial) if n))
            saved = row['bounds'][bound]
            for key, value in independently.items():
                assert int(saved[key]) == value, (word, bound, key)
            checks += 1
        a, b = [row['bounds'][key] for key in tables]
        assert int(a['symbolic_paths']) <= int(b['symbolic_paths'])
        assert a['min_unexplained_units'] >= b['min_unexplained_units']
    assert len(groups) == 4
    for group in result['groups']:
        saved_rows = groups[(group['representation'], group['split_group'])]
        tokens = sum(r['count'] for r in saved_rows)
        units = sum(r['count']*len(r['word']) for r in saved_rows)
        assert (tokens, units, len(saved_rows)) == (group['tokens'], group['units'], group['types'])
        for bound in tables:
            full = sum(r['count'] for r in saved_rows if r['bounds'][bound]['segmentation_paths'])
            single = sum(r['count'] for r in saved_rows if int(r['bounds'][bound]['symbolic_paths']) == 1)
            types = sum(bool(r['bounds'][bound]['segmentation_paths']) for r in saved_rows)
            missing = sum(r['count']*r['bounds'][bound]['min_unexplained_units'] for r in saved_rows)
            expected = dict(full_coverable_tokens=full, full_coverable_fraction=full/tokens,
                single_symbolic_path_tokens=single, single_symbolic_path_fraction=single/tokens,
                multiple_symbolic_path_tokens=full-single, full_coverable_types=types,
                min_unexplained_units=missing, min_unexplained_unit_fraction=missing/units)
            assert expected == group['bounds'][bound]
    receipt = json.loads((HERE/'coverage_receipt.json').read_text())
    checked, skipped = [], []
    for record in receipt['files']:
        if record['path'].startswith('sources/'):
            skipped.append(record['path'])
            continue
        path = HERE.parent.parent / record['path']
        assert sha(path) == record['sha256'], record['path']
        checked.append(record['path'])
    out = HERE/'coverage_independent_review.json'
    assert not out.exists()
    audit = dict(reviewed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        passed=True, method='Independent polynomial path enumeration and exact saved-row aggregation',
        saved_word_rows=len(rows), row_bound_checks=checks, aggregate_groups=len(groups),
        all_integer_path_counts_and_aggregates_match=True,
        rehashed_non_corpus_dependencies=checked, raw_transcriptions_not_reopened=skipped,
        corpus_loader_imported=False, confirm_loaded=False, reserve_loaded=False,
        source_sha256={p.name:sha(p) for p in [Path(__file__), registry,
            HERE/'coverage_words.json.gz', HERE/'coverage_results.json', HERE/'coverage_receipt.json']},
        scope_cautions=[
            'Denominator includes only retained prose words; uncertain whole tokens and non-prose labels are excluded by the frozen parser.',
            'These are path counts with symbolic alternatives, not distinct pronunciations or verified translations.',
            'The m-off/m-on envelope bounds only the missing m eligibility condition within this fixed literal table.',
            'No unknown-unit rule is added, and no outcome is used to complete the table.'])
    out.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
