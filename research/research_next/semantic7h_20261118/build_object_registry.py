"""Join immutable object evidence; never promote an observation into semantic gold."""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import gzip, hashlib, json

BASE=Path(__file__).resolve().parent
FILES=['literature/plant_pairs.json','literature/label_support.json',
       'visual/crossplant/crossplant_visual_review_v1.json',
       'visual/order_candidates/review.json','visual/order_targets/review_v1.json',
       'visual/unresolved_sources/review.json',
       'design/crossplant/run_v2/ZL__strict_space__page_HI.json.gz',
       'design/crossplant/run_v2/IT__strict_space__page_HI.json.gz']

def read(name):
    p=BASE/name;raw=p.read_bytes()
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)

def main():
    hypotheses=read(FILES[0])['records']
    supports={r['pair_id']:r for r in read(FILES[1])['records']}
    numbered={r['pair_id']:r for r in read(FILES[2])['records']}
    sources={r['pair_id']:r for r in read(FILES[3])['records']}
    targets={r['pair_id']:r for r in read(FILES[4])['records']}
    unresolved={pid:r for r in read(FILES[5])['objects'] for pid in r['pair_ids']}
    scored={v:{r['pair_id']:r for r in read(FILES[6+i])['candidates']} for i,v in enumerate(['ZL','IT'])}
    assert set(numbered).isdisjoint(sources) and set(numbered).isdisjoint(unresolved)
    assert set(sources).isdisjoint(unresolved) and set(sources)==set(targets)
    assert set(numbered)|set(sources)|set(unresolved)=={r['pair_id'] for r in hypotheses}
    assert set(scored['ZL'])==set(scored['IT']) and len(scored['ZL'])==11
    rows=[]
    for h in hypotheses:
        pid=h['pair_id'];sup=supports[pid]
        row=dict(pair_id=pid,source_object_id=h['pharma_folio']+'_'+str(h['fragment_id']),
                 prior_hypothesis=h,original_label_support=sup,
                 semantic_gold=False,species_identification=None,
                 object_name_confirmed=False,original_record_modified=False)
        if pid in numbered:
            row.update(source_review_group='numbered_candidate',
                       source_review_file=FILES[2],source_review=numbered[pid]['text_geometry'],
                       pair_geometry_file=FILES[2],pair_geometry=numbered[pid],
                       target_geometry_reviewed=True)
        elif pid in sources:
            row.update(source_review_group='layout_order_candidate',
                       source_review_file=FILES[3],source_review=sources[pid],
                       pair_geometry_file=FILES[4],pair_geometry=targets[pid],
                       target_geometry_reviewed=True)
        else:
            row.update(source_review_group='previously_missing_or_unknown',
                       source_review_file=FILES[5],source_review=unresolved[pid],
                       pair_geometry_file=None,pair_geometry=None,
                       target_geometry_reviewed=False)
        row['crossplant_main_scored']=pid in scored['ZL']
        row['full_word_primary']={}
        if row['crossplant_main_scored']:
            for v in ['ZL','IT']:
                c=scored[v][pid];score=c['models']['exact']['target']
                row['full_word_primary'][v]={'condition':'strict_space/page_HI/exact',
                    'label_loci':c['loci'],'target_folio':c['target_folio'],
                    'source_leaf':c['source_leaf'],'target_leaf':c['target_leaf'],
                    'opportunities':score['opportunities'],'matches':score['matches'],
                    'conditional_rate':score['rate']}
        row['reason_not_scored']=None if row['crossplant_main_scored'] else (
            'Multi-locus three-word group excluded whole by frozen protocol' if h['fragment_id']==110
            else 'Outside the frozen eleven-query main set; later image observation is not retroactive eligibility')
        rows.append(row)
    counts={'relationships':len(rows),'unique_source_objects':len({r['source_object_id'] for r in rows}),
            'source_review_relationships':len(rows),'target_pair_geometry_relationships':sum(r['target_geometry_reviewed'] for r in rows),
            'main_scored_relationships':sum(r['crossplant_main_scored'] for r in rows),
            'semantic_gold_relationships':0,'review_groups':dict(Counter(r['source_review_group'] for r in rows))}
    assert counts['relationships']==35 and counts['unique_source_objects']==34
    assert counts['target_pair_geometry_relationships']==24
    payload={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'Evidence index only; not a new experiment or reclassification of frozen eligibility.',
             'inputs':{f:hashlib.sha256((BASE/f).read_bytes()).hexdigest() for f in FILES},
             'counts':counts,'records':rows,
             'limitations':['All source records reviewed at different times and with different information exposure; not independent expert consensus.',
                            'Historical hypotheses and geometric compatibility are not certified object identity or names.',
                            'The 35 relations share 34 source fragments and fewer physical leaves; counts are not independent trials.',
                            'New candidate #188 and unresolved #40 were not scored; no historical main endpoint changed.']}
    (BASE/'object_registry_v1.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['35条图像关系证据索引','',
           '35条关系来自34个来源对象；全部已有来源图像观察，24条有目标形态比较，11条进入原冻结词形检验。没有任何语义金标准。',
           '这是索引，不改变旧标签资格。来源编号、次序候选、补查的新候选必须分别阅读；#150两目标共用一来源对象。',
           '原图、候选字串、机会N和结果仅在相应关系确有记录时提供。N=0时条件率NA，不把未执行当未命中。','',
           '关系ID | 原资格 | 来源审查组 | 目标形态已看 | 原主检验已执行']
    for r in rows:
        lines.append(' | '.join([r['pair_id'],r['original_label_support']['status'],r['source_review_group'],
                                 str(r['target_geometry_reviewed']),str(r['crossplant_main_scored'])]))
    lines+=['','#188：新空间候选f101v.7，ZL otarar / IT otorar；未评分。',
            '#40：f89r2.17 sodar在#40/#41之间，唯一归属未决；未评分。',
            '8个不同对象（9关系）没有可独立归属的短标签；这不证明历史上没有名称。',
            '完整逐项证据和来源哈希见object_registry_v1.json。']
    (BASE/'object_registry_v1.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(counts))

if __name__=='__main__':main()
