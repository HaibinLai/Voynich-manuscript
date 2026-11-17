"""Report all prespecified copy-prediction comparisons and calibration limits."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
P=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def dump(name,value):(P/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
names=['ZL_EVA','ZL_merged','IT_EVA'];runs=[json.loads((P/'runs'/f'{n}.json').read_text()) for n in names]
calibration=json.loads((P/'calibration_summary.json').read_text());verification=json.loads((P/'replay_verification.json').read_text());assert verification['all_passed']
comparisons=[('base__minus__edit_HV','Copy+edit vs style baseline'),('exact_HV_matched__minus__edit_HV','Copy+edit vs matched exact'),('edit_H_matched__minus__edit_HV','Add previous-line sources')]
rows=[]
for r in runs:
 for key,label in comparisons:
  c=r['contrasts'][key]
  rows.append(dict(representation=r['name'],comparison=key,label=label,mean_leaf_bits_saved=c['mean_leaf_bits_saved'],ci95=c['bootstrap95'],ci98_333=c['bootstrap_98_333'],leaves=c['leaves']))
limitations=[
 '这是已看过阶段一及边界结果后冻结的数据驱动后续；confirm已用于其他研究，不能称全项目从未见过的测试。reserve未被请求、拟合或评分。',
 '完整词概率已包含词尾EOS、非空条件化和训练外单位身份成本；其条件包含已知书手、段首位置和行槽位几何，不是无侧信息的整页压缩。',
 '横坐标是token槽位相对位置；没有用真实像素坐标。上一行来源严格限于同页、同块、已知同段，遇缺失与未知源按协议处理。',
 '模型只允许精确复制或一次单位插入、删除、替换。Timm作者实际也使用更早的页内行、多单位变化、合并/拆分与建议词；这里不是作者生成器的真实似然。',
 'Timm校准的20个种子是相同作者配置与种子短句下的随机输出；其范围不是手稿置信区间，预定响应门槛也不是已验证的语义分类器。',
 '主matched-context比较刻意固定HV的dev选定窗口；独立dev选择的H与exact-HV最优也预定报告，本次三种转写恰好与matched配置一致。',
 '98.333%区间是每表示三个预定主差的保守Bonferroni呈现；不是跨所有历史研究和全部敏感性的统一错误率保证。',
 'ZL基本EVA总增益很小；IT敏感性区间跨零，单编辑相对精确复制的优势也未稳定。不能据此认定复制生成、原文语言、语法或含义。']
summary=dict(schema_version=1,status='completed',completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
 title='完整词复制与单编辑预测',main_result='归一化复制近似在ZL上带来较小预测增益；竖向和编辑贡献对转写/比较方式敏感，尚不能确定历史生成机制。',
 main_source='ZL/EVA',calibration=calibration,manuscript=[dict(name=r['name'],tokens=r['test_tokens'],pages=r['results']['base']['pages'],leaves=r['contrasts'][comparisons[0][0]]['leaves'],
  baseline_bits_per_word=r['results']['base']['bits_per_word'],baseline_weights=r['baseline_weights'],selected=r['selected'],comparisons=r['contrasts'],source_availability=r['source_availability'],unknown_units=r['unknown_units'],escape_bits_total=r['escape_bits_total']) for r in runs],
 primary_table=rows,limitations=limitations,verification=verification,baseline_refit_audit=json.loads((P/'baseline_refit_audit.json').read_text()),figure='完整词复制预测.svg',reserve_used=False)
dump('website_data.json',summary);dump('public_summary.json',summary);dump('summary.json',{k:v for k,v in summary.items() if k!='calibration'})

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig=plt.figure(figsize=(14,8));gs=fig.add_gridspec(2,2,width_ratios=[1.55,1],hspace=.4,wspace=.30)
ax=fig.add_subplot(gs[:,0]);colors=['#176b6f','#5b69a3','#ba7541']
for ci,(key,label) in enumerate(comparisons):
 for ri,r in enumerate(runs):
  c=r['contrasts'][key];mean=c['mean_leaf_bits_saved'];lo,hi=c['bootstrap_98_333'];y=(2-ci)*4+(2-ri)*.65
  ax.errorbar(mean,y,xerr=[[mean-lo],[hi-mean]],fmt='o',markersize=6,color=colors[ri],capsize=3,label=r['name'].replace('_',' / ') if ci==0 else None)
  ax.text(.071,y,f'{mean:+.4f}',va='center',fontsize=9,color=colors[ri])
ax.set_yticks([8.65,4.65,.65],[x[1] for x in comparisons]);ax.axvline(0,color='#64748b',linewidth=1);ax.grid(axis='x',alpha=.15)
ax.set_xlim(-.015,.09);ax.set_ylim(-.9,11.7);ax.set_xlabel('Mean leaf bits saved per complete word')
ax.set_title('Manuscript confirm: 28 pages, 13 leaf groups',loc='left',fontsize=12);ax.legend(frameon=False,fontsize=9,loc='upper right')
ax.text(.0,-.16,'Whiskers: 98.333% leaf-bootstrap intervals for three prespecified\ncomparisons per representation. Positive = lower prediction cost.',transform=ax.transAxes,fontsize=9,color='#475569')
for ri,rep in enumerate(('eva','merged')):
 a=fig.add_subplot(gs[ri,1]);records=[r for r in calibration['all_runs'] if r['representation']==rep]
 for gi,(metric,label) in enumerate([('gain','Total gain'),('vertical_gain','Add previous line')]):
  for oi,order in enumerate(('original','shuffled')):
   values=[r[metric] for r in records if r['order']==order];x=gi+(-.15 if oi==0 else .15)
   color='#176b6f' if oi==0 else '#bc7633'
   a.scatter(x+np.linspace(-.075,.075,len(values)),values,s=19,color=color,alpha=.75,label=order if gi==0 else None)
   a.plot([x-.1,x+.1],[np.median(values)]*2,color=color,linewidth=2.5)
 a.set_xticks([0,1],['Total gain','Add previous line']);a.axhline(0,color='#64748b',linewidth=.8);a.grid(axis='y',alpha=.15);a.set_ylabel('Bits saved / word')
 a.set_title('Timm native layout · '+('EVA' if rep=='eva' else 'merged'),loc='left',fontsize=12)
 if ri==0:a.legend(frameon=False,fontsize=9)
fig.suptitle('Copying as a bounded predictive model',x=.035,ha='left',fontsize=18,y=.98)
fig.text(.035,.932,'Past words only · Nonempty full-word probabilities · EOS + finite-universe escape · Frozen development choices',fontsize=11,color='#475569')
fig.text(.035,.035,'Calibration: 20 seeds per order and representation, each independently refitted. Native generator paragraph markers were logged without changing output.\nThe model detects these Timm controls; manuscript gains are small and transcription-sensitive. Neither result deciphers meaning.',fontsize=9,color='#475569')
fig.subplots_adjust(left=.22,right=.96,top=.86,bottom=.19)
fig.savefig(P/'完整词复制预测.png',dpi=175);fig.savefig(P/'完整词复制预测.svg');plt.close(fig)

lines=['完整词复制与单编辑预测：冻结实验报告','',summary['main_result'],
 '所有三表示先在train+legacy拟合、dev选参并保存配置，再一次读取confirm评分。主ZL/EVA：5025个明确词、28页、13个叶组。保留集未被请求或评分。','',
 '主比较（单位：bits/完整词，叶等权；括号为95%区间，其后为三个主差的保守98.333%区间）：']
for r in runs:
 lines.append(r['name'])
 for key,label in comparisons:
  c=r['contrasts'][key];lo,hi=c['bootstrap95'];bl,bh=c['bootstrap_98_333']
  lines.append(f"  {label}: {c['mean_leaf_bits_saved']:+.6f} ({lo:+.6f}, {hi:+.6f}); 保守 [{bl:+.6f}, {bh:+.6f}]")
lines+=['','如何理解：',
 '主ZL/EVA总增益约0.0258 bits/词，保守区间刚高于零；IT总增益约0.0120，区间跨零。单编辑相对精确复制在ZL为正但区间跨零，在IT略负。增加上一行来源在ZL的普通95%区间为正，较保守区间跨零。因此只能支持一个较弱、转写敏感的预测改进，不能确定实际书写机制。',
 '三表示均在dev选择横向最近8词、上一行中心±1槽、identity占编辑核0.75、复制混合权重0.025；基线的书手和位置模型各0.5。独立dev最优H/exact敏感性恰与matched选择一致。','',
 'Timm检测能力校准：']
for g in calibration['groups']:
 m=g['metrics'];base=m['base__minus__edit_HV'];vertical=m['edit_H_matched__minus__edit_HV'];edit=m['exact_HV_matched__minus__edit_HV']
 lines.append(f"  {g['representation']}: 原顺序总gain中位{base['original']['median']:.6f}、打乱{base['shuffled']['median']:.6f}；原−打乱配对{base['positive_paired_seeds']}/20为正。新增竖向中位{vertical['original']['median']:.6f}，edit-over-exact中位{edit['original']['median']:.6f}。")
lines += ['采用作者真实55字符上限行、29行页及直接记录的段首/段尾状态，40页按20/10/10拆分。去除复制种子行；每split全词打乱保留布局，所有条件重训。加入只读日志后的20个种子输出逐字复现。此观察器确实响应这些生成配置，但门槛不是经验证的分类器。','',
 '每个原/打乱条件均重新构建global/hand/position训练模型，并独立搜索相同15点基线混合网格。40个配对输入顺序不同、词数相同；其中25对最终选择的style混合权重不同。全局词内计数可能因词多重集不变而相同，这是统计性质而不是复用拟合结果。','',
 '概率与完整成本：',
 '基线为含EOS的四元CharLM（alpha=100），每个global/hand/position模型先除以非空质量，再做凸组合。复制核为identity+单次删/插/替；所有产生同一词的路径概率相加，单字删空后显式条件化。空来源回退基线，不删掉难预测目标。',
 'EVA固定语法宇宙1027类；merged1033类。训练外单位先进入UNK类，再在未见合法单位中均匀展开，逐次计入log2 M身份成本。ZL两表示各7个escape单位，共69.3061 bits；IT无escape。核与基线因此均覆盖完整非空显式单位串，不是免费UNK。','',
 '限制与公开边界：']
lines += [f'{i+1}. {x}' for i,x in enumerate(limitations)]
lines += ['', '核验：',
 '小字母表核概率和、重复路径、单字删空、非空LM尾部剩余质量、有限escape展开均通过；未来词/目标候选内容不会改变来源集合。已知竖向复制toy有6.28 bits增益，独立toy约0.015 bits。',
 '独立复算仅重建训练计数并读取已保存的confirm目标/来源文件，不重新读取confirm或选参；逐编辑路径与标量概率累加，三表示所有9模型与原结果最大差不超过1.43e-14 bits。超过10万条来源引用核对为同页合法过去且词形一致。',
 '共享转写解析器读取公共转写文件后按split返回页面；本模型入口从不请求或返回reserve，也未在reserve上计算指标。',
 '文件：protocol.txt/receipt、execution_receipt、layout_verification、verification、replay_verification、calibration_summary、configs、targets、scores、runs均可核查。图与website_data.json可直接用于研究网站。',
 '公开审计数据压缩：targets原JSON约401MB，仅发布确定性gzip和原/压缩双重校验表。原件本地保留；公开包先运行python3 restore_target_archives.py恢复，再运行python3 replay.py独立审计。完整新实验应在同父目录下的全新输出目录复制脚本、协议和校准输入后运行；run.py故意拒绝覆盖已有confirm评分标记。',
 '来源许可：Timm代码MIT及作者声明由父generator_controls/third_party保留；ZL/IT公开转写按voynich.nu CC0说明署名。现代论文PDF和EVA字体均未包含在此交付。']
(P/'研究报告.txt').write_text('\n'.join(lines)+'\n')
checks=[]
for path in sorted((P/'runs').glob('*.json')):
 r=json.loads(path.read_text())
 for field,hfield in [('config_path','config_sha256'),('scores_path','scores_sha256'),('targets_path','targets_sha256')]:assert sha(P/r[field])==r[hfield]
 assert r['config_frozen_utc']<r['test_scoring_started_utc']
 checks.append(path.name)
audit=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),runs_checked=len(checks),
 expected_runs=85,all_config_score_target_hashes_valid=True,all_configs_precede_test_scoring=True,
 native_layout_verified=True,scalar_replay_passed=True,reserve_used=False)
assert len(checks)==85
dump('audit.json',audit)
files=[p for p in P.rglob('*') if p.is_file() and not any(part in ('build','__pycache__') for part in p.relative_to(P).parts) and not p.name.endswith('.log') and p.name not in ('artifact_manifest.json','protocol_draft.txt')]
dump('artifact_manifest.json',dict(files=[dict(path=str(p.relative_to(P)),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(files)]))
print(json.dumps(audit,ensure_ascii=False))
