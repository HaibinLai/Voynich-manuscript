"""Verify saved native crops and freeze W7 view coordinates before visual reading."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parents[1]
W7 = ROOT / 'research/research_next/source_geometry7h_20261119'
PRIVATE = ROOT.parent / 'output/voynich/research_next'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    old_path = ROOT / 'research/research_next/hierarchical7h_20261119/F_observation_v1/observation_v1.json'
    old = json.loads(old_path.read_text())
    entries = {e['id']: e for e in old['entries']}
    candidates = list((PRIVATE / 'repeated_labels7h_20261119').rglob('*'))
    candidates += list((PRIVATE / 'hierarchical7h_20261119/F_observation_v1').glob('*'))
    files, views, locations = {}, [], {}

    def locate(alias, digest):
        matches = [p for p in candidates if p.is_file() and p.name == Path(alias).name and sha(p) == digest]
        assert matches, (alias, digest)
        return matches[0]

    for e in old['entries']:
        path = locate(e['source_file_alias'], e['source_image_sha256'])
        with Image.open(path) as im:
            assert list(im.size) == e['source_dimensions']
        files[e['id']] = path
        locations[e['id'] + '_original_source'] = str(path)

    for prior in old['actual_view_receipts']:
        path = locate(prior['file_alias'], prior['sha256'])
        x, y, w, h = prior['original_xywh']
        with Image.open(path) as image, Image.open(files[prior['entry']]) as source:
            cropped = source.crop((x, y, x + w, y + h))
            assert image.size == cropped.size, prior['id']
            difference = ImageChops.difference(image.convert('RGB'), cropped.convert('RGB'))
            assert difference.getbbox() is None, prior['id']
            dimensions = list(image.size)
        views.append({
            'id': prior['id'], 'entry': prior['entry'], 'file_alias': prior['file_alias'],
            'sha256': sha(path), 'dimensions': dimensions,
            'original_xywh': prior['original_xywh'],
            'coordinate_frame': 'saved_old_raster',
            'source_sha256': entries[prior['entry']]['source_image_sha256'],
            'source_dimensions': entries[prior['entry']]['source_dimensions'],
            'native_crop_pixel_equality_verified': True,
            'exposure': 'Previously viewed image; same-image informed rereading',
            'current_display_status': 'PLANNED_NOT_YET_DISPLAYED',
            'scope': 'Registered old viewport; examine original IDs and aggregate gaps, not a claim of complete pixel certification',
        })
        locations[prior['id']] = str(path)

    candidate = PRIVATE / 'source_geometry7h_20261119/metadata_batch04/M10.response'
    with Image.open(candidate) as im:
        assert im.format == 'PNG' and im.size == (1334, 2000)
    assert sha(candidate) == '1687c61f648acfe5d7a0d2d2f12065f3b3487bd4fa431b0b2d7161fe4c199dd9'
    views.append({
        'id': 'F03_native_region_M10', 'entry': 'F03',
        'file_alias': 'private-output/source_geometry7h/M10.response',
        'sha256': sha(candidate), 'dimensions': [1334, 2000],
        'original_xywh': [2800, 500, 1334, 2000],
        'coordinate_frame': 'official_service_native_4134x2796',
        'source_dimensions': [4134, 2796], 'source_request_id': 'M10',
        'native_crop_pixel_equality_verified': None,
        'pixel_equality_limit': 'No saved full native raster; service-request provenance and delivered dimensions verified, not independent equality to unseen master',
        'exposure': 'New region file from previously exposed same official image service, not independent photography',
        'current_display_status': 'PLANNED_NOT_YET_DISPLAYED',
        'scope': 'First confirm same entry through page layout, heading proximity and three upper caps/red lower region; no coordinates transferred from old raster. Then assess broad region only; later precise windows need a recorded addendum before detailed display.',
    })
    locations['F03_native_region_M10'] = str(candidate)
    output = {
        'schema': 'seventh_actual_view_plan_v1',
        'frozen_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'FROZEN_BEFORE_W7_VISUAL_READING',
        'old_observation_sha256': sha(old_path),
        'protocol_sha256': sha(W7 / 'source_observation_protocol_v1.json'),
        'source_qualification_sha256': sha(W7 / 'source_qualification_v1.json'),
        'entry_order': list(entries),
        'observer': 'root, informed same AI; image observation followed by separate textual review',
        'views': views,
        'coverage_contract': 'All six original units/joins/bodies/child routes/aliases/cases/exclusions and every unresolved aggregate region in operational_scope_inventory_v1. No new H/H4 or Voynich scores.',
        'no_new_image_pixels_exported': True,
        'planned_views_are_not_successful_display_receipts': True,
    }
    target = W7 / 'observation/view_plan_v1.json'
    target.parent.mkdir(exist_ok=True)
    with target.open('x') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        f.write('\n')
    mapping = PRIVATE / 'source_geometry7h_20261119/view_locations_v1.json'
    with mapping.open('x') as f:
        json.dump(locations, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({'views': len(views), 'old_native_views_verified': len(views) - 1, 'plan_sha256': sha(target)}))


if __name__ == '__main__':
    main()
