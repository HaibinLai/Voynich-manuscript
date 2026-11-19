#!/usr/bin/env python3
"""Read-only delta audit, preserving the frozen v1 failures and judgments."""
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path
R=Path(__file__).resolve().parents[6]
B=R/'research/research_next/astronomical7h_20261118/zodiac_object_relations'
L=B/'block_role_ledger';A=L/'structural_audit';used={};cache={}
def raw(p):
    p=p.resolve()
    if p not in used:used[p]=p.read_bytes()
    return used[p]
def sha(p):return hashlib.sha256(raw(p)).hexdigest()
def read(p):
    p=p.resolve()
    if p not in cache:cache[p]=json.loads(raw(p))
    return cache[p]
def canon(x):return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def pointer(x,p):
    for t in p[1:].split('/'):
        t=t.replace('~1','/').replace('~0','~')
        x=x[int(t)] if isinstance(x,list) else x[t]
    return x
def nodes(x):
    yield x
    if isinstance(x,dict):
        for v in x.values():yield from nodes(v)
    elif isinstance(x,list):
        for v in x:yield from nodes(v)
def main():
    freeze=read(A/'v2_appendix_input_freeze_v1.json')
    for x in freeze['files']:assert sha(R/x['path'])==x['sha256']
    baseline=read(A/'calculation_v1.json')
    for x in read(A/'output_freeze_v1.json')['files']:assert sha(A/x['path'])==x['sha256']
    replay=subprocess.run([sys.executable,str(A/'audit_stdout_v1.py')],capture_output=True)
    assert replay.returncode==1 and replay.stdout==raw(A/'calculation_v1.json') and not replay.stderr
    # Retain the failed v1 record, rather than rerunning it against changed files.
    assert len(baseline['structural_or_source_errors'])==9 and baseline['representation_discrepancy_count']==13
    old_errors={x['where'].rsplit('/',1)[0] for x in baseline['structural_or_source_errors']}
    old_placeholder_ids={x['region_uid'] for x in baseline['representation_discrepancies']}
    results={};reports={}
    for group in ['literature','circle_spatial_observer']:
        D=L/group;old=read(D/'report_v1.json');new=read(D/'report_v2.json');out=read(D/'output_freeze_v2.json');correction=read(D/'correction_v2.json')
        for item in out['files']:assert sha(D/item['path'])==item['sha256']
        for item in read(D/'output_freeze_v1.json')['files']:assert sha(D/item['path'])==item['sha256']
        inf=read(D/'correction_input_freeze_v2.json')
        if group=='literature':
            for item in inf['source_files']:assert sha(D/item['path'])==item['sha256']
        else:
            rule=read(D/'correction_rule_v2.json');assert inf['rule_sha256']==sha(D/'correction_rule_v2.json')
            for item in rule['source_files']:assert sha(R/item['path'])==item['sha256']
        assert correction['old_report_sha256']==sha(D/'report_v1.json') and correction['new_report_sha256']==sha(D/'report_v2.json')
        oldtop={k:v for k,v in old.items() if k!='rows'}
        newtop={k:v for k,v in new.items() if k!='rows'}
        top_additions=[]
        if group=='literature':
            assert set(newtop)-set(oldtop)=={'representation_correction'}
            assert not (set(oldtop)-set(newtop))
            metadata=newtop.pop('representation_correction')
            assert metadata['source_report_sha256']==sha(D/'report_v1.json')
            assert metadata['correction_input_freeze_sha256']==sha(D/'correction_input_freeze_v2.json')
            assert metadata['new_observations_or_scoring'] is False and metadata['original_created_utc_preserved'] is True
            assert correction['top_level_only_added_field']=='representation_correction'
            top_additions=[{'json_pointer':'/representation_correction','operation':'add','new_value':metadata}]
        assert canon(oldtop)==canon(newtop)
        assert len(old['rows'])==len(new['rows'])
        changes=[];restored=copy.deepcopy(new)
        for i,(a,b,c) in enumerate(zip(old['rows'],new['rows'],restored['rows'])):
            assert a['region_uid']==b['region_uid'];uid=a['region_uid']
            if canon(a)==canon(b):continue
            if group=='literature':
                assert uid in old_placeholder_ids
                assert a['role_observed_present']==['unresolved_writing_or_graphic'] and b['role_observed_present']==[]
                assert 'uncertainty_placeholders' not in a and b['uncertainty_placeholders']==['unresolved_writing_or_graphic']
                c['role_observed_present']=a['role_observed_present'];del c['uncertainty_placeholders']
                changes.append({'region_uid':uid,'row_index':i,'field_diffs':[{'json_pointer':f'/rows/{i}/role_observed_present','operation':'replace','old_value':a['role_observed_present'],'new_value':b['role_observed_present']},{'json_pointer':f'/rows/{i}/uncertainty_placeholders','operation':'add','old_field_present':False,'new_value':b['uncertainty_placeholders']}]})
            else:
                assert uid in old_errors
                assert len(b['source_refs'])==len(a['source_refs'])+1 and canon(b['source_refs'][:-1])==canon(a['source_refs'])
                assert 'all_seed_fine_alternatives' not in a['full_block_grouping_notes'] and 'seed_fine_source_ref_indices' not in a['full_block_grouping_notes']
                ref=b['source_refs'][-1];assert b['full_block_grouping_notes']['seed_fine_source_ref_indices']==[len(a['source_refs'])]
                assert b['full_block_grouping_notes']['all_seed_fine_alternatives']==[ref['original_field_value']]
                assert ref['evidence_scope']=='context_only' and ref['file']==str((B/'seed_roster_v1.json').relative_to(R))
                assert '/fine_alternatives_original/' in ref['json_pointer']
                assert ref['original_field_value']['coarse_parent_id']==uid.split(':',1)[1]
                assert sha(R/ref['file'])==ref['sha256'] and canon(pointer(read(R/ref['file']),ref['json_pointer']))==canon(ref['original_field_value'])
                c['source_refs']=c['source_refs'][:-1];del c['full_block_grouping_notes']['all_seed_fine_alternatives'];del c['full_block_grouping_notes']['seed_fine_source_ref_indices']
                changes.append({'region_uid':uid,'row_index':i,'field_additions':[{'json_pointer':f'/rows/{i}/source_refs/{len(a["source_refs"])}','operation':'add','new_value':ref},{'json_pointer':f'/rows/{i}/full_block_grouping_notes/all_seed_fine_alternatives','operation':'add','new_value':b['full_block_grouping_notes']['all_seed_fine_alternatives']},{'json_pointer':f'/rows/{i}/full_block_grouping_notes/seed_fine_source_ref_indices','operation':'add','new_value':b['full_block_grouping_notes']['seed_fine_source_ref_indices']}]})
            assert canon(c)==canon(a)
        if group=='literature':del restored['representation_correction']
        assert canon(restored)==canon(old)
        expected_ids=old_placeholder_ids if group=='literature' else old_errors
        assert {x['region_uid'] for x in changes}==expected_ids
        declared=correction['exact_row_field_changes'] if group=='literature' else correction['changes']
        assert canon(changes)==canon(declared)
        results[group]={'old_report_sha256':sha(D/'report_v1.json'),'new_report_sha256':sha(D/'report_v2.json'),'changed_rows':len(changes),'exact_field_change_count':len(changes)*(2 if group=='literature' else 3),'exact_changes':changes,'separate_declared_top_level_additions':top_additions,'all_preexisting_other_values_equal':True,'all_H_scope_NA_writing_presence_and_candidate_values_equal':True,'all_prior_source_references_equal':True,'old_v1_hashes_unchanged':True,'declared_correction_matches_independent_delta':True,'scientific_correctness_not_adjudicated':True}
        reports[group]=new
    reports['astronomical_site']=read(L/'astronomical_site/report_v1.json')
    seed=read(B/'seed_roster_v1.json');expected={t['region_uid']:(p,t) for p in seed['panels'] for t in p['text_records']}
    seen=[];refcount=0;finecount=0
    for group,rep in reports.items():
        for row in rep['rows']:
            uid=row['region_uid'];seen.append(uid);p,t=expected[uid]
            assert row['original_box_xyxy']==t['original_box_xyxy'] and row['original_band']==t['ring_assignment_original']
            assert (row['primary_hypothesis_assessment']=='not_in_predeclared_domain')==(t['ring_assignment_original'] not in ['outer','inner','middle'])
            assert 'unresolved_writing_or_graphic' not in row['role_observed_present']
            if row['writing_presence']!='writing_like_supported':assert row['primary_hypothesis_assessment']!='supported_for_stated_scope'
            refvalues=[]
            for ref in row['source_refs']:
                assert sha(R/ref['file'])==ref['sha256'];value=pointer(read(R/ref['file']),ref['json_pointer']);assert canon(value)==canon(ref['original_field_value']);refvalues.append(value);refcount+=1
            subtree_values={canon(x) for obj in [row['full_block_grouping_notes']]+refvalues for x in nodes(obj) if isinstance(x,dict)}
            for fine in p['fine_alternatives_original']:
                if fine['coarse_parent_id']==t['original_id']:assert canon(fine) in subtree_values;finecount+=1
    assert len(seen)==len(set(seen))==322 and set(seen)==set(expected) and finecount==358
    deps={x['path']:x for x in baseline['runtime_dependencies']}
    for p,payload in used.items():deps[str(p.relative_to(R))]={'path':str(p.relative_to(R)),'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload)}
    for p in [A/'audit_stdout_v1.py',A/'audit_v2_appendices_stdout_v1.py']:
        deps[str(p.relative_to(R))]={'path':str(p.relative_to(R)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    print(json.dumps({'schema':'block_role_separate_v2_compatibility_appendices_v1','baseline_v1_failures_preserved':True,'baseline_expected_exit1_and_stdout_unchanged':True,'literature_v2':results['literature'],'circle_v2':results['circle_spatial_observer'],'selected_versions':{'circle_spatial_observer':'report_v2.json','literature':'report_v2.json','astronomical_site':'report_v1.json'},'combined_structural_scope_only':{'unique_original_rows':322,'source_references_exact':refcount,'all_raw_fine_entries_retained':finecount,'unresolved_placeholder_in_observed_roles':0,'no_judgments_replaced':True,'final_scientific_aggregation_or_approval':False},'runtime_dependencies':[deps[k] for k in sorted(deps)]},ensure_ascii=False,sort_keys=True,indent=2))
if __name__=='__main__':main()
