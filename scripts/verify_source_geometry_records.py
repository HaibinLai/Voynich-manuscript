"""Audit W7 record provenance and preserved inputs; does not certify image claims."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
W7 = ROOT / 'research/research_next/source_geometry7h_20261119'
PRIVATE = ROOT.parent / 'output/voynich/research_next/source_geometry7h_20261119'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    failures = []

    def check(condition, label):
        if not condition:
            failures.append(label)

    baseline = read(W7 / 'prior_payload_baseline_v1.json')
    for item in baseline['files']:
        path = ROOT / item['path']
        check(path.is_file() and sha(path) == item['sha256'], 'prior payload: ' + item['path'])

    old_path = ROOT / 'research/research_next/hierarchical7h_20261119/F_observation_v1/observation_v1.json'
    old = read(old_path)
    report_path = W7 / 'observation/root_observation_v1.json'
    report = read(report_path)
    check(report['original_observation_sha256'] == sha(old_path), 'old observation binding')
    check(report['completed_fixed_entry_order'] == [e['id'] for e in old['entries']], 'fixed six entry order')
    route_counts = {'direct_children': 0, 'uncertain_child_routes': 0, 'known_nonqualifying_relation': 0, 'representative_candidates': 0}
    for current, original in zip(report['entries'], old['entries']):
        prefix = original['id']
        for field in ('units', 'joins', 'bodies', 'unresolved'):
            prior = original[field]
            expected = list(prior) if isinstance(prior, dict) else [r['id'] for r in prior]
            check([r['id'] for r in current[field]] == expected, prefix + ' ' + field)
        check([r['id'] for r in current['coverage_review']] == [r['id'] for r in original['coverage']], prefix + ' coverage')
        check(current['original_at_most_one_retained'] == original['at_most_one'], prefix + ' mutual exclusion')
        for actual, prior in zip(current['case_and_aliases_retained'], original['cases']):
            check(actual == {k: prior[k] for k in ('id', 'choices', 'unselected_candidates')}, prefix + ' complete case choices/aliases ' + prior['id'])
        for actual in current['units']:
            prior = original['units'][actual['id']]
            for field in ('direct_children', 'uncertain_child_routes'):
                check([c['id'] for c in actual.get(field, [])] == [c['id'] for c in prior.get(field, [])], prefix + '/' + actual['id'] + '/' + field)
                route_counts[field] += len(prior.get(field, []))
            non = actual['known_nonqualifying_relations_reviewed']
            check([c.get('original', c)['id'] for c in non] == [c['id'] for c in prior['known_nonqualifying_relation']], prefix + '/' + actual['id'] + '/nonT')
            route_counts['known_nonqualifying_relation'] += len(prior['known_nonqualifying_relation'])
            check(actual['alternatives_retained'] == prior['alternatives'], prefix + '/' + actual['id'] + '/alternatives')
        for actual, prior in zip(current['unresolved'], original['unresolved']):
            check(actual.get('canonical_exclusions', []) == prior.get('canonical_exclusions', []), prefix + '/' + prior['id'] + '/canonical exclusions')
            check([c['id'] for c in actual.get('representative_candidates', [])] == [c['id'] for c in prior.get('representative_candidates', [])], prefix + '/' + prior['id'] + '/candidates')
            route_counts['representative_candidates'] += len(prior.get('representative_candidates', []))

    plan = read(W7 / 'observation/view_plan_v1.json')
    addendum = read(W7 / 'observation/native_view_addendum_v1.json')
    crops = read(W7 / 'observation/native_crop_receipts_v1.json')
    receipts = read(W7 / 'observation/display_receipts_v1.json')
    expected = {v['id']: v for v in plan['views']}
    extra = {v['id']: v for v in addendum['new_views']}
    extra_hashes = {v['id']: v for v in crops['records']}
    mapping = read(PRIVATE / 'view_locations_v1.json')
    seen = set()
    for receipt in receipts['records']:
        ident = receipt['id']
        check(ident not in seen, 'duplicate display: ' + ident)
        seen.add(ident)
        if ident in expected:
            v = expected[ident]
            check(receipt['file_sha256'] == v['sha256'], 'display hash: ' + ident)
            check(receipt['original_xywh'] == v['original_xywh'], 'display coordinates: ' + ident)
            check(sha(Path(mapping[ident])) == v['sha256'], 'actual private bytes: ' + ident)
            frozen = plan['frozen_utc']
        else:
            v = extra[ident]
            path = PRIVATE / 'native_views_v1' / (ident + '.png')
            check(receipt['file_sha256'] == extra_hashes[ident]['sha256'] == sha(path), 'new crop hash: ' + ident)
            check(receipt['original_xywh'] == v['official_native_xywh'], 'new crop native frame: ' + ident)
            x, y, w, h = v['local_xywh']
            with Image.open(PRIVATE / 'metadata_batch04/M10.response') as source, Image.open(path) as crop:
                check(ImageChops.difference(source.crop((x, y, x+w, y+h)).convert('RGB'), crop.convert('RGB')).getbbox() is None, 'new crop exact pixels: ' + ident)
            frozen = addendum['frozen_coordinates_utc']
        check(datetime.fromisoformat(receipt['successful_display_confirmed_utc']) >= datetime.fromisoformat(frozen), 'display before freeze: ' + ident)
    check(seen == set(expected) | set(extra), 'complete 29-view receipt inventory')

    qualification = read(W7 / 'source_qualification_v1.json')
    check(qualification['elapsed_seconds'] <= 1800, 'bounded official source stage')
    check(datetime.fromisoformat(qualification['actual_stage_closed_utc']) <= datetime.fromisoformat(qualification['hard_stop_utc']), 'source deadline')
    for request in qualification['requests']:
        match = [p for p in PRIVATE.glob('metadata_batch*/' + request['id'] + '.response')]
        check(len(match) == 1, 'unique response bytes: ' + request['id'])
        if match:
            check(sha(match[0]) == request['sha256'] and match[0].stat().st_size == request['bytes'], 'source bytes: ' + request['id'])
    result = {
        'schema': 'seventh_root_record_integrity_v1',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS_RECORD_INTEGRITY_NOT_SCIENTIFIC_OR_GOAL_ACCEPTANCE' if not failures else 'FAIL',
        'script_sha256': sha(Path(__file__)),
        'root_observation_sha256': sha(report_path),
        'display_receipts_sha256': sha(W7 / 'observation/display_receipts_v1.json'),
        'old_payload_files_verified': len(baseline['files']),
        'entry_scopes_verified': 6,
        'route_counts_verified': route_counts,
        'display_records_checked': len(receipts['records']),
        'source_responses_verified': len(qualification['requests']),
        'new_native_crops_pixel_equal': len(extra),
        'failures': failures,
        'limits': 'Verifies file bytes, coordinate and identity references, inherited scope and timing records. Does not independently inspect visual meaning, certify Q/T/J or g, prove historical identity, or accept publication/completion.',
    }
    target = W7 / 'observation/root_record_integrity_v1.json'
    with target.open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(bool(failures))


if __name__ == '__main__':
    main()
