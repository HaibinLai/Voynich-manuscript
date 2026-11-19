#!/usr/bin/env python3
"""Only relocate the uncertainty placeholder. No new scientific decisions."""
from pathlib import Path
from datetime import datetime,timezone
import copy,json,hashlib
P=Path(__file__).resolve().parent
U='unresolved_writing_or_graphic'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(n):return json.loads((P/n).read_text())
def now():return datetime.now(timezone.utc).isoformat()
def put(n,x):
    p=P/n
    if p.exists():raise FileExistsError(n)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    freeze=read('correction_input_freeze_v2.json')
    for x in freeze['source_files']:assert sha(P/x['path'])==x['sha256']
    oldfreeze=read('output_freeze_v1.json')
    for x in oldfreeze['files']:assert sha(P/x['path'])==x['sha256']
    old=read('report_v1.json');new=copy.deepcopy(old);diffs=[]
    for i,row in enumerate(new['rows']):
        if U not in row['role_observed_present']:continue
        assert 'uncertainty_placeholders' not in row
        original=copy.deepcopy(row['role_observed_present'])
        row['role_observed_present']=[v for v in original if v!=U]
        row['uncertainty_placeholders']=[U]
        diffs.append({'region_uid':row['region_uid'],'row_index':i,'field_diffs':[
            {'json_pointer':f'/rows/{i}/role_observed_present','operation':'replace','old_value':original,'new_value':row['role_observed_present']},
            {'json_pointer':f'/rows/{i}/uncertainty_placeholders','operation':'add','old_field_present':False,'new_value':[U]}]})
    assert len(diffs)==freeze['expected_changed_rows']==13
    affected={d['region_uid'] for d in diffs}
    for a,b in zip(old['rows'],new['rows']):
        c=copy.deepcopy(b)
        if a['region_uid'] in affected:
            del c['uncertainty_placeholders']
            c['role_observed_present']=a['role_observed_present']
        assert c==a,a['region_uid']
    assert len(old['rows'])==len(new['rows'])==113
    for k in old:
        if k!='rows':assert old[k]==new[k]
    new['representation_correction']={
        'version':2,'created_utc':now(),'source_report':'report_v1.json','source_report_sha256':sha(P/'report_v1.json'),
        'correction_input_freeze_sha256':sha(P/'correction_input_freeze_v2.json'),
        'description':'仅将13行未定占位从role_observed_present移至uncertainty_placeholders；表示统一，不是新的科学判断。',
        'unchanged_scientific_fields':'其余原角色/候选、scope/H/NA/writing_presence、source_refs、理由及所有原记录逐值不变。',
        'new_observations_or_scoring':False,'original_created_utc_preserved':True}
    put('report_v2.json',new)
    # Verify the serialized artifact too; do not rely only on the in-memory copy.
    loaded=read('report_v2.json');assert loaded==new
    for x in oldfreeze['files']:assert sha(P/x['path'])==x['sha256']
    put('correction_v2.json',{
        'schema':'block_role_uncertainty_representation_correction_v2','created_utc':now(),
        'input_freeze_sha256':sha(P/'correction_input_freeze_v2.json'),
        'old_report_sha256':sha(P/'report_v1.json'),'new_report_sha256':sha(P/'report_v2.json'),
        'changed_rows':13,'exact_row_field_changes':diffs,
        'top_level_only_added_field':'representation_correction',
        'validation':{'all_113_rows_order_unchanged':True,'all_other_row_fields_exactly_equal':True,
            'all_other_top_level_fields_exactly_equal':True,'all_v1_frozen_files_unchanged':True,
            'roles_or_scope_rejudged':False,'new_images_or_scores':False},
        'scientific_review_linkage':'根对113项科学复核仍基于v1判断；最终结果可显式绑定此v2纯表示转换，不替换旧稿。'})
    names=['correction_rule_v2.txt','correction_input_freeze_v2.json','correct_representation_v2.py','report_v2.json','correction_v2.json']
    put('output_freeze_v2.json',{'schema':'literature_block_role_representation_output_freeze_v2','created_utc':now(),
        'source_output_freeze_v1_sha256':sha(P/'output_freeze_v1.json'),
        'correction_input_freeze_sha256':sha(P/'correction_input_freeze_v2.json'),
        'files':[{'path':n,'sha256':sha(P/n)} for n in names],
        'pure_representation_change':True,'original_scientific_judgments_unchanged':True})
    print(json.dumps({'report_v2_sha256':sha(P/'report_v2.json'),'correction_v2_sha256':sha(P/'correction_v2.json'),
        'output_freeze_v2_sha256':sha(P/'output_freeze_v2.json'),'affected_ids':[d['region_uid'] for d in diffs]},ensure_ascii=False))
if __name__=='__main__':main()
