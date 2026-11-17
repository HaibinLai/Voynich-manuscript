from pathlib import Path
import datetime,hashlib,json
import numpy as np
P=Path(__file__).resolve().parent

def describe(values):
 a=np.asarray(values,dtype=float);return dict(n=len(a),median=float(np.median(a)),mean=float(a.mean()),min=float(a.min()),max=float(a.max()),simulation_percentiles95=np.quantile(a,[.025,.975]).tolist())
allrows=[];groups=[];lookup={}
for rep in ('eva','merged'):
 for config in (0,28,100):
  rows=[json.loads((P/'runs'/f'p{config}_s{s}_{rep}.json').read_text()) for s in range(19,39)]
  for r in rows:lookup[(config,r['task']['seed'],rep)]=r
  metrics={}
  for key in ('exact','coarse'):
   result=[r['results'][key] for r in rows]
   metrics[key]={field:describe([r[field] for r in result]) for field in ('alignment_specificity_D','observed_V_gain','null_mean','source_identity_moved_mean','singleton_slot_fraction','target_multiset_changed_mean_all_targets','target_multiset_changed_mean_given_V','target_assignment_changed_mean_all_targets','movable_slot_fraction')}
   metrics[key]['positive_D_seeds']=sum(r['alignment_specificity_D']>0 for r in result)
   metrics[key]['reference_p_le_05_count']=sum(r['monte_carlo_reference_p']<=.05 for r in result)
  events={field:describe([r['test_source_events'][field] for r in rows]) for field in ('all_source_choice_calls','localy_fraction')}
  events['conditional']={kind:{field:describe([r['test_source_events']['conditional'][kind][field] for r in rows]) for field in ('calls','alignment_branch_fraction','position_equal_calc_fraction')} for kind in ('line_initial','non_initial')}
  groups.append(dict(config=config,representation=rep,metrics=metrics,events=events,actual_branch_probability_given_LOCALY=rows[0]['actual_branch_probability_given_LOCALY'],test_words=describe([r['test_words'] for r in rows]),test_vocabulary=describe([r['test_vocabulary'] for r in rows]),test_mean_unit_length=describe([r['test_mean_unit_length'] for r in rows])))
  allrows.extend(dict(config=config,seed=r['task']['seed'],representation=rep,exact=r['results']['exact'],coarse=r['results']['coarse'],test_words=r['test_words'],test_vocabulary=r['test_vocabulary'],test_mean_unit_length=r['test_mean_unit_length'],actual_LOCALY_fraction=r['test_source_events']['localy_fraction']) for r in rows)
endpoints=[]
for rep in ('eva','merged'):
 for kind in ('exact','coarse'):
  diff=[lookup[(100,s,rep)]['results'][kind]['alignment_specificity_D']-lookup[(0,s,rep)]['results'][kind]['alignment_specificity_D'] for s in range(19,39)]
  endpoints.append(dict(representation=rep,stratum=kind,config100_minus0=describe(diff),positive_seeds=sum(x>0 for x in diff)))
obj=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='calibration_completed_before_manuscript_review',conditions=120,groups=groups,endpoint_contrasts=endpoints,all_runs=allrows,
 interpretation='A fixed observer responds to stronger author alignment parameters in these synthetic controls. Config 0 is not off. Seed-matched output is not tokenwise counterfactual; length/vocabulary/local-source rates also vary. No manuscript claim follows.',
 source_channel_only=True,manuscript_confirm_scored=False,reserve_used=False,
 scalar_max_error=max(r['results'][kind]['scalar_max_log2_error'] for r in lookup.values() for kind in ('exact','coarse')))
(P/'calibration_summary.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
lines=['上一行位置特异性：生成器校准（手稿新评分前）','',
 '全部120条件/单位表示、精确/粗桶各399次扰动已完成；手稿confirm尚未开始本阶段评分。','',
 'D定义为原V来源收益减去仅置换V来源词身份后的平均收益。H通道、目标、版面和当前模型固定。','',
 '配置 / 单位 | 精确长度D中位 | 粗桶D中位 | 测试平均词长中位 | 测试词型数中位 | 实际LOCALY比例中位']
for g in groups:
 lines.append(f"{g['config']} / {g['representation']} | {g['metrics']['exact']['alignment_specificity_D']['median']:.6f} | {g['metrics']['coarse']['alignment_specificity_D']['median']:.6f} | {g['test_mean_unit_length']['median']:.3f} | {g['test_vocabulary']['median']:.0f} | {g['events']['localy_fraction']['median']:.3f}")
lines+=['','0→100端点对比：']
for e in endpoints:lines.append(f"{e['representation']} / {e['stratum']}: D100−D0中位{e['config100_minus0']['median']:.6f}，{e['positive_seeds']}/20种子为正。")
lines+=['','解释：更强作者参数在这组生成对照中产生更强位置身份信号，说明本观察器对此干预有实测响应。参数28效应较小，精确桶未在所有seed给出正D；负值与参考p均完整保留。',
 '参数0并非完全关闭：LOCALY中普通词实际条件分支概率1%/29%/100%，行首11%/15%/51%；其他mode不受该参数直接控制。所有60份无RNG副作用事件日志均逐词验证输出未变。实际调用频率与随机偶然选中同位置分别报告。',
 '精确桶实际来源身份移动率中位约47%（EVA）/50%（merged），粗桶约72%/74%；候选多重集变化率与单例层比例在JSON逐run披露。','随机轨迹、测试词长和词型分布也随干预变化，同seed不能解释为保持其他词不变的逐token反事实。分布是模拟seed变化范围，不是手稿置信区间；本结果不识别语言或历史机制。',
 '阶段门：等待root审阅该校准，再执行三表示confirm的1999次探索复核；reserve不动。']
(P/'生成器位置校准报告.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps(dict(groups=[dict(config=g['config'],rep=g['representation'],D=g['metrics']['exact']['alignment_specificity_D']['median'],length=g['test_mean_unit_length']['median'],vocab=g['test_vocabulary']['median'],LOCALY=g['events']['localy_fraction']['median']) for g in groups],endpoints=endpoints),ensure_ascii=False,indent=2))
