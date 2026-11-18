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
    ('object_registry_v1.json','object-registry.json'),
    ('object_registry_v1.txt','object-registry.txt'),
    ('visual/unresolved_sources/review.json','remaining-source-review.json'),
    ('visual/unresolved_sources/review.txt','remaining-source-review.txt'),
    ('visual/unresolved_sources/receipt.json','remaining-source-receipt.json'),
    ('literature/hand_attribution_audit/audit_v1.md','hand-attribution-review.md'),
    ('literature/hand_attribution_audit/audit_v1.json','hand-attribution-review.json'),
    ('session.json','session.json'),
    ('plan.txt','plan.txt'),
    ('stage_assessment_v1.txt','stage-assessment.txt'),
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
    ('visual/crossplant/protocol.txt','crossplant-visual-protocol.txt'),
    ('visual/crossplant/protocol_addendum_01.txt','crossplant-visual-protocol-addendum.txt'),
    ('visual/crossplant/crossplant_visual_review_v1.txt','crossplant-visual-review.txt'),
    ('visual/crossplant/crossplant_visual_review_v1.json','crossplant-visual-review.json'),
    ('visual/crossplant/verification_receipt.json','crossplant-visual-verification.json'),
    ('visual/crossplant/completed_image_freeze_v1.json','crossplant-visual-freeze.json'),
    ('visual/crossplant/PUBLICATION_SCOPE.txt','crossplant-image-publication-scope.txt'),
    ('design/crossplant/protocol_v1.txt','crossplant-protocol.txt'),
    ('design/crossplant/report_v2.txt','crossplant-report.txt'),
    ('design/crossplant/summary_v2.json','crossplant-summary.json'),
    ('design/crossplant/support_v1.json','crossplant-candidates.json'),
    ('design/crossplant/audit_v1.json','crossplant-audit.json'),
    ('design/crossplant/audit_v1.txt','crossplant-audit.txt'),
    ('design/crossplant/audit_adapter_note.txt','crossplant-audit-adapter-note.txt'),
    ('design/crossplant/publication_projection.json','crossplant-publication-projection.json'),
    ('design/crossplant/REPRODUCE_PUBLIC.txt','crossplant-reproduce.txt'),
    ('design/crossplant/run_v2/complete.json','crossplant-complete.json'),
    ('design/crossplant/run_v2/freeze.json','crossplant-freeze.json'),
    ('design/known_herbal/protocol_v1.txt','known-herbal-protocol.txt'),
    ('design/known_herbal/report_v1.txt','known-herbal-report.txt'),
    ('design/known_herbal/run_v1/summary.json','known-herbal-summary.json'),
    ('design/known_herbal/audit_v1.json','known-herbal-audit.json'),
    ('design/known_herbal/audit_v1.txt','known-herbal-audit.txt'),
    ('design/known_herbal/source_provenance.json','known-herbal-source.json'),
    ('design/boundary_bridge/protocol_v1.txt','boundary-protocol.txt'),
    ('design/boundary_bridge/report_v1.txt','boundary-report.txt'),
    ('design/boundary_bridge/publication_projection_v1.json','boundary-results.json'),
    ('design/boundary_bridge/run_v1/main_table_72.json','boundary-all-rules.json'),
    ('design/boundary_bridge/audit_v1.json','boundary-audit.json'),
    ('design/boundary_bridge/audit_v1.txt','boundary-audit.txt'),
    ('design/boundary_bridge/audit_implementation_freeze_v1.json','boundary-audit-freeze.json'),
    ('design/boundary_bridge/hit_trace_v1.json','boundary-hit-traces.json'),
    ('design/boundary_bridge/hit_trace_notes_v1.txt','boundary-hit-notes.txt'),
    ('design/boundary_bridge/delivery_manifest_v1.json','boundary-delivery.json'),
    ('design/boundary_bridge/run_v1/complete.json','boundary-complete.json'),
    ('design/boundary_bridge/REPRODUCE_PUBLIC.txt','boundary-reproduce.txt'),
    ('visual/boundary_hits/review.txt','boundary-image-review.txt'),
    ('visual/boundary_hits/review.json','boundary-image-review.json'),
    ('visual/boundary_hits/receipt.json','boundary-image-receipt.json'),
    ('visual/boundary_hits/protocol.txt','boundary-image-protocol.txt'),
    ('visual/boundary_hits/queue.json','boundary-image-queue.json'),
    ('visual/boundary_hits/freeze.json','boundary-image-freeze.json'),
    ('visual/boundary_hits/crop_receipt_v1.json','boundary-image-crops-v1.json'),
    ('visual/boundary_hits/crop_receipt_v2.json','boundary-image-crops-v2.json'),
    ('visual/boundary_hits/source_receipt.json','boundary-image-sources.json'),
    ('visual/order_targets/review_v1.json','order-targets-review.json'),
    ('visual/order_targets/review_v1.txt','order-targets-review.txt'),
    ('visual/order_targets/protocol_v1.txt','order-targets-protocol.txt'),
    ('visual/order_targets/queue_v1.json','order-targets-queue.json'),
    ('visual/order_targets/verification_receipt_v1.json','order-targets-verification.json'),
    ('visual/order_targets/assets_manifest.json','order-targets-assets.json'),
    ('visual/order_targets/publication_projection.json','order-targets-publication-projection.json'),
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

CROSS=SOURCE/'design/crossplant'
cross_audit=json.loads((CROSS/'audit_v1.json').read_text())
assert cross_audit['status']=='PASS' and cross_audit['failure_count']==0
assert sha(CROSS/'run_v2/complete.json')==cross_audit['complete_sha256']
assert sha(CROSS/'audit.py')==cross_audit['audit_source_sha256']
cross_complete=json.loads((CROSS/'run_v2/complete.json').read_text())
for name,expected in cross_complete['files'].items():
    assert sha(CROSS/'run_v2'/name)==expected,name
