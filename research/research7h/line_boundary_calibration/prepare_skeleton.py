"""Extract only permitted train/dev geometry and unit lengths, never glyph pairs."""
from collections import Counter
from pathlib import Path
import datetime, gzip, hashlib, json, re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INPUTS = {
    'train_legacy': ('metadata_sensitivity/inputs/ZL3b-n_train_legacy.json.gz', '139f2ce735689086e4a64f1786271f5f18b3ab288cf7ef84d6abcd994d06cc8c'),
    'dev': ('metadata_sensitivity/inputs/ZL3b-n_dev.json.gz', '0f95c04fae55357398983aca0f0b89e3f3b9a3f8a034f73b13716f1053cd5e73'),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def length_only(token):
    if token is None:
        return None
    # The frozen EVA unit convention; do not retain unit identities or endpoints.
    matched = re.findall(r"@\d{3};|[a-z']", token)
    assert ''.join(matched) == token and matched
    return len(matched)


def main():
    output = HERE / 'skeleton.json.gz'
    receipt = HERE / 'skeleton_receipt.json'
    assert not output.exists() and not receipt.exists()
    result = {}; audits = {}
    for split, (relative, expected_sha) in INPUTS.items():
        path = ROOT / relative
        assert digest(path) == expected_sha
        original = json.loads(gzip.decompress(path.read_bytes()))
        assert {p['split'] for p in original} <= ({'train', 'legacy'} if split == 'train_legacy' else {'dev'})
        pages = []; rows = []; excluded = Counter()
        for page in original:
            clean = dict(folio=page['folio'], leaf=page['leaf'], split=page['split'],
                         section=page['metadata'].get('I', '?'), lines=[])
            for line in page['lines']:
                clean['lines'].append(dict(lengths=[length_only(t) for t in line['tokens']],
                    effective_hands=line['effective_hands'], paragraph=line['paragraph'], block=line['block'],
                    paragraph_known=line['paragraph_known'], paragraph_start=line['paragraph_start'],
                    paragraph_end=line['paragraph_end'], aligned_to_excluded_locus=line['aligned_to_excluded_locus']))
            for li, (previous, current) in enumerate(zip(clean['lines'], clean['lines'][1:]), 1):
                excluded['candidate_adjacent_parsed_rows'] += 1
                if not previous['paragraph_known'] or not current['paragraph_known']:
                    excluded['unknown_paragraph'] += 1; continue
                if previous['paragraph_end'] or current['paragraph_start'] or previous['block'] != current['block'] or previous['paragraph'] != current['paragraph']:
                    excluded['paragraph_or_block_boundary'] += 1; continue
                if previous['aligned_to_excluded_locus'] or current['aligned_to_excluded_locus']:
                    excluded['aligned_to_excluded_locus'] += 1; continue
                if not previous['lengths'] or not current['lengths'] or previous['lengths'][-1] is None or current['lengths'][0] is None:
                    excluded['missing_endpoint'] += 1; continue
                excluded['eligible_same_paragraph_cross_row'] += 1
                rows.append(dict(folio=clean['folio'], leaf=clean['leaf'], line=li, slot=0,
                    hand=current['effective_hands'][0], section=clean['section'],
                    previous_length=previous['lengths'][-1], length=0, position_bin=0, paragraph_line=0))
            pages.append(clean)
        assert len(rows) == (1548 if split == 'train_legacy' else 647)
        result[split] = dict(pages=pages, rows=rows)
        audits[split] = dict(input_path=relative, input_sha256=expected_sha, pages=len(pages),
            eligible_rows=len(rows), eligible_leaves=len({r['leaf'] for r in rows}), counts=dict(excluded),
            retained_slots=sum(v is not None for p in pages for l in p['lines'] for v in l['lengths']),
            missing_slots=sum(v is None for p in pages for l in p['lines'] for v in l['lengths']))
    leaves = sorted({r['leaf'] for r in result['train_legacy']['rows']},
                    key=lambda leaf: hashlib.sha256(('line-calibration-fold-v1|' + leaf).encode()).digest())
    result['inner_leaf_fold'] = {leaf: i % 3 for i, leaf in enumerate(leaves)}
    payload = json.dumps(result, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    output.write_bytes(gzip.compress(payload, mtime=0))
    receipt.write_text(json.dumps(dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        sha256=digest(output), extractor_sha256=digest(Path(__file__)), inputs=audits,
        retained_text_fields=[], glyph_endpoints_or_associations_extracted=False,
        effective_H_scope=True, true_target_length_never_a_model_input=True,
        confirm_loaded=False, reserve_loaded=False), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(audits, ensure_ascii=False))


if __name__ == '__main__':
    main()
