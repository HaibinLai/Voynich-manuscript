"""Render the completed exact summary; does not score or select manuscripts."""
from pathlib import Path
import argparse,gzip,json

HERE=Path(__file__).resolve().parent
MODES={'main_HI':'主比较：同书手/插图类别','strict_HIQ5':'严格：冻结主长度后同册帖','cross_version_lengths':'跨版共同长度'}

def number(x):return x['decimal']

def main(output):
    assert not output.exists()
    summary=json.loads((HERE/'run_v2/summary.json').read_text())
    lines=['整叶标签与正文：真实语料结构下的精确重新配对','2026-11-18 / 第二个七小时窗口阶段2','',
    '结论',
    '在所选13叶与共同长度下，观察配对未比整体重新配对呈明显突出。主exact的ZL关联差为−0.00740个百分点、IT为+0.02097个百分点；规定可交换参照下精确上尾分别约0.503和0.407。严格同册帖及跨版共同长度没有改变这一结论。',
    'k/t允许一次替换后，原配对命中率明显增加，但重新配对也大幅增加；其超过排列平均新增量的部分只有约0.054–0.060个百分点，增量上尾约0.262–0.293。本轮没有获得可作为可靠词义锚点的整叶特有匹配。',
    '未支持这一特定关联检验，不等于证明手稿无语义、不等于所有标签都不是名称，也不否定不同的变长、词形变化或对象关系。六对结果均完整报告，未选择最有利配对定音。','',
    '这轮和上一轮问的不是同一个问题',
    '上一轮比较单个标签在同页正文和异叶正文中的率，采用页→叶汇总。本轮把整片物理叶的标签、正文各自汇成袋；固定每组共同词长，词长等权，再将整叶袋双射重新配对。同叶多个页面合并，同叶重复和真实词形/词频被保留；不能把分面或标签数量当独立样本。',
    '正文机会分母仍为目标叶相同EVA长度的所有保留词次。恒等观察值与含恒等映射的完整排列均值比较；参照不是全部错配。新旧结果不能直接相减解释成“控制某项混杂后的因果变化”。','',
    '支持与排除',
    '全输入有ZL607、IT614个完整单词图旁位置。主分析纳入ZL148、IT182个标签位置，均只来自13个整叶H/I一致的物理叶：医药H1/P六叶f88、f89、f99、f100、f101、f102；浴疗H2/B七叶f75、f77、f78、f80、f82、f83、f84。',
    'ZL医药共同长度4/5/6，IT医药4/5/6/7；浴疗两版均仅长度6。主同长度正文机会为2529/2792。两版标签不是两份独立手稿，也未强制将分词不同的位置对齐。',
    '整叶H/I混合的f67、f68、f70等被排除；f71–f73的完整标签没有保留线性正文。大植物类可配叶各只有一叶，不能组成重新配对组。当前结果不能推广至全部标签或黄道标签。',
    '严格方案锁定主长度再按册帖Q分组，并要求各叶相同长度正文至少5次。当前标签/正文支持恰好与主相同，所有恒等观察值相同；医药拆为Q=O两叶与Q=S四叶，浴疗Q=M七叶不变。改变的是允许配对的集合。support_v1中旧的扩长度strict计数仅设计历史，不是正式结果。',
    '跨版共同长度保持相同叶集合，将医药统一为4/5/6；ZL148标签/2529正文机会，IT153标签/2581机会。相同长度不等于相同标签，IT仍按自己的转写评分。','',
    '精确分布与多重口径',
    '主/跨版组内枚举720和5040个排列，其笛卡尔积为3,628,800个完整分配；严格为2、24、5040，共241,920个。无Monte Carlo。矩阵有理数转共同整数分母，尾数和并列精确判断。',
    'exact是主问题；六总模型及六增量的原始上尾是探索性比较，未称逐项经过多重校正。额外的max六增量参照保留同一排列内六统计量的依赖，只针对整体全局零假设；不提供某一对字形的强FWER保证或语义正确率。','']
    for mode,title in MODES.items():
        lines.extend([title,'列：版本/模型 | 原配对率% | 超过排列均值的百分点 | 精确上尾 | 上尾计数/全部分配'])
        for v in ['ZL','IT']:
            r=summary[v][mode]
            lines.append(f"支持 {v}：{r['leaf_count']}叶，{r['labels']}标签，{r['body_opportunities']}同长度正文机会。")
            for model,x in r['models'].items():
                lines.append(f"{v}/{model:5s} | {number(x['observed'])*100:.6f} | {number(x['excess_over_mean'])*100:+.6f} | {number(x['p_upper']):.9f} | {x['tail_ge']}/{x['assignments']}")
        lines.append('六增量：版本/配对 | 原配对新增百分点 | 超过排列平均新增量的百分点 | 精确上尾 | 上尾计数/全部分配')
        for v in ['ZL','IT']:
            r=summary[v][mode]
            for model,x in r['increments'].items():
                lines.append(f"{v}/{model} | {number(x['observed'])*100:.6f} | {number(x['excess_over_mean'])*100:+.6f} | {number(x['p_upper']):.9f} | {x['tail_ge']}/{x['assignments']}")
            x=r['max_increment_global_null']
            lines.append(f"{v}/max六增量（全局零假设） | 上尾 {number(x['p_upper']):.9f} = {x['tail_ge']}/{x['assignments']}")
        lines.append('')
    lines.extend(['主比较的分组结果（探索性拆分）','列：版本/组 | exact差百分点 | exact上尾 | kt增量差百分点 | kt增量上尾'])
    for v in ['ZL','IT']:
        d=json.loads(gzip.decompress((HERE/f'run_v2/{v}_main_HI.json.gz').read_bytes()))
        for g in d['groups']:
            a=g['summaries']['exact'];b=g['increment_summaries']['kt']
            lines.append(f"{v}/{g['stratum']} | {number(a['excess_over_mean'])*100:+.6f} | {number(a['p_upper']):.9f} | {number(b['excess_over_mean'])*100:+.6f} | {number(b['p_upper']):.9f}")
    lines.extend(['','可交换性仍是前提，不能由这批数据认证',
    'H1/P主组横跨O与S两个册帖；严格组对此作限制，但册帖不是随机分配。f88/89与f99–102相邻，浴疗叶号75–84成簇；叶号差只是顺序代理，不是精测物理邻接或抄写时间。相邻叶、同主题、同图模板或局部复制仍可能相关。',
    '共同长度下标签亚型也不均匀：医药有的叶只有Lf草药片段，有的混合Lc容器；浴疗f78只有Lt管/池，f80只有Ln人物，其他叶混合。控制H/I/Q没有消除所有上下文差异。exchangeability_diagnostics.json保留每叶类型组成与逐对叶号距离。',
    '因此尾数应读成“若这些组内整叶配对可交换，观察值在该完整有限参照中的位置”。不能称语义p值，不能说p证明无关，也不能把未见突出外推为手稿无意义。','',
    '计算、失败与复核状态',
    '原run_v1企图把联合分数展开为巨大重数表，在首个条件未输出完成结果前占约3GB内存，被主动终止。旧代码、协议、冻结、输入与中止收据保留；没有丢弃已完成结果或根据分数改规则。',
    'run_v2只改存储和联合统计累计方式，支持及全部统计量不变。完整分组排列/整数数组足以无损重构联合分布。原实现与紧凑实现的182项人工对比通过；6个正式包均完成。',
    '此报告生成时独立数值审核由另一实现进行中；自身toy校验不是独立审计。发布应另附独立审计收据。所有原字符串保留，未开展新对象识别、音值映射或连续译文验证。','',
    '下一步含义',
    '这一结果降低了把“完整同形标签在同叶正文突出”直接用作词义锚点的优先级。更有约束的后续需要先独立标注标签究竟附着于哪个图像对象，再依据文献冻结有限变长规则或跨页对象关系，保留错误对象和错配作为对照。不能因为本轮弱结果便逐词补字直到命中。','',
    '详见 protocol.txt、representation_change.txt、schema_scope.txt、REPRODUCE.txt 和 run_v2/summary.json。'])
    output.write_text('\n'.join(lines)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
