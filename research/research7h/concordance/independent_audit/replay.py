# -*- coding: utf-8 -*-
"""Independent concordance lexer and saved-index audit; no builder imports."""
from pathlib import Path
from collections import defaultdict, Counter
import argparse, datetime, hashlib, json, re, traceback

HERE = Path(__file__).resolve().parent
CONCORDANCE = HERE.parent
VOYNICH = CONCORDANCE.parent.parent
SOURCE_FILES = {'ZL': 'ZL3b-n.txt', 'IT': 'IT2a-n.txt'}
SOURCE_SHA = {'ZL': 'bf5b6d4ac1e3a51b1847a9c388318d609020441ccd56984c901c32b09beccafc',
              'IT': '7f27a8b0feed8f6de0a99900df6bf912dd1d295c38e5f830bac8b41c3f536fb5'}
LOWER = str.maketrans('ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def display_fragment(raw):
    chars, i = [], 0
    while i < len(raw):
        if raw[i] == '<' and '>' in raw[i + 1:]:
            end = raw.index('>', i + 1) + 1
            if raw[i:end] in ('<->', '<~>'):
                chars.append(' ')
            i = end
        else:
            chars.append(raw[i])
            i += 1
    return ''.join(chars).translate(LOWER)


def canonical_plain(text):
    if not text:
        return False
    i = 0
    while i < len(text):
        if 'a' <= text[i] <= 'z' or text[i] == "'":
            i += 1
        elif text[i] == '@' and i + 4 < len(text) and all('0' <= c <= '9' for c in text[i + 1:i + 4]) and text[i + 4] == ';':
            i += 5
        else:
            return False
    return True


def normalized_slot(display):
    depth, chars = 0, []
    for c in display:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth < 0:
                return None
        elif c in '[]':
            return None
        else:
            chars.append(c)
    if depth:
        return None
    candidate = ''.join(chars)
    return candidate if canonical_plain(candidate) else None


def lex(raw):
    # First identify top-level delimiters while skipping complete annotation tags.
    boundaries, stack, i = [], [], 0
    while i < len(raw):
        c = raw[i]
        if c == '<' and '>' in raw[i + 1:]:
            end = raw.index('>', i + 1) + 1
            if not stack and raw[i:end] in ('<->', '<~>'):
                boundaries.append((i, end, 'illustration', ' '))
            i = end
            continue
        if c in '[{':
            stack.append(c)
        elif c in ']}' and stack and stack[-1] == {']': '[', '}': '{'}[c]:
            stack.pop()
        elif c in '.,' and not stack:
            boundaries.append((i, i + 1, 'certain' if c == '.' else 'uncertain', c))
        i += 1
    start, previous, display, slots = 0, 'start', '', []
    for left, right, kind, separator in boundaries + [(len(raw), len(raw), 'end', '')]:
        fragment = raw[start:left]
        shown = display_fragment(fragment)
        slots.append(dict(raw=fragment, normalized=normalized_slot(shown), left_boundary=previous,
            right_boundary=kind, display_start=len(display), display_end=len(display) + len(shown)))
        display += shown + separator
        start, previous = right, kind
    assert display == display_fragment(raw)
    return display, slots


def leaf(folio):
    if folio == 'fRos':
        return 'f85_86'
    match = re.match(r'^f([0-9]+)', folio)
    if not match:
        return folio
    number = int(match[1])
    return 'f85_86' if number in (85, 86) else 'f' + str(number)


def independent_records():
    records = []
    for version, filename in SOURCE_FILES.items():
        path = VOYNICH / 'sources' / filename
        assert sha(path) == SOURCE_SHA[version]
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            if not line.startswith('<') or '>' not in line:
                continue
            end = line.index('>')
            header = line[1:end]
            if ',' not in header:
                continue
            locator, locus_type = header.split(',', 1)
            folio = locator.split('.', 1)[0]
            raw = line[end + 1:].lstrip(' \t')
            display, slots = lex(raw)
            records.append(dict(id=len(records), version=version, locator=locator, folio=folio,
                leaf_group=leaf(folio), locus_type=locus_type, source_line=line_number,
                raw=raw, display=display, slots=slots))
    return records


def maps_and_counts(records):
    postings = {version: defaultdict(list) for version in SOURCE_FILES}
    locators = defaultdict(lambda: defaultdict(list))
    counts = {}
    for row in records:
        locators[row['locator']][row['version']].append(row['id'])
        for index, slot in enumerate(row['slots']):
            if slot['normalized'] is not None:
                postings[row['version']][slot['normalized']].append([row['id'], index])
    for version in SOURCE_FILES:
        rows = [r for r in records if r['version'] == version]
        slots = [s for r in rows for s in r['slots']]
        uncertain = lambda s: 'uncertain' in (s['left_boundary'], s['right_boundary'])
        counts[version] = dict(records=len(rows), folios=len({r['folio'] for r in rows}),
            leaf_groups=len({r['leaf_group'] for r in rows}), slots=len(slots),
            valid_slots=sum(s['normalized'] is not None for s in slots),
            uncertain_boundary_slots=sum(uncertain(s) for s in slots),
            valid_uncertain_boundary_slots=sum(uncertain(s) and s['normalized'] is not None for s in slots),
            empty_display_slots=sum(s['display_start'] == s['display_end'] for s in slots),
            distinct_normalized_tokens=len(postings[version]))
    return {v: dict(p) for v, p in postings.items()}, {l: dict(v) for l, v in locators.items()}, counts


def differences(expected, actual, path='', limit=80):
    errors = []
    def visit(a, b, key):
        if len(errors) >= limit:
            return
        if isinstance(a, dict) and isinstance(b, dict):
            if set(a) != set(b):
                errors.append(dict(path=key, error='keys', expected=sorted(a), actual=sorted(b)))
            for k in a.keys() & b.keys():
                visit(a[k], b[k], key + '/' + str(k))
        elif isinstance(a, list) and isinstance(b, list):
            if len(a) != len(b):
                errors.append(dict(path=key, error='length', expected=len(a), actual=len(b)))
            for i, (x, y) in enumerate(zip(a, b)):
                visit(x, y, key + '/' + str(i))
        elif a != b:
            errors.append(dict(path=key, expected=a, actual=b))
    visit(expected, actual, path)
    return errors


def query(data, opts):
    version, mode = opts.get('v', 'ZL'), opts.get('mode', 'exact')
    text = str(opts.get('q', '')).translate(LOWER)
    groups, uncertain_count = [], 0
    status = 'empty' if not text else 'invalid' if mode == 'exact' and not canonical_plain(text) else 'ready'
    if status == 'ready':
        for r in data['records']:
            if r['version'] != version or opts.get('folio', 'all') not in ('all', r['folio']) or opts.get('type', 'all') not in ('all', r['locus_type']):
                continue
            if mode == 'literal':
                if text in r['display'].translate(LOWER):
                    groups.append(dict(record_id=r['id'], slots=[]))
            else:
                matched = []
                for i, slot in enumerate(r['slots']):
                    uncertain = 'uncertain' in (slot['left_boundary'], slot['right_boundary'])
                    if slot['normalized'] == text and (opts.get('uncertain', True) or not uncertain):
                        matched.append(i)
                        uncertain_count += int(uncertain)
                if matched:
                    groups.append(dict(record_id=r['id'], slots=matched))
    hits = [data['records'][g['record_id']] for g in groups]
    counts = dict(occurrences=sum(len(g['slots']) for g in groups) if mode == 'exact' else None,
        records=len(groups), folios=len({r['folio'] for r in hits}), leaf_groups=len({r['leaf_group'] for r in hits}),
        uncertain_occurrences=uncertain_count if mode == 'exact' else None)
    page_count = max(1, (len(groups) + 49) // 50)
    page = min(max(1, opts.get('page', 1)), page_count)
    return dict(status=status, groups=groups, counts=counts, page=page, page_count=page_count,
                page_size=50, page_items=groups[(page - 1) * 50:page * 50])


def manual():
    cases = [
        ('a.b', 'a.b', ['a', 'b']), ('a,b', 'a,b', ['a', 'b']),
        ('a,,b', 'a,,b', ['a', None, 'b']), ('.a.', '.a.', [None, 'a', None]),
        ('a.[b.c].d', 'a.[b.c].d', ['a', None, 'd']),
        ('a.[b,c].d', 'a.[b,c].d', ['a', None, 'd']),
        ('a.***.b', 'a.***.b', ['a', None, 'b']),
        ('qo[k:t]dy', 'qo[k:t]dy', [None]), ('q@003;k', 'q@003;k', ['q@003;k']),
        ('q@03;k', 'q@03;k', [None]), ('q@1000;k', 'q@1000;k', [None]),
        ("q'o", "q'o", ["q'o"]), ('q’o', 'q’o', [None]),
        ('{qok}', '{qok}', ['qok']), ('qo{k}dy', 'qo{k}dy', ['qokdy']),
        ('{q{o}k}', '{q{o}k}', ['qok']), ('{a.b}', '{a.b}', [None]),
        ('{qok.a', '{qok.a', [None]), ('qok}.a', 'qok}.a', [None, 'a']),
        ('[a}.b', '[a}.b', [None]), ('qo<->k', 'qo k', ['qo', 'k']),
        ('qo<~>k', 'qo k', ['qo', 'k']), ('{a<->b}', '{a b}', [None]),
        ('qo<note>k', 'qok', ['qok']), ('A.😀b.C', 'a.😀b.c', ['a', None, 'c']),
        ('<script>alert(1)</script>', 'alert(1)', [None]),
    ]
    result = []
    for raw, shown, values in cases:
        display, slots = lex(raw)
        assert display == shown and [s['normalized'] for s in slots] == values, raw
        for slot in slots:
            assert display[slot['display_start']:slot['display_end']] == display_fragment(slot['raw'])
        result.append(dict(raw=raw, expected_display=shown, expected_normalized=values, reconstructed_slots=slots))
    assert [(s['display_start'], s['display_end']) for s in lex('A.😀b.C')[1]] == [(0, 1), (2, 4), (5, 6)]
    assert [(s['left_boundary'], s['right_boundary']) for s in lex('a,,b')[1]] == [('start', 'uncertain'), ('uncertain', 'uncertain'), ('uncertain', 'end')]
    synthetic = []
    for i, raw in enumerate(['a,a.b.[a:b].a', 'aaa']):
        shown, slots = lex(raw)
        synthetic.append(dict(id=i, version='ZL', locator='same', folio='f85r2', leaf_group=leaf('f85r2'), locus_type='@P0', raw=raw, display=shown, slots=slots))
    toy = {'records': synthetic}
    assert query(toy, {'q': 'a'})['counts']['occurrences'] == 3
    assert query(toy, {'q': 'a', 'uncertain': False})['counts']['occurrences'] == 1
    assert query(toy, {'q': 'aa', 'mode': 'literal'})['counts']['records'] == 1
    assert query(toy, {'q': ''})['counts']['records'] == 0
    assert query(toy, {'q': '.*', 'mode': 'literal'})['counts']['records'] == 0
    _, locations, _ = maps_and_counts(synthetic)
    assert locations['same']['ZL'] == [0, 1]
    assert leaf('f85r2') == leaf('f86v') == leaf('fRos') == 'f85_86'
    return result


def image_audit(data):
    manifest = read(VOYNICH / 'research7h/visual_audit/yale_manifest.json')
    receipt = read(VOYNICH / 'research7h/visual_audit/yale_image_receipt.json')
    canvases = {c['id']: c for c in manifest['items']}
    images = {r['folio']: r for r in receipt['images']}
    expected = defaultdict(set)
    for canvas in canvases.values():
        labels = [s for values in canvas.get('label', {}).values() for s in values]
        urls = [a['body']['id'] for page in canvas.get('items', []) for a in page.get('items', []) if isinstance(a.get('body'), dict) and a['body'].get('type') == 'Image']
        for label in labels:
            if re.fullmatch(r'[0-9]+[rv][0-9]*', label):
                expected['f' + label].update(urls)
    counts = Counter()
    assert set(data['folios']) == {r['folio'] for r in data['records']}
    for folio, entry in data['folios'].items():
        assert entry['leaf_group'] == leaf(folio)
        assert entry['collection_url'] == 'https://collections.library.yale.edu/catalog/2002046'
        allowed = set(expected.get(folio, set()))
        if folio in images:
            allowed.add(images[folio]['source_url'])
        link = entry['image_link']
        if link is not None:
            assert link in allowed and entry['image_mapping_evidence'], (folio, link)
        elif len(allowed) == 1:
            raise AssertionError(('omitted exact image', folio))
        assert entry['study20_url'] == ('#manuscript?folio=' + folio if folio in images else None)
        for evidence in entry['image_mapping_evidence']:
            if evidence['source'] == 'yale_manifest':
                c = canvases[evidence['canvas_id']]
                assert evidence['canvas_label'] == c['label']
                assert evidence['image_link'] in expected[folio]
            elif evidence['source'] == 'study20_image_receipt':
                origin = images[folio]
                for k, v in evidence.items():
                    if k != 'source':
                        assert origin[k] == v, (folio, k)
            else:
                raise AssertionError(('unknown mapping evidence', evidence['source']))
        counts[entry['image_mapping_status']] += 1
    return dict(counts)


def execute(data_path, output):
    assert not output.exists(), 'Use a new audit output directory; preserve earlier failures.'
    output.mkdir(parents=True)
    try:
        examples = manual()
        write(output / 'manual_examples.json', examples)
        data = read(data_path)
        assert data['schema_version'] == 1
        rows = independent_records()
        postings, locators, counts = maps_and_counts(rows)
        errors = differences(rows, data['records'], '/records')
        errors += differences(postings, data['postings'], '/postings')
        errors += differences(locators, data['by_locator'], '/by_locator')
        errors += differences(counts, data['metadata']['counts'], '/metadata/counts')
        write(output / 'errors.json', errors)
        assert not errors, 'Independent parser disagrees; see errors.json, do not overwrite this run.'
        for version in SOURCE_FILES:
            assert data['sources'][version]['sha256'] == SOURCE_SHA[version]
            assert data['sources'][version]['source_file'] == 'sources/' + SOURCE_FILES[version]
        for entry in data['metadata']['mapping_inputs'].values():
            assert sha(VOYNICH / entry['source_file']) == entry['sha256']
        assert sha(CONCORDANCE / 'design.txt') == data['metadata']['design_sha256']
        image_counts = image_audit(data)
        assert image_counts == data['metadata']['image_mapping_counts']
        duplicates = {k: v for k, v in locators.items() if any(len(ids) > 1 for ids in v.values())}
        assert data['metadata']['duplicate_locators'] == duplicates
        # Query cases are a scalar record scan, not a replay of the posting lookup.
        cases = []
        for version in SOURCE_FILES:
            for q in ['', 'daiin', 'qok', '@003;', '[a:b]']:
                for uncertain in [True, False]:
                    cases.append(dict(v=version, mode='exact', q=q, uncertain=uncertain, folio='all', type='all', page=1))
            for q in ['aa', '?', '[', '.*', ' ', 'SH', '😀']:
                cases.append(dict(v=version, mode='literal', q=q, uncertain=True, folio='all', type='all', page=1))
            common = max(postings[version], key=lambda token: len(postings[version][token]))
            base = dict(v=version, mode='exact', q=common, uncertain=True, folio='all', type='all')
            cases.extend(dict(base, page=page) for page in [1, 2, 999999])
            cases.append(dict(base, page=1, folio='f1r'))
            cases.append(dict(base, page=1, type='@P0'))
            cases.append(dict(base, page=2, folio='f1r', type='@P0', uncertain=False))
        fixtures = [{'options': options, 'expected': query({'records': rows}, options)} for options in cases]
        write(output / 'query_fixtures.json', fixtures)
        for version in SOURCE_FILES:
            assert sha(VOYNICH / 'sources' / SOURCE_FILES[version]) == SOURCE_SHA[version]
        result = dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), all_data_checks_passed=True,
            data_sha256=sha(data_path), auditor_sha256=sha(HERE / 'replay.py'), source_sha256=SOURCE_SHA,
            counts=counts, records=len(rows), exact_posting_entries=sum(sum(map(len, p.values())) for p in postings.values()),
            duplicate_locators=duplicates, mapping_counts=image_counts, manual_examples=len(examples), query_fixture_cases=len(fixtures),
            all_records_slots_offsets_postings_and_locators_equal=True, source_bytes_unchanged=True,
            no_author_builder_or_normalizer_imports=True, browser_test_performed=False,
            frontend_query_comparison='pending separate Node comparison',
            scope='Descriptive full public transcription audit, including already revealed reserve; no new scientific hypotheses, model scores, translation or image proofreading.')
        write(output / 'audit_report.json', result)
        print(json.dumps(result, ensure_ascii=False))
    except Exception as exc:
        write(output / 'failure.json', dict(type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc(), auditor_sha256=sha(HERE / 'replay.py')))
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', type=Path)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    if args.data:
        assert args.output
        execute(args.data.resolve(), args.output.resolve())
    else:
        print(json.dumps({'synthetic_only_passed': True, 'cases': len(manual())}))
