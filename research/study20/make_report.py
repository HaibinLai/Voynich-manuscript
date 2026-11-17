from pathlib import Path
import hashlib, json, platform, sys
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from analyze import build_pages, parse, tokenize, units

def main():
    result=json.loads((ROOT/'results/statistics.json').read_text());runs=result['runs']
    robust=json.loads((ROOT/'results/descriptive_robustness.json').read_text())
    audit=json.loads((ROOT/'audit_records.json').read_text())
    d=runs['primary_discovery'];v=runs['primary_validation']
    H=list(v['tests']);h1,h2,h3,h4=H
    fig,axs=plt.subplots(2,2,figsize=(14,10),layout='constrained')
    fig.suptitle('Voynich manuscript: 20-page calibration and structural analysis',fontsize=17,weight='bold')
    keys=['primary_validation','merged_units_validation','IT_version_validation','English_contiguous','Latin_contiguous','toy_copy_mutate']
    labels=['Voynich: ZL / EVA','Voynich: merged units','Voynich: IT / EVA','English: one window','Latin: one window','Toy copy-and-mutate']
    for ax,metric,title,xlabel,factor in [
      (axs[0,0],h1,'A  Within-token constraints','H(next | previous) / H(next)',1),
      (axs[0,1],h2,'B  Adjacent identical / one-edit token pairs','Mean page rate (%)',100)]:
        y=np.arange(len(keys));obs=[runs[k]['tests'][metric]['observed']*factor for k in keys]
        ax.barh(y,obs,color=['#216778']*3+['#778780']*2+['#aa7251'],height=.50,label='Observed')
        for i,k in enumerate(keys):
            t=runs[k]['tests'][metric];low,high=np.array(t['null_95_interval'])*factor
            ax.plot([low,high],[i,i],color='#c34d35',lw=3)
            ax.scatter(t['null_median']*factor,i,c='#c34d35',marker='|',s=100,zorder=4)
        ax.set(yticks=y,yticklabels=labels,xlabel=xlabel,title=title);ax.invert_yaxis()
        ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
    axs[0,0].set_xlim(0,1)
    axs[0,1].plot([],[],color='#c34d35',lw=3,label='Shuffle 95% reference range')
    axs[0,1].legend(fontsize=9,loc='lower right')
    ax=axs[1,0]
    examples=[('Discovery: all lines',d['tests'][h3]),('Validation: all lines',v['tests'][h3]),
              ('Discovery: non-initial lines',d['supplemental']['H3_excluding_paragraph_starts']),
              ('Validation: non-initial lines',v['supplemental']['H3_excluding_paragraph_starts'])]
    for i,(label,t) in enumerate(examples):
        low,high=np.array(t['null_95_interval'])*100
        ax.plot([low,high],[i,i],color='#bbb8ac',lw=9,solid_capstyle='round')
        ax.scatter(t['observed']*100,i,c='#216778',s=75,zorder=3)
    ax.axvline(0,color='#444',lw=.8);ax.set(yticks=range(4),yticklabels=[x[0] for x in examples],
        xlabel='Gallows-initial token: line start minus others (pp)',title='C  Paragraph position changes the interpretation')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.15)
    ax=axs[1,1]
    ks=['primary_validation','merged_units_validation','join_uncertain_spaces_validation','IT_version_validation']
    labs=['ZL / EVA','ZL / merged units','ZL / join uncertain spaces','IT / EVA']
    for i,k in enumerate(ks):
        t=runs[k]['tests'][h4];low,high=t['null_95_interval']
        ax.plot([low,high],[i,i],color='#bbb8ac',lw=9,solid_capstyle='round')
        ax.scatter(t['observed'],i,c='#216778',s=75,zorder=3)
    ax.axvline(0,color='#444',lw=.8);ax.set(yticks=range(4),yticklabels=labs,
        xlabel='Final token minus others (encoded units)',title='D  Shorter line endings are not robust here')
    ax.invert_yaxis();ax.grid(axis='x',alpha=.15)
    for ax in axs.flat:
        ax.spines[['top','right']].set_visible(False);ax.title.set_fontsize(12);ax.tick_params(labelsize=10)
    fig.supxlabel('20 pages reviewed; paragraph tests use 17 pages / 1,648 retained tokens.\nReference ranges are shuffled-data ranges, not effect confidence intervals. Purposive sample; no decipherment.',fontsize=10)
    fig.savefig(ROOT/'结构分析结果.png',dpi=170)
    fig.savefig(ROOT/'结构分析结果.svg')
    plt.close(fig)
    rows=[]
    names=['词内条件熵比值','相邻相同/一编辑词形比例','行首高笔画字形比例差','行末编码长度差']
    for name,key in zip(names,H):
        t=v['tests'][key]
        rows.append(f"{name}\n  观察值 {t['observed']:.6f}；对照中位数 {t['null_median']:.6f}；对照95%参考区间 {t['null_95_interval'][0]:.6f} 至 {t['null_95_interval'][1]:.6f}\n  双侧经验 p={t['monte_carlo_p']:.4f}；四项 Holm 校正 p={t['holm_adjusted_p']:.4f}\n")
    pages=build_pages();linecount=sum(len(p['lines']) for p in pages)
    missing=sum(t is None for p in pages for l in p['lines'] for t in l['tokens'])
    chosen={a['folio'] for a in audit};records,_=parse('ZL3b-n.txt')
    drawing_count=sum(r['text_ivtff'].count('<->')+r['text_ivtff'].count('<~>') for r in records if r['folio'] in chosen and r['locus_type'][1]=='P')
    groupcounts=Counter(a['illustration_group'] for a in audit)
    selection_lines='\n'.join(f"{a['folio']:6s} PDF {a['pdf_page']:3d} | {a['illustration_group']:14s} | {a['split']:10s} | {a['loci']} 个位置" for a in audit)
    report=f'''伏尼契手稿：20 页原图校对与带对照结构分析
第一轮研究报告 | 2026-11-17 | 结论范围：字形编码与文字组织

本轮得到的主要结果

可以复核的两个结构信号是：词内编码单位排列受约束；相邻词形更常相同或只差一次编辑。
整体行首高笔画字形富集也出现，但验证组去掉段落首行后不再支持此效应。
因此，“段落首行的书写格式”比“所有行都有统一行首规则”更值得接下来区分。
“行末词更短”没有通过主检验，而且对版本和编码单位敏感，本轮不确立这一规律。
这些是对已有转写的复核和小规模对照，不是新语言鉴定、词义发现或破译成果。

1. 校对完成到什么程度

20 页均已查看原图并核对版面/行与文本位置对应；另记录了 40 个重点位置的字形与空格复核。
覆盖植物图 12 页、宇宙图 2 页、黄道图 2 页、药材图 2 页、沐浴图 2 页。
共 332 个转写位置，包括段落、标签、圆周和径向文字。
必须明确：这不是 20 页逐字符终审；没有两位专家独立转写，也没有可靠的字符错误率金标准。
原图分辨率及单个 AI 审查限制使许多细小笔画无法可靠裁决，已保留两版读法，没有强行“纠正”。
20页原图转写对照.html 包含全部页图、逐位置两版文本和 40 个阅读区域裁剪；
20页校对记录.txt 与 audit_records.json 逐项说明范围和未决点。
黄色对照行只是字符串不同，不代表 ZL 或 IT 一定出错。

2. 修正了前一轮自身整理中的两个问题

前一轮导出时直接删除 <-> / <~> 会粘连插图两侧的词。本轮按 IVTFF 规范保留边界。
20 页中用于段落分析的插图中断标记共有 {drawing_count} 处；原始学术转写本身没有因此被改写。
同时修复页变量解析可能把结尾 > 纳入变量值的问题；固定版解析单字符变量值。
f25r 的 7 个文本位置实际对应 6 条物理行，.7 为 .6 同高的右侧尾题，已接回。
f48r 的 Pr/Pc 则是新的物理行，不能只因右对齐就一律接到上一行。
f41v、f81v 等独立标签不作为正文行首；环形起点也不作为物理行首。

3. 样本与方法

目的性选择 20 页，重视覆盖和可审查性，不是全书随机样本，不能外推全书错误率。
按页预先分 discovery 10 页 / validation 10 页；同一叶的正反面不跨组。
其中 f57v、f71r、f73v 没有 P 类段落，因此主段落检验实际使用 17 页：
探索组 {d['pages']} 页、{d['tokens']} 个保留 token；验证组 {v['pages']} 页、{v['tokens']} 个保留 token。
合计 {linecount} 条重接后的物理行、1,648 个保留 token，{missing} 个不确定 token 槽位保留为缺失。
token 只表示转写空格之间的片段，不承诺是真实语言的词。
不把缺失 token 两侧的片段当作原本相邻。

方案在运行数字结果前写入 protocol_v1.txt 并记录校验值；不是第三方公开预注册。
没有用探索组结果调规则后再挑验证组指标；同一执行者已查看两组原图，不能称为完全盲审。
主版本 ZL3b；IT2a、合并常见 EVA 组合、合并不确定空格和第一备选读法作为敏感性检查。
RF 与 ZL 有来源依赖，没有作为独立确认票数。

四项主检验分别使用词内打乱、页内词序打乱、行内词序打乱作为条件对照。
词内打乱精确保留每个 token 的单位频数与长度；页/行内打乱保留相应词袋、行槽位与缺失位置。
相邻相似率、行首和行末效应在各页计算，再对页面等权平均，避免沐浴图长页主导。
条件熵统计汇总词内相邻单位，不跨 token 或跨缺失位置连边。
主检验各 1,999 次置换，报告双侧经验尾概率；验证组四项做 Holm 校正。
敏感性和外部示例各 399 次置换，属于辅助分析，没有与主检验混作同一验证票数。
参考区间是置换数据的分布范围，不是效应置信区间；p 值条件于这批目的性选页与所用随机化模型。

4. 发现一：词内组合的限制在多种处理下存在

条件熵比值定义为 H(下一个编码单位 | 当前单位) / H(下一个单位)。越低表示前一单位越有预测力。
验证组 ZL/EVA 为 {v['tests'][h1]['observed']:.3f}，逐词打乱后中位数 {v['tests'][h1]['null_median']:.3f}。
Holm 校正 p={v['tests'][h1]['holm_adjusted_p']:.3f}。
把 ch、sh、cth、ckh、cph、cfh 作为合并单位后，为 {runs['merged_units_validation']['tests'][h1]['observed']:.3f}，对应打乱中位数 {runs['merged_units_validation']['tests'][h1]['null_median']:.3f}；
换成 IT 转写为 {runs['IT_version_validation']['tests'][h1]['observed']:.3f}，打乱中位数 {runs['IT_version_validation']['tests'][h1]['null_median']:.3f}。
结论限于：此类词形内部不是按相同单位频率随意排列。
EVA 的一个字母不等于一个已知语言字符；合并方案仍只是敏感性检查，不是字符系统的最终鉴定。

5. 发现二：相邻词形更相似，但不能仅凭这一点判定抄写或语言

相似定义为 EVA 单位编辑距离不超过 1，包括完全相同、插入、删除或替换一个单位。
验证组页均相似率 {100*v['tests'][h2]['observed']:.2f}%；页内打乱中位数 {100*v['tests'][h2]['null_median']:.2f}%，相差 {100*v['tests'][h2]['effect_vs_null']:.2f} 个百分点。
Holm 校正 p={v['tests'][h2]['holm_adjusted_p']:.3f}。
更严格地只在各行内部打乱，参考中位数 {100*v['supplemental']['H2_line_shuffle']['null_median']:.2f}%，辅助经验 p={v['supplemental']['H2_line_shuffle']['monte_carlo_p']:.4f}。
探索组相对页内打乱的效果较弱，p={d['tests'][h2]['monte_carlo_p']:.4f}；相对行内打乱 p={d['supplemental']['H2_line_shuffle']['monte_carlo_p']:.4f}，没有达到 0.05。
因此不能把所有分组和所有对照都描述为一致显著。
换 IT 后验证组为 {100*runs['IT_version_validation']['tests'][h2]['observed']:.2f}%，对照 {100*runs['IT_version_validation']['tests'][h2]['null_median']:.2f}%，方向相同。
事后逐次去掉一个验证页，相对页内打乱的均值差仍为 {100*robust['H2_validation']['leave_one_page_out_range'][0]:.2f}–{100*robust['H2_validation']['leave_one_page_out_range'][1]:.2f} 个百分点。
这是删除单页的稳健性范围，不是置信区间，也不能排除书写者、章节与成书过程的共同影响。

原图中可定位的例子包括 f11r.5 的 shor.shor、f25r.5 的 daiin.daiin、
f88r.19 的 qoekol.qoekol 以及 f100r.23 的 shol.shol。它们不提供词义。

6. 需要收窄的线索：行首效应与段首效应不能混为一谈

以 EVA k/t/p/f 开头的 token，在验证组行首比行中多 {100*v['tests'][h3]['observed']:.2f} 个百分点，Holm p={v['tests'][h3]['holm_adjusted_p']:.3f}。
去掉段落第一行后，该差值为 {100*v['supplemental']['H3_excluding_paragraph_starts']['observed']:.2f} 个百分点，
辅助经验 p={v['supplemental']['H3_excluding_paragraph_starts']['monte_carlo_p']:.3f}，没有支持继续富集。
探索组去掉段首后的效应仍为正，但没有在验证组保持。
这说明现有总体信号可能主要集中于段首，而不能先断言每条物理行具有相同的生成规则。
也不能据此证明段首高字形只是装饰；其功能仍未知。

7. 未获主检验支持的假说：行末 token 更短

验证组行末 token 比其余位置平均短 {abs(v['tests'][h4]['observed']):.3f} 个 EVA 编码单位，
但主置换 p={v['tests'][h4]['monte_carlo_p']:.4f}，不确立该规律。
合并常见组合后差值为 {runs['merged_units_validation']['tests'][h4]['observed']:.3f}；
IT 差值为 {runs['IT_version_validation']['tests'][h4]['observed']:.3f}，辅助 p={runs['IT_version_validation']['tests'][h4]['monte_carlo_p']:.4f}。
版本能改变显著性判断；不能只展示支持假说的 IT 版本。

8. 英文、拉丁文和伪文本对照告诉了我们什么

取 Alice 英文及 Caesar 拉丁文的连续片段，按验证组相同行槽位、缺失位置和 816 个 token 重新排版。
对应单片段的条件熵比值分别为 {runs['English_contiguous']['tests'][h1]['observed']:.3f}、{runs['Latin_contiguous']['tests'][h1]['observed']:.3f}；
相邻相似率分别为 {100*runs['English_contiguous']['tests'][h2]['observed']:.2f}%、{100*runs['Latin_contiguous']['tests'][h2]['observed']:.2f}%。
二者词内顺序也比自身打乱更受约束，因此“有结构”并不是伏尼契手稿独有的性质。
事后各取 100 个可能重叠的等 token 数连续窗口，参考分布保存在 descriptive_robustness.json，
不把这些重叠窗口当作 100 个独立样本或总体置信区间。

另按每个伏尼契 token 的编码长度抽取相同字母数的英文/拉丁词形。
这一对照破坏自然语序，只能检验词形层面的混杂，不能称为正常语言句子。
它也会机械地继承原样本的行末长度差，因此不拿它来证明行末规则。
外部文本字母表及题材、年代、书写系统均未完全匹配；只是两个参考文本，不能排除其对应语言。

固定规则的复制改写伪文本（70% 从前 8 个词形中复制，复制时 60% 概率替换一个单位；其余随机生成）
得到相邻相似率 {100*runs['toy_copy_mutate']['tests'][h2]['observed']:.2f}%，远高于本样本；
但条件熵比值 {runs['toy_copy_mutate']['tests'][h1]['observed']:.3f}，与本样本差别很大。
这既不能支持也不能排除更复杂的复制机制。一个指标接近或偏离都不足以确定成书方式。
模型只使用探索组的单位频数与长度分布；规则固定、没有按验证组拟合。

9. 主验证组的完整数字

{''.join(rows)}
10. 复现与后续最有价值的检查

原始来源的校验值在 ../sources/provenance.json；本轮的脚本和输入输出校验值见 run_manifest.json。
数值分析在本地运行；本轮没有额外调用模型 API 生成译文。原图由当前助手做视觉复核。
复现：先运行 setup_study.py 准备选页与方案，再运行 analyze.py、robustness.py、audit.py、make_report.py。
需要 Python、PyMuPDF、Pillow、NumPy、Matplotlib；OCR 不是本轮主分析依赖。
analyze.py 默认从头计算；--resume 用于接续同一方案已保存的结果。
验证包含：插图中断分词、缺失槽位、同高尾题重接、置换保持词袋/槽位、一一单位替换不改变熵和编辑关系。

建议后续先让熟悉古文字的第二位审查者盲核 40 个疑难位置，再扩充不同书写者/章节中
成对匹配的段首行与段中行，检验行首高字形是否稳定依赖段落位置。
同时区分“完全重复”和“近似重复”，加入更强的行内、相同词频及词形模型对照。
在现阶段，最有约束力的结果是“怎样组织字形”，尚没有可用于中文翻译的稳定映射。

附录：固定的 20 页
{selection_lines}

原始格式和数据来源
René Zandbergen, IVTFF 2.0.1（文档 issue 2.0.2, 08/07/2025），特别是插图中断与词间空格、位置类型定义：
https://voynich.nu/software/ivtt/IVTFF_format.pdf
转写与编码说明（明确提示 EVA 编码影响统计）：
https://voynich.nu/transcr.html
https://voynich.nu/analysis.html
英文语料：Lewis Carroll, Alice's Adventures in Wonderland，Gutenberg #11 的 GITenberg 镜像：
https://github.com/GITenberg/Alice-s-Adventures-in-Wonderland_11/blob/master/11-0.txt
拉丁语料：Perseus Digital Library, Caesar, De bello Gallico, T. Rice Holmes edition：
https://github.com/PerseusDL/canonical-latinLit/blob/master/data/phi0448/phi001/phi0448.phi001.perseus-lat2.xml
'''
    (ROOT/'研究报告.txt').write_text(report)
    (ROOT/'结果摘要.txt').write_text('第一轮完成：20 页版面核对、40 个重点位置复核；不是逐字终审。\n'
        '主分析：17 页线性段落、188 条物理行、1648 个保留 token。\n'
        '1. 词内排列受约束：验证组条件熵比值 0.549，打乱对照 0.896。\n'
        '2. 相邻相同或一编辑词形：6.53%，页内打乱对照 3.64%；行内对照下探索组未显著。\n'
        '3. 行首高字形总体富集，但去掉段首后在验证组消失，不能当作普遍行首规则。\n'
        '4. 行末更短未通过主检验；换转写可改变判断。\n'
        '来源与范围、负结果和所有对照见研究报告.txt；没有得到译文。\n')
    manifest=dict(python=platform.python_version(),numpy=np.__version__,matplotlib=matplotlib.__version__,
        protocol_sha256=result['protocol_sha256'],inputs={},scripts={},outputs={})
    for p in [ROOT/'selection.json',ROOT.parent/'sources/ZL3b-n.txt',ROOT.parent/'sources/IT2a-n.txt',
              ROOT/'controls/english_alice.txt',ROOT/'controls/latin_caesar.xml']:
        manifest['inputs'][str(p.relative_to(ROOT.parent))]=hashlib.sha256(p.read_bytes()).hexdigest()
    for p in ROOT.glob('*.py'):manifest['scripts'][p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    for name in ['results/statistics.json','results/descriptive_robustness.json','results/verification.json',
                 'audit_records.json','研究报告.txt','结构分析结果.png','20页原图转写对照.html']:
        manifest['outputs'][name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    (ROOT/'run_manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Saved report, figure PNG/SVG, summary, and run manifest.')

if __name__=='__main__':main()
