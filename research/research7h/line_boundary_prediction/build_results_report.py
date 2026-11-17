# -*- coding: utf-8 -*-
"""Render archived cross-line outputs only; do not fit or rescore any model."""
from pathlib import Path
import datetime,gzip,hashlib,json,re
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE=Path(__file__).resolve().parent;RUN=HERE/'run_v1'
NAMES=('ZL_EVA','ZL_merged','IT_EVA')
def read(p):
    b=p.read_bytes();return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,obj):(HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def leaf_key(value):
    m=re.match(r'f(\d+)',value);return (int(m[1]) if m else 10000,value)


def main():
    summary=read(RUN/'summary.json');complete=read(RUN/'complete.json');audit=read(HERE/'independent_audit/audit_report.json')
    assert summary['complete'] and complete['all_three_complete'] and audit['all_passed']
    assert sha(RUN/'summary.json')==complete['summary_sha256']==audit['original_summary_sha256']
    rows={r['name']:r for r in summary['representations']};assert set(rows)==set(NAMES)
    configs={};supports={}
    for name in NAMES:
        c=read(RUN/'configs'/f'{name}.json')
        configs[name]=dict(selected={k:c[k] for k in ('base_alpha','alpha','weight','char_order','char_alpha')},
            alphabet_size=len(c['alphabet']),omega_size=c['omega_size'],escape_size=c['escape_size'],train_words=c['train_words'],
            train_pair_counts=c['train_pair_counts'],fold_sizes=[dict(fold=x['fold'],fit_rows=x['fit_rows'],held_rows=x['held_rows']) for x in c['folds']],
            full_config_path=f'run_v1/configs/{name}.json',sha256=sha(RUN/'configs'/f'{name}.json'))
        raw=read(RUN/f'{name}_support.json.gz');supports[name]={}
        for model,value in raw.items():
            clean={k:v for k,v in value.items() if k!='rows'}
            zero=sum(r['final_level_unseen'] for r in value['rows'])
            clean.update(targets=len(value['rows']),final_level_zero_count=zero,final_level_zero_fraction=zero/len(value['rows']))
            supports[name][model]=clean
    leaves=sorted(set().union(*(rows[n]['gain']['per_leaf'] for n in NAMES)),key=leaf_key)
    assert len(leaves)==17
    leaf_table=[dict(leaf=l,representations={n:dict(targets=rows[n]['targets_by_leaf'].get(l,0),
        mean_gain=rows[n]['gain']['per_leaf'].get(l),leave_one_leaf_out_mean=rows[n]['gain']['leave_one_leaf_out'].get(l)) for n in NAMES}) for l in leaves]
    page_table=[]
    for n in NAMES:
        for p,count in sorted(rows[n]['targets_by_page'].items(),key=lambda item:leaf_key(item[0])):
            page_table.append(dict(representation=n,folio=p,targets=count,base_bits=rows[n]['base_cost']['per_page'][p],
                model_bits=rows[n]['model_cost']['per_page'][p],gain=rows[n]['gain']['per_page'][p]))
    write('leaf_table.json',leaf_table);write('page_table.json',page_table)
    chronology=dict(design_review_recorded_utc=read(HERE/'pre_run_review.json')['review_recorded_utc'],
        primary_reserve_started_utc='2026-11-17T14:49:34.615254+00:00',design_frozen_utc=read(HERE/'freeze.json')['created_utc'],
        primary_summary_completed_utc='2026-11-17T14:49:50.245069+00:00',
        interpretation='Freeze occurred after primary reserve scoring began but before its summary, and the designer had not read reserve values. This is not a pre-reserve-start freeze claim.',
        execution_gate_sha256=sha(HERE/'gate.json'))
    limitations=[
        '开发集已经用于其他模型；41个转写页面/17叶组来自同一本手稿，不是新增独立复现。f85/f86按预定规则合为f85_86一组，17叶组不等于17张物理叶。',
        '仅同已知段/块的解析相邻行末→次行首；未逐对以原图认证阅读顺序，也未比较行内/跨行差值。',
        '三个等叶组平均增益均小幅为正，但17叶组内有正有负；预定留一叶组范围均跨零。留一叶组范围不是置信区间。',
        '所有17叶组按固定手稿编号顺序报告；f90的预定留一叶组结果为负不是坏数据判据，不据此删组或增加剔除实验。',
        '增益是两个近似预测器的完整词成本差，不是互信息、语法、译文或历史生成机制。四符号合成校准不保证实际字母表的检测能力。',
        '三个表示的单位和目标可不同且来源相关，不按绝对成本挑最好表示；不新增p、CI或显著性门槛。']
    payload=dict(schema_version=1,status='completed',scope='crossline_trainlegacy_dev_only',summary=summary,
        configs=configs,support=supports,leaf_order=leaves,leaf_table=leaf_table,page_table=page_table,
        complete=dict(path='run_v1/complete.json',sha256=sha(RUN/'complete.json'),cpu_seconds=complete['cpu_seconds']),
        audit=dict(path='independent_audit/audit_report.json',sha256=sha(HERE/'independent_audit/audit_report.json'),all_passed=True,
                   candidate_grid_points=audit['candidate_grid_points'],targets=sum(r['targets'] for r in audit['representations'])),
        protocol=dict(path='protocol.txt',sha256=sha(HERE/'protocol.txt')),
        assets=dict(report='研究报告.txt',png='crossline_results.png',svg='crossline_results.svg',protocol='protocol.txt'),
        chronology=chronology,limitations=limitations,design_manifest_sha256=sha(HERE/'artifact_manifest.json'),
        reporting_only_from_saved_outputs=True,new_parameters_or_scores_generated_by_report=False)
    write('website_data.json',payload)
    lines=['跨行完整词预测：第四阶段探索性结果','',
      '一次执行全部三表示，CPU %.6f秒；没有改动冻结代码、数据范围或选择预算。另一代理逐标量复核全部90个CV网格点、1950个目标、所有支持/成本/页叶/留一叶输出，全部通过。'%complete['cpu_seconds'],
      '固定比较：已知段落/版面块内前行末词的末单位，是否改善次行首完整词预测。基线与候选均只从相同跨行train+legacy目标学习；每折字母表仅用拟合叶，所有参数在训练内部3折选择，dev不补字母表。',
      '这不是旧行内模型迁移，也不检验行内与跨行效应差。以下dev在其他模型中已用，不能称新盲测试。','',
      '完整成本与收益（单位bits/目标；等叶组为页内均→组内页面等均→叶组等均；f85/f86预定合为f85_86一组）：',
      '表示 | targets / pages / leaf groups | base | candidate | mean-leaf-group gain | pooled gain | leave-one-leaf-group-out range (NOT CI)']
    for n in NAMES:
        r=rows[n];lo,hi=r['gain']['leave_one_leaf_out_range']
        lines.append('%s | %d/%d/%d | %.9f | %.9f | %+.9f | %+.9f | [%+.9f,%+.9f]'%(n,r['targets'],r['eligible_pages'],r['eligible_leaves'],r['base_cost']['mean_leaf'],r['model_cost']['mean_leaf'],r['gain']['mean_leaf'],r['gain']['pooled'],lo,hi))
    lines+=['三个平均增益都小幅为正，但预定留一叶组范围均跨零。所有留一叶组值已保存，不能把该范围称作CI或据此新增显著性判断。','','全部17叶组（固定编号顺序；targets按ZL/EVA、ZL/merged、IT/EVA；增益同顺序）：']
    for row in leaf_table:
        ns=[row['representations'][n]['targets'] for n in NAMES]
        gs=[row['representations'][n]['mean_gain'] for n in NAMES]
        lines.append('%s | %s | %s'%(row['leaf'],'/'.join(map(str,ns)),' / '.join('%+.8f'%v for v in gs)))
    lines+=['各转写页面目标分母和成本见page_table.json及完整summary；41个转写页面/17叶组不是新增独立手稿样本，也不等于17张实际物理叶。',
      '预定逐叶组留一中，去掉f90时三表示平均增益均为负。这只说明当前平均值对该组敏感，不说明f90是坏数据；未删除任何组、改变权重或新增剔除分析。','','选参、筛选、稀疏支持与未知费：']
    for n in NAMES:
        r=rows[n];c=configs[n];t=r['target_counts'];s=supports[n]
        lines.append('%s：选择base alpha=%s、candidate alpha=%s、weight=%s；训练词%d，alphabet/Ω=%d/%d。'%(n,c['selected']['base_alpha'],c['selected']['alpha'],c['selected']['weight'],c['train_words'],c['alphabet_size'],c['omega_size']))
        lines.append('  候选相邻行%d→合格%d；段/块界%d、段落未知%d、缺失端点%d；跨H=%d。文件行号连续%d仅作计数，未另评分。'%(t['candidate_adjacent_parsed_rows'],r['targets'],t.get('paragraph_or_block_boundary',0),t.get('unknown_paragraph',0),t.get('missing_endpoint',0),t['cross_hand_pairs'],t['source_file_adjacent_only']))
        lines.append('  最深层零训练计数：base %d/%d，candidate %d/%d；确切逐层计数和回退深度在保存support文件。'%(s['base']['final_level_zero_count'],r['targets'],s['augmented']['final_level_zero_count'],r['targets']))
        lines.append('  来源未知单位%d（其中末单位UNK词对%d）；目标未知单位%d，总目标escape %.6f，首目标escape %.6f。'%(r['source_unknown_units'],r['source_unknown_endpoint_pairs'],r['target_unknown_units'],r['target_escape_bits'],r['first_target_escape_bits']))
    lines+=['首class成本与实际首单位成本已分列，完整费用=first_class+mapped continuation+target_escape；亦等于first_actual+mapped continuation+target_escape−first_target_escape。EOS和所有未知目标身份费均已计，首身份费没有重复加。来源词是已知条件，不把来源身份费算到目标。',
      '本次目标未知费为0，但这不允许删掉模型的未知编码规则；人工例及独立复算已经核对该规则。零计数层回退不等于有足够估计精度。','','时间与复核范围：',
      '设计审阅记录14:48:26.438108 UTC；设计freeze14:49:40.969793，在主reserve启动14:49:34.615254之后、主摘要14:49:50.245069之前，设计者当时未读reserve数值。不能写成reserve开跑前冻结。',
      '第三阶段完成后新goal和gate才允许本次执行；本次未重新加载confirm/reserve。报告只读取已保存输出，未再拟合/选参。',
      '独立审核最大逐目标成本差1.4211e-14 bits、CV网格8.8818e-16、聚合3.5527e-15；支持/内折字母表/叶隔离及3×30点选择均一致。',
      '现有设计artifact_manifest原样保留；结果用另一个results_artifact_manifest.json列出。']+limitations
    (HERE/'研究报告.txt').write_text('\n'.join(lines)+'\n')
    # Fixed order, same display treatment for every leaf; no outcome-driven deletion.
    fig,axs=plt.subplots(2,1,figsize=(13.5,7.4),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2.1,1]})
    x=np.arange(len(leaves));colors=['#306895','#b66b40','#3d8268'];width=.24
    for j,n in enumerate(NAMES):
        gain=[rows[n]['gain']['per_leaf'].get(l,np.nan) for l in leaves]
        counts=[rows[n]['targets_by_leaf'].get(l,0) for l in leaves]
        axs[0].bar(x+(j-1)*width,gain,width,color=colors[j],label=n)
        axs[1].bar(x+(j-1)*width,counts,width,color=colors[j])
    axs[0].axhline(0,color='#273b49',lw=.8);axs[0].set_ylabel('Mean gain per leaf group (bits / target)');axs[0].legend(ncols=3)
    axs[1].set_ylabel('Eligible targets');axs[1].set_xticks(x,leaves,rotation=40,ha='right')
    for ax in axs:ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    fig.suptitle('Cross-line exploratory evaluation: all 17 leaf groups in fixed manuscript order',fontsize=14)
    fig.supxlabel('No groups removed. f85/f86 form the pre-specified f85_86 group. Leave-one-group-out ranges are descriptive, not confidence intervals.',fontsize=9)
    fig.savefig(HERE/'crossline_results.png',dpi=170);fig.savefig(HERE/'crossline_results.svg');plt.close(fig)
    print(json.dumps(dict(status='completed',representations=3,leaves=len(leaves),pages_in_table=len(page_table),audit_passed=True)))


if __name__=='__main__':main()