cross_summary=json.loads((CROSS/'summary_v2.json').read_text())
for condition,models in cross_audit['condition_summary'].items():
    for model,values in models.items():
        recorded=cross_summary['conditions'][condition][model]
        assert recorded['target_candidate_hits']==values['target_positive_count']
        assert recorded['primary']['binary']['value']==values['source_leaf_binary_difference']
projection=json.loads((CROSS/'publication_projection.json').read_text())
for row in projection['files']:
    assert sha(CROSS/row['path'])==row['public_sha256'],row['path']

HERBAL=SOURCE/'design/known_herbal'
herbal_audit=json.loads((HERBAL/'audit_v1.json').read_text())
assert herbal_audit['passed'] and not herbal_audit['errors']
for name,expected in herbal_audit['input_hashes'].items():
    assert sha(HERBAL/'run_v1'/name)==expected,name
assert sha(HERBAL/'audit.py')==herbal_audit['audit_code_sha256']

BOUNDARY=SOURCE/'design/boundary_bridge'
boundary_audit=json.loads((BOUNDARY/'audit_v1.json').read_text())
assert boundary_audit['status']=='PASS' and boundary_audit['failure_count']==0
assert sha(BOUNDARY/'run_v1/complete.json')==boundary_audit['complete_sha256']
assert sha(BOUNDARY/'audit.py')==boundary_audit['audit_script_sha256']
assert sha(BOUNDARY/'audit_implementation_freeze_v1.json')==boundary_audit['independent_core_freeze_sha256']
boundary_freeze=json.loads((BOUNDARY/'audit_implementation_freeze_v1.json').read_text())
assert sha(BOUNDARY/boundary_freeze['frozen_implementation'])==boundary_freeze['frozen_sha256']
boundary_complete=json.loads((BOUNDARY/'run_v1/complete.json').read_text())
for name,expected in boundary_complete['files'].items():
    assert sha(BOUNDARY/'run_v1'/name)==expected,name
boundary_delivery=json.loads((BOUNDARY/'delivery_manifest_v1.json').read_text())
for name,expected in boundary_delivery['files'].items():
    assert sha(BOUNDARY/name)==expected,name
boundary_projection=json.loads((BOUNDARY/'publication_projection_v1.json').read_text())
assert boundary_projection['independent_audit']['receipt_sha256']==sha(BOUNDARY/'audit_v1.json')
for row in boundary_projection['rule_table']:
    record=next(x for x in boundary_audit['version_summaries'][row['version']]['all_rule_summary'] if x['rule']==row['rule']['id'])
    assert row['valid_labels']==record['label_valid']
    assert row['target_hit_candidates']==record['target_hit_candidates']
    assert row['delta']==record['source_leaf_delta']

BOUNDARY_VISUAL=SOURCE/'visual/boundary_hits'
visual_receipt=json.loads((BOUNDARY_VISUAL/'receipt.json').read_text())
assert visual_receipt['protocol_and_queue_match_frozen'] and not visual_receipt['changed_original_data']
assert visual_receipt['official_crops']==12 and visual_receipt['all_crops_viewed']
for row in visual_receipt['files']:
    assert sha(BOUNDARY_VISUAL/row['path'])==row['sha256'],row['path']

ORDER=SOURCE/'visual/order_targets'
order_receipt=json.loads((ORDER/'verification_receipt_v1.json').read_text())
order_projection=json.loads((ORDER/'publication_projection.json').read_text())
assert order_receipt['status']=='PASS_GEOMETRY_RECORD_INTEGRITY'
assert order_receipt['pair_count']==12 and order_receipt['target_object_regions']==14
assert order_receipt['files']['assets_manifest.json']==order_projection['original_sha256']
assert sha(ORDER/'assets_manifest.json')==order_projection['public_sha256']
order_additional={row['path']:row for row in order_projection.get('additional_files',[])}
for name,expected in order_receipt['files'].items():
    if name in order_additional:
        assert expected==order_additional[name]['original_sha256'],name
    elif name!='assets_manifest.json': assert sha(ORDER/name)==expected,name
for row in order_projection.get('additional_files',[]):
    assert sha(ORDER/row['path'])==row['public_sha256'],row['path']
registry=json.loads((SOURCE/'object_registry_v1.json').read_text())
for name,expected in registry['inputs'].items():
    assert sha(SOURCE/name)==expected,name
assert registry['counts']['relationships']==35 and registry['counts']['main_scored_relationships']==11

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
          'scope':'Explicit public text/JSON allowlist; no author thumbnails, image files or large score arrays. Leaf, crossplant, known-herbal and boundary independent audits checked against saved hashes. Boundary image records and all 12 official crop hashes verified; crops are linked to official URLs rather than exported here. Crossplant audit canonical source is the documented public traceback-path projection, not a new audit.',
          'files':receipt,'audit_sha256':sha(LEAF/'leaf_audit_v1.json'),
          'crossplant_audit_sha256':sha(CROSS/'audit_v1.json'),
          'crossplant_projection_sha256':sha(CROSS/'publication_projection.json'),
          'known_herbal_audit_sha256':sha(HERBAL/'audit_v1.json'),
          'boundary_audit_sha256':sha(BOUNDARY/'audit_v1.json')}
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'files':len(receipt),'bytes':sum(x['bytes'] for x in receipt),'audit':'PASS'},ensure_ascii=False))
