#!/usr/bin/env python3
"""Generate the two frozen, explicit path projections or verify public bytes.

Default --verify-public is read-only and works with the public package.
--generate requires the exact original private-path freeze records; it changes
only the registered JSON pointers, never their embedded original-artifact hashes.
Existing unequal outputs are refused. No Git, browser, or source writes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

BASE = Path('research/research_next/astronomical7h_20261118/publication/evidence_coverage_review')
PLAN = BASE / 'proposed_minimal_public_files_v1.json'
PLAN_SHA = 'd445c218adce54a1ce5fc962f2b9739ce085d7097a220e241dad3616c9011db7'
RECEIPT = BASE / 'new_projection_field_fidelity_receipt_v1.json'

def sha(data):
    return hashlib.sha256(data).hexdigest()

def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2) + '\n').encode()

def pointer_tokens(pointer):
    return [t.replace('~1', '/').replace('~0', '~') for t in pointer.strip('/').split('/')]

def get(obj, pointer):
    for token in pointer_tokens(pointer):
        obj = obj[int(token)] if isinstance(obj, list) else obj[token]
    return obj

def put(obj, pointer, value):
    tokens = pointer_tokens(pointer)
    for token in tokens[:-1]:
        obj = obj[int(token)] if isinstance(obj, list) else obj[token]
    key = int(tokens[-1]) if isinstance(obj, list) else tokens[-1]
    obj[key] = value

def differences(a, b, pointer=''):
    if type(a) is not type(b):
        return [pointer]
    if isinstance(a, dict):
        if a.keys() != b.keys():
            return [pointer + '/@keys']
        return [p for k in a for p in differences(a[k], b[k], pointer + '/' + k.replace('~', '~0').replace('/', '~1'))]
    if isinstance(a, list):
        if len(a) != len(b):
            return [pointer + '/@length']
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in differences(x, y, pointer + '/' + str(i))]
    return [] if a == b else [pointer]

def leaf_count(obj):
    if isinstance(obj, dict):
        return sum(leaf_count(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(leaf_count(v) for v in obj)
    return 1

def safe_write(path, payload):
    if path.exists():
        if path.read_bytes() != payload:
            raise ValueError('Refusing to overwrite unequal output: ' + path.name)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--generate', action='store_true')
    mode.add_argument('--verify-public', action='store_true')
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[5])
    args = parser.parse_args()
    root = args.repo_root
    plan_bytes = (root / PLAN).read_bytes()
    assert sha(plan_bytes) == PLAN_SHA
    plans = json.loads(plan_bytes)['new_explicit_path_projections']
    receipts = []
    for plan in plans:
        destination = root / plan['proposed_site_destination']
        if args.generate:
            source_bytes = (root / plan['source']).read_bytes()
            assert sha(source_bytes) == plan['source_sha256']
            source = json.loads(source_bytes)
            projected = copy.deepcopy(source)
            for change in plan['changes']:
                pointer = change['json_pointer']
                original = get(source, pointer)
                assert sha(json.dumps(original, ensure_ascii=False).encode()) == change['original_value_sha256']
                assert isinstance(original, str) and pointer.endswith('/path')
                public = change['proposed_public_value']
                # The source absolute prefix is never serialized into receipts.
                assert original.endswith('/' + public)
                put(projected, pointer, public)
            changed = differences(source, projected)
            assert changed == [x['json_pointer'] for x in plan['changes']]
            payload = encode(projected)
            assert sha(payload) == plan['proposed_sha256'] and len(payload) == plan['proposed_bytes']
            assert b'/Users/' not in payload and b'/home/' not in payload
            safe_write(destination, payload)
            assert (root / plan['source']).read_bytes() == source_bytes
            receipts.append({
                'original_source': plan['source'], 'original_source_sha256': plan['source_sha256'],
                'public_projection': plan['proposed_site_destination'], 'projection_sha256': sha(payload),
                'projection_bytes': len(payload), 'changed_fields': plan['changes'],
                'total_scalar_leaves': leaf_count(source), 'changed_scalar_leaves': len(changed),
                'unchanged_scalar_leaves': leaf_count(source) - len(changed),
                'same_keys_array_lengths_and_types': True,
                'all_unlisted_fields_exactly_equal': True,
                'embedded_original_artifact_hashes_and_bytes_unchanged': True,
                'original_source_unchanged_after_generation': True,
                'no_private_absolute_paths_in_projection': True,
            })
        else:
            payload = destination.read_bytes()
            assert sha(payload) == plan['proposed_sha256'] and len(payload) == plan['proposed_bytes']
            obj = json.loads(payload)
            for change in plan['changes']:
                assert get(obj, change['json_pointer']) == change['proposed_public_value']
            assert b'/Users/' not in payload and b'/home/' not in payload
    if args.generate:
        receipt = {
            'schema': 'two_explicit_freeze_path_projection_fidelity_v1',
            'plan': str(PLAN), 'plan_sha256': PLAN_SHA,
            'generator': str(BASE / 'generate_freeze_projections_v1.py'),
            'files': receipts,
            'scope': 'Exact original hash gate, registered pointer changes only, full recursive object comparison; no original freeze or scientific field changed.',
            'hash_semantics': 'Embedded hashes and byte counts refer to original frozen artifacts. Public relative identifiers do not assert child-file availability or byte identity of separate child projections.',
            'replay_limits': 'Public verification checks plan, output hashes and replacement fields without private originals. Regeneration and independent source-to-projection fidelity replay require the original hash-matching records; no claim that the entire private source chain is public.',
            'publication_status': 'Local files generated; no Git, remote or browser verification.',
        }
        safe_write(root / RECEIPT, encode(receipt))
    else:
        receipt = json.loads((root / RECEIPT).read_bytes())
        assert receipt['plan_sha256'] == PLAN_SHA
        assert len(receipt['files']) == len(plans)
        for row, plan in zip(receipt['files'], plans):
            assert row['original_source_sha256'] == plan['source_sha256']
            assert row['projection_sha256'] == plan['proposed_sha256']
            assert row['changed_fields'] == plan['changes']
    print(json.dumps({'mode': 'generate' if args.generate else 'verify-public', 'projection_count': len(plans), 'changed_path_fields': sum(len(x['changes']) for x in plans), 'all_checks_passed': True}, sort_keys=True))

if __name__ == '__main__':
    main()
