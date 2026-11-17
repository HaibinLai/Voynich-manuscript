"""How much of the known corpus can a published partial table even describe?"""
from pathlib import Path
from collections import Counter
from functools import lru_cache
import datetime
import gzip
import hashlib
import itertools
import json
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import corpus


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, obj):
    assert not path.exists(), ('Refusing overwrite', path)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def rules(mapping, allow_m):
    return [(tuple(corpus.units(row['eva'], 'eva')), len(row['phonetic_candidates']))
        for row in mapping if allow_m or row['eva'] != 'm']


def dynamic(word, table):
    n = len(word)
    segments, branches, missing = [0]*(n+1), [0]*(n+1), [n+1]*(n+1)
    segments[n] = branches[n] = 1
    missing[n] = 0
    for i in range(n-1, -1, -1):
        missing[i] = 1 + missing[i+1]
        for pattern, count in table:
            j = i+len(pattern)
            if word[i:j] == pattern:
                segments[i] += segments[j]
                branches[i] += count*branches[j]
                missing[i] = min(missing[i], missing[j])
    return dict(segmentation_paths=segments[0], symbolic_paths=branches[0], min_unexplained_units=missing[0])


def brute(word, table):
    paths = []
    def visit(i, missing, multiplicity, used_unknown):
        if i == len(word):
            paths.append((missing, multiplicity, used_unknown))
            return
        visit(i+1, missing+1, multiplicity, True)
        for pattern, count in table:
            if word[i:i+len(pattern)] == pattern:
                visit(i+len(pattern), missing, multiplicity*count, used_unknown)
    visit(0, 0, 1, False)
    full = [p for p in paths if not p[2]]
    return dict(segmentation_paths=len(full), symbolic_paths=sum(p[1] for p in full),
        min_unexplained_units=min(p[0] for p in paths))


def verify(mapping):
    cases = set(itertools.chain.from_iterable(itertools.product('einm', repeat=n) for n in range(1, 5)))
    cases.update(tuple(corpus.units(x, 'eva')) for x in ('shaiin','keedey','qokedy','ch','@177;','poror','ee','iin','in','orom'))
    for allow in (False, True):
        table = rules(mapping, allow)
        for word in cases:
            assert dynamic(word, table) == brute(word, table), word
    assert dynamic(tuple('ee'), rules(mapping, True))['segmentation_paths'] == 2
    assert dynamic(tuple('poror'), rules(mapping, True))['min_unexplained_units'] >= 1
    assert dynamic(('@177;',), rules(mapping, True))['min_unexplained_units'] == 1
    return dict(short_words=len(cases), compared_bounds=2, exhaustive_enumeration_matches=True,
        initial_unknown_p_not_deleted=True, rare_EVA_code_one_unit=True, reserve_requested=False)


def main():
    registry = ROOT / 'literature/candidate_claims.json'
    candidate = json.loads(registry.read_text())
    mapping = candidate['bax']['mapping']
    assert len(mapping) == 14
    inputs = [HERE/'coverage_protocol.txt', Path(__file__), registry, ROOT/'corpus.py',
        ROOT/'split_manifest.json', ROOT.parent/'study20/analyze.py', ROOT.parent/'build_corpus.py',
        ROOT.parent/'sources/ZL3b-n.txt', ROOT.parent/'sources/IT2a-n.txt']
    receipt = dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        files=[dict(path=str(p.relative_to(ROOT.parent)), sha256=sha(p)) for p in inputs],
        scope='Partial-table executability; neither translation accuracy nor semantic validation.')
    write(HERE/'coverage_receipt.json', receipt)
    write(HERE/'coverage_verification.json', verify(mapping))
    outputs, words_out = [], []
    for source, name in [('ZL3b-n.txt', 'ZL_EVA'), ('IT2a-n.txt', 'IT_EVA')]:
        for group, splits in [('train_legacy', ['train','legacy']), ('dev', ['dev'])]:
            pages = corpus.load(source, splits=splits)
            assert all(p['split'] in splits and p['split'] not in ('confirm','reserve') for p in pages)
            counts = Counter(tuple(corpus.units(t, 'eva')) for p in pages for line in p['lines'] for t in line['tokens'] if t)
            total = sum(counts.values())
            units = sum(len(w)*n for w,n in counts.items())
            summary = dict(representation=name, split_group=group, pages=len(pages), tokens=total,
                types=len(counts), units=units, bounds={})
            tables = {bound: rules(mapping, allow) for bound, allow in [('conservative_m_excluded',False), ('optimistic_m_allowed',True)]}
            audits = {bound: {word: dynamic(word, table) for word in counts} for bound, table in tables.items()}
            for word in counts:
                low, high = [audits[key][word] for key in tables]
                assert low['symbolic_paths'] <= high['symbolic_paths']
                assert low['min_unexplained_units'] >= high['min_unexplained_units']
            for bound, results in audits.items():
                full = sum(counts[w] for w,r in results.items() if r['segmentation_paths'])
                single = sum(counts[w] for w,r in results.items() if r['symbolic_paths']==1)
                unexplained = sum(counts[w]*r['min_unexplained_units'] for w,r in results.items())
                summary['bounds'][bound] = dict(full_coverable_tokens=full, full_coverable_fraction=full/total,
                    single_symbolic_path_tokens=single, single_symbolic_path_fraction=single/total,
                    multiple_symbolic_path_tokens=full-single,
                    full_coverable_types=sum(bool(r['segmentation_paths']) for r in results.values()),
                    min_unexplained_units=unexplained, min_unexplained_unit_fraction=unexplained/units)
            outputs.append(summary)
            words_out.extend(dict(representation=name, split_group=group, word=list(w), count=n,
                bounds={bound: {**audits[bound][w], 'symbolic_paths':str(audits[bound][w]['symbolic_paths'])} for bound in tables})
                for w,n in sorted(counts.items()))
    write(HERE/'coverage_words.json.gz', words_out)
    write(HERE/'coverage_results.json', dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        groups=outputs, confirm_used=False, reserve_used=False, reliable_translation_claimed=False,
        interpretation='Coverage and symbolic path counts only. One path is not one established pronunciation.'))
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
