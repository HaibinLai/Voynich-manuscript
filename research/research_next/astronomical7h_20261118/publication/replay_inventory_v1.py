"""Portable source-line replay; does not fetch catalogues or inspect images."""
from pathlib import Path
from collections import Counter
import hashlib
import json

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
inventory=HERE.parent/'zodiac_inventory/inventory_v1.json'
d=json.loads(inventory.read_text())
counts={}
for version,record in d['versions'].items():
    p=ROOT/record['file']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256'],version
    lines=p.read_text().splitlines()
    n=0
    for folio, saved in record['folios'].items():
        original={i:s for i,s in enumerate(lines,1) if s.startswith('<'+folio+'.')}
        assert original=={r['line']:r['raw'] for r in saved['records']},(version,folio)
        code_counts=Counter(s.split('>',1)[0].rsplit(',',1)[1][1:] for s in original.values())
        assert dict(code_counts)==saved['type_counts']
        assert len(original)==saved['count']
        page=next(p for p in d['pages'] if p['folio']==folio)
        assert page['versions'][version]['count']==len(original)
        assert page['catalogue_counts']['all']==len(original)
        assert page['catalogue_counts']['circular']==code_counts['Cc']
        assert page['catalogue_counts']['zodiac_labels']==code_counts['Lz']
        n+=len(original)
    assert n==record['selected_line_count']
    counts[version]=n
assert {p['folio'] for p in d['pages']}=={'f70v2','f70v1','f71r','f71v','f72r1','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v'}
assert len({p['physical_leaf'] for p in d['pages']})==d['physical_leaf_count']==4
print(json.dumps({'status':'PASS_PUBLIC_SOURCE_LINE_REPLAY','figures':len(d['pages']),
                  'loci_per_version':counts,'physical_leaves':4,
                  'limits':'Rechecks original source lines and stored metadata consistency. Does not independently reopen catalogues, validate image roles or test words.'},ensure_ascii=False,indent=2))
