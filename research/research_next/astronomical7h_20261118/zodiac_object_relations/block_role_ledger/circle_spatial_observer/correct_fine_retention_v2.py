#!/usr/bin/env python3
"""Read-only deterministic v2 projection: append exact seed fine provenance only."""
import copy
import hashlib
import json
from pathlib import Path
D=Path(__file__).resolve().parent
R=D.parents[5]
B=D.parents[1]
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rule=read(D/'correction_rule_v2.json')
    frozen=read(D/'correction_input_freeze_v2.json')
    assert frozen['rule_sha256']==sha(D/'correction_rule_v2.json')
    for x in rule['source_files']:assert sha(R/x['path'])==x['sha256']
    old=read(D/'report_v1.json');new=copy.deepcopy(old);seed_path=B/'seed_roster_v1.json';seed=read(seed_path)
    changed=[]
    for row in new['rows']:
        if row['region_uid'] not in rule['exact_region_ids']:continue
        panel_index,panel=next((i,p) for i,p in enumerate(seed['panels']) if p['panel']==row['panel'])
        original_id=row['region_uid'].split(':',1)[1]
        fine=[(i,x) for i,x in enumerate(panel['fine_alternatives_original']) if x['coarse_parent_id']==original_id]
        assert len(fine)==1
        assert 'all_seed_fine_alternatives' not in row['full_block_grouping_notes']
        assert 'seed_fine_source_ref_indices' not in row['full_block_grouping_notes']
        indices=[]
        for fi,item in fine:
            indices.append(len(row['source_refs']))
            row['source_refs'].append({'file':str(seed_path.relative_to(R)),'sha256':sha(seed_path),'json_pointer':f'/panels/{panel_index}/fine_alternatives_original/{fi}','original_field_value':item,'evidence_scope':'context_only','interpretive_use':'Exact original unsplit fine entry added for provenance completeness only. It does not replace the parent window, change any spatial role/scope/H/NA judgment, or add an opportunity.'})
        row['full_block_grouping_notes']['all_seed_fine_alternatives']=[item for _,item in fine]
        row['full_block_grouping_notes']['seed_fine_source_ref_indices']=indices
        changed.append(row['region_uid'])
    assert set(changed)==set(rule['exact_region_ids']) and len(changed)==9
    restored=copy.deepcopy(new)
    for row,prior in zip(restored['rows'],old['rows']):
        if row['region_uid'] not in changed:assert row==prior;continue
        del row['full_block_grouping_notes']['all_seed_fine_alternatives']
        del row['full_block_grouping_notes']['seed_fine_source_ref_indices']
        row['source_refs']=row['source_refs'][:len(prior['source_refs'])]
        assert row==prior
    assert restored==old
    print(json.dumps(new,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
