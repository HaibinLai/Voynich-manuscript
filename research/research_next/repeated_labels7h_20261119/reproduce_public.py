#!/usr/bin/env python3
"""Replay frozen numerical results into a new external directory.

Python standard library only. No image download, new image judgment, training,
or semantic interpretation. Frozen repository outputs are never overwritten.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    if output.exists() or output.is_relative_to(REPO):
        raise ValueError('Use a nonexistent output directory outside the repository')
    manifest = json.loads((WORK / 'reproduction_manifest_v1.json').read_text())
    for r in manifest['inputs']:
        if sha(WORK / r['path']) != r['sha256']:
            raise ValueError('Frozen input changed: ' + r['path'])
    output.mkdir(parents=True)
    main_path, control_path = output / 'main-replay.json', output / 'known-name-control.json'
    subprocess.run([sys.executable, str(WORK / 'numeric_replay/replay.py'),
                    '--work', str(WORK), '--domains', str(WORK / 'primary_results_v1/canonical_domains_v1.json'),
                    '--output', str(main_path)], check=True, capture_output=True, text=True)
    control_domains = WORK / 'known_language_control/canonical_domains_v1.json'
    subprocess.run([sys.executable, str(WORK / 'known_language_control/calculate.py'),
                    '--domains', str(control_domains), '--expected-sha', sha(control_domains),
                    '--output', str(control_path)], check=True, capture_output=True, text=True)
    actual_main = json.loads(main_path.read_text())
    expected_main = json.loads((WORK / 'numeric_replay/actual_v1/replay_results_v1.json').read_text())
    for field in ['counts', 'denominators', 'global_bounds', 'scenarios']:
        if actual_main[field] != expected_main[field]:
            raise ValueError('Main replay differs: ' + field)
    actual_control = json.loads(control_path.read_text())
    expected_control = json.loads((WORK / 'known_language_control/results_v1.json').read_text())
    for field in ['bounds', 'features', 'pairs']:
        if actual_control[field] != expected_control[field]:
            raise ValueError('Control replay differs: ' + field)
    # Includes frozen observations even though the replay uses their checked
    # projections. This does not replace the original projection/image audit.
    for r in manifest['inputs']:
        if sha(WORK / r['path']) != r['sha256']:
            raise ValueError('Input changed during replay: ' + r['path'])
    result = {'status': 'REPLAY_MATCHES_SAVED_RESULTS',
              'completed_utc': datetime.now(timezone.utc).isoformat(),
              'manifest_sha256': sha(WORK / 'reproduction_manifest_v1.json'),
              'inputs_unchanged': True,
              'compared_main': 'All16 scenarios, per-feature/per-stratum objectives and witnesses, all36 pairs, global bounds.',
              'compared_control': 'C/C11/C00, all four features and all six pairs.',
              'limits': 'Replays saved binary observations. Does not authenticate images, plant identity, labels or translations.',
              'outputs': [{'file': p.name, 'sha256': sha(p)} for p in [main_path, control_path]]}
    (output / 'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
