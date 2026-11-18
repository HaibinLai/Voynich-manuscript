"""Lossless locus inventory. This program never scores text correspondence."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PRIVATE = ROOT.parent / 'output/voynich/research_next/astronomical7h_20261118/zodiac_inventory'
# Catalogue counts and image links observed in the three specified source pages.
# Interpretive zodiac names are intentionally not used as text meanings.
CATALOGUE = [
    ('f70v2', 10, 33, 3, 30, '1006200'),
    ('f70v1', 10, 17, 2, 15, '1006201'),
    ('f71r', 11, 18, 3, 15, '1006202'),
    ('f71v', 11, 18, 3, 15, '1006203'),
    ('f72r1', 11, 18, 3, 15, '1006203'),
    ('f72r2', 11, 32, 3, 29, '1006203'),
    ('f72r3', 11, 34, 4, 30, '1006203'),
    ('f72v3', 11, 33, 3, 30, '1006204'),
    ('f72v2', 11, 33, 3, 30, '1006204'),
    ('f72v1', 11, 33, 3, 30, '1006205'),
    ('f73r', 12, 33, 3, 30, '1006206'),
    ('f73v', 12, 33, 3, 30, '1006207'),
]
FOLIOS = [r[0] for r in CATALOGUE]
PATTERN = re.compile(r'^<(?P<folio>f\d+[rv]\d*)\.(?P<number>\d+),(?P<code>[^>]+)>\s*(?P<body>.*)$')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read_version(name):
    path = ROOT / 'research/sources' / name
    out = {f: {'header': None, 'records': []} for f in FOLIOS}
    selected_lines = []
    unmatched = []
    for index, raw in enumerate(path.read_text().splitlines(), 1):
        h = re.match(r'^<(f\d+[rv]\d*)>\s+(.*)', raw)
        if h and h[1] in out:
            out[h[1]]['header'] = {'line': index, 'raw': raw}
        if not any(raw.startswith('<' + f + '.') for f in FOLIOS):
            continue
        selected_lines.append(index)
        match = PATTERN.fullmatch(raw)
        if not match:
            unmatched.append({'line': index, 'raw': raw})
            continue
        f, n, code, body = match.group('folio', 'number', 'code', 'body')
        # Only separate explicit angle-bracket markup; no letter, space or
        # punctuation normalization. The raw source remains reconstructable.
        markup = re.findall(r'<[^>]*>', body)
        visible = re.sub(r'<[^>]*>', '', body)
        flags = {c: visible.count(c) for c in ['.', ',', '?', '*', '[', ']', '{', '}', '@', ' ']}
        rec = {'line': index, 'raw': raw, 'locator': f + '.' + n,
               'number': int(n), 'code': code, 'type_code': code[1:],
               'continuation_code': code[:1], 'raw_body': body,
               'explicit_markup': markup, 'body_without_angle_markup': visible,
               'literal_marker_counts': flags,
               'dot_separated_parts': visible.split('.'),
               'role_status': 'SOURCE_CODE_ONLY_NOT_VISUALLY_CERTIFIED'}
        out[f]['records'].append(rec)
    assert not unmatched, unmatched
    assert len(selected_lines) == sum(len(v['records']) for v in out.values())
    for f, v in out.items():
        assert v['header'] is not None, f
        assert len({r['locator'] for r in v['records']}) == len(v['records']), f
        v['count'] = len(v['records'])
        v['type_counts'] = dict(sorted(Counter(r['type_code'] for r in v['records']).items()))
        v['marker_locus_counts'] = {c: sum(r['literal_marker_counts'][c] > 0 for r in v['records'])
                                    for c in ['.', ',', '?', '*', '[', '{', '@', ' ']}
    return {'file': str(path.relative_to(ROOT)), 'sha256': sha(path),
            'selected_line_count': len(selected_lines), 'unmatched_lines': unmatched,
            'folios': out}

def main():
    frozen = json.loads((HERE / 'input_freeze_v1.json').read_text())
    for item in frozen['files']:
        assert sha(ROOT / item['path']) == item['sha256'], item['path']
    sources = json.loads((HERE / 'source_acquisition_v1.json').read_text())
    for item in sources['sources']:
        assert item.get('status') == 200
        assert sha(PRIVATE / item['name']) == item['sha256'], item['name']
    manifest = json.loads((PRIVATE / 'yale_manifest.json').read_text())
    canvases = {x['id'].split('/')[-1]: x for x in manifest['items']}
    versions = {'ZL': read_version('ZL3b-n.txt'), 'IT': read_version('IT2a-n.txt')}
    pages = []
    for folio, quire, total, circular, labels, image_id in CATALOGUE:
        c = canvases[image_id]
        page = {'folio': folio, 'physical_leaf': re.match(r'f\d+', folio)[0],
                'source_page': f'https://www.voynich.nu/q{quire}/index.html',
                'catalogue_counts': {'all': total, 'circular': circular, 'zodiac_labels': labels},
                'catalogue_role_evidence': 'Author description; not a new image observation.',
                'official_canvas': {'id': c['id'], 'label': c['label'], 'width': c['width'], 'height': c['height'],
                    'image_url': c['items'][0]['items'][0]['body']['id'],
                    'mapping_evidence': 'Explicit image link in the specified author folio section, joined to official manifest ID.',
                    'folio_pixel_region': None, 'shared_canvas_folios': [x[0] for x in CATALOGUE if x[5] == image_id]},
                'visual_role_gate': 'NOT_YET_ASSESSED', 'cross_figure_score': None,
                'versions': {}}
        for v, data in versions.items():
            local = data['folios'][folio]
            page['versions'][v] = {k: local[k] for k in ['count', 'type_counts', 'marker_locus_counts']}
            page['versions'][v]['catalogue_count_differences'] = {
                'all': local['count'] - total,
                'Cc_vs_circular': local['type_counts'].get('Cc', 0) - circular,
                'Lz_vs_zodiac_labels': local['type_counts'].get('Lz', 0) - labels,
            }
        z = {r['locator']: r for r in versions['ZL']['folios'][folio]['records']}
        i = {r['locator']: r for r in versions['IT']['folios'][folio]['records']}
        page['locus_id_comparison'] = {
            'shared': len(z.keys() & i.keys()), 'only_ZL': sorted(z.keys() - i.keys()),
            'only_IT': sorted(i.keys() - z.keys()),
            'body_without_angle_markup_identical': sum(z[k]['body_without_angle_markup'] == i[k]['body_without_angle_markup'] for k in z.keys() & i.keys()),
            'limitation': 'Shared identifiers and identical strings do not independently certify image correspondence or readings.'}
        pages.append(page)
    out = {'scope': 'All twelve fixed zodiac figure panels; metadata only, no text prediction.',
           'status': 'METADATA_COMPLETE_VISUAL_ELIGIBILITY_PENDING',
           'physical_leaf_count': len({p['physical_leaf'] for p in pages}),
           'figure_count': len(pages), 'official_canvas_count': len({p['official_canvas']['id'] for p in pages}),
           'protocol_sha256': sha(HERE / 'protocol_v1.txt'), 'source_acquisition_sha256': sha(HERE / 'source_acquisition_v1.json'),
           'limits': ['All twelve figures share only four physical leaves.',
                      'Circular writing and short labels are source categories, not semantic identities.',
                      'Catalogue f73v illustration is Sagittarius but its tentative-identification paragraph says Scorpius; conflict retained, neither used as a text anchor.',
                      'Later month-name additions are not accepted as readings of the main script.',
                      'No words, zodiac names, months, phonetics, language or best rotation have been tested.'],
           'pages': pages, 'versions': versions}
    target = HERE / 'inventory_v1.json'
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    print('figures', len(pages), 'physical leaves', out['physical_leaf_count'], 'canvases', out['official_canvas_count'])
    for p in pages:
        print(p['folio'], p['catalogue_counts'], {v: d['type_counts'] for v, d in p['versions'].items()})
    print('saved', target.relative_to(ROOT), sha(target))

if __name__ == '__main__':
    main()
