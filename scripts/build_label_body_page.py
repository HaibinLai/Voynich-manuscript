"""Build the public label/body snapshot from saved, versioned results."""
from pathlib import Path
import gzip
import hashlib
import json
import statistics

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'research/research_next/label_body/saved_v1'

def load(name):
    raw = (SOURCE/name).read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith('.gz') else raw)

def candidate(row):
    output = {k: row[k] for k in ['locator', 'word']}
    for version in ['ZL', 'IT']:
        output[version] = {k: row[version][k] for k in
            ['folio', 'leaf', 'type', 'own_n', 'own_m', 'own', 'control', 'delta', 'control_leaves', 'body_hits']}
    return output

results = load('results.json')
candidates = load('candidates.json')
calibration = load('calibration.json.gz')
data = {
    'schema_version': 1,
    'snapshot': load('complete.json')['completed_utc'],
    'results': results,
    'calibration': {v: {
        'vocabulary_size': c['vocabulary_size'],
        'seeds': len(c['seeds']),
        'mean_delta': c['mean_delta'],
        'independent_std': statistics.stdev(x['independent']['delta'] for x in c['seeds']),
        'independent_range': [min(x['independent']['delta'] for x in c['seeds']), max(x['independent']['delta'] for x in c['seeds'])],
        'caution': c['caution'],
    } for v, c in calibration.items()},
    'candidates': {
        'common': candidates['shared_identical_eligible_labels'],
        'hit_count': len(candidates['both_hit']),
        'no_hit_count': len(candidates['both_no_hit']),
        'discordant_count': candidates['shared_identical_eligible_labels'] - len(candidates['both_hit']) - len(candidates['both_no_hit']),
        'hits': [candidate(r) for r in candidates['both_hit'][:6]],
        'no_hits': [candidate(r) for r in candidates['both_no_hit'][:6]],
        'note': candidates['note'],
    },
    'inputs': [{'path': name, 'sha256': hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()}
               for name in ['results.json', 'candidates.json', 'calibration.json.gz', 'complete.json']],
}
target = ROOT / 'site/data/label-body.json'
target.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
print(f'{target.relative_to(ROOT)}: {target.stat().st_size} bytes')
