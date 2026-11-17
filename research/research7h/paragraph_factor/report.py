"""Package completed, independently replayed paragraph-factor results."""
from pathlib import Path
import gzip
import hashlib
import json
import platform
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent


def read(path):
    path = ROOT/path
    raw = gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_bytes()
    return json.loads(raw)


def main():
    names = ['ZL_EVA', 'ZL_merged', 'IT_EVA']
    results = {n: read(f'{n}/confirm_results.json') for n in names}
    config = {n: read(f'{n}/frozen_config.json') for n in names}
    replay = read('replay_verification.json')
    assert all(v['independent_replay_passed'] for v in replay)
    rows = [json.loads(s) for s in gzip.decompress((ROOT/'ZL_EVA/confirm_word_scores.jsonl.gz').read_bytes()).decode().splitlines()]
    first = [r for r in rows if r['position'] == 'paragraph_first']
    key = 'gallows_beta'+str(config['ZL_EVA']['selected']['factors']['gallows']['direct']['beta'])
    costs = {k: float(np.mean([r['factor_costs'][key][k] for r in first])) for k in
        ['prefix_bits', 'body_raw_bits', 'support_normalization_bits', 'total_bits']}
    model_names = ['body_full', 'position_full', 'gallows_selected', 'any_first_selected']
    labels = ['Body full-word', 'Position full-word', 'Gallows factor', 'Any-first factor']
    colors = ['#a6afa2', '#285b4d', '#b28b49', '#b57b64']
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False, 'figure.facecolor': '#fcfbf7', 'axes.facecolor': '#fcfbf7'})
    fig = plt.figure(figsize=(12.5, 8.8))
    grid = fig.add_gridspec(2, 2, height_ratios=[1, 1.1], hspace=.57, wspace=.35)
    ax = fig.add_subplot(grid[0, 0])
    vals = [results['ZL_EVA']['summaries']['paragraph_first'][k]['bits_per_word'] for k in model_names]
    bars = ax.barh(np.arange(4), vals, color=colors, height=.62)
    ax.set_yticks(np.arange(4), labels); ax.invert_yaxis(); ax.set_xlim(0, 25)
    ax.set_xlabel('Bits per complete paragraph-initial token (lower is better)')
    ax.set_title('A  Held-out prediction: ZL / EVA', loc='left', fontweight='bold', pad=15)
    for b, v in zip(bars, vals):
        ax.text(v+.25, b.get_y()+b.get_height()/2, f'{v:.3f}', va='center', fontsize=10)
    ax.text(0, -.32, '100 readable paragraph-initial tokens; 28 pages / 13 leaves', transform=ax.transAxes, fontsize=9, color='#626d64')
    ax = fig.add_subplot(grid[0, 1])
    ax.bar([0], [costs['body_raw_bits']], color='#a6afa2', label='Root including EOS + escapes', width=.6)
    ax.bar([0], [costs['prefix_bits']], bottom=[costs['body_raw_bits']], color='#b28b49', label='Prefix identity', width=.6)
    ax.bar([1], [costs['total_bits']], color='#285b4d', width=.6)
    ax.axhline(vals[1], color='#a94e31', linestyle='--', linewidth=1)
    ax.text(1.4, vals[1]+.15, 'Position LM', color='#a94e31', ha='right', fontsize=9)
    ax.set_xticks([0, 1], ['Root + prefix', 'Normalized total'])
    ax.set_ylim(0, 23); ax.set_xlim(-.6, 1.65); ax.set_ylabel('Bits / paragraph-initial token')
    ax.set_title('B  The prefix must be paid for', loc='left', fontweight='bold', pad=15)
    ax.text(0, costs['body_raw_bits']/2, f"Root {costs['body_raw_bits']:.3f}", ha='center', va='center')
    ax.text(0, costs['body_raw_bits']+costs['prefix_bits']/2, f"+ {costs['prefix_bits']:.3f}", ha='center', va='center', fontsize=9)
    ax.text(1, costs['total_bits']+.3, f"{costs['total_bits']:.3f}", ha='center')
    ax.text(0, -.32, f"NONE-branch normalization: {costs['support_normalization_bits']:.4f} bits / token\nDeleting the prefix would falsely omit {costs['prefix_bits']:.3f} bits.", transform=ax.transAxes, fontsize=9, color='#626d64')
    ax = fig.add_subplot(grid[1, :])
    y = 0
    ticks, ticklabels = [], []
    for name, display in zip(names, ['ZL / EVA', 'ZL / merged', 'IT / EVA']):
        comps = results[name]['comparisons']['paragraph_first']
        for label, key, color in [('vs. position full-word', 'position_full__minus__gallows_selected', '#285b4d'),
                                 ('vs. any-first factor', 'any_first_selected__minus__gallows_selected', '#b28b49')]:
            c = comps[key]; value = c['mean_leaf_bits_saved']; low, high = c['bootstrap95']
            ax.errorbar(value, y, xerr=[[value-low], [high-value]], fmt='o', color=color, capsize=4)
            ticks.append(y); ticklabels.append(f'{display}  |  {label}')
            ax.text(1.0, y, f'{value:+.3f}  [{low:+.3f}, {high:+.3f}]', va='center', fontsize=9)
            y += 1
        y += .3
    ax.set_yticks(ticks, ticklabels); ax.invert_yaxis(); ax.axvline(0, color='#8d958a', linewidth=1)
    ax.set_xlim(-2.6, 2.7); ax.set_xlabel('Leaf-mean bits saved by gallows factor: positive favors factor')
    ax.set_title('C  Same direction across encodings; no superiority over the position LM', loc='left', fontweight='bold', pad=14)
    fig.suptitle('Reversible paragraph-initial factorization', x=.035, ha='left', fontsize=17, fontweight='bold', y=.99)
    fig.text(.035, .95, 'Fixed training/development splits; explicit prefix, EOS, support normalization and unseen-unit escape costs.', fontsize=10, color='#626d64')
    fig.text(.035, .015, 'Intervals: descriptive 95% leaf bootstrap, 9,999 resamples; no reserve pages used. Prediction of unit strings is not decipherment.', fontsize=9, color='#626d64')
    fig.subplots_adjust(left=.22, right=.96, top=.88, bottom=.10)
    fig.savefig(ROOT/'段首因子结果.png', dpi=180)
    fig.savefig(ROOT/'段首因子结果.svg')
    plt.close(fig)

    report = '''伏尼契手稿：段首可逆前缀因子实验
阶段二的一项已完成子实验；七小时总研究仍在继续。没有提出语义、音值或译文。

结论
段首高字形单独编码有预测作用，但没有超过“段首使用独立完整词模型”的对照。
因此，本轮支持段首需要特殊分布建模，不支持把 k/t/p/f 直接删掉后就获得更真实正文。
Gallows 因子比任意首单位分离对照略好；这种有限收益并不能确定历史写作机制。

1. 数据边界与冻结过程
继承根任务整叶分组：train+legacy 113 页、57 叶；dev 41 页、17 叶；confirm 28 页、13 叶。
ZL 训练 17,754 个词形，其中段首首词 359 个；正文模型仅用另外 17,395 个词形。
ZL 开发 6,886 个词形，其中段首首词 131 个。确认 5,025 个词形，其中可读段首首词 100 个。
IT 因读法/缺失差异，确认集有 5,047 个词形、106 个段首首词；分叶没有变化。
第 0 槽缺失不拿后面的可读词替代。没有排除整条段首行；只排除该行第 0 槽。
确认集上一阶段结果已经被查看，因此这不是全盲研究；本实验的模型规则及参数在本次 confirm 评分前冻结。
三个版本均先完成训练和 dev 参数冻结，再一次载入 confirm 评分。后续 22 页 reserve 完全未用于本实验。

2. 编码目标必须相同
所有模型编码同一个完整、非空的规范化单位序列。只在 paragraph_first 槽替换预测分布；
其他所有位置使用同一个正文模型。位置由原始版面标记提供，没有从词义推断。
正文模型 B 是可输出空串、以 EOS 结束的平滑四元模型；完整词基线条件化为非空。
参数网格 order=1..4、alpha={1,5,20,100}；三个版本都在 dev 正文词上选中 order=4、alpha=100。
位置完整词对照用训练段首首词训练另一个完整词模型，与正文基线做 dev 选择的混合。
ZL/merged 的位置混合权重为 1，IT 为 0.75。

3. 可逆因子与归一化
G={k,t,p,f}。首单位在 G 时，唯一分解为“该前缀 + 剩余串”，剩余串可为空。
首单位不在 G 时，唯一分解为“NONE + 完整词”；该 root 必须非空且首单位不在 G。
各位置类分别训练含 NONE 的五类前缀分布。G 分支概率为 pi(g)B(root)。
NONE 分支概率为 pi(NONE)B(word)/Z_NONE，Z_NONE 是 B 的第一单位非 G 且非 EOS 的总质量。
这使两类支持互斥且完整覆盖。任意首单位对照把每一种第一单位都分开，使用同样的平滑/混合网格。
两个因子都报告直接形式与 dev 选择的混合形式；没有为 G 对照额外使用确认集调参。

未知单位不是免费的 UNK。编码宇宙在确认集前固定：a-z、apostrophe、@000;…@999;（1027 类）；
merged 再增加六个明确组合（1033 类）。它是语法代码上界，不是推断出来的真实字母表。
训练外单位的 UNK 质量在该有限剩余集合上均分，每次支付相应 escape 身份成本。
ZL 与 merged 确认集各有 7 个训练外单位出现，段首中各有 2 个；IT 没有。
可逆性针对显式单位序列，不意味着恢复原始字迹或有歧义的转写标记。

4. 主结果：ZL/EVA 段首首词，完整编码的平均 bits/词形
  正文完整词基线                 21.766691
  位置条件完整词模型             16.450112
  Gallows 因子（dev 选中纯因子）  17.252518
  任意首单位分离（dev 混合）     17.514645
  任意首单位分离（直接形式）     17.680924
越低越好。这里的正文基线刻意没有用段首首词训练，因此较弱；不能只强调对它的巨大改善而忽略位置对照。

G 因子每词三项平均成本为：
  前缀身份             1.765302 bits
  root 含 EOS/escape  15.494359 bits
  NONE 支持归一化     -0.007144 bits
  完整总成本          17.252518 bits
如果只删前缀再计算 root，就会漏算约 1.765 bits/词，造成看似超过位置模型的虚假压缩。
100 个可读段首首词中，前缀类别 p=59、t=22、k=9、f=2、NONE=8。
这只是既定样本的字形统计，不是前缀音值、词性或装饰功能的认定。

5. 按叶配对与编码敏感性
下列是“对照减 G 因子”的每叶平均节省，正值才是 G 因子更好；区间为 9999 次叶重采样的描述性 95% 区间。
                      vs 位置完整词模型                 vs 任意首单位混合
  ZL/EVA       -0.9502 [-1.9861, +0.0166]          +0.2232 [+0.0883, +0.3392]
  ZL/merged    -1.3469 [-2.2987, -0.5276]          +0.2226 [+0.0882, +0.3371]
  IT/EVA       -0.4364 [-0.8281, -0.0621]          +0.1814 [+0.0527, +0.2913]
主 ZL 相对位置模型的区间略跨零；不能说三个版本均证明位置模型显著更好。
三版点估计方向一致：G 因子没有超过位置模型。其相对任意首单位对照的优势有限。
不同表示的裸 bits 不能直接横比；这里只比较各表示内部的模型差值。
全部词形的主 ZL 平均为正文 11.56018、位置 11.45438、G 因子 11.47035、任意首单位混合 11.47556 bits/词。
这些全词平均主要反映段首词只占约 2%；非段首目标在四模型中完全一致。

6. 独立验证与解释限制
8 组短字母表/阶数枚举通过，检查了有限长度概率质量恒等式、G/NONE 互斥、未知首单位与空 root。
全部保存的条件概率和三个位置类的前缀分布都归一化；平滑有限状态模型 EOS 有统一正下界，最终终止概率为 1。
独立 replay.py 不导入拟合/评分实现，不重开手稿语料；从冻结计数重新计算所有条件概率、前缀后验、
确认集逐词成本、总分与全部 bootstrap 数组。最大逐词误差小于 3e-14 bits，均通过。
完整概率表、计数、原始逐词三项成本、所有 dev 候选配置和重采样数组均保存。

这些是固定训练模型的留出预测成本，未计算传输模型参数本身的成本，不能当作完整 MDL 成书机制选择。
段落标记可能部分参考高字形，不能把位置当作完全独立的古文字真值；样本的书手、章节和词形分布仍混杂。
13 叶的 bootstrap 区间不是所有手稿的总体参数，也不是多个假说均独立验证的证明。
下一步若检验位置替代或更细致词形机制，应另行冻结规则，不从本轮确认集挑例子后仍称盲预测。

复现
在 research7h 目录：python3 paragraph_factor/run.py prepare；python3 paragraph_factor/run.py evaluate；
python3 paragraph_factor/replay.py；python3 paragraph_factor/report.py。
prepare/evaluate 拒绝覆盖既有冻结配置与确认结果；完整重跑应使用新的输出副本，保留原审计记录。
依赖 Python、NumPy、Matplotlib；解析沿用 corpus.py、build_corpus.py 和 study20/analyze.py。

原始格式与转写：https://voynich.nu/software/ivtt/IVTFF_format.pdf
https://voynich.nu/transcr.html
转写发布许可：https://voynich.nu/roadmap.html
'''
    (ROOT/'研究报告.txt').write_text(report)
    website = dict(title='段首可逆前缀因子', status='completed_subexperiment',
        overall_research_status='active', scope='28 页确认集 / 13 叶；ZL 100 个段首首词，IT 106 个。与旧 20 页实验不同。',
        primary=dict(variant='ZL_EVA', paragraph_tokens=100, all_tokens=5025,
            complete_token_bits={k: results['ZL_EVA']['summaries']['paragraph_first'][k]['bits_per_word'] for k in model_names},
            factor_cost_components=costs),
        variants={n: dict(paragraph_tokens=results[n]['test_summary']['positions']['paragraph_first'],
            complete_token_bits={k: results[n]['summaries']['paragraph_first'][k]['bits_per_word'] for k in model_names},
            comparisons={key: {k: v for k, v in value.items() if k not in ['raw_bootstrap', 'per_leaf']}
                for key, value in results[n]['comparisons']['paragraph_first'].items()
                if key.startswith(('position_full', 'any_first_selected'))}) for n in names},
        findings=[dict(title='段首需要特殊分布，但不能直接删字',
            summary='支付完整前缀成本后，G 因子为17.253 bits/词，位置完整词模型为16.450；前者未超过后者。',
            limitation='只针对规范化单位串预测，没有词义或历史机制证明。'),
            dict(title='前缀成本不可遗漏', summary='G因子的平均前缀身份成本1.765 bits；只看root会产生虚假改善。',
            limitation='已计入EOS、支持归一化与训练外单位escape。'),
            dict(title='比任意首单位分离略好', summary='主ZL按叶平均节省0.223 bits/段首词，描述性95%区间[0.088,0.339]；两个敏感性版本同向。',
            limitation='不把有限预测优势解释成音值、语法或译文。')],
        verification='独立从冻结计数重算逐词概率及全部bootstrap；最大逐词差小于3e-14 bits。reserve未使用。',
        files=dict(report='研究报告.txt', figure_png='段首因子结果.png', figure_svg='段首因子结果.svg',
            protocol='protocol.txt', checks='replay_verification.json'),
        limits=['确认集的上一阶段结果已见，不是全盲研究。', '段落标记继承转写，可能参考高字形。',
            '描述性叶bootstrap，未作多重假说显著性宣称。', '固定模型预测成本未包含模型参数传输成本。'])
    (ROOT/'website_data.json').write_text(json.dumps(website, ensure_ascii=False, indent=2)+'\n')
    (ROOT/'PUBLIC_EXPORT.txt').write_text('公开可用：研究报告.txt、website_data.json、段首因子结果.png、段首因子结果.svg、protocol.txt、replay_verification.json；代码和完整冻结模型/结果可归档供复现。无现代论文全文，无私有输入。\n')
    manifest = dict(python=platform.python_version(), numpy=np.__version__, matplotlib=matplotlib.__version__,
        files=[dict(path=str(p.relative_to(ROOT)), sha256=hashlib.sha256(p.read_bytes()).hexdigest(), bytes=p.stat().st_size)
               for p in sorted(ROOT.rglob('*')) if p.is_file() and p.name != 'artifact_manifest.json' and '__pycache__' not in p.parts])
    (ROOT/'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print('Report, figure, public summary, and hashed artifact manifest written.')


if __name__ == '__main__':
    main()
