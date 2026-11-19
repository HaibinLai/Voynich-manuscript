#!/usr/bin/env python3
"""Assemble eight manually reasoned reviews; no image or scientific inference."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
HERE=Path(__file__).resolve().parent
LEDGER=HERE.parent.parent
ROOT=LEDGER.parent
REPO=ROOT.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def now():return datetime.now(timezone.utc).isoformat()
def at(x,p):
    for k in p.strip('/').split('/'):
        k=k.replace('~1','/').replace('~0','~')
        x=x[int(k)] if isinstance(x,list) else x[k]
    return x
def put(n,x):
    p=HERE/n
    if p.exists():raise FileExistsError(n)
    p.write_text(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
    inp=read(HERE/'input_freeze_v1.json')
    for f in inp['source_files']:assert sha(REPO/f['file'])==f['sha256'],f['file']
    root_path=LEDGER/'root_adjudication/manual_scope_decisions_v1.json'
    decisions=read(root_path)['decisions']
    manual=read(HERE/'manual_review_v1.json')['decisions']
    assert [x['region_uid'] for x in manual]==inp['fixed_ids']==[x['region_uid'] for x in decisions]
    assert len(manual)==8
    cache={};rows=[];refcount=0
    own_ids={'f72v3:ZO05','f72v3:ZO13'}
    review_ids={'f71v:ZO08','f72v1:ZO09'}
    own_path=LEDGER/'literature/report_v1.json'
    prior_path=LEDGER/'cross_reviews/literature_reviews_site/report_v1.json'
    for i,(m,d) in enumerate(zip(manual,decisions)):
        row={k:v for k,v in m.items() if k!='sources'}
        refs=[]
        for file,ptr,scope,use in m['sources']:
            path=ROOT/file
            if file not in cache:cache[file]=read(path)
            assert str(path.relative_to(REPO)) in {x['file'] for x in inp['source_files']}
            refs.append({'file':str(path.relative_to(REPO)),'sha256':sha(path),'json_pointer':ptr,
                'original_field_value':at(cache[file],ptr),'evidence_scope':scope,'interpretive_use':use})
        refcount+=len(refs)
        row['source_refs']=refs
        row['root_decision_reference']={'file':str(root_path.relative_to(REPO)),'sha256':sha(root_path),
            'json_pointer':f'/decisions/{i}','original_field_value':d}
        row['previous_participation']='此前仅见旧汇编/原记录，本次未参与这条原空间角色编码。'
        row['previous_judgment_refs']=[]
        if m['region_uid'] in own_ids:
            old=read(own_path);j=next(j for j,r in enumerate(old['rows']) if r['region_uid']==m['region_uid'])
            row['previous_participation']='本代理曾将此项原编码为partial/NA；现在仅重新审查相同原文能承载的范围，不新增像素证据，原件不改。'
            for key in ['whole_window_evidence_scope','primary_hypothesis_assessment','scope_justification']:
                ptr=f'/rows/{j}/{key}'
                row['previous_judgment_refs'].append({'file':str(own_path.relative_to(REPO)),'sha256':sha(own_path),
                    'json_pointer':ptr,'original_field_value':at(old,ptr)})
        if m['region_uid'] in review_ids:
            old=read(prior_path);j=next(j for j,r in enumerate(old['rows']) if r['region_uid']==m['region_uid'])
            row['previous_participation']='本代理此前已复核并建议此项整组full/H支持；本次为同材料反证审查，不算第二次独立确认。'
            ptr=f'/rows/{j}/whole_window_and_H_judgment'
            row['previous_judgment_refs'].append({'file':str(prior_path.relative_to(REPO)),'sha256':sha(prior_path),
                'json_pointer':ptr,'original_field_value':at(old,ptr)})
        row['no_new_image_judgment']=True
        row['does_not_edit_original_or_root_decision']=True
        row['not_a_majority_vote']=True
        rows.append(row)
    report={'schema':'literature_eight_scope_adversarial_review_v1','created_utc':now(),
       'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),
       'root_manual_decisions_sha256':sha(root_path),'reviewer':'literature',
       'fixed_cases':8,'rows':rows,
       'conclusion':'在冻结合同的记录级、已观察写字样组范围内，没有发现足以要求撤销这八项裁定的具体反证。接受七项范围修订及一项继续保留未知，但每项反驳尝试和剩余限制均保留。',
       'material_cautions':['full_window不是逐像素穷尽声明；肯定支持来自原事实对整组的位置/分离描述，不来自未见反例。',
          'f72r2 ZO14必须并列保留旧尖形称呼与后续组件否定，不能把被否定的尖形用作角色依据。',
          'f72r2 ZE04 outer endpoint的对象未明；partial表示来源范围歧义，不等于已证实文字截断或混层。',
          'f72v3两项涉及本人先前范围解释变更；原v1及纯表示v2均不改，本次不是新图像证据。',
          'f71v/f72v1两项此前已由本人审过；再次接受不增加独立证据或形成多数票。'],
       'exposure':{'same_AI':True,'blind':False,'own_original_cases':sorted(own_ids),
          'previous_cross_review_cases':sorted(review_ids),'root_working_decisions_read':False,
          'new_images_viewed':False,'new_matching_or_scores':False},
       'timeline':'输入在前一工作段冻结，来源阅读已进行；21:52UTC恢复后先检查已有文件，再完成逐项书面审查。未将中断时段计为持续观察。',
       'scientific_effect':'只提供范围审查意见，不改任何原编码、根裁定或统计；原完整序列资格门不变。'}
    put('report_v1.json',report)
    lines=['八项根范围裁定：针对性反证审查','',report['conclusion'],
      '这不是独立盲复认：本代理原编码过f72v3两项，并复核过f71v/f72v1各一项。没有新看图、匹配或统计。','']
    for row in rows:
        lines += [row['region_uid']+' — '+row['verdict'],
           '角色：'+row['role_review'],'范围/H：'+row['scope_and_H_review'],
           '尝试反驳：'+row['attempted_counterargument'],
           '处理：'+row['counterevidence_disposition'],'仍未知：'+row['remaining_unknown'],
           '措辞：'+row['wording_caution'],'参与情况：'+row['previous_participation']]
        for ref in row['source_refs']:
            lines += ['来源：'+ref['file']+' '+ref['json_pointer']+' SHA '+ref['sha256'],
                     '原值：'+json.dumps(ref['original_field_value'],ensure_ascii=False)]
        lines += ['']
    lines += ['共同限制']+report['material_cautions']+['',report['scientific_effect'],'']
    put('report_v1.txt','\n'.join(lines))
    # Validate serialized quotations against the current exact frozen files.
    for row in read(HERE/'report_v1.json')['rows']:
        for ref in row['source_refs']+[row['root_decision_reference']]+row['previous_judgment_refs']:
            path=REPO/ref['file'];assert sha(path)==ref['sha256']
            assert at(read(path),ref['json_pointer'])==ref['original_field_value']
    for f in inp['source_files']:assert sha(REPO/f['file'])==f['sha256']
    put('validation_v1.json',{'created_utc':now(),'all_passed':True,'all_8_exact_IDs_reviewed':True,
       'primary_source_ref_count':refcount,'all_original_field_values_verified':True,
       'all_frozen_input_hashes_unchanged':True,'no_new_images_or_scientific_counts':True,
       'scope':'引用一致性验证；不把程序通过当作科学判断的独立证明。'})
    names=['protocol_v1.txt','prepare_input_v1.py','input_freeze_v1.json','manual_review_v1.json',
           'assemble_review_v1.py','report_v1.json','report_v1.txt','validation_v1.json']
    put('output_freeze_v1.json',{'schema':'eight_scope_challenge_review_output_freeze_v1','created_utc':now(),
       'input_freeze_sha256':sha(HERE/'input_freeze_v1.json'),
       'files':[{'path':n,'sha256':sha(HERE/n)} for n in names],
       'all_8_record_level_reviews_complete':True,'no_original_mutations':True})
    print(json.dumps({'report_sha256':sha(HERE/'report_v1.json'),'output_freeze_sha256':sha(HERE/'output_freeze_v1.json'),
                     'source_refs':refcount,'rows':8}))
if __name__=='__main__':main()
