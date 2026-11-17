import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from corpus import ROOT,save,sha

def main():
    names=['boundary_word_confirm','boundary_word_confirm_merged','boundary_word_confirm_IT','boundary_word_confirm_join']
    ds=[json.loads((ROOT/'results'/f'{n}.json').read_text()) for n in names]
    labels=['ZL/EVA','ZL/合并单位','IT/EVA','ZL/合并不确定空格']
    report='''完整词形边界模型：移除目标长度后，词尾→后词首的预测收益仍在

这是观察前一边界实验后提出、随后冻结的后续检验，不是独立重复。沿用同一确认集，22页保留集仍未评分。
主问题是此前提供下一词长度是否导致结果难以解释。本实验不给模型下一词长度、下一词末字形或未来词。
已知条件包括书手、章节、前词长度与当前行内位置；因此是版面条件下的完整词形概率，不是整页无条件编码。

概率模型
完整非空词分为首单位与后续单位（含结束标记）。首单位Q由版面/前词条件预测，后续单位来自训练组固定四元词内模型。
P(w|context)=Q(first|context)×Pchar(rest,EOS|first)，包含首字、所有词内字形和EOS成本。
Q与有限状态CharLM各自归一化。短字母表枚举长度1..6的完整词概率加更长串剩余质量为1，实测误差约2e-16。
训练外单位合并为UNK，因此这里报告规范化类别串的概率，不冒称逐字无损压缩。

实际结果（正数为相对相同基线的改善）
'''
    for label,d in zip(labels,ds):
        report+=f'\n{label}，{d["confirm_pairs"]}个不重叠内部词对：\n'
        report+=f'  完整词基线 {d["results"]["base"]["bits_per_target"]:.5f} bits/词；加入前词末单位 {d["results"]["last"]["bits_per_target"]:.5f} bits/词。\n'
        for f,title in [('last','前词末'),('first','前词首')]:
            s=d['results'][f]['improvement'];lo,hi=s['bootstrap95'];p=d['primary']['tests'][f]
            report+=f'  {title}：叶均节省{s["mean_leaf_bits_saved"]:.5f} bits/词，叶bootstrap95% [{lo:.5f},{hi:.5f}]；条件重配Holm p={p["holm_p"]:.4f}。\n'
    report+='''
主ZL/EVA与合并单位、合并不确定空格都有正的叶均区间。IT的点估计同向，但叶bootstrap区间略跨零；不能写成所有敏感性版本都通过相同门槛。
首→首的收益更弱，所有叶bootstrap区间跨零，虽然若干条件重配检验有信号。
pooled bits按词等权，叶均改善先页内平均再叶内平均，因此两列差值不要求相等。
完整词基线10.83不能直接与阶段一11.52横比：当前只评分被选择的内部词对目标，样本不同。

对照与验证
条件重配保留同页、前词精确长度、行内三分位、段首行标志；这里不再按目标长度分桶。
这使允许移动的记录更多，但也改变了随机参考；本结果与上一实验不是同一估计量的直接优劣赛。
完整词增益逐词与首单位增益一致，因为剩余部分的模型完全相同，独立逐符号累加复核了这一点。
全部目标长度输入强制为0，直接扫描训练记录得到的概率与缓存一致；主ZL/EVA全部1999次排列用math.fsum重放。
没有使用下一词长度并不等于已理解内容：拼写接续、分词习惯、生成器、冗余编码与语言都可能有这种预测结构。
没有得到可译成中文的句子。

复现
python3 research/research7h/boundary_word.py
python3 research/research7h/validate_boundary_word.py
python3 research/research7h/make_boundary_word_report.py
结果与逐词分数、冻结配置位于results/；所有模型网格与数据范围见boundary_word_protocol.txt。
'''
    (ROOT/'完整词形边界研究报告.txt').write_text(report)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axs=plt.subplots(1,2,figsize=(11,4.5),layout='constrained');fig.patch.set_facecolor('#faf8f3')
    for i,(f,label,color) in enumerate([('last','Previous last unit','#365b4f'),('first','Previous first unit','#b66b40')]):
        v=np.array([d['results'][f]['improvement']['mean_leaf_bits_saved'] for d in ds]);ci=np.array([d['results'][f]['improvement']['bootstrap95'] for d in ds])
        axs[0].errorbar(np.arange(4)+(i-.5)*.15,v,yerr=np.array([v-ci[:,0],ci[:,1]-v]),fmt='o',capsize=4,label=label,color=color)
    axs[0].axhline(0,color='#999',lw=.8);axs[0].set(xticks=range(4),xticklabels=['ZL/EVA','ZL/merged','IT/EVA','Join spaces'],ylabel='Bits saved per complete word (leaf mean)',title='A. No target-length side information');axs[0].legend(frameon=False,fontsize=8)
    d=ds[0];null=np.load(ROOT/d['primary']['null_array'])['last'];obs=d['primary']['tests']['last']['observed_leaf_bits_saved']
    axs[1].hist(null,bins=32,color='#aaa99a',label='Conditional reassignment');axs[1].axvline(obs,color='#365b4f',lw=2,label='Observed')
    axs[1].set(xlabel='Bits saved per complete word (leaf mean)',ylabel='Replicates',title='B. ZL/EVA: observed versus constrained null');axs[1].legend(frameon=False,fontsize=8)
    fig.suptitle('Predictable word forms, with no recovered plaintext',fontsize=13)
    fig.savefig(ROOT/'完整词形边界结果.png',dpi=180);fig.savefig(ROOT/'完整词形边界结果.svg');plt.close(fig)
    save('boundary_word_public_summary.json',dict(status='complete',no_decipherment=True,
        report='完整词形边界研究报告.txt',figure='完整词形边界结果.png',target_length_input=False,
        protocol_sha256=sha(ROOT/'boundary_word_protocol.txt'),
        variants=[dict(name=n,source=d['source'],representation=d['representation'],spaces=d['spaces'],pairs=d['confirm_pairs'],results=d['results'],primary=d['primary']) for n,d in zip(names,ds)],
        limitations=['Follow-up designed after earlier confirmation results; not independent replication.',
                    'IT leaf bootstrap interval crosses zero slightly.','Unknown units collapse to UNK.','No plaintext recovered.']))

if __name__=='__main__':main()
