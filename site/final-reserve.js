'use strict';

// Labels and interpretation scopes are fixed before reserve values are shown.
const reserveContrastLabels = {
  style:['全局 → 书手 / 位置混合','页级 H 与位置作为已知条件；不确认真实书手身份或因果。'],
  boundary_last:['边界基线 → 前词末单位','仅限行内固定、不重叠的内部词对；不是语法或跨行结论。'],
  gallows_vs_position:['段首位置 → 已付费高杆因子','只看段首原始第 0 槽的合格词；段首标签可能部分依赖醒目的首字形。'],
  gallows_vs_any_first:['任意首单位 → 高杆因子','比较两种已选因子，并计入前缀与恢复原词的完整成本。'],
  copy_total:['风格基线 → 单编辑横向＋上一行','合法过去来源的预测比较，不确定历史复制过程。'],
  copy_edit_vs_exact:['精确复制 → 单编辑复制','来源窗口相同；不是只改变编辑路径的单因素实验。'],
  copy_vertical:['单编辑横向 → 横向＋上一行','两模型保留各自已选权重，不是只开关上一行通道的单参数消融。'],
  allograph_FP:['原词 → f/p 合并并恢复','付清原字形恢复费用的参数共享，不证明同音或同字母。'],
  allograph_KT:['原词 → k/t 合并并恢复','付清原字形恢复费用；额外模型容量和选参预算不等。'],
  allograph_both:['原词 → 两组合并并恢复','f/p 与 k/t 联合共享参数，不识别词义或历史异体。']
};
const reserveMetaIds={style:'style',boundary_last1:'boundary_last',HV_vs_base:'copy_total',HV_vs_exact:'copy_edit_vs_exact',HV_vs_H:'copy_vertical',FP:'allograph_FP',KT:'allograph_KT',both:'allograph_both'};
const reserveRepNames={ZL_EVA:'ZL / EVA（主表示）',ZL_merged:'ZL / 合并单位',IT_EVA:'IT / EVA'};

