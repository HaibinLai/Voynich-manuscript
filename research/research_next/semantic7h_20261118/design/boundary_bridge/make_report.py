"""Report-only projection of completed frozen results. No rescoring or rule selection."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent
OUT=HERE/'run_v1'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def number(x):return x['value'] if x is not None else None
def main():
    complete=read(OUT/'complete.json');assert complete['status']=='complete'
    for n,h in complete['files'].items():assert sha(OUT/n)==h,n
    data={v:read(OUT/(v+'_main.json.gz')) for v in ['ZL','IT']}
    folds={v:read(OUT/(v+'_loo.json.gz')) for v in data}
    inventories={v:read(OUT/(v+'_inventory.json.gz')) for v in data}
    table=[];hits=[]
    for v,d in data.items():
        for rid,r in d['rules'].items():
            s=r['summary'];target=s['source_leaf']['target']['value'];control=s['source_leaf']['control']['value'];delta=s['source_leaf']['delta']['value']
            table.append(dict(version=v,rule=r['rule'],candidates=11,valid_labels=s['valid_labels'],invalid_labels=11-s['valid_labels'],
                target_hit_candidates=s['target_hit_candidates'],source_leaves_hit=s['target_hit_source_leaves'],target_leaves_hit=s['target_hit_target_leaves'],
                target_rate=target,control_rate=control,delta=delta,conditional=s['source_leaf']['conditional_delta']))
            for c in r['candidates']:
                if not c['target']['binary']:continue
                hits.append(dict(version=v,rule=rid,fragment_id=c['fragment_id'],pair_id=c['pair_id'],label=c['label_loci'],core=c['core'],target_folio=c['target_folio'],
                    target_opportunities=c['target']['n'],positions=[inventories[v][c['target_folio']]['words'][i] for i in c['target']['hit_indices']],contrast=c['contrast']))
    loo={v:dict(status=x['status'],completed_folds=x['completed_folds'],test_delta=x['source_leaf_equal_test_delta'],baseline_delta=x['source_leaf_equal_baseline_delta'],
        folds=[dict(held_source_leaf=f['held_source_leaf'],status=f['status'],selected_rule=f.get('selected_rule'),train=f.get('selected_training'),test=f.get('test'),
            baseline_test=f.get('baseline_test'),gain_vs_baseline=f.get('test_gain_vs_baseline'),purged_pair_ids=f['all_rules'][0]['purged_pair_ids'],
            donor_clearance=f['all_rules'][0]['donor_clearance']) for f in x['folds']]) for v,x in folds.items()}
    audit=read(HERE/'audit_v1.json');assert audit['status']=='PASS'
    projection=dict(status='completed_post_result_exploration',complete_receipt_sha256=sha(OUT/'complete.json'),independent_audit=dict(status=audit['status'],failure_count=audit['failure_count'],coverage=audit['coverage'],receipt_sha256=sha(HERE/'audit_v1.json')),rule_table=table,target_hits=hits,loo=loo,
        image_traces=read(HERE/'hit_trace_v1.json'),warning='No phonetic or semantic decipherment; different singleton rules in IT only, four-source internal selection adds zero average test gain. Full data already exposed; no significance claim.')
    (HERE/'publication_projection_v1.json').write_text(json.dumps(projection,ensure_ascii=False,indent=2)+'\n')
    text=['固定短边界实验结果：没有形成可泛化的词干桥梁',
      '2026-11-18；已看过完整词零结果后的探索；固定36规则×ZL/IT两版，strict_space/page_HI。',
      '', '全部72条规则结果已保存。ZL的36规则均没有指定目标命中。IT只有两个不同规则各命中一个候选：#95的otoldy去右2→otol，对应f44r.3的otol；#133的opchor去左2→chor，对应f13v.10的kchor去左1。两者各仅覆盖1来源叶、1目标叶；没有一条规则命中两个指定候选。不能把两个不同规则按词拼接为统一读法。',
      '', '4fold内部选择的源叶等权平均测试差与完整词基线完全相同：ZL为−1/368（−0.271739百分点），IT为−5/1104（−0.452899百分点），平均测试增益为0。IT中一个单例在训练中选出的规则不能复现另一个单例；ZL没有任何目标命中。这里没有显著性结论，只有4来源叶，全部资料已见，留一诊断不构成盲验证。',
      '', '版本差异与原图定位',
      '#95：IT在f44r.3第4词为otol，ZL为otal；两版该行均通过strict_space。这是实质字读差异。官方OID1006160，上方文字区第3行，kshotol之后、daiin之前。',
      '#133：两版f13v.10第5词都为kchor；ZL行首y,ol含不确定空格，按已定strict_space规则整行排除，IT y.ol保留。因此不能说ZL没有kchor；差异来自预定过滤。官方OID1006099，下方文字区左部末行，kchey之后、dal之前。',
      '已查看保存的官方全图定位文字区和行布局，没有裁定o/a字形或空格正确读法，没有改转写。两条仍标记探索性未核实。完整原行、画布URL、图像哈希和上下文区域见hit_trace_v1.json与hit_trace_notes_v1.txt。',
      '', '以下完整36行同时列两版，等价于全部72条结果；数值为源叶等权“指定目标－异叶对照”的百分点差。不是p值。core至少4，bench不截断。有效标签数小于11时，失效标签依协议主二值置0但仍占固定权重；该种0不等于观察到语言缺席。',
      '规则(label左/右；body左/右)    有效标签  ZL命中/源叶/目标叶  ZL差(pp)   IT命中/源叶/目标叶  IT差(pp)']
    for rid,r in data['ZL']['rules'].items():
        a=r['summary'];b=data['IT']['rules'][rid]['summary']
        ac=f"{a['target_hit_candidates']}/{len(a['target_hit_source_leaves'])}/{len(a['target_hit_target_leaves'])}"
        bc=f"{b['target_hit_candidates']}/{len(b['target_hit_source_leaves'])}/{len(b['target_hit_target_leaves'])}"
        text.append(f"{rid:22s} {a['valid_labels']:2d}        {ac:7s} {100*number(a['source_leaf']['delta']['value']):+10.6f}   {bc:7s} {100*number(b['source_leaf']['delta']['value']):+10.6f}")
    text.extend(['', '所有4fold的选择与测试（差值单位为概率）：'])
    for v,x in folds.items():
        for f in x['folds']:
            text.append(f"{v} held={f['held_source_leaf']}: selected={f['selected_rule']['id']}; train={number(f['selected_training']['source_leaf']['delta']['value']):+.9f}; test={number(f['test']['source_leaf']['delta']['value']):+.9f}; test_gain={number(f['test_gain_vs_baseline']):+.9f}")
    text.extend(['', '训练清除按协议执行：留f99时删训练#116/f96v，留f100时删训练#94/f96v；每fold还从所有训练donor池清除留出source的全部target物理叶。测试端保持原对照池。详见每fold全部36训练分数、候选清除与逐项控制清除计数。没有用测试结果重新选规则或调门槛。',
      '', '解释边界',
      '这不是完全任意的子串搜索：仅原词两端合计各删不超过2、core>=4、36个统一规则、同H/I对照与固定全11权重。但短串更常见、图像对应只是历史假说、标签未必是植物名，因此两个单例不足以建立语义。#95规则在IT有正主差，#133规则的IT主二值差为正而条件率差为负；这说明端点和长度机会重要，不能只报有利数值。',
      'ZL全零及IT单例对版本/边界口径的依赖，没有支持一个跨来源稳定的短边界转换机制。不能彻底否定所有形态变化语言，也不能把某个规则双边都零造成的差0当成突破。下次若扩大切除长度、允许内部编辑或增加植物对象，将是新的事后探索，不能并入本轮验证。',
      '', '复查文件', 'run_v1/complete.json：执行完成及全部文件哈希；main_table_72.json保存完整72行。',
      'ZL/IT_main.json.gz：36规则×11候选、target/donor逐页位置与分母、各叶贡献及失效原因。',
      'ZL/IT_inventory.json.gz：原词/locator/slot、六种固定body切法的有效core和失效原因。',
      'ZL/IT_loo.json.gz：4fold全部36训练指标、清除清单、所选规则和原池测试结果。',
      'toy_receipt_v1.json：先于真实匹配冻结的15个纯人工测试与源码/协议哈希。',
      'publication_projection_v1.json：全72表、全部2处命中、所有fold摘要及官方图像定位。',
      '另一agent的独立协议重建已PASS，失败0：复核792个候选规则行、67896个逐页评分块、8fold与288个训练规则fold。其评分核心在查看主结果/结构前冻结，未读或导入主scorer；audit_v1.json为收据。该审核确认实现一致，不验证古文字转写、对象语义或增加独立科学样本。'])
    (HERE/'report_v1.txt').write_text('\n'.join(text)+'\n')
    print('Wrote full 72-row projection and report; target-hit rule/candidate rows:',len(hits))
if __name__=='__main__':main()
