"""Check listed source bytes and native crop pixels without inferring image roles."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from PIL import Image


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def locate(alias, expected_hash, directories):
    # Public aliases never select paths outside the explicitly supplied roots.
    candidates = [directory / Path(alias).name for directory in directories]
    matches = [path for path in candidates if path.is_file() and digest(path) == expected_hash]
    if not matches:
        raise ValueError(f"No matching retained bytes for alias {Path(alias).name}")
    return matches[0]


def audit(observation_path, expected_ids, source_directories, view_directories):
    raw = observation_path.read_bytes()
    observation = json.loads(raw)
    assert [row['id'] for row in observation['entries']] == expected_ids
    views = {row['id']: row for row in observation['actual_view_receipts']}
    assert len(views) == len(observation['actual_view_receipts'])
    rows, sources, used = [], [], set()
    for entry in observation['entries']:
        source_path = locate(entry['source_file_alias'], entry['source_image_sha256'], source_directories)
        with Image.open(source_path) as handle:
            source = handle.convert('RGB')
        assert list(source.size) == entry['source_dimensions']
        sources.append({'entry': entry['id'], 'source_sha256': entry['source_image_sha256'],
                        'dimensions': list(source.size), 'matches': True})
        assert len(set(entry['view_refs'])) == len(entry['view_refs'])
        for view_id in entry['view_refs']:
            view = views[view_id]
            path = locate(view['file_alias'], view['sha256'], view_directories)
            box = view['original_xywh']
            assert len(box) == 4 and all(type(value) is int for value in box)
            x, y, width, height = box
            assert 0 <= x < x + width <= source.width and 0 <= y < y + height <= source.height
            with Image.open(path) as handle:
                actual = handle.convert('RGB')
            expected = source.crop((x, y, x + width, y + height))
            assert actual.size == expected.size and actual.tobytes() == expected.tobytes()
            rows.append({'entry': entry['id'], 'view_id': view_id,
                         'source_sha256': entry['source_image_sha256'],
                         'view_sha256': view['sha256'], 'native_xywh': box,
                         'hash_and_native_RGB_pixels_match': True})
            used.add(view_id)
    assert used == set(views), 'All recorded actual views must be assigned to a listed entry'
    return {'schema': 'native_source_views_audit_v2',
            'checked_utc': datetime.now(timezone.utc).isoformat(),
            'observation_sha256': sha256(raw).hexdigest(),
            'script_sha256': digest(Path(__file__)), 'all_checks_pass': True,
            'entry_count': len(sources), 'distinct_view_count': len(used),
            'entry_view_relation_count': len(rows), 'sources': sources, 'views': rows,
            'limits': ['Checks retained source bytes, dimensions, integer bounds and decoded RGB pixel identity only.',
                       'Does not independently prove the recorded human/AI view time, visual interpretation, coverage or local exclusion.',
                       'Requires privately retained images; output exports no images or private directory paths.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--observation', type=Path, required=True)
    parser.add_argument('--expected-ids', nargs='+', required=True)
    parser.add_argument('--source-directory', type=Path, action='append', required=True)
    parser.add_argument('--view-directory', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.observation, args.expected_ids, args.source_directory, args.view_directory)
    with args.output.open('x') as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(json.dumps({key: result[key] for key in ['all_checks_pass', 'entry_count', 'distinct_view_count']}))
