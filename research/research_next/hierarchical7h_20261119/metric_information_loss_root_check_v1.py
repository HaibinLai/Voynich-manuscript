"""Independent check from serialized artificial tree shapes, not agent code."""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path


def parse_shape(text):
    pos = 0

    def node():
        nonlocal pos
        if text[pos] == 'L':
            pos += 1
            return None
        assert text[pos] == '('
        pos += 1
        left = node()
        assert text[pos] == ','
        pos += 1
        right = node()
        assert text[pos] == ')'
        pos += 1
        return (left, right)

    root = node()
    assert pos == len(text)
    return root


def check(data):
    checks = []
    for row in data['artificial_examples']:
        stack = [(parse_shape(row['unordered_shape']), 0)]
        counts, a, leaves, internal, height = [0] * 4, [0] * 3, 0, 0, 0
        while stack:
            node, depth = stack.pop()
            height = max(height, depth)
            if node is None:
                leaves += 1
                counts[0] += 1  # Bare end-zone.
            else:
                internal += 1
                direct_free_children = sum(child is None for child in node)
                a[direct_free_children] += 1
                counts[direct_free_children] += 1
                counts[3] += 1
                stack.extend((child, depth + 1) for child in node)
        assert (leaves, internal, height, a) == (row['leaves'], row['internal_nodes'], row['height'], row['a'])
        assert counts == row['raw_Q0_Q1_Q2_QJ']
        assert [min(2, n) for n in counts] == row['capped_signature']
        if internal:
            assert leaves == internal + 1 and leaves == a[1] + 2*a[2]
            assert a[2] == a[0] + 1
            assert counts == [3*a[0]+a[1]+2, a[1], a[0]+1, 2*a[0]+a[1]+1]
        checks.append({'id': row['id'], 'raw_counts': counts, 'height': height, 'matches': True})
    by_id = {r['id']: r for r in data['artificial_examples']}
    first, second = by_id['double_comb_p1_q3'], by_id['double_comb_p2_q2']
    assert first['raw_Q0_Q1_Q2_QJ'] == second['raw_Q0_Q1_Q2_QJ'] == [7, 2, 2, 5]
    assert first['height'] == 4 and second['height'] == 3
    assert first['unordered_shape'] != second['unordered_shape']
    return checks


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    results = check(json.loads(raw))
    receipt = {'schema': 'root_artificial_tree_information_loss_check_v1',
               'checked_utc': datetime.now(timezone.utc).isoformat(),
               'input_sha256': sha256(raw).hexdigest(),
               'script_sha256': sha256(Path(__file__).read_bytes()).hexdigest(),
               'examples': results, 'all_pass': True,
               'derivation_check': 'For internal nodes, L=I+1 and L=a1+2a2 imply a2=a0+1. Direct node-role counts give the stated raw vector. After saturation a0=0 gives three signatures; a0>=1 gives three more, according to a1=0/1/>=2.',
               'limits': 'Ideal artificial full binary trees only; no image or F data read, no real name score or method revision.'}
    with args.output.open('x') as out:
        json.dump(receipt, out, ensure_ascii=False, indent=2)
        out.write('\n')
    print('Independently checked', len(results), 'serialized artificial trees and the same-raw/different-height counterexample.')
