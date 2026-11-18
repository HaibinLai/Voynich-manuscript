#!/usr/bin/env python3
"""Replay the archived known-English audit without changing its inputs."""
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import json
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
REPO = BASE.parents[4]
MANIFEST_SHA256 = '9e87ab2eaae9d0535b0a205585c2c0b658e3439b63678986db7983c789e59b2a'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify():
    manifest = BASE / 'manifest.json'
    if sha(manifest) != MANIFEST_SHA256:
        raise ValueError('Archived manifest hash mismatch')
    hashes = {'manifest.json': sha(manifest)}
    for entry in json.loads(manifest.read_text())['files']:
        relative = Path(entry['path'])
        path = (BASE / relative).resolve()
        if relative.is_absolute() or '..' in relative.parts or BASE not in path.parents:
            raise ValueError('Unsafe archived input path')
        digest = sha(path)
        if digest != entry['sha256'] or path.stat().st_size != entry['bytes']:
            raise ValueError('Archived input mismatch: ' + entry['path'])
        hashes[entry['path']] = digest
    return hashes

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New directory outside this checkout')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output == REPO or REPO in output.parents:
        raise ValueError('Output must be a new directory outside the checkout')
    before = verify()
    source = gzip.decompress((BASE / 'A35365.xml.gz').read_bytes())
    expected = json.loads((BASE / 'run_v1/freeze.json').read_text())['source_sha256']
    if hashlib.sha256(source).hexdigest() != expected:
        raise ValueError('Uncompressed source hash mismatch')
    output.mkdir(parents=True, exist_ok=False)
    xml = output / 'A35365.xml'
    xml.write_bytes(source)
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    command = [sys.executable, '-B', str(BASE/'audit.py'), '--source', str(xml), '--output', str(output/'audit')]
    process = subprocess.run(command, text=True, capture_output=True)
    (output/'audit.log').write_text(process.stdout + process.stderr)
    after = verify()
    if before != after:
        raise ValueError('Archived input bytes changed during replay')
    report_path = output/'audit.json'
    report = json.loads(report_path.read_text()) if report_path.exists() else {}
    archived = json.loads((BASE/'audit_v1.json').read_text())
    compared = ['counts', 'max_float_difference', 'errors', 'structural_checks',
                'toy_checks', 'source_sha256', 'audit_code_sha256', 'no_hit_ids',
                'log2_insufficient_controls', 'leakage_positive_rows', 'post_result_measurement_example']
    differences = [key for key in compared if report.get(key) != archived.get(key)]
    passed = process.returncode == 0 and report.get('passed') is True and not differences
    receipt = dict(passed=passed, started_utc=started,
                   completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   original_inputs_unchanged=before == after, original_inputs=before,
                   compared_archived_fields=compared, differing_fields=differences,
                   matrix_cells=report.get('counts', {}).get('matrix_cells'),
                   wrapper_sha256=sha(Path(__file__)), output_audit_sha256=sha(report_path) if report_path.exists() else None,
                   returncode=process.returncode,
                   scope='Replay of the already-published independent DOM audit; no new experiment, split, image review or semantic validation.')
    (output/'replay_receipt.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({key: receipt[key] for key in ['passed', 'matrix_cells', 'original_inputs_unchanged', 'differing_fields']}))
    if not passed:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
