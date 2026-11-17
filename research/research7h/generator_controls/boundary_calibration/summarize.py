"""Aggregate every frozen run; simulation spread is not a manuscript CI."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,datetime,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent

def dump(name,obj):
 (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def describe(values):
 a=np.asarray(values,dtype=float)
 return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),min=float(a.min()),max=float(a.max()),simulation_percentiles_2_5_97_5=np.quantile(a,[.025,.975]).tolist())

runs=[json.loads(p.read_text()) for p in sorted((HERE/'runs').glob('*.json'))]
assert len(runs)==181
expected=json.loads((HERE/'execution_receipt.json').read_text())['tasks']
assert {json.dumps(r['task'],sort_keys=True) for r in runs}=={json.dumps(t,sort_keys=True) for t in expected}
groups=defaultdict(list)
for r in runs:
 t=r['task'];groups[(t['generator'],t['order'],t['representation'])].append(r)
 assert r['targets']=={'train':1665,'dev':830,'test':830}
 assert {k:v['discarded_tokens'] for k,v in r['metadata']['splits'].items()}=={'train':4,'dev':8,'test':8}
 config=json.loads((HERE/r['config_path']).read_text())
 assert r['config_sha256']==sha(HERE/r['config_path'])
 assert config['frozen_utc']<r['test_scoring_started_utc']
 assert r['permutation']['null_sha256']==sha(HERE/r['permutation']['null_array'])
 arr=np.load(HERE/r['permutation']['null_array'])
 for feature in ('last','first'):
  test=r['permutation']['tests'][feature]
  assert len(arr[feature])==1999
  assert np.isclose(test['raw_p'],(1+np.sum(arr[feature]>=test['observed_leaf_bits_saved']-1e-14))/2000)
summary=[]
for (generator,order,representation),rows in sorted(groups.items()):
 item=dict(generator=generator,order=order,representation=representation,n=len(rows),seeds=sorted(r['task']['seed'] for r in rows),
  metrics={key:describe([r['scores'][key]['bits_per_target'] for r in rows]) for key in ('base','last','first')},
  last_minus_first=describe([r['last_minus_first_bits'] for r in rows]),
  conditional_permutation=dict(joint_changed_fraction=describe([r['permutation']['joint_actual_changed_fraction'] for r in rows]),
   movable_fraction=describe([r['permutation']['non_singleton_target_fraction'] for r in rows])),
  unknown_units_test=describe([r['unknown_units']['test'] for r in rows]))
 for key in ('last','first'):
  item['metrics'][key]['gain']=describe([r['scores'][key]['bits_saved'] for r in rows])
  item['metrics'][key]['zero_weight_count']=sum(r['selected']['features'][key]['weight']==0 for r in rows)
  item['metrics'][key]['positive_test_gain_count']=sum(r['scores'][key]['bits_saved']>0 for r in rows)
  item['metrics'][key]['holm_below_05_count']=sum(r['permutation']['tests'][key]['holm_p']<.05 for r in rows)
  item['metrics'][key]['selected_weights']=dict(Counter(str(r['selected']['features'][key]['weight']) for r in rows))
 summary.append(item)
paired=[]
for generator in ('naibbe_strict','timm'):
 for representation in ('eva','merged'):
  lookup={(r['task']['seed'],r['task']['order']):r for r in groups[(generator,'original',representation)]+groups[(generator,'shuffled',representation)]}
  paired.append(dict(generator=generator,representation=representation,
   original_minus_shuffled={feature:describe([lookup[(seed,'original')]['scores'][feature]['bits_saved']-lookup[(seed,'shuffled')]['scores'][feature]['bits_saved'] for seed in range(19,39)]) for feature in ('last','first')}))
caveats=[
 '所有数值均为每个目标首单位的条件预测分数，已知前词与目标词长度，不是完整词概率。',
 '每次仅1665个训练、830个开发、830个测试词对；同预算重训与开发选择可能把弱信号权重压到0。Latin原顺序也未检出正优势，显示该设置的灵敏度限制。',
 '20个Naibbe种子使用同一底层拉丁段落；不同编码分段使字符边界略变。种子范围及百分位是模拟分布，不是20篇独立语义文本或手稿置信区间。',
 '每个split被重排为12词人工行，弃4/8/8尾词；原行换行与段落几何未保留。不能与手稿原生页面上的叶均值作等量实验比较。',
 '整词打乱在split内先执行再弃尾，因而原顺序与打乱条件省略的词略不同；全部原始位置已逐run披露。',
 'Naibbe采用我们预先声明的严格唯一解适配，Timm采用f1r种子后走A分支；两者均含作者基于全手稿设计的外部先验，不构成独立留出验证。',
 '各run的两特征Holm只控制该run内比较，不控制181次运行的全家族；零权重使观测与排列增益均为0、p=1，这是选择结果，不是证明独立。',
 'Timm无提供的逐词明文；已知机制可产生部分跨词关联。Naibbe可还原明文但本指标较弱；边界信号不能直接识别语义。',
 '本阶段未加载或评分任何手稿转写、确认集或保留集。']
obj=dict(schema_version=1,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='completed',
 question='固定跨词条件预测器对有明文密码、无提供明文生成器及自然文本的灵敏度如何？',
 task_count=181,groups=summary,paired_original_minus_shuffled=paired,caveats=caveats,
 protocol_receipt_sha256=sha(HERE/'protocol_receipt.json'),execution_receipt_sha256=sha(HERE/'execution_receipt.json'))
dump('summary.json',obj)
flat=[]
for r in runs:
 item=dict(r['task']);item.update(base_bits=r['scores']['base']['bits_per_target'],last_gain=r['scores']['last']['bits_saved'],first_gain=r['scores']['first']['bits_saved'],last_minus_first=r['last_minus_first_bits'],base_alpha=r['selected']['base_alpha'])
 for key in ('last','first'):
  item.update({key+'_alpha':r['selected']['features'][key]['alpha'],key+'_weight':r['selected']['features'][key]['weight'],key+'_p':r['permutation']['tests'][key]['raw_p'],key+'_holm_p':r['permutation']['tests'][key]['holm_p'],key+'_changed_fraction':r['permutation']['tests'][key]['actual_context_changed_fraction']})
 item['joint_changed_fraction']=r['permutation']['joint_actual_changed_fraction'];flat.append(item)
with (HERE/'all_runs.csv').open('w',newline='') as f:
 writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
dump('website_data.json',dict(obj,all_runs=flat,figure='跨词预测校准.svg'))

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(2,3,figsize=(13.5,8),sharey=True)
colors={'original':'#176b6f','shuffled':'#bc7633'}
for ri,representation in enumerate(('eva','merged')):
 generators=['naibbe_strict','timm']+(['latin'] if representation=='eva' else [])
 for ci,metric in enumerate(('last','first','difference')):
  ax=axes[ri,ci];ax.axhline(0,color='#64748b',linewidth=.8)
  for gi,generator in enumerate(generators):
   for oi,order in enumerate(('original','shuffled')):
    rows=groups[(generator,order,representation)]
    values=[r['last_minus_first_bits'] if metric=='difference' else r['scores'][metric]['bits_saved'] for r in rows]
    center=gi+(-.15 if oi==0 else .15)
    jitter=np.linspace(-.08,.08,len(rows))
    ax.scatter(center+jitter,values,s=22,alpha=.72,color=colors[order],edgecolor='white',linewidth=.35,label=order if gi==0 else None)
    ax.plot([center-.1,center+.1],[np.median(values)]*2,color=colors[order],linewidth=2.5)
  ax.set_xticks(range(len(generators)),[{'naibbe_strict':'Strict Naibbe','timm':'Timm f1r/A','latin':'Latin (1 original)'}[g] for g in generators])
  ax.set_title(('Basic EVA' if ri==0 else 'Merged units')+' · '+{'last':'Previous last → next first','first':'Previous first → next first','difference':'Last gain − first gain'}[metric],fontsize=10)
  ax.grid(axis='y',alpha=.16);ax.set_ylim(-.05,.05)
  if ci==0:ax.set_ylabel('Test bits saved per target')
  if ri==0 and ci==0:ax.legend(frameon=False,fontsize=9,loc='upper left')
fig.suptitle('Boundary predictor calibration: all frozen control runs',fontsize=17,x=.06,ha='left',y=.98)
fig.text(.06,.935,'1665 train / 830 dev / 830 test pairs per fit · Same tuning budget · Both word lengths are known',fontsize=11,color='#475569')
fig.text(.06,.035,'Dots: encoder/permutation seeds (shared underlying Latin); bars: medians. Simulation spread is not a manuscript confidence interval.\n12-token artificial lines, independent train/dev/test reflow. No manuscript test scores are plotted.',fontsize=10,color='#475569')
fig.subplots_adjust(top=.86,bottom=.14,hspace=.30,wspace=.12,left=.07,right=.98)
fig.savefig(HERE/'跨词预测校准.png',dpi=170);fig.savefig(HERE/'跨词预测校准.svg');plt.close(fig)

lines=['跨词首单位预测：生成器校准报告','',
 '结果：相同冻结预测器在Timm生成序列中检出少量跨词优势，在严格Naibbe和这段Latin上通常选择零权重。我们不能据此把手稿归为语言、密码或无语义生成物。',
 '本轮共181个拟合，全部完成并保留逐run结果、开发网格、选定参数与1999次条件排列数组。',
 '', '主结果（基本EVA；单位：bits/目标首单位）：',
 '机制 / 顺序 | 次数 | 末→首中位数 [最小,最大] | 首→首中位数 | 末→首零权重数 | run内Holm<.05次数']
for item in summary:
 if item['representation']!='eva':continue
 m=item['metrics'];g=m['last']['gain'];f=m['first']['gain']
 lines.append(f"{item['generator']} / {item['order']} | {item['n']} | {g['median']:.6f} [{g['min']:.6f},{g['max']:.6f}] | {f['median']:.6f} | {m['last']['zero_weight_count']} | {m['last']['holm_below_05_count']}")
lines+=['','敏感性：merged下Timm原顺序末→首中位数0.008627，范围[-0.011971,0.028173]；全部seed及首→首、二者差值见summary.json与all_runs.csv。','',
 '设计：先取每个序列前8000词，顺序拆为4000/2000/2000；split内独立12词排版，弃4/8/8尾词。仅选内部非重叠词对，目标数1665/830/830。训练字母表、UNK及条件上下文与根boundary.py相同，alpha×混合权重网格完全复用。每个原顺序/打乱条件独立重新训练，开发配置先落盘后测试。',
 'Naibbe明文核查：各seed对应truth片段连接与既有normalized Latin前缀一致；每次train/dev/test对应连续且不重叠字符范围。未把相同底层Latin的20次编码当作独立文本。',
 '排列检验：每个测试人工页内，按两词精确长度、相对位置桶、段落标志重新分配前词首末特征，二者成对保留。所有模型均执行1999次。changed fraction与可移动比例逐run记录。',
 '', '解释与限制：']
lines += [f'{i+1}. {value}' for i,value in enumerate(caveats)]
lines += ['', '验证：根合成依赖toy检出2.00098 bits，独立toy选择0；概率归一、24种排列穷举、未知字形映射、非重叠词对、配置先冻结、源校验、全部181组与排列p复算已通过。没有对一个人工页做假bootstrap。',
 '产物：summary.json、all_runs.csv、website_data.json、跨词预测校准.png/.svg、runs/*.json、configs/*.json、results/*_nulls.npz。',
 '复现：在保留仓库目录层次及父生成器数据后运行 python3 calibrate.py --workers 2，再运行 python3 summarize.py。依赖NumPy/Matplotlib和已固定的corpus.py、study20/analyze.py及Latin XML。',
 '许可证：本目录的Latin衍生统计和上游语料应随父目录THIRD_PARTY_NOTICES.txt保留Perseus/Tufts署名与CC BY-SA 4.0要求；Naibbe/Timm上游MIT及附加论文引用说明均在父目录。没有发布现代论文PDF。']
(HERE/'研究报告.txt').write_text('\n'.join(lines)+'\n')
checks=dict(completed_utc=obj['completed_utc'],runs=181,all_expected_tasks=True,all_frozen_configs_precede_test_scoring=True,
 all_config_hashes_checked=True,all_permutation_hashes_checked=True,all_p_values_recomputed=True,
 all_target_and_discard_counts_checked=True,unknown_test_unit_max=max(r['unknown_units']['test'] for r in runs),
 source_receipt_sha256=obj['protocol_receipt_sha256'],no_manuscript_input=True)
dump('audit.json',checks)
files=[p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.name not in ('artifact_manifest.json','run.log')]
dump('artifact_manifest.json',dict(files=[dict(path=str(p.relative_to(HERE)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)]))
print(json.dumps({'runs':len(runs),'groups':len(summary),'paired':paired,'audit':checks},ensure_ascii=False,indent=2))
