"""Describe same-locator differences in the already exposed ZL/IT index."""
from pathlib import Path
import argparse
import collections
import csv
import hashlib
import json

ROOT = Path(__file__).resolve().parent
CATEGORIES = ['display_equal', 'boundary_only', 'glyph_or_annotation', 'ZL_only', 'IT_only']


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def joined_display(record):
    return ''.join(record['display'][s['display_start']:s['display_end']] for s in record['slots'])


def classify(zl, it):
    if zl is None:
        return 'IT_only'
    if it is None:
        return 'ZL_only'
    if zl['display'] == it['display']:
        return 'display_equal'
    if joined_display(zl) == joined_display(it):
        return 'boundary_only'
    return 'glyph_or_annotation'


def flags(record):
    if record is None:
        return None
    slots = record['slots']
    return dict(unresolved_nonempty=any(s['normalized'] is None and bool(record['display'][s['display_start']:s['display_end']]) for s in slots),
                empty_slot=any(not record['display'][s['display_start']:s['display_end']] for s in slots),
                uncertain_boundary=any('uncertain' in (s['left_boundary'], s['right_boundary']) for s in slots))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT.parent/'concordance/out_v1/data.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a new output directory.')
    raw = args.input.read_bytes()
    data = json.loads(raw)
    grouped = {}
    for record in data['records']:
        pair = grouped.setdefault(record['locator'], {})
        if record['version'] in pair:
            raise ValueError('Duplicate version and locator: ' + record['locator'])
        pair[record['version']] = record
    rows = []
    counts = collections.Counter()
    flagged = {c: collections.Counter() for c in CATEGORIES}
    folios = {}
    for locator, pair in sorted(grouped.items()):
        zl, it = pair.get('ZL'), pair.get('IT')
        category = classify(zl, it)
        counts[category] += 1
        example = zl or it
        folio = example['folio']
        if zl and it:
            assert zl['folio'] == it['folio']
        f = folios.setdefault(folio, dict(folio=folio, leaf_group=example['leaf_group'],
                                         counts={c: 0 for c in CATEGORIES}))
        f['counts'][category] += 1
        zf, itf = flags(zl), flags(it)
        for version, values in [('ZL', zf), ('IT', itf)]:
            if values is not None:
                flagged[category][version+'_records'] += 1
                for k, v in values.items():
                    flagged[category][version+'_'+k] += int(v)
        mapping = data['folios'][folio]
        rows.append(dict(locator=locator, folio=folio, category=category,
                         ZL_id=zl['id'] if zl else None, IT_id=it['id'] if it else None,
                         ZL_display=zl['display'] if zl else None,
                         IT_display=it['display'] if it else None,
                         ZL_raw=zl['raw'] if zl else None, IT_raw=it['raw'] if it else None,
                         ZL_flags=zf, IT_flags=itf,
                         image_link=mapping['image_link'],
                         collection_url=mapping['collection_url'],
                         image_mapping_status=mapping['image_mapping_status']))
    pages = []
    for f in sorted(folios.values(), key=lambda v: v['folio']):
        f['shared_locators'] = sum(f['counts'][c] for c in CATEGORIES[:3])
        f['total_locators'] = sum(f['counts'].values())
        f['glyph_or_annotation_share_of_shared'] = (
            f['counts']['glyph_or_annotation']/f['shared_locators'] if f['shared_locators'] else None)
        pages.append(f)
    priorities = sorted((p for p in pages if p['shared_locators'] >= 10),
                        key=lambda p: (-p['glyph_or_annotation_share_of_shared'], -p['shared_locators'], p['folio']))
    summary = dict(input_sha256=hashlib.sha256(raw).hexdigest(),
                   builder_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   design_sha256=hashlib.sha256((ROOT/'design.txt').read_bytes()).hexdigest(),
                   locator_count=len(rows), versioned_record_count=len(data['records']),
                   shared_locators=sum(counts[c] for c in CATEGORIES[:3]),
                   counts={c: counts[c] for c in CATEGORIES}, folio_count=len(pages),
                   flags_by_category=flagged, priority_folio_count=len(priorities),
                   denominator_note='Categories partition complete locators, not physical lines or independent observations. Flags have version-specific record denominators.',
                   source_records_modified=False, new_hypothesis_test=False,
                   scope='Descriptive comparison of already public transcriptions. Differences are not errors or semantic discoveries.')
    args.output.mkdir(parents=True)
    for name, value in [('rows', rows), ('folios', pages), ('priority_folios', priorities), ('summary', summary)]:
        write(args.output/(name+'.json'), value)
    with (args.output/'rows.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        keys=['locator','folio','category','ZL_id','IT_id','ZL_display','IT_display','image_link','collection_url','image_mapping_status']
        writer=csv.DictWriter(stream, fieldnames=keys, extrasaction='ignore');writer.writeheader();writer.writerows(rows)
    with (args.output/'folios.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        keys=['folio','leaf_group','total_locators','shared_locators',*CATEGORIES,'glyph_or_annotation_share_of_shared']
        writer=csv.DictWriter(stream, fieldnames=keys);writer.writeheader()
        for p in pages:
            writer.writerow({k:v for k,v in p.items() if k != 'counts'} | p['counts'])
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
