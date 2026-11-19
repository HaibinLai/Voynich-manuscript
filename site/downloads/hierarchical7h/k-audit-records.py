"""Audit frozen K bookkeeping and privately held source/crop pixel identity.

Does not infer image roles, measure new features, or export images.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from PIL import Image


def audit(observation_path, private_research_root):
    raw = observation_path.read_bytes()
    record = json.loads(raw)
    assert [e['id'] for e in record['entries']] == ['K01', 'K02', 'K03', 'K04']
    inventory = private_research_root / 'repeated_labels7h_20261119/known_language_inventory'
    candidates = [inventory,
                  private_research_root / 'repeated_labels7h_20261119/measurement_development_v1',
                  private_research_root / 'hierarchical7h_20261119/K_development_v1']
    views = {v['id']: v for v in record['actual_view_receipts']}
    assert len(views) == len(record['actual_view_receipts'])
    checks, totals = [], {'units': 0, 'joins': 0, 'child_aliases': 0, 'views': 0}
    for entry in record['entries']:
        name = entry['id']
        source = inventory / Path(entry['source_file_alias']).name
        assert sha256(source.read_bytes()).hexdigest() == entry['source_image_sha256']
        source_image = Image.open(source).convert('RGB')
        assert list(source_image.size) == entry['source_dimensions']
        carrier_ids = {u['carrier_id']: u for u in entry['units'].values()}
        assert len(carrier_ids) == len(entry['units'])
        bodies = {b['id'] for b in entry['bodies']}
        for uid, unit in entry['units'].items():
            assert unit['body_or_join_id'] in bodies | set(entry['joins'])
            assert len(unit['carrier_transverse_boundary_witnesses_xy']) == 2
            assert len(unit['carrier_path_xy']) >= 2
            assert set(unit['view_refs']) <= set(views)
            for feature in unit['allowed_classes']:
                child_count = len(unit['direct_children'])
                assert (feature == 'Q0' and child_count == 0) or (feature == 'Q1' and child_count == 1) or (feature == 'Q2' and child_count >= 2)
                assert unit['local_exclusion_evidence']['scope']
                if feature in ('Q0', 'Q1'):
                    assert unit['local_exclusion_evidence']['excludes']
            for child in unit['direct_children']:
                if 'same_physical_channel_as' in child:
                    target = carrier_ids[child['same_physical_channel_as']]
                    assert child['path_xy'] == target['carrier_path_xy']
                    assert child['endpoint_bbox_xywh'] == target['zone_bbox_xywh']
                    totals['child_aliases'] += 1
            totals['units'] += 1
        for join in entry['joins'].values():
            assert len(join['arms']) >= 3 and join['continuity_basis']
            assert set(join['view_refs']) <= set(views)
            totals['joins'] += 1
        coverage_ids = {c['id'] for c in entry['coverage']}
        for case in entry['cases']:
            assert set(case['residual']['coverage_refs']) <= coverage_ids
        for vid in entry['view_refs']:
            view = views[vid]
            files = [d / Path(view['file_alias']).name for d in candidates]
            path = next(p for p in files if p.is_file() and sha256(p.read_bytes()).hexdigest() == view['sha256'])
            x, y, width, height = view['original_xywh']
            assert all(type(v) is int for v in (x, y, width, height))
            assert 0 <= x < x + width <= source_image.width and 0 <= y < y + height <= source_image.height
            actual = Image.open(path).convert('RGB')
            expected = source_image.crop((x, y, x + width, y + height))
            assert actual.size == expected.size and actual.tobytes() == expected.tobytes()
            checks.append({'entry': name, 'view_id': vid, 'source_sha256': entry['source_image_sha256'],
                           'view_sha256': view['sha256'], 'hash_and_native_pixels_match': True})
            totals['views'] += 1
    return {'schema': 'root_K_record_source_audit_v1', 'checked_utc': datetime.now(timezone.utc).isoformat(),
            'observation_sha256': sha256(raw).hexdigest(), 'script_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
            'all_checks_pass': True, 'totals': totals, 'source_view_checks': checks,
            'scope': 'All listed K source/view identities and basic relation bookkeeping.',
            'limits': ['Does not validate visual truth or completeness of local observations.',
                       'Existing coverage IDs do not prove that all relevant coverage references were attached; textual review is separate.',
                       'No new feature values or name comparisons; private paths and image pixels are not included in this output.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--observation', type=Path, required=True)
    parser.add_argument('--private-research-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.observation, args.private_research_root)
    with args.output.open('x') as out:
        json.dump(result, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print(json.dumps(result['totals']))
