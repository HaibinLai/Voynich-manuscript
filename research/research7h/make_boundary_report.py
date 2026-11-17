from pathlib import Path
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from corpus import ROOT,sha,save


def main():
    names=['boundary_confirm','boundary_confirm_merged','boundary_confirm_IT']
    ds=[json.loads((ROOT/'results'/f'{n}.json').read_text()) for n in names]
    d=ds[0]
    text='''跨词边界研究：存在较小、可复现的词尾→后词首预测信号

本轮没有获得词义、语言识别或译文。实验目标很窄：已知版面与两词长度后，前一词首/末单位能否进一步预测下一词首单位。
训练/开发/确认仍按物理叶划分，模型只在训练组拟合、开发组选参数。22页后续保留组未评分。
确认组阶段一统计已被观察，所以只称本次边界规则事前冻结，不称该组从未见过。

主设计
取每行内部不重叠词对，0起始目标槽位2、4、6……，排除行首和行末；未知词保留缺口，不跨过缺口接词。
ZL/EVA有1783对，来自28页、13叶组。基线提供书手、图像章节、两词长度桶、行内三分位、段首行标志。
两个候选分别额外提供前词末单位与前词首单位。目标长度属于侧信息，因此本试验不是完整的下一词生成/压缩模型。
预测分布分层平滑并归一化，开发集选择平滑与混合权重；固定配置文件先写出，再评分确认页。

实测结果（同叶的页均值先合并，各叶等权；正数为改善）
'''
    for label,x in zip(['ZL / EVA主分析','ZL / 合并复合单位','IT / EVA转写敏感性'],ds):
        text+=f'\n{label}，{x["confirm_pairs"]}对：\n'
        for feature,title in [('last','前词末→后词首'),('first','前词首→后词首')]:
            s=x['results'][feature]['improvement'];p=x['primary']['tests'][feature]
            lo,hi=s['bootstrap95']
            text+=f'  {title}：平均节省{s["mean_leaf_bits_saved"]:.5f} bits/目标，整叶bootstrap95%区间[{lo:.5f},{hi:.5f}]；条件重配Holm p={p["holm_p"]:.4f}。\n'
    text+='''
前词末单位的改善在三种表示中方向一致，按叶区间均为正；约0.06 bits/目标的量级较小，不能描述成恢复大部分文本。
前词首单位的平均收益接近零；主条件重配检验有较弱信号，但叶间bootstrap跨零，合并单位敏感性不通过条件重配门槛。
这两种统计问题不同：重配p比较某个受约束重配参考，bootstrap衡量这13个确认叶之间的收益变化。不能拿其中一个掩盖另一个。

较严格对照的局限
随机对照在同页、精确两词长度、行内三分位、段首行标志相同的桶内，重配前词首/末特征，目标和模型不变。
这里重配的是记录特征，并非保证所有词能重新组成同一张真实页面；依赖桶内可交换假设，不是所有历史机制下的通用检验。
'''
    for label,x in zip(['ZL/EVA','ZL/合并','IT/EVA'],ds):
        p=x['primary']
        text+=f'{label}：非单元素桶涉及{p["non_singleton_target_fraction"]:.1%}目标；前词末特征实际改变{p["tests"]["last"]["actual_context_changed_fraction"]:.1%}、前词首改变{p["tests"]["first"]["actual_context_changed_fraction"]:.1%}。\n'
    text+='''主ZL/EVA的重配参考本身平均保留约0.0305 bits收益；真实平均0.0639，不能把全部0.0639当作重配所隔离的净效应。
放宽桶、或使用全部相邻内部词对，词尾信号仍在；这些是399次辅助检查，含重叠词对，不取代主设计。

核验
人工构造确定词间依赖，已检出约2 bits改善；独立随机目标对照的dev选择回退为基线，确认收益0。
逐条件概率归一化、缺失槽、词对不重叠、全部24种小例排列均已检查。
另用直接遍历训练记录的公式核对缓存概率，用math.fsum独立重算完整1999次随机数组，三种表示最大差低于1e-13。
首次加权dot操作在本机数值库触发RuntimeWarning，但输出有限；改用显式乘积求和并用math.fsum复核。
原始运行和数组保留在results/diagnostic_boundary_dot/，协议和选参未改变，不按结果重新挑模型。

下一步
用包含完整词概率且不提供目标词长度的模型检验，进一步核对局部拼写规则、书写分词习惯与生成器能否产生该信号。
有明文密码与无指定明文生成器都必须做相同条件预测，不能由本信号直接支持某种语言或否定另一种机制。
在任何新规则使用22页保留组前，先冻结目标、评价和失败条件。

复现
python3 research/research7h/boundary.py
python3 research/research7h/validate_boundary.py
python3 research/research7h/make_boundary_report.py
依赖与来源同根目录README；结果、全部随机数组与冻结配置位于results/。
转写来源 https://www.voynich.nu/transcr.html；本报告全部数值来自本地实际运行。
'''
    (ROOT/'跨词边界研究报告.txt').write_text(text)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axs=plt.subplots(1,3,figsize=(14,4.3),layout='constrained');fig.patch.set_facecolor('#faf8f3')
    labels=['ZL / EVA','ZL / merged','IT / EVA'];colors=['#365b4f','#b66b40']
    for fi,(f,title) in enumerate([('last','Previous last unit'),('first','Previous first unit')]):
        x=np.arange(3)+(fi-.5)*.14
        v=np.array([q['results'][f]['improvement']['mean_leaf_bits_saved'] for q in ds])
        ci=np.array([q['results'][f]['improvement']['bootstrap95'] for q in ds])
        axs[0].errorbar(x,v,yerr=np.array([v-ci[:,0],ci[:,1]-v]),fmt='o',capsize=4,color=colors[fi],label=title)
    axs[0].axhline(0,color='#888',lw=.8);axs[0].set(xticks=range(3),xticklabels=labels,ylabel='Bits saved per target (leaf mean)',title='A. Held-out conditional prediction');axs[0].legend(frameon=False,fontsize=8)
    arr=np.load(ROOT/d['primary']['null_array'])
    axs[1].hist(arr['last'],bins=32,color='#aaa99a',label='Conditional reassignment')
    axs[1].axvline(d['primary']['tests']['last']['observed_leaf_bits_saved'],color=colors[0],lw=2,label='Observed')
    axs[1].set(xlabel='Bits saved per target (leaf mean)',ylabel='Replicates',title='B. Tail-to-head: constrained null');axs[1].legend(frameon=False,fontsize=8)
    vals=d['results']['last']['improvement']['per_leaf'];axs[2].barh(list(vals),list(vals.values()),color=[colors[0] if v>0 else colors[1] for v in vals.values()]);axs[2].axvline(0,color='#888',lw=.8)
    axs[2].set(xlabel='Bits saved per target',title='C. Gains vary across the 13 leaves')
    fig.suptitle('Word-boundary predictability is measurable; word meanings remain unknown',fontsize=13)
    fig.savefig(ROOT/'跨词边界结果.png',dpi=180);fig.savefig(ROOT/'跨词边界结果.svg');plt.close(fig)
    save('boundary_public_summary.json',dict(status='complete',no_decipherment=True,
        report='跨词边界研究报告.txt',figure='跨词边界结果.png',
        protocol_sha256=sha(ROOT/'boundary_protocol.txt'),variants=[dict(name=n,source=x['source'],representation=x['representation'],pairs=x['confirm_pairs'],
              results=x['results'],primary=x['primary']) for n,x in zip(names,ds)],
        limitations=['Target word length is known side information.','Only 13 confirmation leaf groups; original corpus publicly available.',
                     'Conditional permutation moves fewer than half of contexts; not a universal null.','No word meaning or language identified.']))


if __name__=='__main__':main()
