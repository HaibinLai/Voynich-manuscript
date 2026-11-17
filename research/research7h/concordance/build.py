"""Build a loss-aware reading index, not a statistical or semantic evaluation."""
from pathlib import Path
import argparse
from collections import Counter, defaultdict
import datetime
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
ASCII_LOWER = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')
VALID = re.compile(r"(?:[a-z']|@[0-9]{3};)+\Z", re.ASCII)
ROW = re.compile(r'^<([^>,]+),([^>]+)>[ \t]*(.*)$')
NORMALIZATION = 'concordance-v1-ascii-balanced-slots-20261117'
COLLECTION = 'https://collections.library.yale.edu/catalog/2002046'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj, compact=False):
    path.write_text(json.dumps(obj, ensure_ascii=False, allow_nan=False,
        separators=(',', ':') if compact else None, indent=None if compact else 2) + '\n', encoding='utf-8')


def normalize(display):
    """Only balanced curly wrappers may disappear; never salvage substrings."""
    stack = []
    output = []
    for char in display:
        if char in '[]?*':
            return None
        if char == '{':
            stack.append(char)
        elif char == '}':
            if not stack:
                return None
            stack.pop()
        else:
            output.append(char)
    if stack:
        return None
    word = ''.join(output).translate(ASCII_LOWER)
    return word if VALID.fullmatch(word) else None


def parse_text(raw):
    """Preserve raw slices and display codepoint offsets, including empty slots."""
    display = []
    slots = []
    stack = []
    raw_start = display_start = i = 0
    left = 'start'

    def finish(raw_end, right):
        text = ''.join(display[display_start:])
        slots.append(dict(raw=raw[raw_start:raw_end], normalized=normalize(text),
            left_boundary=left, right_boundary=right,
            display_start=display_start, display_end=len(display)))

    while i < len(raw):
        end = i + 1
        char = raw[i]
        illustration = False
        if char == '<':
            closing = raw.find('>', i + 1)
            # Nested '<' is not an ordinary complete marker; retain it as unknown text.
            if closing >= 0 and '<' not in raw[i + 1:closing]:
                end = closing + 1
                marker = raw[i:end]
                if marker in ('<->', '<~>'):
                    char, illustration = ' ', True
                else:
                    i = end
                    continue
        boundary = ('illustration' if illustration else
            'certain' if char == '.' else 'uncertain' if char == ',' else None)
        if boundary and not stack:
            finish(i, boundary)
            display.append(char.translate(ASCII_LOWER))
            raw_start, display_start, left = end, len(display), boundary
        else:
            display.append(char.translate(ASCII_LOWER))
            if char in '[{':
                stack.append(char)
            elif char in ']}':
                expected = '[' if char == ']' else '{'
                if stack and stack[-1] == expected:
                    stack.pop()
                # A wrong closing bracket does not erase an unmatched opening.
        i = end
    finish(len(raw), 'end')
    return ''.join(display), slots


def leaf_group(folio):
    if folio == 'fRos' or re.match(r'f8[56][rv]', folio):
        return 'f85_86'
    match = re.match(r'f([0-9]+)', folio)
    return 'f' + match[1] if match else folio


def manual_examples():
    cases = [
        ('a,,b', ['a', None, 'b']), ('.a.', [None, 'a', None]),
        ('a.[b.c].d', ['a', None, 'd']), ('a.[b,c].d', ['a', None, 'd']),
        ('a.***.b', ['a', None, 'b']), ('qo[k:t]dy', [None]),
        ('q@003;k.q@03;k', ['q@003;k', None]), ("c'y.c’y", ["c'y", None]),
        ('{qok}.qo{k}dy.{{q}}', ['qok', 'qokdy', 'q']),
        ('a.{b.c', ['a', None]), ('a.b}.c', ['a', None, 'c']),
        ('a.[b,c.d', ['a', None]), ('a.{b,c}.d', ['a', None, 'd']),
        ('qo<->k.qo<~>k', ['qo', 'k', 'qo', 'k']),
        ('qo<!note>k', ['qok']), ('<%>a<$>', ['a']),
        ('a,a.b.[a:b].a', ['a', 'a', 'b', None, 'a']),
        ('aaa', ['aaa']), ('😀.A', [None, 'a']),
        ('a.[{b]}.c', ['a', None]), ('', [None]),
        ('<script>alert(1)</script>.a', [None, 'a']),
    ]
    results = []
    for raw, expected in cases:
        display, slots = parse_text(raw)
        assert [s['normalized'] for s in slots] == expected, raw
        for slot in slots:
            assert normalize(display[slot['display_start']:slot['display_end']]) == slot['normalized']
        results.append(dict(raw=raw, display=display, slots=slots, expected_normalized=expected))
    display, slots = parse_text('a,a.b.[a:b].a')
    hit = [s for s in slots if s['normalized'] == 'a']
    assert len(hit) == 3
    certain = [s for s in hit if 'uncertain' not in (s['left_boundary'], s['right_boundary'])]
    assert len(certain) == 1
    assert 'aa' in parse_text('aaa')[0]  # literal result is one locus, not two occurrences
    return dict(all_passed=True, examples=results, query_checks=dict(
        exact_a_in_example=3, exact_a_excluding_uncertain=1,
        literal_aa_in_aaa_locus_count=1, empty_query_count=0),
        note='Raw strings are data. Rendering and download escaping are separately tested in the website.')


