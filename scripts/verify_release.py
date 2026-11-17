"""Verify the published snapshot; optionally replay saved evidence in fresh folders.

Default mode needs only Python's standard library. It hashes bytes without
parsing manuscript text or opening a new experimental split. Optional replays
use the package's existing saved-data wrappers and need its Python dependencies.
Neither mode tunes models or launches a decipherment search. Optional replays
read saved evaluation packets, including already-exposed reserve records for
the parameter-sharing package; they do not open a new blind split.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import subprocess
import sys

REPO = Path(__file__).resolve().parent.parent
RESEARCH = REPO / 'research/research7h'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def safe_member(base, value):
    path = Path(value)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError('Manifest contains an unsafe relative path')
    resolved = (base / path).resolve()
    if base.resolve() not in resolved.parents or not resolved.is_file():
        raise ValueError('Missing or escaping manifest member: ' + str(path))
    return resolved


def check_manifest(manifest, base, *, container=None, path_key='path', hash_key='sha256'):
    data = json.loads(manifest.read_text())
    entries = data[container] if container else data
    checked = 0
    seen = set()
    total_bytes = 0
    for entry in entries:
        if entry.get('publish') is False:
            continue
        name = entry[path_key]
        if name in seen:
            raise ValueError('Duplicate manifest member: ' + name)
        seen.add(name)
        target = safe_member(base, name)
        if digest(target) != entry[hash_key]:
            raise ValueError('Hash mismatch: ' + str(target.relative_to(REPO)))
        size = target.stat().st_size
        if 'bytes' in entry and size != entry['bytes']:
            raise ValueError('Size mismatch: ' + str(target.relative_to(REPO)))
        if hash_key == 'public_sha256' and entry.get('transformation') is None:
            if entry['source_sha256'] != entry['public_sha256']:
                raise ValueError('Undeclared source/public change: ' + name)
        checked += 1
        total_bytes += size
    return dict(manifest=str(manifest.relative_to(REPO)), sha256=digest(manifest),
                entries_checked=checked, bytes_checked=total_bytes, passed=True)


def verify_snapshot():
    definitions = [
        (REPO/'research/sources/provenance.json', REPO/'research/sources',
         dict(path_key='file')),
        (REPO/'site/data/manifest.json', REPO/'site', dict(container='files')),
        (RESEARCH/'stage2_publication_manifest.json', RESEARCH,
         dict(container='files', hash_key='public_sha256')),
        (RESEARCH/'allograph_factor/artifact_manifest.json', RESEARCH/'allograph_factor',
         dict(container='files')),
        (RESEARCH/'metadata_sensitivity/artifact_manifest.json', RESEARCH/'metadata_sensitivity', {}),
        (RESEARCH/'line_boundary_calibration/artifact_manifest.json', RESEARCH/'line_boundary_calibration',
         dict(container='files')),
    ]
    for name, base in [('reserve_publication_manifest.json', RESEARCH),
                       ('cipher_controls/voynich_substitution/artifact_manifest.json', RESEARCH/'cipher_controls/voynich_substitution'),
                       ('line_boundary_prediction/results_artifact_manifest.json', RESEARCH/'line_boundary_prediction'),
                       ('concordance/artifact_manifest.json', RESEARCH/'concordance'),
                       ('concordance/independent_audit/artifact_manifest.json', RESEARCH/'concordance/independent_audit'),
                       ('synthesis_final/artifact_manifest.json', RESEARCH/'synthesis_final'),
                       ('version_differences/artifact_manifest.json', RESEARCH/'version_differences')]:
        path = RESEARCH/name
        if path.exists():
            definitions.append((path, base, dict(container='files')))
    parameter = REPO/'research/research_next/parameter_sharing'
    if (parameter/'manifest.json').exists():
        definitions.append((parameter/'manifest.json', parameter, dict(container='files')))
        definitions.append((parameter/'freeze.json', parameter, dict(container='files')))
    checks = [check_manifest(path, base, **options) for path, base, options in definitions]
    session = json.loads((RESEARCH/'session.json').read_text())
    return dict(passed=True, checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                checks=checks, manifests_overlap=True,
                limitation='Integrity checks validate recorded bytes, not scientific claims or semantic decipherment. Manifest counts overlap; do not sum them as unique files.',
                snapshot_stage=session.get('stage'), snapshot_status=session.get('status'),
                snapshot_updated_utc=session.get('updated_utc'),
                research_deadline_utc=session.get('deadline_utc'),
                raw_text_interpreted=False, new_split_scored=False)


def replay_commands(output):
    return {
        'parameter': ['research/research_next/parameter_sharing/independent_score_replay.py',
                      '--output', str(output/'parameter')],
        'anchor': ['research/research7h/anchor_audit/coverage_public_replay.py',
                   '--out-dir', str(output/'anchor')],
        'copy': ['research/research7h/copy_prediction/public_reproduce.py',
                 'replay', '--output', str(output/'copy')],
        'allograph': ['research/research7h/allograph_factor/public_reproduce.py',
                      'replay', '--scope', 'manuscript', '--output', str(output/'allograph')],
        'metadata': ['research/research7h/metadata_sensitivity/public_replay.py',
                     '--out-dir', str(output/'metadata')],
        'synthetic': ['research/research7h/line_boundary_calibration/public_replay.py',
                      '--output', str(output/'synthetic')],
    }


def write(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replay', nargs='+', choices=['anchor', 'copy', 'allograph', 'metadata', 'synthetic', 'parameter'],
                        help='Run named independent saved-data replays after integrity checks')
    parser.add_argument('--output', type=Path, help='Required new directory for replay receipts and logs')
    args = parser.parse_args()
    if bool(args.replay) != bool(args.output):
        parser.error('--replay and --output must be supplied together')
    if args.replay and len(set(args.replay)) != len(args.replay):
        parser.error('Each replay may be requested only once')
    report = verify_snapshot()
    if not args.replay:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return
    output = args.output.resolve()
    if output.exists() or output == REPO or REPO in output.parents:
        parser.error('Use a new output directory outside the repository')
    output.mkdir(parents=True)
    write(output/'snapshot_verification.json', report)
    jobs = replay_commands(output)
    runs = []
    for name in args.replay:
        arguments = jobs[name]
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (output/(name+'.log')).open('w') as stream:
            completed = subprocess.run([sys.executable, *arguments], cwd=REPO,
                                       stdout=stream, stderr=subprocess.STDOUT)
        runs.append(dict(name=name, entry_point=arguments[0], started_utc=started,
                         completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                         returncode=completed.returncode, passed=completed.returncode == 0,
                         log=name+'.log'))
        write(output/'replay_status.json', dict(passed=all(r['passed'] for r in runs), runs=runs,
                                              all_requested_finished=len(runs) == len(args.replay)))
        print(json.dumps(runs[-1], ensure_ascii=False), flush=True)
        if completed.returncode:
            raise SystemExit('Saved-data replay failed; its fresh output and log are preserved.')
    # Wrappers may restore ignored, hash-checked logical JSON files; original
    # manifest entries must remain unchanged after all requested replays.
    write(output/'post_replay_verification.json', verify_snapshot())
    print('All requested saved-data replays passed. No new split was scored.')


if __name__ == '__main__':
    main()
