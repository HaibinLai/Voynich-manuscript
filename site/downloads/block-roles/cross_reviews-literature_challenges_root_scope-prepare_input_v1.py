#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pathlib import Path
from datetime import datetime, timezone
import json,hashlib
O=Path(__file__).resolve().parent
L=O.parent.parent
B=L.parent
REPO=B.parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
dec=L/'root_adjudication/manual_scope_decisions_v1.json'
assert sha(dec)=='ed41dfaffb0cb93b02ab48e0dce6b75328f8cad0b04c36d4f1545e56dab68c64'
d=json.loads(dec.read_text())
files=[dec,L/'execution_protocol_v1.txt',L/'execution_approval_v1.json',L/'empty_or_uncertain_window_clarification_v1.txt',L/'clarification_freeze_v1.json',B/'role_contract_review/contract_proposal_v1.json',B/'role_contract_review/record_schema_proposal_v1.json',B/'seed_roster_v1.json',B/'circle_spatial_observer/f72r2/observer_report_v1.json',B/'circle_spatial_observer/f72r2/output_freeze_v1.json',B/'literature/f72v3_report_v1.json',B/'literature/f72v3_freeze_v1.json',B/'astronomical_site/f71v_relations_v1.json',B/'astronomical_site/f71v_freeze_v1.json',B/'astronomical_site/f72v1_relations_v1.json',B/'astronomical_site/f72v1_freeze_v1.json',L/'literature/report_v1.json',L/'cross_reviews/literature_reviews_site/report_v1.json']
p=O/'protocol_v1.txt'
assert not p.exists()
p.write_text('''八项根裁定的针对性反证审查
固定manual_scope_decisions_v1.json全部8项，不因既有参与更换例。检查原事实是否对整条已观察写字样组作正面位置陈述，还是只描述一端/一子组；不可从没有反证推出全框支持。检查场界与文字/手线分离不同问题、损伤是否明确影响书写端点或只是对象、来源矛盾是否被跳过。
特别保留outer endpoint含义不明的可能，不自行指定为文字或星形。记录每项接受/挑战/未决及原file/SHA/pointer/value。原框全部可见内容的角色合同不改；完整采样窗不是完整铭文，组级事实也不能替代明确未覆盖子组。
本代理原编码参与f72v3 ZO05/ZO13，后复核参与f71v ZO08和f72v1 ZO09；已知全12记录与自身113项及site97项的结果，属同AI知情方法复核。不能称独立盲复认或专家图像认证。
不新看图，不读根working_decisions或未冻结汇编，不改任何原件/统计/科学结论。对根裁定只另写反证审查；是否接受由具体肯定证据决定，不多数票。
''')
files.extend([p,Path(__file__)])
f={'schema':'literature_adversarial_review_root_scope_input_v1','created_utc':datetime.now(timezone.utc).isoformat(),'fixed_ids':[x['region_uid'] for x in d['decisions']],'fixed_cases':8,'source_files':[{'file':str(p.relative_to(REPO)),'sha256':sha(p)} for p in files],'exposure':'已读根8项冻结理由；已参与自己的2项原编码与site2项复核，另4项只曾见原汇编；不称盲。','root_unfrozen_working_or_aggregate_read':False,'new_images':False,'status':'问题与输入已冻结，尚未形成8项反证结论。'}
q=O/'input_freeze_v1.json';assert not q.exists();q.write_text(json.dumps(f,ensure_ascii=False,indent=2)+'\n')
print('input_sha',sha(q))
r=json.loads((B/'circle_spatial_observer/f72r2/observer_report_v1.json').read_text())
for i,x in enumerate(r['text_records']):
    if x['region_uid'] in f['fixed_ids']:print('\nROW',i,json.dumps(x,ensure_ascii=False,indent=2))
print('\nCONTEXTS')
for i,x in enumerate(r['context_reviews']):
    print(i,json.dumps({k:v for k,v in x.items() if k not in ['viewed_view_ids','view_ids','original_record']},ensure_ascii=False))
