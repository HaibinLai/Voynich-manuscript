"""Report all fixed metadata comparisons without selecting positive outcomes."""
from pathlib import Path
import json
import numpy as np
from metadata import HERE,read,write,sha

LABELS={'style':'全局→书手/位置混合','HV_vs_base':'基线→横竖变异复制',
    'HV_vs_exact':'精确复制→变异复制','HV_vs_H':'仅横向→横竖复制',
    'boundary_last1':'跨词末→首完整词','FP':'FP可逆因子','KT':'KT可逆因子','both':'FP+KT可逆因子'}


def main():
    run=HERE/'confirm_v1';summary=read(run/'summary.json');replay=read(HERE/'replay_verification.json')
    assert replay['all_passed'] and read(HERE/'aggregation_verification.json')['passed']
    table=[]
    for r in summary['comparisons']:
        saved=np.load(run/(r['family']+'_'+r['name']+'.npz'))
        model={'style':'base','HV_vs_base':'edit_HV','HV_vs_exact':'edit_HV','HV_vs_H':'edit_HV',
            'boundary_last1':'last','FP':'FP_complete','KT':'KT_complete','both':'both_complete'}[r['contrast']]
        changes=saved['inline__'+model]-saved['old__'+model]
        table.append(dict(representation=r['name'],contrast=r['contrast'],label=LABELS[r['contrast']],
            targets=r['targets'],old_leaf_gain=r['old_gain']['mean_leaf'],inline_leaf_gain=r['inline_gain']['mean_leaf'],
            delta_leaf_gain=r['gain_change']['mean_leaf'],old_pooled_gain=r['old_gain']['pooled'],
            inline_pooled_gain=r['inline_gain']['pooled'],max_abs_per_token_model_cost_change=float(np.max(np.abs(changes))),
            changed_token_cost_fraction=float(np.mean(np.abs(changes)>1e-12))))
    maximum=max(abs(r['delta_leaf_gain']) for r in table)
    limits=[
        '这是已见确认页上的固定旧参数敏感性，不是新独立验证；保留页未由本任务读取。',
        '所有旧平滑、混合、复制和恢复配置不变；如果重新选择参数，结果可能不同，本轮不进行该搜索。',
        '仅恢复原 IVTFF 明确记录的行内 H，不重新判断书手，也不等于完整真实书手金标准。',
        '最大改变量指24项等叶平均增益，不是每词、每页的影响上限；逐词成本变化单独列出。',
        '不计算新显著性或置信区间；原 IT 敏感性及既有小样本限制继续成立。',
        '预测增益不能证明同音、字形同值、自然语言内容或已破译。']
    out=dict(title='展开行内书手标签后的固定参数敏感性',status='independently_verified_exploratory',
        freeze_sha256=sha(HERE/'freeze.json'),summary_sha256=sha(run/'summary.json'),
        root_gate_sha256=sha(HERE/'confirm_gate.json'),comparison_count=24,primary_table=table,
        changed_training={'ZL_EVA':{'total':456,'H2':128,'H3':328},'ZL_merged':{'total':456,'H2':128,'H3':328},'IT_EVA':{'total':444,'H2':120,'H3':324}},
        inline_overrides_on_confirm_pages=0,max_abs_leaf_gain_change=maximum,
        sign_changes=sum(int(np.sign(r['old_leaf_gain'])!=np.sign(r['inline_leaf_gain'])) for r in table),
        paragraph_all_four_arrays_unchanged=True,independent_probability_max_error=max(r['max_error'] for r in replay['findings']),
        parameters_reselected=False,new_p_values=False,new_intervals=False,reserve_read_by_this_task=False,
        limitations=limits,files={'full_results':'confirm_v1/summary.json','report':'研究报告.txt','replay':'public_replay.py'})
    write(HERE/'website_data.json',out);write(HERE/'public_summary.json',out)
    text=['行内书手标签敏感性：独立复核完成','',
        '结论：只恢复 f115r 原转写中的明确行内 H，固定所有旧参数后，24项等叶平均增益的最大绝对变化为 %.9f bits/target；没有符号翻转。段首模型四数组×三表示逐值完全不变。'%maximum,
        '这支持此前描述性趋势对这处标签处理问题较稳定，但没有提供任何词义译文或新的显著性结论。','',
        '为何单列本实验',
        '原页头 H=@ 是需要行内覆盖的哨兵，却被旧模型当作一个观测类别。它不是第六位书手。f115r.1 起为 H2，f115r.13 起为 H3；ZL保留456词=128+328，IT保留444词=120+324。旧结果保留，敏感性结果不替代旧结果。',
        '允许 train+legacy/dev 的源标签独立扫描仅发现这一页。确认页本身没有行内覆盖；此次变化来自训练词归类后的计数重分配。所有正文、词槽、字母表、未知符号费用、段落和复制来源相同。','',
        '固定设计',
        'train+legacy重新计数，开发集只核对提取一致性，不重新选权重/平滑/复制/恢复参数。全部8比较×3表示同时展示。正文分母及未知/备选整词的排除沿用原解析器。',
        '原参考为 final_reserve/preflight_v1：12个家族×表示任务全部重现旧完整记录和旧数值。新标签只改变 hand 字段。global/position组件、escape和全局恢复表保持一致；手条件部分重新计数。','',
        '等叶平均预测增益（正值为右侧模型节省的比特；Δ=新−旧）',
        '表示 | 比较 | 旧 | 行内标签 | Δ']
    text += ['%s | %s | %.9f | %.9f | %+.9f'%(r['representation'],r['label'],r['old_leaf_gain'],r['inline_leaf_gain'],r['delta_leaf_gain']) for r in table]
    text += ['', '理解这些数字',
        '例如 IT 的精确复制→变异复制仍为负：仅这处标签修正没有消除转写敏感性。FP/KT模型支付合并串和原字形恢复的完整费用；它们的收益仍只能解释为参数共享可能有用，不能证明同音或字形同值。',
        '逐词、逐页和逐叶结果及旧/新成本均公开；完整 allograph 分解含 quotient、restoration、escape 与 total。最大平均改变量不限制单个词可能的成本变化。','',
        '独立验证',
        '独立标量字符计数、算术混合、显式单编辑路径、恢复二元表和首单位条件计数重算全部九个相关家族×表示，最大绝对概率成本误差 %.3g bits；另用独立词权重重算24项的72个增益向量。'%out['independent_probability_max_error'],
        '只读保存的训练页和目标记录，没有新语料加载或参数选择。段首模型的H字段不参与概率，重新求值后四数组完全相同。','',
        '公开及后续接口',
        'public_replay.py --out-dir 新目录：校验保存包并独立复算，不重新打开原转写。',
        'make_sidecar.py --pages ROOT提供的保存页 --source 源名 --out 新文件：只解析所给folio对应源标签，检查源SHA及完整规范化页；不自行选split。',
        'run.py 使用同一冻结实现和root另写gate，可对未来root提供的已保存页作相同24项敏感性；本任务没有调用保留页入口。',
        '原 freeze 已原样保留为 pre_portability_freeze.json；仅在确认评分前将旧参考路径改为包内相对形式，amendment完整记录。概率代码、数据与参数未因此改变。','', '限制']
    text += ['• '+v for v in limits]
    (HERE/'研究报告.txt').write_text('\n'.join(text)+'\n')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    order=list(LABELS);english=['Style mixture','Edit HV vs baseline','Edit HV vs exact HV','Edit HV vs edit H','Last-to-first boundary','Reversible FP','Reversible KT','Reversible FP+KT']
    fig,ax=plt.subplots(figsize=(9.3,5.1),constrained_layout=True)
    for i,(name,color) in enumerate([('ZL_EVA','#2563eb'),('ZL_merged','#059669'),('IT_EVA','#d97706')]):
        values=[next(r['delta_leaf_gain'] for r in table if r['representation']==name and r['contrast']==key) for key in order]
        ax.scatter(values,np.arange(8)+(i-1)*.18,label=name,color=color,s=30)
    ax.axvline(0,color='#64748b',lw=1);ax.set_yticks(np.arange(8),english);ax.invert_yaxis()
    ax.set_xlabel('Change in equal-leaf mean gain (bits per target)')
    ax.set_title('Explicit inline-hand correction, with all old parameters fixed')
    ax.grid(axis='x',alpha=.2);ax.legend(loc='lower right');ax.ticklabel_format(axis='x',style='sci',scilimits=(-3,-3))
    fig.savefig(HERE/'metadata_gain_changes.png',dpi=180);fig.savefig(HERE/'metadata_gain_changes.svg');plt.close(fig)


if __name__=='__main__':main()
