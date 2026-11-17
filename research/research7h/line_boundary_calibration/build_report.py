"""Descriptive postprocessing of saved synthetic costs; no new scores or fits."""
from pathlib import Path
import datetime,hashlib,json,math
import numpy as np

HERE=Path(__file__).resolve().parent


def write(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def distribution(values):
    a=np.asarray(values,dtype=float)
    return dict(mean=float(a.mean()),median=float(np.median(a)),minimum=float(a.min()),maximum=float(a.max()))


def main():
    summary=json.loads((HERE/'run_v1/summary.json').read_text())
    complete=json.loads((HERE/'run_v1/complete.json').read_text())
    verification=json.loads((HERE/'independent_verification.json').read_text())
    cv=json.loads((HERE/'independent_cv_audit/run_v1/verification.json').read_text())
    assert summary['complete'] and complete['all_passed'] and verification['passed'] and cv['all_passed']
    entropy=-math.fsum(p*math.log2(p) for p in [.55,.25,.15,.05])
    decomp=[];max_identity=0.
    for entry in complete['cases']:
        case=json.loads((HERE/'run_v1'/entry['path']).read_text())
        arrays=np.load(HERE/'run_v1'/case['score_path'])
        for r in case['results']:
            prefix=r['shift']+'__'+r['mode'];information=r['oracle_mutual_information_bits']
            base=r['mean_leaf_expected_base_bits'];model=r['mean_leaf_expected_model_bits']
            kb=base-entropy;kc=model-(entropy-information)
            poolbase=float(arrays[prefix+'__expected_base_bits'].mean())
            poolmodel=float(arrays[prefix+'__expected_model_bits'].mean())
            pkb=poolbase-entropy;pkc=poolmodel-(entropy-information)
            gap=abs(r['mean_leaf_expected_gain']-(information+kb-kc))
            pgap=abs(r['pooled_expected_gain']-(information+pkb-pkc))
            assert min(kb,kc,pkb,pkc)>-1e-12
            max_identity=max(max_identity,gap,pgap)
            decomp.append(dict(seed=r['seed'],rho=r['rho'],shift=r['shift'],mode=r['mode'],
                oracle_H_Y=entropy,oracle_H_Y_given_X=entropy-information,oracle_I=information,
                mean_leaf_KL_base=kb,mean_leaf_KL_child=kc,mean_leaf_expected_gain=r['mean_leaf_expected_gain'],
                pooled_KL_base=pkb,pooled_KL_child=pkc,pooled_expected_gain=r['pooled_expected_gain'],
                identity_error_mean_leaf=gap,identity_error_pooled=pgap))
    groups=[]
    for g in summary['groups']:
        rows=[r for r in decomp if (r['rho'],r['shift'],r['mode'])==(g['rho'],g['shift'],g['mode'])]
        groups.append(dict(rho=g['rho'],shift=g['shift'],mode=g['mode'],seeds=len(rows),
            **{key:distribution([r[key] for r in rows]) for key in ('mean_leaf_KL_base','mean_leaf_KL_child','pooled_KL_base','pooled_KL_child')}))
    decomposition=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='Descriptive algebra from all saved expected costs; no model re-evaluation, parameter choice, p-value or interval.',
        identity='gain = I + KL_base - KL_child',
        KL_child_definition='Expected KL to the FINAL augmented mixture Q1, not the unmixed conditional table.',
        main_weighting='mean within page, equal pages within leaf, equal leaves; pooled separately labelled',
        exact_entropy_bits=entropy,max_identity_error=max_identity,groups=groups,records=decomp)
    write('decomposition.json',decomposition)
    limitation=[
      '仅四个合成符号，固定目标双射；真实依赖不变，但边际与条件对应均改变。不是自然语言或实际字母表的检测保证。',
      '只借用无字形的ZL长度/元数据/缺失/页面骨架，没有新手稿目标评分；不比较真实行内与跨行效应。',
      'A与B训练样本独立；目标训练和评价的identity/shift配对重编码使重拟合等变，这是实现合同，不是两次独立恢复证据。',
      '主数值为精确期望的页均后叶均增益；有限评价样本的经验增益和pooled值均另列。20种子不是手稿置信区间。',
      'rho0正增益来自Q0和最终Q1近似误差差；无预先定义统计分类阈值，不能简称假阳性或把gain当MI。',
      '所有条件、负/零结果及零权重数均报告；不能据此认定手稿使用角色重编码或某种语言。']
    obj=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),title='合成分布改变：预测收益不等于真实依赖',
        status='complete_independent_scalar_replay_passed',scope='synthetic_only',
        freeze_sha256=hashlib.sha256((HERE/'freeze.json').read_bytes()).hexdigest(),
        cases=60,conditions=240,seeds=20,selected_models=180,cpu_seconds=complete['cpu_seconds'],
        geometry=dict(train_rows=1548,train_leaves=57,evaluation_rows=647,evaluation_leaves=17),
        main_permutation=[2,3,0,1],groups=summary['groups'],decomposition_groups=groups,
        independent_max_error=max(r['max_error'] for r in verification['findings']),
        decomposition_identity_max_error=max_identity,limitations=limitation,
        independent_cv_status='First-seed 9/180 searches independently recalculated; all 45 baseline/225 mixture grid values pass, 9 selections identical.',
        independent_cv=dict(searches=cv['searches'],all_searches=180,
            base_grid_points=cv['base_grid_points'],mixture_grid_points=cv['mixture_grid_points'],
            maximum_grid_error=max(cv['maximum_base_grid_error_bits'],cv['maximum_feature_grid_error_bits']),
            exact_selection_matches=cv['exact_selection_matches']),
        manuscript_target_scoring=False,reserve_loaded=False)
    write('website_data.json',obj);write('public_summary.json',obj)
    lines=['合成边界观察器校准：完整结果与解释','',
      '本实验仅使用合成符号，未给任何新手稿目标评分。原模型、rho、双射、20种子和搜索预算均在正式执行前冻结。',
      '60个case、240个条件、180次同预算选参全部完成；正式运行CPU %.4f秒。独立标量重建全部60case的概率/期望/叶聚合通过，最大误差 %.3g。'%(complete['cpu_seconds'],obj['independent_max_error']),
      '来源域训练A、目标域训练B与评价T相互独立；都使用固定的几何和元数据条件。每个选参只在1548个合成训练位置的57叶内做3折，647个评价位置/17叶不参与选择。',
      '有限4字母p=(.55,.25,.15,.05)，rho=0/.15/.5，目标双射[2,3,0,1]。真实I分别0、.0393919903、.3686972501 bits，两域相同。双射改变边际和条件对应，刻意构造失配。','',
      '全条件：精确期望增益为主（页均后叶均），方括号是20seed最小/最大，不是CI。<=0是操作性非正收益数，不是检验拒绝/分类错误率。',
      'rho | domain | observer | expected median [min,max] | <=0/20 | empirical median | empirical <=0/20 | weight0/20']
    for g in summary['groups']:
        e=g['exact_expected_gain'];a=g['empirical_gain']
        lines.append('%.2f | %s | %s | %+.6f [%+.6f,%+.6f] | %d | %+.6f | %d | %d'%(
            g['rho'],g['shift'],g['mode'],e['median'],e['minimum'],e['maximum'],e['nonpositive_seeds'],
            a['median'],a['nonpositive_seeds'],g['selected_zero_weight_seeds']))
    lines+=['','相同真依赖可以被旧观察器漏检：rho=.15时shift来源模型18/20个种子的预期收益非正；rho=.5时20/20非正。目标域重拟合在两强度均20/20为正。但它在identity与shift上的精确相等源于预定的标签等变性，不能作为额外独立复制。',
      'rho0同样不能略去：无shift来源19/20、shift来源12/20、目标重拟合19/20有正预期收益；全部180次选择的混合权重均非0。不能说“模型选了前词特征就发现真依赖”。','',
      '近似误差分解（全部20seed的均值；不是新评分/新CI）',
      '每个已保存expected成本减去解析H(Y)或H(Y|X)，得到KLbase与KLchild。child在此是最终混合Q1，不是未混合条件表。恒等式：gain=I+KLbase−KLchild。',
      'rho | domain | observer | mean_leaf KLbase | mean_leaf KLchild | difference']
    for g in groups:
        b=g['mean_leaf_KL_base']['mean'];c=g['mean_leaf_KL_child']['mean']
        lines.append('%.2f | %s | %s | %.8f | %.8f | %+.8f'%(g['rho'],g['shift'],g['mode'],b,c,b-c))
    lines+=['分解全部240条件、每seed与pooled口径在decomposition.json；最大恒等式误差%.3g。'%max_identity,
      'rho0时I=0，正收益完全是两个近似预测器的误差差。来源模型在shift后两者绝对KL都很大，即使正差也不表示预测已良好或存在真实依赖。','','限制与可复现性']+limitation+[
      'independent_replay.py独立重建已选模型并核对保存网格的最小值；并未重算全部内折CV概率。另一agent在independent_cv_audit对首个seed的9/180组搜索独立逐标量复算：45基线+225混合网格全通过，最大误差4.44e-16 bits，9/9配置完全一致；不扩大为全部180组网格已独立核算。',
      'protocol.txt、freeze.json、synthetic_gate.json、run_v1/cases、independent_verification.json保留完整方法/记录/哈希。可移植入口 public_replay.py 只复算保存证据，不再拟合或评分新手稿。']
    (HERE/'研究报告.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(groups=len(groups),decomposition_records=len(decomp),max_identity_error=max_identity)))


if __name__=='__main__':main()
