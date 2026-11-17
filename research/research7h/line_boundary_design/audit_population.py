"""Recount cross-line eligibility from four saved train/dev page files only."""
from pathlib import Path
from collections import Counter
import argparse
import datetime
import gzip
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def recount(pages):
    counts=Counter();by_hand=Counter();by_illustration=Counter();by_page=Counter();leaves=set();strict=0
    for page in pages:
        assert page['split'] in ('train','legacy','dev')
        for previous,current in zip(page['lines'],page['lines'][1:]):
            counts['candidate_adjacent_parsed_rows']+=1
            # Mutually exclusive categories: count the first failing condition.
            # Root confirmed this order on 2026-11-17; eligibility is unchanged
            # if overlapping exclusion reasons are assigned in another order.
            if not previous['paragraph_known'] or not current['paragraph_known']:
                counts['unknown_paragraph']+=1;continue
            if previous['paragraph_end'] or current['paragraph_start'] or previous['block']!=current['block'] or previous['paragraph']!=current['paragraph']:
                counts['paragraph_or_block_boundary']+=1;continue
            if previous.get('aligned_to_excluded_locus',False) or current.get('aligned_to_excluded_locus',False):
                counts['aligned_to_excluded_locus']+=1;continue
            if not previous['tokens'] or not current['tokens'] or previous['tokens'][-1] is None or current['tokens'][0] is None:
                counts['missing_endpoint']+=1;continue
            counts['eligible_same_paragraph_cross_row']+=1
            by_hand[current['effective_hands'][0]]+=1
            by_illustration[page['metadata'].get('I','?')]+=1
            by_page[page['folio']]+=1;leaves.add(page['leaf'])
            strict+=max(previous['source_lines'])+1==min(current['source_lines'])
    return dict(pages=len(pages),counts=dict(counts),eligible_pages=len(by_page),eligible_leaves=len(leaves),
        strict_source_line_adjacent=strict,by_effective_H=dict(by_hand),by_illustration=dict(by_illustration),per_page=dict(by_page))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out-dir',type=Path,default=HERE,
        help='Fresh result directory, or a directory without the verification filename.')
    args=parser.parse_args()
    original=json.loads((HERE/'population.json').read_text())
    allowed={f'metadata_sensitivity/inputs/{source}_{split}.json.gz'
        for source in ('ZL3b-n','IT2a-n') for split in ('train_legacy','dev')}
    assert {row['input_path'] for row in original['rows']}==allowed
    findings=[]
    for row in original['rows']:
        path=ROOT/row['input_path'];assert sha(path)==row['input_sha256']
        pages=json.loads(gzip.decompress(path.read_bytes()))
        expected_splits={'train','legacy'} if row['split']=='train_legacy' else {'dev'}
        assert pages and {p['split'] for p in pages}<=expected_splits
        result=recount(pages)
        mismatches={k:dict(expected=row[k],observed=v) for k,v in result.items() if row[k]!=v}
        findings.append(dict(source=row['source'],split=row['split'],input_sha256=sha(path),
            matched=not mismatches,mismatches=mismatches,recount=result))
    if not all(r['matched'] for r in findings):
        raise AssertionError([{k:r[k] for k in ('source','split','mismatches')} for r in findings if not r['matched']])
    args.out_dir.mkdir(parents=True,exist_ok=True)
    out=args.out_dir/'population_independent_verification.json';assert not out.exists()
    result=dict(verified_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=True,
        original_population_sha256=sha(HERE/'population.json'),audit_code_sha256=sha(Path(__file__)),
        sources=findings,scope='Four saved train+legacy/dev page files; eligibility counts only, no endpoint association or probability scoring.',
        source_line_adjacent_meaning='Consecutive source-file line numbers only. Comments/blank lines can prevent this; it is not a physical adjacency gold standard.',
        exclusion_priority=['unknown_paragraph','paragraph_or_block_boundary','aligned_to_excluded_locus','missing_endpoint'],
        exclusion_counting='First failing condition, mutually exclusive; one IT dev pair satisfies both unknown and paragraph/block exclusion.',
        original_population_modified=False,raw_corpus_loaded=False,confirm_loaded=False,reserve_loaded=False)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print('Four saved populations match exactly; no scores computed.')


if __name__=='__main__':main()