function reserveNumber(v,d=5){return Number.isFinite(v)?number(v,d):'未估计';}
function reserveInterval(v){return Array.isArray(v)&&v.length===2&&v.every(Number.isFinite)?`[${reserveNumber(v[0])}, ${reserveNumber(v[1])}]`:'未估计';}
function reserveLabel(id){const base=id.replace(/_global_restore$/,'');return (reserveContrastLabels[base]?.[0]||id)+(id.endsWith('_global_restore')?' · 总体比例恢复':'');}
function reservePopulation(r){return ({all_words:'全部保留词',nonoverlapping_interior_pairs:'内部词对目标',paragraph_first_words:'段首目标词'}[r.population]||r.population)+` · ${r.words} 词 / ${r.eligible_pages} 页 / ${r.eligible_leaves} 叶`;
}
function reserveTable(headers,rows,kind=''){
  return `<div class="sensitivity-table-wrap reserve-table" tabindex="0" role="region" aria-label="${esc(kind||'结果表，可横向滚动')}"><table class="data-table"><thead><tr>${headers.map(x=>`<th scope="col">${x}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
}
function reserveGainTable(rows,intervalKey='bootstrap99_833_all30',intervalLabel='全 30 项族 99.833333…% 区间'){
  return reserveTable(['比较','表示','各项目标范围','等叶平均节省<br>bits / 目标词',intervalLabel],rows.map(r=>`<tr><th scope="row">${esc(reserveLabel(r.id))}</th><td>${esc(reserveRepNames[r.representation]||r.representation)}</td><td>${esc(reservePopulation(r))}</td><td>${reserveNumber(r.mean_leaf_bits_saved)}</td><td>${reserveInterval(r[intervalKey])}</td></tr>`),'固定模型比较，结果表可横向滚动');
}
function reserveLocationDetails(rows){
  return rows.map(r=>`<details class="study-details reserve-location"><summary>${esc(reserveRepNames[r.representation])} · ${esc(reserveLabel(r.id))}</summary><p>${esc(reservePopulation(r))}。原模型 ${esc(r.model_before)} → 后模型 ${esc(r.model_after)}。</p><p>未纳入的页：${esc((r.ineligible?.pages||[]).join('、')||'无')}；未纳入的叶：${esc((r.ineligible?.leaves||[]).join('、')||'无')}。无目标不计零。</p>${reserveTable(['层级 / 位置','该位置平均节省 bits / 目标词'],[...Object.entries(r.per_page_gain||{}).map(([k,v])=>`<tr><th scope="row">页 ${esc(k)}</th><td>${reserveNumber(v)}</td></tr>`),...Object.entries(r.per_leaf_gain||{}).map(([k,v])=>`<tr><th scope="row">叶 ${esc(k)}</th><td>${reserveNumber(v)}</td></tr>`)])}</details>`).join('');
}
function reserveAllographCosts(s){
  const rows=[];
  for(const r of s.metadata.allograph_decompositions){
    const comparison=s.metadata.comparisons.find(c=>c.name===r.name&&c.contrast===r.merge);
    for(const mode of ['old','inline']){
      const c=r.costs?.[mode]||{},base=comparison?.[mode==='old'?'old_baseline':'inline_baseline'];
      rows.push(`<tr><th scope="row">${esc(reserveRepNames[r.name])} · ${esc(r.merge)}</th><td>${mode==='old'?'原页级 H':'展开行内 H'}</td><td>${reserveNumber(base?.pooled)}</td><td>${reserveNumber(c.quotient?.pooled)}</td><td>${reserveNumber(c.restoration?.pooled)}</td><td>${reserveNumber(c.quotient_escape?.pooled)}</td><td>${reserveNumber(c.complete?.pooled)}</td><td>${reserveNumber(c.restoration_global?.pooled)}</td><td>${reserveNumber(c.complete_global?.pooled)}</td></tr>`);
    }
  }
  return `<details class="study-details"><summary>完整成本拆分 · 9 组原页 H 与 9 组行内 H</summary><p>本表采用<strong>所有目标词合并平均（pooled）</strong>，与上方等页、等叶平均增益口径不同。合并流已含未知身份费用；“其中 escape”是拆出的组成部分，<strong>不能再加一次</strong>。缺少的细分以逐词数组为准，不从差值推断。</p>${reserveTable(['表示 / 合并','H 条件','原词成本','合并流成本','条件恢复费','其中 escape','完整成本','总体恢复费','总体恢复完整成本'],rows,'字形恢复成本，按目标词合并平均')}</details>`;
}
function finalReservePanel(s){
  if(!s?.available||s.status!=='independently_reviewed')return '';
  const rows=s.results,main=rows.filter(r=>r.representation==='ZL_EVA'),sens=rows.filter(r=>r.representation!=='ZL_EVA');
  const all=[...rows,...s.global_restoration_sensitivity],meta=s.metadata;
  const positions=Object.entries(s.position_specificity).flatMap(([rep,g])=>Object.entries(g.conditions).map(([stratum,v])=>({rep,stratum,...v})));
  const intervalRows=rows.map(r=>`<tr><th scope="row">${esc(reserveLabel(r.id))}</th><td>${esc(reserveRepNames[r.representation])}</td><td>${reserveInterval(r.bootstrap95)}</td><td>${r.representation==='ZL_EVA'?reserveInterval(r.bootstrap99_5_primary10):'不属于主 ZL 十项族'}</td><td>${reserveInterval(r.bootstrap99_833_all30)}</td><td>${reserveInterval(r.leave_one_leaf_out_range)}</td><td>${reserveNumber(r.pooled_bits_saved)}</td><td>${reserveNumber(r.pooled_before_bits)} → ${reserveNumber(r.pooled_after_bits)}</td></tr>`);
  const exposureRows=all.map(r=>{const e=r.exposure_sensitivity||{};return `<tr><th scope="row">${esc(reserveLabel(r.id))}</th><td>${esc(reserveRepNames[r.representation])}</td><td>${esc((e.omitted_leaves||[]).join('、'))}</td><td>${e.eligible_leaves??'未记录'}</td><td>${reserveNumber(e.mean_leaf_bits_saved)}</td></tr>`;});
  const metadataRows=meta.comparisons.map(r=>`<tr><th scope="row">${esc(reserveLabel(reserveMetaIds[r.contrast]||r.contrast))}</th><td>${esc(reserveRepNames[r.name])}</td><td>${r.targets}</td><td>${reserveNumber(r.old_gain?.mean_leaf)}</td><td>${reserveNumber(r.inline_gain?.mean_leaf)}</td><td>${reserveNumber(r.gain_change?.mean_leaf)}</td><td>${reserveNumber(r.old_gain?.pooled)} → ${reserveNumber(r.inline_gain?.pooled)}</td></tr>`);
  const a=s.assets||{};
  return `<section class="panel journal-panel final-reserve-panel" id="final-reserve"><span class="eyebrow">RESERVED-PAGE REPLICATION</span><h2>保留页上的固定预测检查</h2><p><span class="pill good">执行与独立复核收据已匹配</span></p><p>按开封前方案逐项展示结果，不据大小给语言或机制排名。${s.pages} 页、${s.leaf_groups} 个叶组是分区范围；下方每项各有自己的合格目标数。它们来自同一手稿，并非独立的语言证据。</p><div class="note-strip"><strong>正数表示后模型节省预测成本，负数表示后模型成本更高。</strong>全词、内部词对与段首词是不同目标总体；完整词与原字形恢复费用已经计入。版面和书手标签作为已知条件，其传输费用未计入；这不是译文或完整档案压缩器。</div>
    <h3>主结果 · ZL / EVA 的十项固定比较</h3><p>先取每页目标词平均，再对叶内合格页面等权，最后对合格叶等权。最多 ${s.leaf_groups} 叶；抽样次数不增加独立叶数。主表完整列十项与主十项族区间。</p>${reserveGainTable(main,'bootstrap99_5_primary10','主 ZL 十项族<br>99.5% 区间')}
    ${a.main_figure?`<figure class="study-figure"><img src="${esc(a.main_figure)}" alt="主表示十项固定比较，含零线与各项目标范围" loading="lazy"><figcaption>主表示十项；每格采用自己的横轴，不能按画面长度跨格比较。</figcaption></figure>`:''}
    <details class="study-details"><summary>每项比较能说明什么</summary><ol class="reserve-scopes">${Object.values(reserveContrastLabels).map(([title,scope])=>`<li><strong>${esc(title)}</strong><p>${esc(scope)}</p></li>`).join('')}</ol><p>既有页级 H 未展开 f115r 的行内书手标签，@ 不是第六位书手；修正后的 24 项敏感性在下方完整保留。任何预测收益均不直接识别词义、语言或历史机制。</p></details>
    <details class="study-details"><summary>两种表示敏感性 · 20 项全部结果</summary><p>ZL 合并单位与 IT 转写共享手稿来源，目标数和单位不必一致，不算两次独立证据。</p>${reserveGainTable(sens)}</details>
    ${a.all30_figure?`<details class="study-details"><summary>三种表示的完整对照图</summary><figure class="study-figure"><img src="${esc(a.all30_figure)}" alt="三种表示的全部三十项比较与全族区间" loading="lazy"><figcaption>全三十项族区间；三种表示共享手稿来源。</figcaption></figure></details>`:''}
    <details class="study-details"><summary>全部 30 项区间、词合并均值与留一叶范围</summary><p>95%、主十项族 99.5% 与全部三十项族 99.833333…% 区间原样列出。它们是小叶组样本下的近似百分位 bootstrap，不保证精确同时覆盖。<strong>跨零不等于无效、等效或依赖消失</strong>，一项区间跨零而另一项不跨，也不证明两项有差异。不选择更宽松的区间改写结论。</p>${reserveTable(['比较','表示','95% 区间','主十项族 99.5%','全三十项族 99.833333…%','留一叶均值范围','词合并平均节省','词合并成本 前 → 后'],intervalRows)}<p>零合格叶不估计；只有一叶时不估计区间及留一叶范围。bootstrap 尾比例不是零假设 p 值，也不是假设为真概率。</p></details>
    <details class="study-details"><summary>逐页、逐叶与缺失范围 · 30 项</summary><p>无合格目标的页或叶不填零；未纳入范围与每页、每叶平均值分别记录。</p>${reserveLocationDetails(rows)}</details>
    <details class="study-details"><summary>总体比例恢复辅助对照 · 9 项</summary><p>这九项用总体比例恢复原字形，属于预定辅助敏感性；不代替主表的条件恢复，也不加入主十项族中挑选结果。</p>${reserveGainTable(s.global_restoration_sensitivity,'bootstrap95','描述性 95% 区间')}</details>
    ${reserveAllographCosts(s)}
    <details class="study-details"><summary>上一行位置辅助对照 · 6 项及统一 Holm 参考值</summary><p>只在过去来源行内按精确长度或既定长度桶换位；横向通道、目标、槽位和缺失固定，每个来源行共用一份置换。这是<strong>上一行通道的条件干预</strong>，不是全篇洗牌。原始与六项统一 Holm 尾面积只在该条件可交换性下解释，不能证明或否定历史复制，也不与 bootstrap 区间混算。</p>${reserveTable(['表示 / 分层','原上一行收益','换位均值','差值 D','参考尾面积','六项 Holm'],positions.map(r=>`<tr><th scope="row">${esc(reserveRepNames[r.rep])} / ${r.stratum==='exact'?'精确长度':'粗长度桶'}</th><td>${reserveNumber(r.observed_V_gain)}</td><td>${reserveNumber(r.null_mean)}</td><td>${reserveNumber(r.alignment_specificity_D)}</td><td>${reserveNumber(r.monte_carlo_reference_p,4)}</td><td>${reserveNumber(r.holm_reference_p_family6,4)}</td></tr>`))}${reserveTable(['表示 / 分层','来源行数','有效来源槽','可用上一行目标','身份移动比例','来源集合变化 / 全目标','来源集合变化 / 可用上一行','置换次数','换位分布 95% 范围'],positions.map(r=>`<tr><th scope="row">${esc(reserveRepNames[r.rep])} / ${r.stratum==='exact'?'精确长度':'粗长度桶'}</th><td>${r.source_rows}</td><td>${r.source_valid_slots}</td><td>${r.V_available_targets}</td><td>${reserveNumber(r.source_identity_moved_mean,4)}</td><td>${reserveNumber(r.target_multiset_changed_mean_all_targets,4)}</td><td>${reserveNumber(r.target_multiset_changed_mean_given_V,4)}</td><td>${r.replicates}</td><td>${reserveInterval(r.null95)}</td></tr>`))}<p>换位分布范围是参考分布的描述，不是 D 的置信区间。</p></details>
    <details class="study-details"><summary>曝光叶剔除 · 30 项比较与 9 项恢复辅助的描述性结果</summary><p>主分析保留全部 ${s.pages} 页。本表按预定方案一起剔除 f15、f103 叶，只描述敏感性；不能代替主结果或作为第二次争取阳性的机会。既有锚词、默认种子和全文汇总已有曝光，不能称完全盲。</p>${reserveTable(['比较','表示','一起剔除的叶','剩余合格叶','描述性等叶平均节省'],exposureRows)}</details>
    <details class="study-details"><summary>展开明确行内 H 的敏感性 · 24 项</summary><p>所有旧参数和权重固定，只修正原 IVTFF 可确定的行内 H；旧主数值保留。此处无新增 p 值或区间，也没有重新选参。平均增益的变化不是逐词影响上界。</p>${reserveTable(['比较','表示','目标词数','旧页 H 等叶增益','行内 H 等叶增益','等叶增益变化','词合并增益 旧 → 新'],metadataRows)}<p>段首四组成本数组的逐值核验：${meta.paragraph_invariance.map(r=>`${esc(reserveRepNames[r.name])}：${r.all_arrays_unchanged?'保持不变':'存在变化，见复核记录'}`).join('；')}。</p><p>逐页、逐叶及新旧基线/模型成本见完整摘要；逐词变化见公开研究数组。</p></details>
    <div class="paper-links">${a.report?`<a href="${esc(a.report)}" download>完整研究报告 ↓</a>`:''}${a.summary?`<a href="${esc(a.summary)}" download>全部结果摘要 ↓</a>`:''}${a.metadata_summary?`<a href="${esc(a.metadata_summary)}" download>24 项标签敏感性 ↓</a>`:''}${a.review?`<a href="${esc(a.review)}" download>独立复核与哈希 ↓</a>`:''}${a.protocol?`<a href="${esc(a.protocol)}" download>冻结方案 ↓</a>`:''}${a.reporting_scope?`<a href="${esc(a.reporting_scope)}" download>报告解释准则 ↓</a>`:''}${externalLink(s.research_url,'完整保存数组与复现')}</div><p class="updated-label">评分完成：${esc(dateText(s.completed_utc))}；独立复核：${esc(dateText(s.reviewed_utc))}。只有真实保留集完成记录与三份执行 / 复算收据、两份结果摘要哈希全部匹配后，此面板才会展示。</p></section>`;
}
