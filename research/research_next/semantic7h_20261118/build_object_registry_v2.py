"""Append completed target geometry to the immutable v1 evidence index."""
from pathlib import Path
from datetime import datetime, timezone
import copy, hashlib, json

BASE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())

def main():
    output=BASE/'object_registry_v2.json'
    assert not output.exists(), 'Do not overwrite a frozen index version'
    previous=read(BASE/'object_registry_v1.json')
    extra_name='visual/remaining_targets/review_v1.json'
    extra=read(BASE/extra_name)
    receipt=read(BASE/'visual/remaining_targets/verification_receipt_v1.json')
    assert sha(BASE/extra_name)==receipt['files']['review_v1.json']
    for name,h in previous['inputs'].items(): assert sha(BASE/name)==h,name
    rows=copy.deepcopy(previous['records'])
    addition={r['pair_id']:r for r in extra['records']}
    assert len(addition)==11
    assert set(addition)=={r['pair_id'] for r in rows if not r['target_geometry_reviewed']}
    for row in rows:
        if row['pair_id'] in addition:
            row['pair_geometry_file']=extra_name
            row['pair_geometry']=addition[row['pair_id']]
            row['target_geometry_reviewed']=True
    for old,new in zip(previous['records'],rows):
        for key in ['original_label_support','crossplant_main_scored','full_word_primary','semantic_gold','species_identification','object_name_confirmed']:
            assert old[key]==new[key],(old['pair_id'],key)
    counts=copy.deepcopy(previous['counts'])
    counts['target_pair_geometry_relationships']=sum(r['target_geometry_reviewed'] for r in rows)
    assert counts['target_pair_geometry_relationships']==35
    payload={**previous,'created_utc':datetime.now(timezone.utc).isoformat(),
      'scope':'Version 2 evidence index: all 35 target comparisons recorded. Original eligibility and scores unchanged; no new semantic gold.',
      'previous_version':{'path':'object_registry_v1.json','sha256':sha(BASE/'object_registry_v1.json')},
      'inputs':{**previous['inputs'],extra_name:sha(BASE/extra_name),
                'visual/remaining_targets/verification_receipt_v1.json':sha(BASE/'visual/remaining_targets/verification_receipt_v1.json')},
      'counts':counts,'records':rows}
    output.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['35条图像关系证据索引 v2','',
      '35关系、34来源对象全部完成描述性目标图像比较；11条仍是原冻结词形检验主集。新增11关系没有执行词形评分。',
      '目标形态已看不等于相同植物。新增11关系：6可作局部比较，5有限或含混；#40保留两株未决目标；#150两关系共用一来源。',
      '语义金标、已认证名称、已认证植物身份均为零。原标签资格、历史词形结果和v1索引逐字保留。',
      '#188为新空间候选，#40附着未决；其余9关系未见独立归属标签，未拿邻近正文或容器字补位。','',
      '关系 | 来源审查组 | 目标已观察 | 原主检验已执行']
    for row in rows:
        lines.append(' | '.join([row['pair_id'],row['source_review_group'],str(row['target_geometry_reviewed']),str(row['crossplant_main_scored'])]))
    (BASE/'object_registry_v2.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(counts))

if __name__=='__main__':main()
