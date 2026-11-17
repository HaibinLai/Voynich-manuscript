from pathlib import Path
import datetime,hashlib,json,gzip
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent

def dump(n,v):(P/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
cal=json.loads((P/'calibration_summary.json').read_text());audit=json.loads((P/'replay_verification.json').read_text());assert audit['all_passed']
runs=[json.loads((P/'runs'/('confirm_'+n+'.json')).read_text()) for n in ['ZL_EVA','ZL_merged','IT_EVA']]
rows=[dict(r['results'][s],representation=r['name'],stratum=s) for r in runs for s in ['exact','coarse']]
limitations=[
 'confirm已用于其他分析；这是冻结后一次执行的探索复核，不是全项目独立留出验证。reserve未请求、拟合或评分。',
 '置换仅扰动V来源通道，H、目标词、既有模型与原行槽位固定；不是一份完整真实文本的随机排列，也不具有语义或历史机制的因果解释。',
 '精确长度主对照仍有约25%–28%源槽处于单例层；报告真实词身份移动与来源多重集改变比例。粗桶扩大扰动同时放松长度条件，只作敏感性。',
 '条件Monte Carlo p仅为探索参考；六组全报，没有把p值解释为机制概率或经过历史所有探索校正的确认性显著性。',
 '作者same_position配置0/28/100的普通LOCALY分支实际概率为1%/29%/100%，行首为11%/15%/51%，因为源码使用<=。0不等于关闭，其他生成mode不受直接控制。',
 '作者LOCALY可以从多条过去行抽源词，按累计字符宽度定位；本模型仅上一行、按相对token槽估计位置，不覆盖全部真实生成操作。',
 '干预改变后续随机轨迹，词长、词型及LOCALY比例也变化；相同seed不是逐词配对反事实。20seed分布不是手稿置信区间。',
 '原复制预测只有很小且转写敏感的收益。本实验不能排除局部复制或无语义生成，也没有解出词义、语言或原文。']
summary=dict(schema_version=1,status='completed_and_independently_replayed',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 title='上一行词身份的位置特异性',main_result='校准能响应强位置复制；手稿的小幅上一行收益在同长度词换位后大多保留，六组探索复核均未显示清晰位置特异性。',
 metric='D = original V gain minus mean V gain after source-line identity permutations; bits per word, leaf equal weighted',
 manuscript=rows,calibration=cal,verification=audit,limitations=limitations,figure='上一行位置特异性.svg',reserve_used=False,
 actual_LOCALY_alignment_branch_probabilities={'configuration':[0,28,100],'non_line_initial':[.01,.29,1.],'line_initial':[.11,.15,.51]},
 toy_verification=json.loads((P/'toy_verification.json').read_text()),generation_audit=json.loads((P/'generation_audit.json').read_text()))
dump('website_data.json',summary);dump('public_summary.json',summary)
text=['上一行词身份的位置特异性：完整探索复核','',summary['main_result'],'','设计：固定既有归一化完整词模型与参数；每条上一源行仅抽一份置换供全部目标共享，缺失/未知固定，H通道不动。精确单位长度分层为主，1–3/4–6/7–9/≥10为辅助。每组1999次；没有新调参。','',
 '表示 / 分层 | 原V收益 | 置换均值 | D | 条件参考p | 源身份移动 | 有V目标来源多重集变化']
for r in rows:text.append(f"{r['representation']} / {r['stratum']} | {r['observed_V_gain']:.6f} | {r['null_mean']:.6f} | {r['alignment_specificity_D']:.6f} | {r['monte_carlo_reference_p']:.4f} | {r['source_identity_moved_mean']:.1%} | {r['target_multiset_changed_mean_given_V']:.1%}")
text+=['','主精确长度结果：原上一行收益约85%–91%（ZL）及77%（IT）在置换均值中保留。六组均没有清晰位置特异性证据；粗桶也未改变这一谨慎结论。这里只能限制当前观察器和条件对照，不能以负结果证明作者生成机制不成立。','',
 '生成器校准：Timm作者Java实现，same_position 0/28/100 × 20seed × EVA/merged，精确/粗桶各399次。固定28配置原先选定超参；每条件独立拟合训练计数。精确D中位 EVA=.001118/.004665/.042953，merged=−.000900/.007482/.045939；100−0在两表示均20/20为正。完整分布、测试词长、词型、LOCALY调用与分支事件频率见calibration_summary.json。60份事件日志版本生成文字与无事件日志版逐词完全一致。','',
 '独立验证：不再读取手稿，直接从上一阶段保存的targets重建源行；独立枚举全部单编辑路径并归一化，复算六组全部11994次置换。最大预测增益差约1.5e−16 bits，移动率完全一致。基线/H概率此前已独立重算通过。','',*limitations]
(P/'研究报告.txt').write_text('\n'.join(text)+'\n')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.right':False,'axes.spines.top':False})
fig,ax=plt.subplots(1,2,figsize=(13,5.5),gridspec_kw={'width_ratios':[1,1.3]});colors=['#176b6f','#5b69a3']
for j,rep in enumerate(['eva','merged']):
 vals=[]
 for config in [0,28,100]:
  rr=[json.loads(p.read_text()) for p in (P/'runs').glob(f'p{config}_s*_{rep}.json')];vals.append([r['results']['exact']['alignment_specificity_D'] for r in rr])
 pos=np.arange(3)+(j-.5)*.23
 b=ax[0].boxplot(vals,positions=pos,widths=.19,patch_artist=True,manage_ticks=False)
 for patch in b['boxes']:patch.set_facecolor(colors[j]);patch.set_alpha(.65)
 ax[0].plot([],[],color=colors[j],label=rep.upper())
ax[0].set_xticks(range(3),['0','28','100']);ax[0].set_xlabel('Author same_position setting (0 is not off)');ax[0].set_ylabel('D: original minus permuted V gain (bits/word)');ax[0].set_title('Generator calibration: exact-length strata\n20 seeds per condition, 399 permutations');ax[0].legend();ax[0].axhline(0,color='.5',lw=.8)
for i,r in enumerate(rows):
 lo,hi=r['null95'];ax[1].plot([lo,hi],[i,i],color='#a6b4b7',lw=4);ax[1].plot(r['null_mean'],i,'o',color='#176b6f');ax[1].plot(r['observed_V_gain'],i,'D',color='#c47843')
 ax[1].text(.0162,i,f"D={r['alignment_specificity_D']:.4f}  p={r['monte_carlo_reference_p']:.3f}",va='center',fontsize=8)
ax[1].set_yticks(range(6),[r['representation'].replace('_','/')+' '+r['stratum'] for r in rows]);ax[1].set_ylim(7,-.5);ax[1].set_xlim(-.002,.026);ax[1].set_xlabel('V gain over fixed horizontal model (bits/word)');ax[1].set_title('Previously used confirm: all six exploratory checks\n1999 conditional source-channel permutations')
ax[1].plot([],[],'D',color='#c47843',label='Original');ax[1].plot([],[],'o-',color='#176b6f',label='Permutation mean + central 95% range');ax[1].legend(loc='lower left',fontsize=8);ax[1].axvline(0,color='.5',lw=.8)
fig.suptitle('Does previous-line prediction depend on the word being in that position?',fontsize=13);fig.text(.5,.01,'Permutation ranges are conditional references, not confidence intervals. No reserve pages were scored.',ha='center',fontsize=9);fig.tight_layout(rect=[0,.04,1,.93]);fig.savefig(P/'上一行位置特异性.png',dpi=180);fig.savefig(P/'上一行位置特异性.svg');plt.close(fig)
archives=[]
for f in sorted((P/'inputs').glob('*.json')):
 data=f.read_bytes();packed=gzip.compress(data,mtime=0);g=f.with_suffix('.json.gz');g.write_bytes(packed)
 archives.append(dict(original=str(f.relative_to(P)),original_sha256=hashlib.sha256(data).hexdigest(),archive=str(g.relative_to(P)),archive_sha256=hashlib.sha256(packed).hexdigest()))
dump('input_archives.json',dict(files=archives,format='gzip mtime 0; originals local'))
print(json.dumps({'rows':len(rows),'archives':len(archives),'reserve_used':False}))
