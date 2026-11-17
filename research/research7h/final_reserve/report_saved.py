#!/usr/bin/env python3
"""Render a hash-bound, independently reviewed *reserve* packet, never preflight.

This is a reporting adapter only: no scorer, corpus loader, fitting, resampling,
parameter selection or inferential decision is run. A fresh output is required.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent.parent
REPRESENTATIONS = ('ZL_EVA', 'ZL_merged', 'IT_EVA')
REP_LABEL = {'ZL_EVA':'ZL / EVA', 'ZL_merged':'ZL / 合并单位', 'IT_EVA':'IT / EVA'}
CONTRASTS = (
    ('style', '全局 → 书手 / 位置混合', '全部保留词；页级 H / 位置为已知条件'),
    ('boundary_last', '边界基线 → 前词末单位', '行内固定、不重叠的内部词对目标'),
    ('gallows_vs_position', '段首位置 → 已付费高杆因子', '段首原始第 0 槽的合格词'),
    ('gallows_vs_any_first', '任意首单位 → 高杆因子', '段首原始第 0 槽的合格词'),
    ('copy_total', '风格基线 → 单编辑复制', '全部保留词；合法过去来源 H + V'),
    ('copy_edit_vs_exact', '精确复制 → 单编辑复制', '全部保留词；同来源窗口，非单因素'),
    ('copy_vertical', '横向复制 → 加入上一行', '全部保留词；两模型保留各自权重'),
    ('allograph_FP', '原词 → f/p 合并并恢复', '全部保留词；包含原字形恢复费用'),
    ('allograph_KT', '原词 → k/t 合并并恢复', '全部保留词；包含原字形恢复费用'),
    ('allograph_both', '原词 → 两组合并并恢复', '全部保留词；包含原字形恢复费用'),
)
META_IDS = {'style':'style', 'boundary_last1':'boundary_last', 'HV_vs_base':'copy_total',
    'HV_vs_exact':'copy_edit_vs_exact', 'HV_vs_H':'copy_vertical',
    'FP':'allograph_FP', 'KT':'allograph_KT', 'both':'allograph_both'}
LABELS = {key:title for key,title,_ in CONTRASTS}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def num(value):
    return format(value, '.12g') if isinstance(value, (int, float)) and math.isfinite(value) else '未估计'


def interval(value):
    return '['+', '.join(num(x) for x in value)+']' if isinstance(value, list) and len(value)==2 else '未估计'


def label(identifier):
    key = identifier.removesuffix('_global_restore')
    return LABELS.get(key, key) + ('（总体比例恢复）' if identifier.endswith('_global_restore') else '')


def verified_packet(run):
    """Reject before reading any numerical summary unless all gates bind."""
    complete_path = run/'complete.json'
    complete = load(complete_path)
    if complete.get('mode') != 'reserve' or complete.get('all_passed') is not True:
        raise ValueError('Only a completed reserve packet is accepted; preflight is forbidden.')
    if not (run.parent/'reserve_opened.json').exists():
        raise ValueError('The actual reserve-opened receipt is missing.')
    review_path = run/'independent_review.json'
    review = load(review_path)
    if review.get('all_passed') is not True:
        raise ValueError('Independent final review has not passed.')
    if review.get('saved_reserve_packet_read') is not True or review.get('raw_corpus_reopened') is not False:
        raise ValueError('Final review must distinguish saved reserve access from raw-corpus reopening.')
    metadata_dir = ROOT/'metadata_sensitivity/reserve_v1'
    inputs = {'main_complete':complete_path, 'independent_review':review_path,
        'summary':run/'summary.json', 'metadata_complete':metadata_dir/'complete.json',
        'metadata_summary':metadata_dir/'summary.json', 'metadata_replay':metadata_dir/'replay_verification.json',
        'freeze':run.parent/'freeze.json', 'opened':run.parent/'reserve_opened.json',
        'split_manifest':ROOT/'split_manifest.json', 'reporting_scope':run.parent/'reporting_scope.txt',
        'protocol':run.parent/'protocol.txt', 'replay_scope_note':run.parent/'replay_scope_note.txt'}
    for key, field in [('main_complete','complete_sha256'), ('summary','summary_sha256'),
            ('metadata_complete','metadata_complete_sha256'), ('metadata_summary','metadata_summary_sha256'),
            ('metadata_replay','metadata_replay_sha256')]:
        if sha(inputs[key]) != review.get(field):
            raise ValueError('Independent review hash mismatch: '+field)
    if load(inputs['metadata_complete']).get('all_passed') is not True or load(inputs['metadata_replay']).get('all_passed') is not True:
        raise ValueError('Metadata completion or independent replay did not pass.')
    summary, metadata = load(inputs['summary']), load(inputs['metadata_summary'])
    if summary.get('mode') != 'reserve' or summary.get('split') != 'reserve':
        raise ValueError('Summary is not a true reserve result.')
    if summary.get('freeze_sha256') != sha(inputs['freeze']) or complete.get('freeze_sha256') != sha(inputs['freeze']):
        raise ValueError('Frozen protocol binding mismatch.')
    expected = {(rep,key) for rep in REPRESENTATIONS for key,_,_ in CONTRASTS}
    assert summary['primary_representation']=='ZL_EVA' and summary['primary_contrasts']==10 and summary['all_combinations']==30
    assert len(summary['results'])==30 and {(r['representation'],r['id']) for r in summary['results']}==expected
    assert len(summary['global_restoration_sensitivity'])==9
    assert {(r['representation'],r['id']) for r in summary['global_restoration_sensitivity']} == {
        (rep,f'allograph_{merge}_global_restore') for rep in REPRESENTATIONS for merge in ('FP','KT','both')}
    assert set(summary['position_specificity'])==set(REPRESENTATIONS)
    assert all(set(g['conditions'])=={'exact','coarse'} for g in summary['position_specificity'].values())
    assert all('holm_reference_p_family6' in row for g in summary['position_specificity'].values() for row in g['conditions'].values())
    assert len(metadata['comparisons'])==24 and {(r['name'],r['contrast']) for r in metadata['comparisons']}=={
        (rep,key) for rep in REPRESENTATIONS for key in META_IDS}
    assert metadata['parameters_reselected'] is False and metadata['intervals_computed'] is False and metadata['p_values_computed'] is False
    assert len(metadata['allograph_decompositions'])==9 and len(metadata['paragraph_invariance'])==3
    split = load(inputs['split_manifest'])
    reserve = [p for p in split if p['split']=='reserve']
    population = {'partition_pages':len(reserve), 'partition_leaves':len({p['leaf'] for p in reserve})}
    assert population=={'partition_pages':22,'partition_leaves':11}
    receipts = {key:{'path':str(path.relative_to(ROOT)), 'sha256':sha(path), 'bytes':path.stat().st_size}
                for key,path in inputs.items()}
    return summary, metadata, review, population, inputs, receipts


def numeric_report(summary, metadata, review, population):
    index = {(r['representation'],r['id']):r for r in summary['results']}
    ordered = [index[rep,key] for rep in REPRESENTATIONS for key,_,_ in CONTRASTS]
    lines = ['最终预留页：固定预测比较与敏感性完整报告', '',
        '本报告读取已保存的真实 reserve 结果摘要；执行、独立复核及摘要哈希已经匹配。',
        '保存包复算会访问其中的reserve目标记录，但不重开原始手稿分区加载器；不能把旧程序的reserve_loaded=false解释为从未接触保留数据。',
        f"评分完成：{summary.get('completed_utc')}；独立复核：{review.get('reviewed_utc',review.get('completed_utc'))}。",
        f"分区为{population['partition_pages']}页 / {population['partition_leaves']}叶；每项合格词、页、叶另列，不混用分母。", '',
        '解释范围',
        '正数=后模型比前模型节省 bits / 原始归一化目标词；负数=后模型成本更高。',
        '先页内目标词平均，再叶内合格页面等均，最后合格叶等均；词合并均值另列。',
        '计完整非空词、EOS、未知身份及规定恢复费。版面/书手已知条件的传输费用未计入。',
        '全词、内部词对、段首词总体不同；不按分数排名语言或跨总体比较效应大小。',
        '三种表示与十项比较共享手稿、基线和组件，并非独立语言证据。',
        '95%、主ZL十项族99.5%、全三十项族99.833333…%均为冻结口径的近似百分位区间。',
        '最多11叶，百分位bootstrap不保证精确同时覆盖，99,999次抽样不增加独立叶数。',
        '跨零不等于无效、等效或依赖消失；两项显著性不同不等于两项有差异。',
        '零合格叶不估计；一叶仅报均值，不估计区间或留一叶范围。未纳入页/叶不填零。',
        'EVA是字形编码；任何收益均不直接识别语言、词义、同音同值或历史生成机制。', '',
        '一、主ZL十项与两表示敏感性：全部30项，按冻结顺序',
        '表示\t比较\t目标词/页/叶\t等叶平均节省\t词合并节省\t95%\t主十项族99.5%\t全三十项族99.833333…%\t留一叶范围']
    for r in ordered:
        lines.append('\t'.join([REP_LABEL[r['representation']],label(r['id']),f"{r['words']}/{r['eligible_pages']}/{r['eligible_leaves']}",
            num(r['mean_leaf_bits_saved']),num(r['pooled_bits_saved']),interval(r['bootstrap95']),
            interval(r['bootstrap99_5_primary10']) if r['representation']=='ZL_EVA' else '不属于主十项族',
            interval(r['bootstrap99_833_all30']),interval(r['leave_one_leaf_out_range'])]))
    lines += ['', '各比较的解释边界']
    lines += [f'{i:02d} {title}：{scope}。' for i,(_,title,scope) in enumerate(CONTRASTS,1)]
    lines += ['段首标签可能部分依赖醒目首字形，不能作为独立因果。高杆因子包含前缀费用和NONE归一化。',
        '精确/编辑复制与H/HV比较保留各自已选参数，不是纯单因素或单参数开关。',
        '合并与恢复模型容量及选参预算不等；只支持限定模型的参数共享解释。', '',
        '二、总体比例恢复辅助：全部9项，不替代条件恢复主结果',
        '表示\t比较\t词/页/叶\t等叶节省\t词合并节省\t95%描述区间']
    for r in summary['global_restoration_sensitivity']:
        lines.append('\t'.join([REP_LABEL[r['representation']],label(r['id']),f"{r['words']}/{r['eligible_pages']}/{r['eligible_leaves']}",num(r['mean_leaf_bits_saved']),num(r['pooled_bits_saved']),interval(r['bootstrap95'])]))
    lines += ['', '三、字形成本拆分：全部9组原H与9组行内H；以下均为词合并平均pooled',
        'escape是已计入合并流的组成项，不能再加一次；不与等叶增益混用。',
        '原词escape的单独分量未存于此摘要，见逐词数组；不从完整成本差值推断。',
        '表示/合并\tH版本\t原词成本\t合并流\t条件恢复\t其中escape\t完整成本\t总体恢复\t总体完整成本']
    for r in metadata['allograph_decompositions']:
        compare = next(c for c in metadata['comparisons'] if c['name']==r['name'] and c['contrast']==r['merge'])
        for mode in ('old','inline'):
            costs = r['costs'][mode]
            raw = compare['old_baseline' if mode=='old' else 'inline_baseline']['pooled']
            lines.append('\t'.join([REP_LABEL[r['name']]+'/'+r['merge'],mode,num(raw)]+[num(costs.get(k,{}).get('pooled')) for k in ['quotient','restoration','quotient_escape','complete','restoration_global','complete_global']]))
    lines += ['', '四、上一行位置辅助：全部6项及六项统一Holm参考尾面积',
        '仅V来源条件换位，保持H、目标、槽和缺失；不是全篇洗牌，不证明或否定历史复制。',
        '条件可交换性限于冻结方案；参考尾面积不与bootstrap区间混算。',
        '表示/分层\t原V收益\t换位均值\t差值D\t原始参考尾面积\t六项Holm\t身份移动比例\t来源集合变化/全目标\t来源集合变化/可用V\t可用V目标/来源槽/来源行\t置换数\t换位分布95%范围']
    for rep in REPRESENTATIONS:
        for kind in ('exact','coarse'):
            r = summary['position_specificity'][rep]['conditions'][kind]
            lines.append('\t'.join([REP_LABEL[rep]+'/'+kind]+[num(r[k]) for k in ['observed_V_gain','null_mean','alignment_specificity_D','monte_carlo_reference_p','holm_reference_p_family6','source_identity_moved_mean','target_multiset_changed_mean_all_targets','target_multiset_changed_mean_given_V']]+[f"{r['V_available_targets']}/{r['source_valid_slots']}/{r['source_rows']}",str(r['replicates']),interval(r['null95'])]))
    lines += ['换位分布95%范围是参考分布描述，不是D的置信区间。', '',
        '五、共同剔除曝光叶：全部30项及9项恢复辅助，只有描述性均值',
        '主分析仍保留全部22页。一起剔除f15/f103不能代替主结果或成为第二次争取阳性的机会。',
        '既有锚词、默认种子和全文汇总已有曝光，不称完全盲。',
        '表示\t比较\t一起剔除\t剩余合格叶\t描述性等叶节省']
    for r in ordered+summary['global_restoration_sensitivity']:
        e=r['exposure_sensitivity']
        lines.append('\t'.join([REP_LABEL[r['representation']],label(r['id']),','.join(e['omitted_leaves']),str(e['eligible_leaves']),num(e['mean_leaf_bits_saved'])]))
    lines += ['', '六、明确行内H修正：全部24项，参数固定，无新p/CI',
        '原页H未展开f115r页内2/3；@是标签值，不是第六位书手。旧主结果不覆盖。',
        '平均增益变化不是逐词影响上界。完整逐页/叶与基线/模型均值见tables.json。',
        '表示\t比较\t目标词\t旧H等叶增益\t行内H等叶增益\t等叶变化\t旧H词合并增益\t行内H词合并增益']
    for r in metadata['comparisons']:
        lines.append('\t'.join([REP_LABEL[r['name']],label(META_IDS[r['contrast']]),str(r['targets']),num(r['old_gain']['mean_leaf']),num(r['inline_gain']['mean_leaf']),num(r['gain_change']['mean_leaf']),num(r['old_gain']['pooled']),num(r['inline_gain']['pooled'])]))
    lines += ['', '段首四数组核验']
    for r in metadata['paragraph_invariance']:
        lines.append(REP_LABEL[r['name']]+'：'+('逐值不变' if r['all_arrays_unchanged'] else '存在变化，详见复核')+'；各数组误差='+json.dumps(r['max_errors'],ensure_ascii=False))
    lines += ['', '各项无目标范围']
    for r in ordered:
        lines.append(REP_LABEL[r['representation']]+' / '+label(r['id'])+'：'+json.dumps(r['ineligible'],ensure_ascii=False))
    lines += ['', '此报告不新增拟合、目标评分、抽样、阈值或模型选择。图中各格独立刻度，保持冻结比较顺序。',
        '所有原始摘要与复核哈希在manifest.json绑定；tables.json保留全部数值、逐页/叶和限制。']
    return '\n'.join(lines)+'\n'


def plotting_setup(font_path=None):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt, font_manager
    if font_path:
        chosen = Path(font_path)
    else:
        paths = sorted(Path(p) for p in font_manager.findSystemFonts())
        preferred = ('pingfang.ttc','notosanscjk-regular.ttc','notosanssc-regular.ttf','arial unicode.ttf','stheiti light.ttc')
        chosen = next((p for name in preferred for p in paths if p.name.lower()==name), None)
    if not chosen or not chosen.exists():
        raise ValueError('A Chinese font is required; pass --font /path/to/font.ttf or .ttc.')
    font_manager.fontManager.addfont(str(chosen))
    family = font_manager.FontProperties(fname=str(chosen)).get_name()
    plt.rcParams.update({'font.family':family, 'font.size':9, 'svg.fonttype':'path',
        'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
        'axes.spines.left':False, 'figure.facecolor':'#fbfaf5','axes.facecolor':'#fbfaf5'})
    return plt, {'matplotlib':matplotlib.__version__, 'font_file':chosen.name, 'font_family':family}


def plot_facets(plt, summary, reps, ci_key, title, subtitle, output_stem):
    from matplotlib.ticker import MaxNLocator
    lookup={(r['representation'],r['id']):r for r in summary['results']}
    fig, axes=plt.subplots(5,2,figsize=(14,14 if len(reps)==1 else 17),squeeze=False)
    colors={'ZL_EVA':'#2f6255','ZL_merged':'#98732b','IT_EVA':'#8a4e52'}
    for order,(key,name,scope) in enumerate(CONTRASTS):
        ax=axes[order//2,order%2]
        rows=[lookup[rep,key] for rep in reps]
        values=[0.0]
        for row in rows:
            if row['mean_leaf_bits_saved'] is not None:values.append(row['mean_leaf_bits_saved'])
            if row.get(ci_key):values.extend(row[ci_key])
        low,high=min(values),max(values);span=high-low
        padding=span*.14 if span else 0.01
        ax.set_xlim(low-padding,high+padding)
        for y,(rep,row) in enumerate(zip(reps,rows)):
            point=row['mean_leaf_bits_saved'];ci=row.get(ci_key)
            if ci is not None:
                ax.hlines(y,ci[0],ci[1],color=colors[rep],lw=2.2)
                ax.vlines(ci,y-.055,y+.055,color=colors[rep],lw=1.2)
            if point is not None:ax.plot(point,y,'o',color=colors[rep],ms=6)
            if ci is None:ax.text(.98,y,'区间未估计',ha='right',va='bottom',transform=ax.get_yaxis_transform(),fontsize=8)
        labels=[REP_LABEL[rep]+f"\n{r['words']:,}词 · {r['eligible_pages']}页 · {r['eligible_leaves']}叶" for rep,r in zip(reps,rows)]
        ax.set_yticks(list(range(len(reps))),labels=labels,fontsize=8)
        ax.set_ylim(len(reps)-.4,-.6)
        ax.axvline(0,color='#8a8a83',lw=.9,ls='--',zorder=0)
        ax.grid(axis='x',color='#deded6',lw=.5)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
        ax.tick_params(axis='y',length=0,pad=9)
        ax.tick_params(axis='x',labelsize=8)
        ax.set_xlabel('后模型节省 bits / 目标词（正数为节省）',fontsize=8)
        ax.set_title(f'{order+1:02d}  {name}\n{scope}',loc='left',fontsize=10,pad=12)
    fig.suptitle(title,fontsize=19,x=.04,ha='left',y=.985,color='#243e35')
    fig.text(.04,.953,subtitle,fontsize=10,ha='left')
    fig.text(.04,.019,'每格独立横轴刻度；全词、内部词对、段首词分母不同，不跨总体排名。正值不识别语言、词义或历史机制。\n'
        '最多11叶的近似百分位区间，不保证精确同时覆盖；抽样次数不增加独立叶数。跨零不等于无效或等效。',fontsize=9,ha='left')
    fig.subplots_adjust(left=.13,right=.97,top=.91,bottom=.083,hspace=.85,wspace=.62)
    fig.savefig(str(output_stem)+'.png',dpi=190,facecolor=fig.get_facecolor())
    fig.savefig(str(output_stem)+'.svg',facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--font',type=Path)
    args=ap.parse_args();run=args.run.resolve();out=args.output.resolve()
    if out.exists() or run==out or run in out.parents:
        raise ValueError('Use a new output directory outside the saved scoring packet.')
    summary,metadata,review,population,inputs,receipts=verified_packet(run)
    plt,render_info=plotting_setup(args.font)
    out.mkdir(parents=True)
    try:
        plot_facets(plt,summary,('ZL_EVA',),'bootstrap99_5_primary10',
            '保留页 · 主 ZL / EVA 十项固定比较','原样报告主十项族 99.5% 近似区间；顺序预定，负值与未估计项完整保留。',out/'主表示十项')
        plot_facets(plt,summary,REPRESENTATIONS,'bootstrap99_833_all30',
            '保留页 · 三种表示的三十项固定比较','原样报告全三十项族 99.833333…% 近似区间；三表示共享手稿，不是独立语言证据。',out/'三表示三十项')
        (out/'最终预留研究报告.txt').write_text(numeric_report(summary,metadata,review,population),encoding='utf-8-sig')
        tables={'scope':'Reviewed reserve values, unchanged; no new statistical calculation',
            'population':population,'summary':summary,'metadata_summary':metadata,
            'row_counts':{'main':10,'representation_sensitivity':20,'global_restore':9,'position':6,'metadata':24}}
        (out/'tables.json').write_text(json.dumps(tables,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
        for key,path in inputs.items():
            assert sha(path)==receipts[key]['sha256'], 'Input changed during reporting: '+key
        artifacts=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(out.iterdir()) if p.is_file()]
        manifest={'complete':True,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'mode':'reserve','generator_sha256':sha(Path(__file__)),'inputs':receipts,'outputs':artifacts,
            'rendering':render_info,'scoring_or_selection_performed':False,'values_filtered_or_sorted_by_result':False,
            'review_sha256':receipts['independent_review']['sha256'],
            'saved_reserve_packet_read':True, 'raw_corpus_reopened':False}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'complete':True,'output_files':len(artifacts),'review_sha256':manifest['review_sha256']}))
    except Exception as exc:
        (out/'incomplete.json').write_text(json.dumps({'complete':False,'error':str(exc),'preserve_partial_outputs':True},ensure_ascii=False,indent=2)+'\n')
        raise


if __name__=='__main__':main()