def manifest_images(manifest):
    exact = defaultdict(list)
    all_images = {}
    for canvas in manifest['items']:
        urls = [a['body']['id'] for page in canvas.get('items', []) for a in page.get('items', [])
                if isinstance(a.get('body'), dict) and a['body'].get('type') == 'Image']
        if len(urls) != 1:
            continue
        item = dict(canvas_id=canvas['id'], canvas_label=canvas.get('label'), image_link=urls[0])
        all_images[canvas['id']] = item
        labels = [v for values in canvas.get('label', {}).values() for v in values]
        for label in set(labels):
            if re.fullmatch(r'[0-9]+[rv][0-9]*', label):
                exact['f' + label].append(item)
    return exact, all_images


def build(output):
    assert not output.exists(), 'Refuse to overwrite any existing output directory.'
    inputs = {
        'sources_provenance': BASE/'sources/provenance.json',
        'yale_manifest': BASE/'research7h/visual_audit/yale_manifest.json',
        'study20_image_receipt': BASE/'research7h/visual_audit/yale_image_receipt.json',
        'study20_selection': BASE/'study20/selection.json',
    }
    provenance = {x['file']: x for x in json.loads(inputs['sources_provenance'].read_text())}
    manifest = json.loads(inputs['yale_manifest'].read_text())
    receipt = json.loads(inputs['study20_image_receipt'].read_text())
    assert receipt['manifest_sha256'] == sha(inputs['yale_manifest'])
    selected = {x['folio'] for x in json.loads(inputs['study20_selection'].read_text())}
    images20 = {x['folio']: x for x in receipt['images']}
    assert selected == set(images20) and len(selected) == 20
    exact, canvas_images = manifest_images(manifest)
    records, by_locator, sources, postings = [], defaultdict(lambda: defaultdict(list)), {}, {}
    counts = {}
    for version, filename in [('ZL', 'ZL3b-n.txt'), ('IT', 'IT2a-n.txt')]:
        path = BASE/'sources'/filename
        assert sha(path) == provenance[filename]['sha256']
        inputs[version] = path
        sources[version] = dict(source_file='sources/' + filename, sha256=sha(path),
            url=provenance[filename]['upstream_url'], retrieved_url=provenance[filename]['retrieved_url'],
            description='Published IVTFF transliteration, all loci; not newly generated OCR or independent proofreading.')
        p = defaultdict(list)
        for line_number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            match = ROW.fullmatch(line)
            if not match:
                assert not line or line.startswith('#') or re.match(r'^<[^>,]+>', line), (version, line_number)
                continue
            locator, locus_type, raw = match.groups()
            assert '.' in locator, (version, locator)
            folio = locator.split('.', 1)[0]
            display, slots = parse_text(raw)
            record = dict(id=len(records), version=version, locator=locator, folio=folio,
                leaf_group=leaf_group(folio), locus_type=locus_type, source_line=line_number,
                raw=raw, display=display, slots=slots)
            records.append(record)
            by_locator[locator][version].append(record['id'])
            for slot_index, slot in enumerate(slots):
                if slot['normalized'] is not None:
                    p[slot['normalized']].append([record['id'], slot_index])
        postings[version] = dict(p)
        vr = [r for r in records if r['version'] == version]
        ss = [s for r in vr for s in r['slots']]
        counts[version] = dict(records=len(vr), folios=len({r['folio'] for r in vr}),
            leaf_groups=len({r['leaf_group'] for r in vr}), slots=len(ss),
            valid_slots=sum(s['normalized'] is not None for s in ss),
            uncertain_boundary_slots=sum('uncertain' in (s['left_boundary'], s['right_boundary']) for s in ss),
            valid_uncertain_boundary_slots=sum(s['normalized'] is not None and 'uncertain' in (s['left_boundary'], s['right_boundary']) for s in ss),
            empty_display_slots=sum(s['display_start'] == s['display_end'] for s in ss),
            distinct_normalized_tokens=len(p))
    mapping_inputs = {k: dict(source_file=str(v.relative_to(BASE)), sha256=sha(v)) for k, v in inputs.items() if k not in sources}
    folios = {}
    for folio in sorted({r['folio'] for r in records}):
        evidence, link, status = [], None, 'collection_only'
        if len(exact.get(folio, [])) == 1:
            match = exact[folio][0]
            link, status = match['image_link'], 'exact_manifest_label'
            evidence.append(dict(source='yale_manifest', **match))
        if folio in images20:
            image = images20[folio]
            assert image['canvas_id'] in canvas_images
            assert canvas_images[image['canvas_id']]['image_link'] == image['source_url']
            if link is not None:
                assert link == image['source_url']
            else:
                link, status = image['source_url'], 'study20_receipt'
            evidence.append(dict(source='study20_image_receipt', folio=folio,
                canvas_id=image['canvas_id'], canvas_label=image['canvas_label'],
                source_url=image['source_url'], image_sha256=image['image_sha256']))
        folios[folio] = dict(leaf_group=leaf_group(folio), image_link=link,
            collection_url=COLLECTION, study20_url='#manuscript?folio=' + folio if folio in selected else None,
            image_mapping_status=status, image_mapping_evidence=evidence)
    duplicate = {loc: {v: ids for v, ids in vv.items() if len(ids) > 1}
                 for loc, vv in by_locator.items() if any(len(ids) > 1 for ids in vv.values())}
    meta = dict(built_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), normalization_version=NORMALIZATION,
        counts=counts, duplicate_locators=duplicate,
        mapping_inputs=mapping_inputs, source_hashes={v: s['sha256'] for v, s in sources.items()},
        image_mapping_counts=dict(Counter(x['image_mapping_status'] for x in folios.values())),
        design_sha256=sha(HERE/'design.txt'), builder_sha256=sha(Path(__file__)),
        scope='Descriptive full published transcription index, including previously revealed reserve. No new scores, hypothesis tests, translation or independent OCR.',
        ordinary_angle_tags_removed_may_join_sides=True, illustration_display='one ASCII space per <-> or <~>',
        offsets='half-open Unicode codepoint offsets in ASCII-lowercase display',
        slots_are_index_specific=True, no_word_slot_alignment_across_versions=True,
        image_links_are_page_level_only=True, leaf_group_note='f85, f86 and fRos share f85_86; groups are not independent manuscripts.')
    data = dict(schema_version=1, sources=sources, records=records, postings=postings,
        by_locator=dict(by_locator), folios=folios, metadata=meta)
    examples = manual_examples()
    output.mkdir(parents=True)
    dump(output/'data.json', data, compact=True)
    dump(output/'summary.json', dict(schema_version=1, metadata=meta, total_records=len(records),
        shared_locators=sum('ZL' in v and 'IT' in v for v in by_locator.values()),
        locator_count=len(by_locator), folio_count=len(folios)))
    dump(output/'source_hashes.json', dict(sources=sources, mapping_inputs=mapping_inputs))
    dump(output/'manual_examples.json', examples)
    for version in sources:
        text = ['# Published transcription reading index; not a translation or independently corrected OCR.',
                '# Fields: source_line\tlocator\tlocus_type\tdisplay\traw',
                '# source_sha256=' + sources[version]['sha256']]
        text += ['\t'.join(str(r[k]) for k in ('source_line', 'locator', 'locus_type', 'display', 'raw'))
                 for r in records if r['version'] == version]
        (output/(version + '_lines.txt')).write_text('\n'.join(text) + '\n', encoding='utf-8')
    assert all(sha(path) == (sources[key]['sha256'] if key in sources else mapping_inputs[key]['sha256'])
               for key, path in inputs.items())
    print(json.dumps(dict(output=output.name, counts=counts, image_mapping_counts=meta['image_mapping_counts'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    build(args.output.resolve())
