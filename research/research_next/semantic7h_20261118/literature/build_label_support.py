"""Read image-pair inventory and label loci only; never score herbal body text."""
from pathlib import Path
import csv
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    pairs = json.loads((HERE / 'plant_pairs.json').read_text())['records']
    pharma = {r['pharma_folio'] for r in pairs}
    source = {}
    for short, name in [('ZL', 'ZL3b-n.txt'), ('IT', 'IT2a-n.txt')]:
        path = ROOT / 'research' / 'sources' / name
        labels = {}
        for line in path.read_text().splitlines():
            m = re.match(r'<(f[^.>]+\.\d+),([^>]+)>\s*(.*)', line)
            if not m or m[1].split('.')[0] not in pharma:
                continue
            if not re.fullmatch(r'.L[fcp]', m[2]):
                continue
            labels[m[1]] = {'locator': m[1], 'layout_type': m[2],
                            'raw': m[3], 'source_line': line,
                            'fragment_annotations': re.findall(r'<!([0-9]+[^>]*)>', m[3])}
        source[short] = {'file': name, 'url': 'https://voynich.nu/data/' + name,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'labels': labels}

    # Candidate mappings follow published numbered illustration tables and locus layout,
    # not the occurrence of any text on the target herbal page.
    inferred = {
        ('f88r', 8): ['f88r.15'], ('f88r', 11): ['f88r.24'],
        ('f88v', 22): ['f88v.30'], ('f89r1', 25): ['f89r1.4'],
        ('f89r1', 26): ['f89r1.5'], ('f89r1', 28): ['f89r1.13'],
        ('f89r1', 31): ['f89r1.26'], ('f89r2', 35): ['f89r2.4'],
        ('f89v2', 50): ['f89v2.2'], ('f89v2', 52): ['f89v2.4'],
        ('f89v2', 54): ['f89v2.6'], ('f89v2', 56): ['f89v2.13'],
    }
    absent = {('f101r', 150), ('f101r', 155), ('f101r', 168),
              ('f102r1', 203), ('f102r1', 204),
              ('f102r2', 205), ('f102r2', 206), ('f102r2', 209)}
    unknown = {
        ('f89r2', 40): 'Six fragments in this row but five Lf loci (17-21); first-fragment mapping unresolved. Do not attach Lc 16.',
        ('f101v', 188): '28 fragments but 18 Lf loci across historical panels; unnumbered locus order insufficient for object identity.',
    }
    out = []
    for pair in pairs:
        key = pair['pharma_folio'], pair['fragment_id']
        exact = []
        for loc, label in source['ZL']['labels'].items():
            if loc.split('.')[0] != key[0] or label['layout_type'][-2:] != 'Lf':
                continue
            if any(re.match(r'^' + str(key[1]) + r'(?:\D|$)', a) for a in label['fragment_annotations']):
                exact.append(loc)
        if exact:
            status, candidates = 'source_numbered_locator', exact
            reason = 'ZL inline Petersen fragment annotation ties Lf locus to numbered object; not independent visual certification.'
        elif key in inferred:
            status, candidates = 'layout_order_candidate_unverified', inferred[key]
            reason = 'Inference from full label ordering and published row/object inventory; no lexical target search. Requires image check.'
        elif key in absent:
            status, candidates = 'no_fragment_label_in_sources', []
            reason = 'No Lf for this object in stated layout; nearby Lc labels are containers. This is source-layout absence, not a new image census.'
        else:
            assert key in unknown, key
            status, candidates = 'unknown_object_locator', []
            reason = unknown[key]
        records = {s: [source[s]['labels'][loc] for loc in candidates if loc in source[s]['labels']] for s in source}
        for s in records:
            for rec in records[s]:
                # Boundary flags describe the raw string; no token sequence is repaired.
                raw = re.sub(r'<![^>]*>', '', rec['raw'])
                rec['has_certain_word_separator'] = '.' in raw
                rec['has_uncertain_word_separator'] = ',' in raw
                rec['has_alternative_or_unknown'] = any(c in raw for c in '[?*')
                rec['has_graphic_interruption'] = '<->' in raw
        out.append({'pair_id': pair['pair_id'], 'pharma_folio': key[0], 'fragment_id': key[1],
                    'herbal_folio': pair['herbal_folio'], 'source_grade': pair['source_grade'],
                    'status': status, 'candidate_locators': candidates, 'reason': reason,
                    'label_records': records, 'illustration_source_url': pair['source_url'],
                    'visual_rechecked': False, 'herbal_body_match_computed': False})
    summary = {k: sum(r['status'] == k for r in out) for k in sorted({r['status'] for r in out})}
    obj = {'date': '2026-11-18', 'scope': 'Label-layout support only. No herbal body lexical comparison; all pair records retained.',
           'sources': {s: {k: v for k, v in d.items() if k != 'labels'} for s, d in source.items()},
           'summary': summary, 'records': out}
    (HERE / 'label_support.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    with (HERE / 'label_support.csv').open('w', newline='') as f:
        cols = ['pair_id', 'pharma_folio', 'fragment_id', 'herbal_folio', 'source_grade', 'status', 'candidate_locators', 'reason']
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in out:
            writer.writerow({k: ';'.join(r[k]) if k == 'candidate_locators' else r[k] for k in cols})
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
