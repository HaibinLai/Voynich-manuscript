#!/usr/bin/env python3
"""Reproduce the within-leaf supplement in a new, minimal copied workspace."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SUPP = Path(__file__).resolve().parent
WORK = SUPP.parent
REPO = WORK.parents[2]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, required=True)
    out = ap.parse_args().output.expanduser().resolve()
    if out.exists() or out.is_relative_to(REPO):
        raise ValueError('Choose a nonexistent output directory outside the repository')
    manifest = json.loads((SUPP / 'reproduction_manifest_v1.json').read_text())
    for r in manifest['files']:
        if sha(WORK / r['path']) != r['sha256']:
            raise ValueError('Frozen source mismatch: ' + r['path'])
    # The historical runner writes beside itself. Run a minimal source copy,
    # never that file in the published research directory.
    target = out / 'copied-inputs'
    for name in manifest['copy_inputs']:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORK / name, dest)
    run_dir = target / 'same_leaf_supplement_v1/independent'
    subprocess.run([sys.executable, str(run_dir / 'replay.py')],
                   check=True, capture_output=True, text=True)
    checks = []
    for name in ['results_v1.json', 'missingness_v1.json', 'domains_v1.json']:
        actual, expected = run_dir / name, SUPP / 'independent' / name
        if sha(actual) != sha(expected):
            raise ValueError('Replay differs from frozen output: ' + name)
        checks.append({'file': name, 'sha256': sha(actual), 'exact_bytes_match': True})
    for r in manifest['files']:
        if sha(WORK / r['path']) != r['sha256']:
            raise ValueError('Original source changed during replay: ' + r['path'])
    receipt = {'status': 'CLEAN_COPY_REPLAY_MATCHES_SAVED_RESULTS',
               'completed_utc': datetime.now(timezone.utc).isoformat(),
               'manifest_sha256': sha(SUPP / 'reproduction_manifest_v1.json'),
               'checks': checks, 'original_files_unchanged': True,
               'scope': 'Within-leaf numerical replay plus per-node missingness. No image download or new interpretation.'}
    (out / 'receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
