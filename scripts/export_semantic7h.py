"""Export reviewed seven-hour records through an explicit public allowlist.

No recursive directory copy; no unfinished crossplant results, local images,
machine paths, credentials, or large permutation arrays are exported. Original
report bytes are preserved, including its historical audit-in-progress wording;
the later independent audit is exported separately and governs release status.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT/'research/research_next/semantic7h_20261118'
OUT = ROOT/'site/downloads/semantic7h'
LEAF = SOURCE/'design/leaf_controls'

FILES = [
    ('session.json','session.json'),
    ('plan.txt','plan.txt'),
    ('publication.json','publication.json'),
    ('visual/protocol_v1.txt','visual-protocol.txt'),
    ('visual/geometry_review_v1.txt','geometry-review.txt'),
    ('visual/geometry_review_v1.json','geometry-review.json'),
    ('visual/geometry_publication_projection.json','geometry-projection.json'),
    ('visual/root_review_v1.txt','guided-image-review.txt'),
    ('visual/root_review_v1.json','guided-image-review.json'),
    ('literature/plant_pairs.json','plant-pairs.json'),
    ('literature/plant_pairs.csv','plant-pairs.csv'),
    ('literature/label_support.json','label-support.json'),
    ('literature/label_support.csv','label-support.csv'),
    ('literature/label_support_notes.txt','label-support-notes.txt'),
    ('literature/external_constraints.txt','external-constraints.txt'),
    ('literature/external_anchors.json','external-anchors.json'),
    ('literature/davis_scope.txt','davis-scope.txt'),
    ('literature/davis_rules.json','davis-rules.json'),
    ('design/leaf_controls/protocol.txt','leaf-controls-protocol.txt'),
    ('design/leaf_controls/support_v1.json','support.json'),
    ('design/leaf_controls/report.txt','leaf-report.txt'),
    ('design/leaf_controls/REPRODUCE.txt','leaf-reproduce.txt'),
    ('design/leaf_controls/run_v2/summary.json','leaf-summary.json'),
    ('design/leaf_controls/leaf_audit_v1.json','leaf-audit.json'),
    ('design/leaf_controls/leaf_audit_v1.txt','leaf-audit.txt'),
    ('design/leaf_controls/exchangeability_diagnostics.json','leaf-exchangeability.json'),
    ('design/leaf_controls/representation_change.txt','leaf-representation-change.txt'),
    ('design/leaf_controls/schema_scope.txt','leaf-schema-scope.txt'),
    ('design/leaf_controls/run_v2/freeze.json','leaf-freeze.json'),
    ('design/leaf_controls/run_v2/selection.json','leaf-selection.json'),
    ('design/leaf_controls/run_v2/complete.json','leaf-complete.json'),
]

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

audit = json.loads((LEAF/'leaf_audit_v1.json').read_text())
assert audit['status']=='PASS' and not audit['failures']
for relative, expected in audit['source_hashes'].items():
    assert sha(LEAF/relative)==expected, f'Audited input changed: {relative}'
completion = json.loads((LEAF/'run_v2/complete.json').read_text())
for row in completion['files']:
    path=LEAF/'run_v2'/row['path']
    assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes'], row['path']
summary = json.loads((LEAF/'run_v2/summary.json').read_text())
assert len(audit['packages'])==6
for package in audit['packages']:
    recorded=summary[package['version']][package['condition']]
    assert package['leaves']==recorded['leaf_count']
    for model, values in recorded['models'].items():
        for field in ['observed','excess_over_mean','p_upper']:
            assert values[field]==package['joint'][model][field]
    for model, values in recorded['increments'].items():
        for field in ['observed','excess_over_mean','p_upper']:
            assert values[field]==package['joint']['delta_'+model][field]

staged=[]
for source_name, destination in FILES:
    path=SOURCE/source_name
    raw=path.read_bytes()
    text=raw.decode('utf-8-sig')
    assert '/Users/' not in text and '/home/' not in text, f'Private path in {source_name}'
    assert 'BEGIN PRIVATE KEY' not in text and 'ghp_' not in text, f'Credential-like material in {source_name}'
    staged.append((source_name,destination,raw))
OUT.mkdir(parents=True,exist_ok=True)
receipt=[]
for source_name,destination,raw in staged:
    target=OUT/destination
    target.write_bytes(raw)
    receipt.append({'path':destination,'source':source_name,'bytes':len(raw),
                    'sha256':hashlib.sha256(raw).hexdigest(),'transformation':'none'})
manifest={'created_utc':datetime.now(timezone.utc).isoformat(),
          'scope':'Explicit public allowlist; no crossplant or permutation-array exports. Independent leaf audit PASS checked against saved source and result hashes.',
          'files':receipt,'audit_sha256':sha(LEAF/'leaf_audit_v1.json')}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':len(receipt),'bytes':sum(x['bytes'] for x in receipt),'audit':'PASS'},ensure_ascii=False))
