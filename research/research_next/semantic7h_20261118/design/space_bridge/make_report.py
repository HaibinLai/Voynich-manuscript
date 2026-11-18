"""Projection of the fixed complete run. Does not match or select new rules."""
from pathlib import Path
import gzip,hashlib,json
HERE=Path(__file__).resolve().parent
OUT=HERE/'run_v1'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def num(x):return None if x is None else x['value']
def main():
    receipt=read(OUT/'complete.json');assert receipt['status']=='complete'
    for n,h in receipt['files'].items():assert sha(OUT/n)==h,n
    table=[];targets={};join_control_hits=[]
    for version in ['ZL','IT']:
        for boundary in ['strict_space','packet_tokens']:
            key=version+'__'+boundary;d=read(OUT/(key+'.json.gz'))
            for model,s in d['models'].items():
                z=s['source_leaf']
                table.append(dict(condition=key,model=model,candidate_count=11,target_hits=s['target_hit_candidates'],new_target_coverage=s['target_newly_covered_candidates'],
                    target_source_leaves=s['target_hit_source_leaves'],target_target_leaves=s['target_hit_target_leaves'],
                    metrics={f:z[f] for f in ['binary_target','binary_control','binary_delta','union_binary_target','union_binary_control','union_binary_delta','coverage_gain_target','coverage_gain_control','coverage_gain_delta','conditional_delta']}))
            targets[key]=[]
            for c in d['candidates']:
                targets[key].append(dict(pair_id=c['pair_id'],fragment_id=c['fragment_id'],query=c['query'],target_folio=c['target_folio'],source_leaf=c['source_leaf'],target_leaf=c['target_leaf'],
                    models={m:dict(n=s['n'],m=s['m'],binary=s['binary'],rate=s['rate'],union_binary=s['union_binary'],coverage_gain=s['coverage_gain'],
                        hits=s['hits'],conditional_status=c['contrasts'][m]['conditional_status']) for m,s in c['target'].items()}))
                for donor in c['donor_pages']:
                    for model,score in donor['models'].items():
                        if model!='exact' and score['m']:
                            join_control_hits.append(dict(condition=key,pair_id=c['pair_id'],query=c['query'],donor_folio=donor['folio'],model=model,hits=score['hits']))
    compact=read(HERE/'support_compact_v1.json')
    audit=read(HERE/'audit_v1.json');assert audit['status']=='PASS'
    result=dict(status='complete_no_target_join_matches',complete_sha256=sha(OUT/'complete.json'),independent_audit=dict(status=audit['status'],counts=audit['counts'],receipt_sha256=sha(HERE/'audit_v1.json')),models_table=table,targets=targets,join_control_hits=join_control_hits,
        parser_support=compact['parser'],adjacent_opportunities_shared=True,
        limits=['Post-result exploration on historical image hypotheses, not semantic gold.','Four source leaves and reused target f96v; repeated conditions are not independent samples.','Only encoded raw barriers are guaranteed not crossed.','IT strict/packet inputs identical.','English calibration is separate; its rates are not manuscript null probabilities.'])
    (HERE/'publication_projection_v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    text=['空格桥梁实验：相邻两词没有恢复指定植物标签',
      '2026-11-18；固定11标签，ZL/IT×strict_space/packet_tokens，共4条件、4机制。事后探索，不作统计显著或破译声明。',
      '', '主结果：11个指定目标在正向相邻两词、反序相邻两词、隔一个完整词的同向拼接中全部0命中。正向相邻的union新增覆盖在目标和对照两边均为0，四条件主增量都是0。不是缺少所有机会：若干原完整词无同长度机会的目标页有合法两词总长度窗口，但仍未拼回指定标签。',
      '', '四机制全部结果（源叶等权目标－对照差，单位百分点；不是p值）：',
      '条件                     机制                 命中目标  单机制差     exact∪机制差  新增覆盖差']
    for r in table:
        z=r['metrics'];text.append(f"{r['condition']:24s} {r['model']:19s} {r['target_hits']:3d} {100*num(z['binary_delta']['value']):+11.6f} {100*num(z['union_binary_delta']['value']):+11.6f} {100*num(z['coverage_gain_delta']['value']):+11.6f}")
    text.extend(['', '唯一join对照命中：ZL packet_tokens下，#133标签opchor在异叶f21r.1的原slot0、1反序拼接出现；物理顺序pchor / o，按反序才得到o+pchor。这行有不确定空格，所以strict_space不保留。它发生在原非目标对照，不是指定f13v，不据此新增植物配对。它只使该描述性反序对照的新增覆盖差为−1/1104（−0.090580百分点）；正向主机制无收益。',
      '', '目标长度机会与NA',
      '逐11候选×4条件的exact、正反相邻、gap2机会N、条件率NA及原因全部在publication_projection_v1.json和run_v1完整包。正反相邻对所有页使用完全相同物理窗口支持。#80各条件均无两词长度机会：主binary0，条件率NA，不能据此判标签没有意义。#212/#213等有合法窗口但不匹配，也仅约束这个固定两词拼接模型。',
      '', '输入和屏障检查',
      '从raw重建原slots：ZL3996 loci/34509槽，IT3995/33972，含None逐slot全部复现，失败0。所有尖括号tag保留屏障；图形、段落及注释阻止跨越。有效旧token内部tag排除数两版均0，因此本轮共同输入exact实际与旧单词输入一致，但名称仍明确是共同可比输入基线。',
      'ZL有1677条uncertain_space行，strict_space整行排除；IT没有，所以IT两个口径本就相同，不能当独立重复。None槽不压缩，gap2中间必须完整可比。只能保证不跨raw已经编码的屏障，转写漏标的图形中断不能由这项检查消除。',
      '', '方法边界',
      '没有改字、三词拼接、跨locus、字符删除、六对或Davis。标签bench的正反两种接缝都合法才计窗口，扩展EVA码是原子。exact与三个join分别评分，每个join只与exact做自己的union，未做三规则总union或自动选赢家。union新增页面覆盖与join出现本身分开，union没有混合分母的条件率。',
      '数据仍是4来源物理叶的11历史图像假说，f96v复用；图像不是专家语义gold，标签也未被证明是植物学名。这个负结果只表示预定有限两词空间差异模型没有恢复目标完整标签，不能否定所有分词机制、语言性或图像对应。已知英文Asarabacca例促发此机制，英文校准由另一任务独立处理，其恢复率不能迁移为手稿概率。',
      '', '冻结与可复查文件',
      'protocol_v1.txt、toy_receipt_v1.json：先于真实匹配冻结，主实现15项人工toy通过。',
      'run_v1/complete.json：4条件评分包、inventory、16行汇总和冻结收据的全部哈希。',
      '各条件.json.gz包含全部target/donor的机会窗口与命中，原locator/source_line/slot/顺序/组成词/拼接串、N/NA、各自union和固定页叶权重。',
      'inventory保存原slots、raw、屏障坐标及被排除行，support_v1.json保存先于评分的长度盘点。',
      'publication_projection_v1.json提供完整16机制表、所有11目标支持、唯一join对照定位。',
      '独立agent全量审核PASS：15,088页模型块、86,670机会及全部位置/率/NA/各union/页叶权重一致，0差异，见audit_v1.json与audit_release_receipt_v1.json。独立核心没有读取或导入主scorer/parser实现；只说明计算一致，不增加独立手稿样本或验证原始字读。',
      '另有support_consistency_v1.json确认评分后全部15,088项机会数与评分前支持完全一致，无结果后资格调整。'])
    (HERE/'report_v1.txt').write_text('\n'.join(text)+'\n')
    print('Report and complete 16-row projection saved; join control traces',len(join_control_hits))
if __name__=='__main__':main()
