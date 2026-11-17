from pathlib import Path
import json,datetime,hashlib
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from corpus import ROOT,save,load,sha

def main():
    s=json.loads((ROOT/'results/structure_confirm.json').read_text())
    p=json.loads((ROOT/'results/predictive_confirm.json').read_text())
    split=json.loads((ROOT/'split_receipt.json').read_text());t=s['tests'];pr=p['results'];cp=p['comparisons']
    report='''伏尼契手稿：七小时研究·阶段一报告
结论范围：全书分组结构验证与词形预测；没有得到语言、固定解码键或译文。

一、这轮实际做了什么
将可按既定规则处理的线性正文扩展为204个转写分区，按物理叶分组；同叶正反面和折页分区不跨组。
旧样本相关叶38分区，新增训练75分区，开发41分区，确认28分区，后续保留22分区。
本阶段确认集来自13个叶组，共5025个保留词形；后续22分区没有在本阶段评分。
原始语料为公开学术转写，上一轮已导出全书，因此“留出”指未参与当前拟合/参数选择，不指从未被载入或绝对盲审。
确认集只有书手1/2/3与植物、沐浴、药材、星形条目等分组；不冒称所有书手都有独立确认。

二、版面解析的重要修正
IVTFF的“=”是与紧邻的原始位置同高，而不是与上一个筛选后保留的正文同高。
f11v/f49v/f76r中，“=”正文往往对齐页边单字；误删标签后再接行会把很多行粘在一起。
现已保留来源位置关系，并对f49v原图检查。前轮20页不包含受影响页。
另看6幅页面缩览，其中f49v/f80r/f106r查看原生整页。f89r1折页分区仍未逐行定位。
这些是版面抽查，不是增加6页逐字校对或建立独立段落金标准。

三、段首信号很强，普通行首信号较弱且有版本敏感性
只比较同一条段首行的第一词形与其余词形，以EVA k/t/p/f开头为指标，确认集页均差83.70个百分点。
主检验Holm校正p=0.002。IT版相应差80.20个百分点；不是某一种编码细节才产生。
非段首行差只有3.24个百分点，主检验Holm p=0.0645，没有通过四项检验的校正门槛。
IT版或合并不确定空格时这一较小效应有辅助支持，不能断言所有版本都没有效应。
段落边界继承转写者标记，部分边界可能也参考高字形；因此不能当作完全独立于字形的段落真值。
f106r星形条目提供外部版面线索，但尚未逐条制作与字形无关的段落标注。
这提示需要区分词形内容与书写位置规则，不能证明高字形仅是装饰或无语义。

四、更严格的相邻词形对照收窄了上一轮解释
本轮固定每行首尾，只考察中间相邻词形；完全重复与不同但编辑距离为1的词形分开计数。
确认集完全重复率1.089%，行内重排期望1.296%；主Holm p=0.3415，没有富集证据。
不同但一编辑相似率4.164%，行内重排期望3.597%；主Holm p=0.204，没有通过主检验。
再精确保留每个位置的编码长度，相似率对照变为3.913%，辅助p=0.317。
因此，上一轮对“页内打乱”的阳性结果不能直接推出即时复制/改单字。
新旧结果的样本、统计量和保留条件不同，不是改写旧实验；二者必须并列阅读。
也不能由此次不显著证明没有局部相关；开发组较大的样本中有较弱富集，仍需更有针对性的机制比较。

五、怎样更好地预测未拟合的词形
用训练组拟合词内单位模型，开发组选阶数与平滑强度，再一次评分28页确认集。
最优为四元模型（当前单位依赖最多3个前置单位），每个词形重置上下文，并计入结束标记。
它描述符号拼写约束，不包含语义或翻译。以词形平均负log2概率计，越低越好：
  单位独立模型      23.411 bits/词形
  二元模型          12.924
  三元模型          11.639
  四元模型          11.519
  加已知位置类别    11.341
  加已知书手类别    11.265
位置与书手分别加入，并非宣称两者改善可直接相加。
按叶等权配对，位置模型平均节省0.174 bits/词形，叶重采样95%区间[0.145,0.200]；
书手模型节省0.409 bits/词形，区间[0.260,0.550]。
这些区间条件于13个确认叶组；不是整本手稿/所有手稿的普遍参数。
书手与章节/Currier类别混杂，不把收益解释成单纯作者身份效应。

把训练词频混入模型后为11.623 bits/词形；再加入最近8词的5%精确重复记忆后为11.626。
记忆模型没有在确认集稳定改善；正向与反向记忆也无清晰差异。
这只否定这一个窄模型的验证收益，不否定可改字、跨行或更复杂的复制机制。
IT版与合并编码单位版中，位置/书手改善和简单记忆未改善方向保持。
不能跨不同单位表示直接拿裸bits高低判断谁更接近真实语言。

六、统计与复现边界
四项结构主检验1999次置换，先按页计算再等权汇总；主确认四项做Holm校正。
敏感性版本399次属于辅助检查；分组结果为描述性，不依据未校正小p挑故事。
随机对照区间是置换参考范围，预测模型区间是按叶重采样范围，两者不是同一个量。
首次诊断运行误用seed2026111702；已保留诊断文件，并按事前方案seed2026111701重跑主结果。
没有按结果挑种子。主随机化完整数组与所选预测模型均在独立执行中准确重现。
来源与方案校验值、逐页结果、全部版本及阴性结果均保留在results/与对应协议文件。

七、下一阶段问题
优先检验段首额外字形、位置依赖替代、书手与章节混杂，以及跨词关系是否超出词形/长度/位置模型。
文献中的固定候选解码与已知答案密码对照并行推进；新假说定规则后才使用后续保留页。
当前没有可负责任地译成中文的一句话。

来源
ZL3b / IT2a公开转写与IVTFF规则：https://voynich.nu/transcr.html
https://voynich.nu/software/ivtt/IVTFF_format.pdf
CC0转写许可说明：https://voynich.nu/roadmap.html
本轮结果与脚本均为本地实际运行；没有借助外部模型API生成解读。
'''
    (ROOT/'阶段一研究报告.txt').write_text(report)
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10})
    fig,axs=plt.subplots(2,2,figsize=(12,8),layout='constrained');fig.patch.set_facecolor('#faf8f3')
    keys=list(t)
    ax=axs[0,0];ax.bar(['Paragraph first','Other line first'],[t[k]['observed']*100 for k in keys[:2]],color=['#365b4f','#b8b5a6'])
    ax.set(ylabel='First minus other slots (percentage points)',title='A. Position effect on 28 confirmation pages');ax.axhline(0,color='#333',lw=.6)
    ax.text(.02,.94,'Primary Holm p: .002 / .0645',transform=ax.transAxes,va='top')
    ax=axs[0,1];x=np.arange(2);ax.bar(x-.18,[t[k]['observed']*100 for k in keys[2:]],.36,label='Observed',color='#365b4f')
    ax.bar(x+.18,[t[k]['null_mean']*100 for k in keys[2:]],.36,label='Interior shuffle',color='#b8b5a6')
    ax.set(xticks=x,xticklabels=['Identical','Distinct edit-distance 1'],ylabel='Adjacent interior pairs (%)',title='B. Stronger control weakens local-repeat evidence');ax.legend(frameon=False)
    ax=axs[1,0];names=['char_order1','char_order2','char_order3','char_order4','char_position','char_hand']
    ax.barh(['IID','Bigram','Trigram','4-gram','+ position','+ hand'],[pr[k]['bits_per_token'] for k in names],color=['#b8b5a6']*4+['#365b4f']*2)
    ax.invert_yaxis();ax.set(xlabel='Held-out bits per token (lower is better)',title='C. Predictive scores; no decoded language')
    ax=axs[1,1];cks=['char_selected__minus__char_position','char_selected__minus__char_hand','word_unigram__minus__word_cache_forward']
    vals=[cp[k]['mean_leaf_bits_saved'] for k in cks];ints=[cp[k]['bootstrap95'] for k in cks]
    ax.errorbar(vals,np.arange(3),xerr=np.array([[v-z[0] for v,z in zip(vals,ints)],[z[1]-v for v,z in zip(vals,ints)]]),fmt='o',color='#365b4f',capsize=4)
    ax.set(yticks=np.arange(3),yticklabels=['Position','Hand','Exact-word cache'],xlabel='Leaf-mean bits saved per token',title='D. Added information: 13-leaf paired bootstrap');ax.axvline(0,color='#a35236',lw=1)
    fig.suptitle('Voynich research — Stage 1 | 28 pages, 13 leaf groups, 5,025 retained tokens',fontsize=14)
    fig.savefig(ROOT/'阶段一结果.png',dpi=180);fig.savefig(ROOT/'阶段一结果.svg');plt.close(fig)
    now=datetime.datetime.now(datetime.timezone.utc).isoformat()
    findings=[
      dict(title='段首格式跨新页保持',summary='28页确认集段首首词高字形比例较同一行其余词形高83.70个百分点。',evidence='ZL主检验Holm p=0.002；IT版方向保持。',limitation='段落边界继承转写标记；不说明字形仅有装饰作用。'),
      dict(title='相邻相似信号在更强对照下减弱',summary='固定行首尾后，不同但一编辑相似率4.16%，行内对照3.60%；未通过主检验。',evidence='Holm p=0.204；再保留长度，辅助p=0.317。',limitation='与旧20页实验的样本/统计量不同；不证明完全不存在局部依赖。'),
      dict(title='位置与书手帮助预测',summary='四元模型11.519 bits/词形；加入位置11.341，加入书手11.265。',evidence='训练/开发按整叶隔离；同一28页确认集、同一目标评分。',limitation='使用已知版面/书手信息，存在章节混杂；预测压缩不是语义解读。'),
      dict(title='简单复制记忆未改善确认集',summary='词频模型11.623 bits/词形，加入开发集选出的最近8词记忆后11.626。',evidence='IT与合并编码版本方向保持；逐叶差值区间包含零。',limitation='只检验精确重复的窄模型，不排除改写或更复杂机制。')]
    save('public_summary.json',dict(title='扩展研究：段首格式与词形预测',status='active',updated_at=now,
         stage_status='stage1_complete',findings=findings,
         scope='总研究仍在原定7小时窗口中继续；本页为已完成阶段一的静态快照。',
         confirmation_pages=28,confirmation_leaf_groups=13,confirmation_tokens=5025,reserved_pages=22))
    tracked=['corpus.py','structure.py','predictive.py','validate_stage1.py','stage1_protocol.txt','predictive_protocol.txt',
             'split_manifest.json','阶段一研究报告.txt','public_summary.json','results/stage1_verification.json',
             'results/structure_confirm.json','results/predictive_confirm.json']
    save('stage1_manifest.json',dict(created_utc=now,files={f:sha(ROOT/f) for f in tracked}))

if __name__=='__main__':main()
