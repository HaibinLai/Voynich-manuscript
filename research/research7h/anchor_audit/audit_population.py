"""Reconcile saved Bax coverage histograms to the frozen retained-prose parser."""
from collections import Counter
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import sys

P = Path(__file__).resolve().parent
ROOT = P.parent
sys.path.insert(0, str(ROOT))
import corpus


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists(), 'Use a new output file'
    receipt = json.loads((P / 'coverage_receipt.json').read_text())
    for item in receipt['files']:
        assert hashlib.sha256((ROOT.parent/item['path']).read_bytes()).hexdigest() == item['sha256']
    saved = json.loads(gzip.decompress((P/'coverage_words.json.gz').read_bytes()))
    summaries = []
    for source, name in [('ZL3b-n.txt','ZL_EVA'), ('IT2a-n.txt','IT_EVA')]:
        for group, splits in [('train_legacy',['train','legacy']), ('dev',['dev'])]:
            pages = corpus.load(source, splits=splits)
            assert all(p['split'] in splits for p in pages)
            tokens = [t for p in pages for line in p['lines'] for t in line['tokens']]
            actual = Counter(tuple(corpus.units(t,'eva')) for t in tokens if t)
            historical = Counter({tuple(r['word']):r['count'] for r in saved if r['representation']==name and r['split_group']==group})
            assert actual == historical
            summaries.append(dict(representation=name, split_group=group, pages=len(pages),
                parsed_prose_slots=len(tokens), excluded_missing_slots=sum(t is None for t in tokens),
                retained_words=sum(actual.values()), types=len(actual), exact_saved_histogram_match=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        groups=summaries, passed=True, confirm_returned=False, reserve_returned=False,
        limitation='Same frozen source parser, second end-to-end derivation; not an independent transcription or alternative parser.'),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(summaries, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
