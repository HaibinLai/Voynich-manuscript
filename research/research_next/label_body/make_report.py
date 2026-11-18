"""Render the saved results without rescoring or choosing new hypotheses."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
def pp(x):return f'{100*x:+.4f}' if x is not None else '无支持'
def rate(x):return f'{100*x:.4f}' if x is not None else '无支持'
def main():
    r=json.loads((HERE/'saved_v1/results.json').read_text())
    s=json.loads((HERE/'supplement.json').read_text())
    c=json.loads((HERE/'saved_v1/candidates.json').read_text())
    lines=['图旁标签与正文：迈向语义对应的一轮筛查','2026-11-18','',
    '结论：存在小幅本页词形集中，尚未获得词义。两版精确同词差为+0.1221/+0.1470个百分点，主要来自浴疗类页面；医药类页面整体为负。k/t一次替换额外增加约0.07个百分点，但增加命中不等于字形同音。没有显著性检验结论。',
    '', '一、测量的是什么',
    '固定一个完整标签词，分子是正文中该词的出现次数，分母是正文中与它同EVA长度的保留词次数。比较本页与同书手H、同插图类别I且不同物理叶的正文；控制页先在叶内平均，再对照叶等权。目标标签先页内平均，页再在叶内平均，最后目标叶等权。单位为每100个同长度正文词的命中数；不是“多少百分比标签已读懂”，也不是未校正的标签至少出现一次率。',
    'L位置是转写布局类别，不是已确认的对象ID；完整词和EVA字符不保证是真实语言单位。全部语料已曝光，两版只是同一手稿的测量敏感性。',
    '', '二、完整范围与主结果']
    for v,x in r.items():
        main=x['main']['exact'];m=main['summary']
        lines += [f"{v}: {x['inventory']['image_loci_total']}图形相关位置，{x['inventory']['complete_singleword_labels']}完整单词位置；可比{m['labels']}标签/{m['pages']}页/{m['leaves']}叶。",
        f"排除：{main['excluded']}。无同长度正文机会包含本页没有线性正文的情形，不能视为零命中。",
        f"本页率{rate(m['own'])}；异叶率{rate(m['control'])}；差{pp(m['delta'])}个百分点。{m['labels_with_own_match']}个可比标签至少一次本页精确命中（仅辅助计数）。"]
    lines += ['', '三、所有六对，不只展示k/t','配对允许最多一处相应字形替换，词其余部分完全相同；包含精确命中。总差与相对精确匹配的新增差分开。','模型 | ZL总差 | IT总差 | ZL新增差 | IT新增差（百分点）']
    for model in r['ZL']['main']:
        a=r['ZL']['main'][model]['summary']['delta'];b=r['IT']['main'][model]['summary']['delta']
        lines.append(f"{model} | {pp(a)} | {pp(b)} | {pp(a-r['ZL']['main']['exact']['summary']['delta'])} | {pp(b-r['IT']['main']['exact']['summary']['delta'])}")
    lines += ['例如 qotedy 放宽k/t会增加同页匹配，但异叶匹配也增加，净优势反而减小。只看命中数量会误判。', '', '四、分层、预定敏感性和删叶']
    for v,x in r.items():
        lines.append(v+' 插图类别（A天文，B浴疗/生物，H大植物，P医药）：')
        for k,z in x['by_illustration'].items():lines.append(f"  {k}: {z['labels']}标签/{z['leaves']}叶，差{pp(z['delta'])}")
        lines.append('  全部叶级贡献：')
        for z in x['main']['exact']['summary']['by_leaf']:lines.append(f"  {z['leaf']}: {z['labels']}标签，差{pp(z['delta'])}")
        for k,z in x['sensitivity'].items():
            a=z['summary'];lines.append(f"  {k}: {a['labels']}标签/{a['leaves']}叶，差{pp(a['delta'])}")
        d=[z['summary']['delta'] for z in x['leave_one_leaf_out']]
        lines.append(f"  删除任一目标叶且从对照池删除同叶、重新匹配后的差范围{pp(min(d))}至{pp(max(d))}；不是置信区间。")
    lines += ['HIQ另匹配册帖；min5要求自身/对照页至少5个同长度机会且至少2个对照叶；certain_loci排除含不确定空格的整位置；dedup_labels同页相同标签只计一次。',
              '两个版本的医药类别各197个可比标签、6叶，均为负；优势不能推广为所有插图标签通用规则。H/I相关，分类结果不鉴定因果。',
              '', '五、结果后补充检查（不是先验检验）']
    for v,x in s['results'].items():
        a=x['common_support']['exact'];d=[z['summary']['delta'] for z in x['drop_label_type']]
        lines += [f"{v}: 限两版共同同定位同写法的{a['labels']}标签/{a['leaves']}叶，精确差{pp(a['delta'])}。正文仍各按自己的转写。",
                  f"逐一删除{len(d)}种标签词（只删查询目标，正文与其他对照保留），剩余差范围{pp(min(d))}至{pp(max(d))}。"]
        for a in x['drop_illustration']:lines.append(f"  去掉目标类别{a['removed_I']}后差{pp(a['summary']['delta'])}。")
    lines += ['', '六、已知答案校准与证据强度',
              '保留真实页/叶/词长/机会数，人工正文使用每词长100种等概率抽象身份。标签独立生成作为阴性；从本页正文抽取作为复制阳性。各100个种子，共400个版本×机制×种子结果。不是自然语言校准，也不模拟真实词频/复制关联。']
    for v,x in s['results'].items():
        for k,a in x['calibration'].items():
            lines.append(f"{v} {k}: 均值{pp(a['mean'])}，样本标准差{rate(a['sample_sd'])}，最小/最大{pp(a['min'])}/{pp(a['max'])}个百分点。")
    lines += ['程序能检出人为植入的强复制关联；阴性随机波动大于本轮微弱的手稿差值。不能据此声称手稿超过随机或已具备检测当前效应的能力；也不能以不同生成机制的范围当真实手稿的p值。',
              '', '七、读图队列，不是译词表',
              f"两版共同相同标签且均有对照的位置{c['shared_identical_eligible_labels']}个，其中双方本页均命中{len(c['both_hit'])}个，双方均未命中{len(c['both_no_hit'])}个，另2个仅一版命中。这些是标签位置数量，不是对象数量或不同词型数。"]
    for key,title in [('both_hit','自然定位顺序前6个双版命中'),('both_no_hit','自然定位顺序前6个双版均未命中')]:
        lines.append(title)
        for row in c[key][:6]:
            lines.append(f"  {row['locator']} {row['word']} | ZL正文位置: {', '.join(dict.fromkeys(h['locator'] for h in row['ZL']['body_hits'])) or '无'} | IT正文位置: {', '.join(dict.fromkeys(h['locator'] for h in row['IT']['body_hits'])) or '无'}")
    lines += ['队列按结果选出；本轮没有新增独立原图对象认证。不能将它称为视觉验证过的语义锚点。下一步与失败门槛见plan.txt。',
              '', '八、复核、来源与局限',
              '主数据、全部对照页、概率分母、校准和后验补充均保存；独立复算状态和范围见audit_v1.txt。哈希验证不等于科学解释被证实。',
              '公开转写的原始字节与预处理代码见saved_v1/freeze.json，独立计算只验证实现与保存结果相符；没有独立新语料。',
              'Stolfi已有标签检索；Zhang–Sheng v2已有不支持简单标签对应的结果。本轮测量、筛选、权重不同，不能称推翻其研究。文献核查见literature_review.txt。',
              'https://ic.unicamp.br/~stolfi/voynich/00-EXPORT/97-10-23-label-maps/source.html',
              'https://arxiv.org/html/2610.34499v2',
              'https://www.voynich.nu/extra/labels.html',
              'https://www.voynich.nu/software/ivtt/IVTFF_format.pdf',
              '本轮产出是可复查的候选与收窄后的路线，没有确认读音、植物名称、语种或连续译文。']
    (HERE/'report.txt').write_text('\n'.join(lines)+'\n')

if __name__=='__main__':main()
