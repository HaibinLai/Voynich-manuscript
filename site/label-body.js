(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const pct = value => value == null ? '无支持' : `${(value * 100).toFixed(3)}%`;
  const pp = value => value == null ? '无支持' : `${value > 0 ? '+' : ''}${(value * 100).toFixed(4)}`;
  const color = value => value > 0 ? 'lb-positive' : value < 0 ? 'lb-negative' : '';
  const cell = value => `<td class="${color(value)}">${pp(value)}</td>`;
  const table = (headers, rows) => `<table class="lb-table"><thead><tr>${headers.map(h => `<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`;
  const names = {A:'天文（不含黄道）',B:'浴疗／生物',C:'宇宙图',H:'草药',P:'医药',S:'带星记号段落',T:'文字页',Z:'黄道'};
  let data;

  function candidateCard(row, version) {
    const r = row[version];
    const positions = [...new Set(r.body_hits.map(h => h.locator))];
    return `<article class="lb-candidate"><code>${esc(row.word)}</code><p class="lb-location">标签 ${esc(row.locator)} · ${esc(r.type)}</p><p>本页命中 <strong>${r.own_m} / ${r.own_n}</strong> 个同长度词次</p><p class="${positions.length ? '' : 'lb-empty'}">${positions.length ? '正文位置：' + positions.map(esc).join('、') : '正文中未找到精确同词。'}</p><p>${r.control_leaves} 个对照叶 · 本页减对照 ${pp(r.delta)} 百分点</p></article>`;
  }

  function render() {
    const version = $('lb-version').value;
    const r = data.results[version], s = r.main.exact.summary;
    $('lb-status').textContent = `${version}：${s.labels} 个可比标签位置，${s.pages} 个分面，${s.leaves} 个物理叶。切换只改变保存结果的展示。`;
    $('lb-metrics').innerHTML = [
      [pp(s.delta), '百分点 · 本页减相近异叶'],
      [`${s.labels} / ${s.leaves}`, '可比标签位置 / 物理叶'],
      [`${s.labels_with_own_match}`, '标签位置在本页至少命中一次'],
    ].map(([value,label]) => `<div class="lb-metric"><strong>${value}</strong><span>${label}</span></div>`).join('');
    const excluded = r.main.exact.excluded;
    $('lb-main-description').innerHTML = `<p>同长度机会校正后，本页加权命中率为 <strong>${pct(s.own)}</strong>，相近异叶为 <strong>${pct(s.control)}</strong>。${r.inventory.complete_singleword_labels} 个完整单词标签中，${excluded.insufficient_own_length_opportunities || 0} 个缺少本页同长度正文机会，${excluded.insufficient_other_leaf_controls || 0} 个缺少异叶对照。数百个标签只覆盖 ${s.leaves} 个可比物理叶。</p>`;
    $('lb-sections').innerHTML = table(['插图类别','标签位置','物理叶','本页 − 对照（百分点）'],Object.entries(r.by_illustration).map(([key,x])=>`<tr><th scope="row">${esc(names[key] || key)} · ${esc(key)}</th><td>${x.labels}</td><td>${x.leaves}</td>${cell(x.delta)}</tr>`));
    const leaves = s.by_leaf;
    const max = Math.max(...leaves.map(x => Math.abs(x.delta)), 0.001);
    $('lb-leaf-chart').innerHTML = '<div class="lb-chart-heading"><span>← 对照更高</span><span>零线</span><span>本页更高 →　百分点</span></div>' + leaves.map(x => {
      const width = Math.abs(x.delta)/max * 48;
      const left = x.delta < 0 ? 50-width : 50;
      return `<div class="lb-chart-row"><span class="lb-chart-label">${esc(x.leaf)}</span><span class="lb-chart-track"><span class="lb-chart-bar ${x.delta < 0 ? 'negative' : ''}" style="left:${left.toFixed(4)}%;width:${width.toFixed(4)}%"></span></span><span class="lb-chart-value ${color(x.delta)}">${pp(x.delta)}</span></div>`;
    }).join('');
    $('lb-leaf-chart').setAttribute('aria-label', `${version} 逐叶本页减对照率差，单位百分点；完整数值位于下一项表格。`);
    $('lb-leaf-table').innerHTML = table(['物理叶','分面','标签位置','本页 − 对照（百分点）'],leaves.map(x=>`<tr><th scope="row">${esc(x.leaf)}</th><td>${x.pages}</td><td>${x.labels}</td>${cell(x.delta)}</tr>`));
    $('lb-model-table').innerHTML = table(['匹配规则','本页率','对照率','差（百分点）','比精确新增（百分点）'],Object.entries(r.main).map(([key,x])=>`<tr class="${key === 'kt' ? 'lb-highlight' : ''}"><th scope="row">${key === 'exact' ? '完整词精确匹配' : key.split('').join(' / ') + ' 单次替换'}</th><td>${pct(x.summary.own)}</td><td>${pct(x.summary.control)}</td>${cell(x.summary.delta)}${cell(x.summary.delta-s.delta)}</tr>`));
    const variants = {HIQ:'再匹配册帖',min5:'各页 ≥5 机会，≥2 异叶',certain_loci:'仅无不确定空格的位置',dedup_labels:'每页相同标签只计一次'};
    $('lb-sensitivity').innerHTML = table(['精确匹配的口径','标签位置','物理叶','差（百分点）'],Object.entries(r.sensitivity).map(([key,x])=>`<tr><th scope="row">${esc(variants[key])}</th><td>${x.summary.labels}</td><td>${x.summary.leaves}</td>${cell(x.summary.delta)}</tr>`));
    const deletion = r.leave_one_leaf_out.map(x=>x.summary.delta).filter(x=>x!=null);
    $('lb-delete').innerHTML = `<p>逐一删去每个目标叶，并同时移除它作为其他标签的对照，重新判断资格。${deletion.length} 次结果介于 <strong>${pp(Math.min(...deletion))} 至 ${pp(Math.max(...deletion))} 百分点</strong>。${deletion.every(x=>x>0) ? '这些单叶删除均保留正方向；这不等于各章节都有同样的关联。' : '部分删除改变方向，说明汇总依赖具体支持。'}</p>`;
    const c = data.calibration[version];
    $('lb-calibration').innerHTML = `<article><h3>独立随机标签</h3><strong>${pp(c.mean_delta.independent)}</strong><p>百分点 · ${c.seeds} 个种子的平均差。种子间标准差 ${(c.independent_std*100).toFixed(4)}，范围 ${pp(c.independent_range[0])} 至 ${pp(c.independent_range[1])} 百分点。保留真实页、长度、机会数和对照结构，词身份从 ${c.vocabulary_size} 种抽象身份中均匀生成。</p></article><article><h3>从本页复制标签</h3><strong>${pp(c.mean_delta.copy_from_own)}</strong><p>百分点 · 同一规模、同一评分程序的植入复制正控。较大正差只说明程序能识别这个规定的机制。</p></article>`;
    const cand = data.candidates;
    $('lb-candidate-counts').textContent = `两版共有 ${cand.common} 个相同定位、相同完整写法且可比的标签：${cand.hit_count} 个两版都在本页命中，${cand.no_hit_count} 个两版都未命中，${cand.discordant_count} 个命中状态不同。它们不是 ${cand.common} 个独立对象。`;
    $('lb-hits').innerHTML = cand.hits.map(x=>candidateCard(x,version)).join('');
    $('lb-no-hits').innerHTML = cand.no_hits.map(x=>candidateCard(x,version)).join('');
    $('lb-snapshot').textContent = `结果快照：${data.snapshot.replace('T',' ').replace('+00:00',' UTC')}`;
    const url = new URL(location.href); url.searchParams.set('version',version); history.replaceState(null,'',url);
  }

  async function init() {
    try {
      const response = await fetch('data/label-body.json');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      data = await response.json();
      if (data.schema_version !== 1 || !data.results.ZL || !data.results.IT) throw new Error('Unsupported snapshot');
      const requested = new URLSearchParams(location.search).get('version');
      if (['ZL','IT'].includes(requested)) $('lb-version').value=requested;
      render(); $('lb-version').disabled=false; $('lb-version').addEventListener('change',render);
    } catch (error) {
      $('lb-status').textContent = '结果未能加载。请使用本页底部的中文报告与数据下载；页面不会填入示例结果。';
      $('lb-status').classList.add('lb-error');
    }
  }
  init();
})();
