#!/usr/bin/env python3
"""Assemble the explicit manual 97-row scientific review; never infer verdicts.
The TSV is manually authored after reading all frozen per-row facts and
constraints. This program only copies, dereferences, hashes and validates.
"""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import json,hashlib,csv

HERE=Path(__file__).resolve().parent
LEDGER=HERE.parent.parent
ROOT=LEDGER.parent
REPO=ROOT.parents[3]
SUBJECT=LEDGER/'astronomical_site/report_v1.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def now():return datetime.now(timezone.utc).isoformat()
def at(x,pointer):
    for k in pointer.strip('/').split('/'):
        k=k.replace('~1','/').replace('~0','~')
        x=x[int(k)] if isinstance(x,list) else x[k]
    return x
def put(n,v):
    p=HERE/n
    if p.exists():raise FileExistsError(p.name)
    p.write_text(v if isinstance(v,str) else json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    freeze=read(HERE/'input_freeze_v1.json')
    for f in freeze['source_files']:assert sha(REPO/f['file'])==f['sha256'],f['file']
    subject=read(SUBJECT)
    manual=list(csv.DictReader((HERE/'manual_review_v1.tsv').open(),delimiter='\t'))
    assert [r['region_uid'] for r in manual]==freeze['fixed_region_ids']==[r['region_uid'] for r in subject['rows']]
    assert len(manual)==len({r['region_uid'] for r in manual})==97
    cache={}; checks=0; rows=[]
    for i,(m,original) in enumerate(zip(manual,subject['rows'])):
        refs=[]
        for r in original['source_refs']:
            if r['file'] not in cache:cache[r['file']]=read(REPO/r['file'])
            assert sha(REPO/r['file'])==r['sha256']
            value=at(cache[r['file']],r['json_pointer'])
            assert value==r['original_field_value']
            refs.append(r);checks+=1
        assert refs[0]['json_pointer'].endswith('/observation_facts')
        assert refs[1]['json_pointer'].endswith('/candidate_constraints')
        assert m['verdict'] in ['adequate','overly_strict']
        fields=['assessment_status','whole_window_evidence_scope','writing_presence',
                'role_observed_present','role_candidates','mixed_roles_observed',
                'primary_hypothesis_assessment','NA_reasons']
        old={k:original[k] for k in fields}
        proposed=json.loads(json.dumps(old))
        difference=[]
        if m['verdict']=='overly_strict':
            # The two IDs were explicitly selected in the manual TSV; no prose classifier.
            assert m['region_uid'] in ['f71v:ZO08','f72v1:ZO09']
            proposed.update(assessment_status='record_reviewed',whole_window_evidence_scope='full_window',
                role_candidates=[],mixed_roles_observed=False,
                primary_hypothesis_assessment='supported_for_stated_scope',NA_reasons=[])
            difference=[k for k in fields if old[k]!=proposed[k]]
        row={'region_uid':m['region_uid'],'panel':original['panel'],
             'original_box_xyxy':original['original_box_xyxy'],
             'primary_proposition_domain':original['primary_proposition_domain'],
             'review_status':'all_listed_frozen_facts_read_and_scientifically_reviewed',
             'original_coding':old,'reviewer_proposed_coding':proposed,
             'role_judgment':'原宽角色或未定保留有依据；没有由本文新增文字身份、语义或图像判断。',
             'whole_window_and_H_judgment':m['reason'],
             'verdict':m['verdict'],'specific_reason':m['reason'],
             'changed_field_proposals':difference,
             'original_row_reference':{'file':str(SUBJECT.relative_to(REPO)),'sha256':sha(SUBJECT),
                                       'json_pointer':f'/rows/{i}'},
             'evidence_source_refs':refs,
             'core_fact_ref_indices':[0,1],
             'exact_original_coding_scope_justification':original['scope_justification'],
             'all_original_subgroup_options_retained':original['full_block_grouping_notes'],
             'all_original_candidate_objects_retained':original['candidate_object_ids_context_only'],
             'unresolved_contacts_not_upgraded':True,
             'no_new_image_confirmation':True,
             'not_a_vote_or_overwrite':True}
        if difference:
            row['difference_scope']={
                'reason_NA_not_established':'所引原文未指出额外未覆盖书写组、跨空间层成分或文字身份全区未定，困难限定于局部接触/轮廓分离。',
                'recommended_full_scope_meaning':'在合同允许整组空间描述承载全框已观察书写成分的意义上支持；不是逐像素穷尽、完整铭文、文字-对象独有对应或读序。',
                'limits_preserved':'接点细节、字与手/星轮廓局部分离仍未解；不得升级P/E关系或认证历史指代。',
                'future_contrary_evidence':'若另有固定原记录明确某书写成分未覆盖或跨场，须凭该精确字段另议；本审查没有新看图以排除这种可能。'}
        rows.append(row)
    assert len(rows)==97
    report={'schema':'literature_scientific_cross_review_site_v1','created_utc':now(),
            'reviewer_id':'literature','subject_observer':'astronomical_site',
            'subject_report_sha256':sha(SUBJECT),'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),
            'fixed_panel_order':subject['fixed_panel_order'],'rows':rows,
            'inventory_only':{'reviewed_rows':97,'verdicts':dict(Counter(r['verdict'] for r in rows)),
                              'all_source_refs_verified':checks},
            'manual_method':{'file':'manual_review_v1.tsv','sha256':sha(HERE/'manual_review_v1.tsv'),
                'reasoning_is_per_ID_not_keyword_classifier':True,'program_only_assembly_reference_check':True},
            'exposure_and_limits':['同一AI代理，已知自己113项编码和原全12资料；不是外部盲审或独立原图复读。',
              '实际逐ID阅读原观察事实、候选约束和原编码理由；哈希核对只证明引用一致，不替代本表科学理由。',
              '没有新看图、字符串匹配、相位、语义或统计评分，也未读根未冻结审查。',
              '原97项全部保持不变；建议并列保留，由根协调证据范围，不按多数票解决。',
              '未定角色或空的已认证角色集合不能支持全称命题；域外不作阴性或成功项。',
              '本次两处范围建议不改变原全12已知反例或完整序列资格门，亦不认证文字命名。'],
            'root_adjudication_status':'pending; original coding remains frozen'}
    put('report_v1.json',report)
    lines=['literature对astronomical_site固定97项的逐ID科学复核','',
       '审查基于冻结原记录，没有新看图。角色、全框范围和H结论分别判断。原编码完整保留，任何建议不覆盖原稿；同一AI、已知自身编码，不称独立盲验证。',
       '97项均完成科学理由审查；95项现有证据及限定足够，2项全框NA的现有理由过严。此计数仅审稿登记，不是测量成功率。',
       '两处建议：f71v:ZO08、f72v1:ZO09。原事实分别给出整条短组的位置；most of local crop可分及small local contacts难分都没有明确指出未覆盖的其他书写层。建议在原记录已观察整组的范围内支持H，同时保留接点/墨迹角色未解。此建议不是证明不可见墨迹不存在。','']
    for r in rows:
        lines += [r['region_uid']+' — '+r['verdict'],
          '原角色/范围/H：'+json.dumps(r['original_coding'],ensure_ascii=False),
          '复核建议：'+json.dumps(r['reviewer_proposed_coding'],ensure_ascii=False),
          '理由：'+r['specific_reason']]
        for idx in r['core_fact_ref_indices']:
            ref=r['evidence_source_refs'][idx]
            lines += ['原字段：'+ref['file']+' '+ref['json_pointer'],
                      'SHA：'+ref['sha256'],'值：'+json.dumps(ref['original_field_value'],ensure_ascii=False)]
        lines += ['']
    lines += ['限制']+report['exposure_and_limits']+['']
    put('report_v1.txt','\n'.join(lines))
    put('validation_v1.json',{'created_utc':now(),'all_passed':True,'all_97_original_IDs_order_boxes_preserved':True,
        'all_exact_source_reference_values_verified':checks,'original_coding_not_modified':True,
        'all_rows_have_manual_scientific_reason':True,'scope':'程序验证是记录完整性；逐行理由才是科学审查，二者不等同。'})
    names=['protocol_v1.txt','input_freeze_v1.json','manual_review_v1.tsv','assemble_review_v1.py','report_v1.json','report_v1.txt','validation_v1.json']
    put('output_freeze_v1.json',{'schema':'literature_reviews_site_output_freeze_v1','created_utc':now(),
        'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),
        'files':[{'path':n,'sha256':sha(HERE/n)} for n in names],
        'all_97_scientific_reviews_completed':True,'root_unfrozen_review_not_read':True,'no_original_coding_replaced':True})
    print(json.dumps({'report_sha256':sha(HERE/'report_v1.json'),'output_freeze_sha256':sha(HERE/'output_freeze_v1.json'),
        'reviewed_rows':97,'reference_checks':checks}))
if __name__=='__main__':main()
