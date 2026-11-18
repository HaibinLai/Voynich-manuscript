"""Projection of frozen outputs for review/publication; does not score new text."""
from pathlib import Path
import gzip,json,hashlib
HERE=Path(__file__).resolve().parent
OUT=HERE/'run_v2'
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def val(f):return None if f is None else f['value']
def main():
    results={};summary={};targets={};collisions={}
    for file in sorted(OUT.glob('*__*__*.json.gz')):
        if file.name.startswith(('inventory','collisions')):continue
        d=read(file);key=file.name.removesuffix('.json.gz');results[key]=d
        summary[key]={}
        for m,a in d['aggregate'].items():
            p=a['primary_source_leaf']
            summary[key][m]=dict(target_candidate_hits=sum(c['models'][m]['target']['binary'] for c in d['candidates']),
                candidates=11,source_leaves=4,primary=p,
                active_candidate_count=a['diagnostics']['active_only']['binary']['candidate_count'],
                primary_difference_unit='probability; multiply by 100 for percentage points')
        targets[key]=[dict(fragment_id=c['fragment_id'],pair_id=c['pair_id'],source_folio=c['source_folio'],target_folio=c['target_folio'],source_leaf=c['source_leaf'],target_leaf=c['target_leaf'],
            query=c['models']['exact']['query_original'],models={m:dict(target=s['target'],donor_leaf_count=s['endpoints']['min1']['donor']['leaf_count'],
                conditional_status=s['endpoints']['min1']['conditional_status'],primary_delta=s['endpoints']['min1']['binary_delta']) for m,s in c['models'].items()}) for c in d['candidates']]
    for file in sorted(OUT.glob('collisions__*.json.gz')):
        cc=read(file)
        collisions[file.name.removesuffix('.json.gz')]={m:dict(groups=c['collision_group_count'],canonical_types=c['canonical_type_count']) for m,c in cc.items()}
    compact=dict(status='completed_no_positive_crossplant_target_match',complete_receipt_sha256=sha(OUT/'complete.json'),audit=read(HERE/'audit_run_v2.json'),
        design='11 frozen single-word image-pair hypotheses, four source leaves; image review is not semantic gold; #110 three-word group excluded intact.',
        all_target_binary_zero=all(s['target_candidate_hits']==0 for d in summary.values() for s in d.values()),
        conditions=summary,target_records=targets,canonical_collision_counts=collisions,
        note='Eight conditions and ten models reuse the same eleven hypotheses, not 880 independent observations. No inferential p-value or decipherment claim.')
    (HERE/'summary_v2.json').write_text(json.dumps(compact,ensure_ascii=False,indent=2)+'\n')
    text=['跨植物历史图像假说：完整词形桥梁检验结果','2026-11-18；执行protocol_v1；完成数据run_v2。',
      '', '结论：没有发现预先指定的跨植物完整词形关联。全部8条件、10模型中，11条指定草药目标均为0命中。六对裸gallows单次替换，以及Davis原展开、交换展开、等长度假展开，都没有救回任何目标。这个结果限制了“标签完整词形直接出现在对应大植物正文”的强预测；它不证明植物图像对应错误、标签无意义或手稿不是语言。',
      '', '取样边界：12条来源编号对象中，#110保留两个位置三词整组，按协议未执行；其余11条全部进入主报告，没有根据图像强弱或零长度机会删除。来自4个来源物理叶，f96v又被两个来源对象指定，不能当作11个独立语义样本。8×10×11是重复规则检查数，不是880次独立验证。图像审核是AI辅助形态观察，不是专家金标或已知物种。',
      '', '主端点：指定页是否至少有一次完整接受词形；对照为同target H/I异叶页面，先页平均到叶，再叶等权；总体按source leaf等权。下表是“目标－对照”的概率差，不是p值。全部目标为0，负数来自对照页偶有相同/近形词。',
      '', '主展示strict_space / page_HI（数值单位：百分点；乘100后的差值）', '模型                 ZL          IT']
    for model in ['exact','fk','fp','ft','kp','kt','pt','davis','davis_swapped','davis_sham']:
        numbers=[val(summary[v+'__strict_space__page_HI'][model]['primary']['binary']['value'])*100 for v in ['ZL','IT']]
        text.append(f'{model:18s} {numbers[0]:+.6f}  {numbers[1]:+.6f}')
    text.extend(['', 'k/t在本批主结果中与exact完全相同，没有新增目标或对照覆盖。k/p、p/t的单次放宽主要让异叶对照更容易出现接受形，主差值因此更负。不能据此宣称某对音值正确，也不能与旧leaf_controls数字横比：本轮保护cth/ckh/cfh/cph中的gallows，旧实现未保护，而且对象、分母、权重都不同。',
      '', '完整8条件的exact主差值和条件率支持数（概率差）：'])
    for key,ss in summary.items():
        a=ss['exact']['primary'];text.append(f"{key}: binary={val(a['binary']['value']):+.9f}; conditional min1 n={a['conditional1']['candidate_count']}, min5 n={a['conditional5']['candidate_count']}")
    text.extend(['', '各候选strict_space原长度机会（不是命中数）：', '编号  标签ZL/IT                       目标       N_ZL N_IT'])
    zl=targets['ZL__strict_space__page_HI'];it=targets['IT__strict_space__page_HI']
    for a,b in zip(zl,it):
        text.append(f"{a['fragment_id']:3d}  {a['query']+'/'+b['query']:32s} {a['target_folio']:8s} {a['models']['exact']['target']['opportunities']:4d} {b['models']['exact']['target']['opportunities']:4d}")
    text.extend(['', '零机会与缺席要分开：#212/f18v和#213/f23r两版原长度机会为0；#240/f19r在ZL也为0。整页端点仍是可观察的完整词形缺席binary=0；条件率m/N为NA，不能赋0或当作独立词义反证。其余长词机会也很少，#116仅1；严格条件率不应掩盖全11条主结果。wholeleaf_HI中#61只剩1个H5对照叶，因此次端点因少于2叶不支持，但主二值仍保留。',
      '', '精确对照的可定位例（strict_space/page_HI）：两版otoldy在f22r、f28r、f53v出现，历史指定目标f44r没有；IT版opchor还在f15v和f49r出现，指定f13v没有。ZL严格边界下这些opchor对照位置不保留。所有这些例子来自冻结输出，没有据此新增或替换植物对应。',
      '', 'Davis附加检查：11标签只有opchor含裸p；sochorcfhy的f属于cfh而受保护。三展开在所有8条件的主端点相同、目标均0，不能区分作者映射与交换或假展开。全保留正文+11标签的规范化并非空操作：strict_space下ZL的作者/交换/假展开分别有60/55/4个多原形碰撞组，IT为110/111/7。但这些全书碰撞不是本批跨植物语义证据；主查询无收益。映射后长度机会改变，原/展开条件率不可忽视支持集变化直接比较。',
      '', '运行与验证：run_v1在相对路径写入冻结哈希时失败，尚未读取真实匹配语料；failure.json完整保留。run_v2只把命令中的图像冻结路径改为绝对路径，脚本与协议字节未改。17个预先人工测试通过。完成后另用独立正则分块匹配实现，核对880个目标条件模型和74080个对照页检查、目标机会/NA、页→叶→来源叶二值聚合；全部一致。该审核验证实现一致性，不增加独立手稿证据。',
      '', '没有做显著性检验或把小负差解释为确定反证。当前最合理结论是：在这组历史图像对应、现有转写和有限规则下，未建立从标签到对应大植物正文的完整词形桥梁。继续研究若改成词干/形态或复合标签，必须先得到外部约束、另立协议并作为新探索，不能在本结果上放宽到找到一个阳性。',
      '', '可复查文件：', 'run_v2/complete.json：17个冻结输出文件哈希；8条件×10模型完整评分、4个正文位置inventory、4个规范化碰撞表和freeze。',
      'run_v1/failure.json：失败原因与回溯；execution_addendum_01.txt：仅调用路径修正。',
      'audit_run_v2.json / audit_run_v2.py：独立实现复核收据与代码。', 'summary_v2.json：80个条件模型的全部主/次指标、11候选逐条机会与零命中记录、碰撞计数；原始全输出不删减。',
      'protocol_v1.txt、implementation_review_v1.json：协议、人工测试及实现哈希。',
      '', '外部来源：', 'https://www.voynich.nu/q15/index.html', 'https://www.voynich.nu/q19/index.html', 'https://collections.library.yale.edu/manifests/2002046', 'https://ceur-ws.org/Vol-3313/keynote2.pdf'])
    (HERE/'report_v2.txt').write_text('\n'.join(text)+'\n')
    print('Wrote report_v2.txt and summary_v2.json; all_target_binary_zero =',compact['all_target_binary_zero'])
if __name__=='__main__':main()
