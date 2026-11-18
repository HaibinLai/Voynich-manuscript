(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const frac = v => v == null ? '未识别' : v.exact;
  const number = v => v.numerator / v.denominator;
  const status = value => value === 1 ? '完整名称已出现' : value === 0 ? '给定完整文字中未出现' : '存在未知内容，不能判定未出现';
  let data, current;
  function detail(i, j) {
    const label = current.labels[i], group = current.groups[j];
    const cell = current.cells.find(c => c.row === i && c.column === j);
    const witnesses = cell.witnesses.map(w => `<li>${esc(w.block_id)}：<code>${esc(w.source_items.map(t => t.token).join(' '))}</code>；源字段 ${esc(w.source_items[0].source_field_id)}，字符区间 ${esc(w.source_items[0].source_interval.join('–'))}（包含该词的来源片段）。</li>`).join('');
    const unknowns = group.blocks.flatMap(b => b.segments.filter(s => s.state === 'unknown_content').map(s => `${b.id} / ${s.id}`));
    $('wind-cell-detail').innerHTML = `<h3>${esc(label.given_text)} → ${esc(group.catalogue_id)} / ${esc(group.visual_id)}</h3><p><strong>${status(cell.value)}</strong>${i === j ? '；这是冻结的自身对应。' : '；这是其他说明组。'}</p><p>名称原始联合／目录字段：</p><pre>${esc(label.raw_catalogue_field)}</pre><p>说明的目录原串（保留编辑符号，不当作完整原图认证）：</p><pre>${esc(group.raw_catalogue_field)}</pre>${witnesses ? `<p>已知完整出现的来源：</p><ul>${witnesses}</ul>` : '<p>没有在已知连续片段内找到完整名称。</p>'}${unknowns.length ? `<p>保留的未知内容：</p><ul>${unknowns.map(v => `<li>${esc(v)}</li>`).join('')}</ul><p>这些未知内容不记作零，也不跨过去拼接词组。</p>` : '<p>本条件输入没有另列未知片段；这仍以目录给定读法为前提。</p>'}`;
  }
  function render() {
    current = data.cases.find(c => c.folio === $('wind-leaf').value && c.regime === $('wind-regime').value);
    if (!current) throw new Error('Missing fixed case');
    $('wind-case-note').textContent = current.note;
    $('wind-matrix').innerHTML = `<table class="wind-table"><thead><tr><th scope="col">名称 / 说明</th>${current.groups.map(g => `<th scope="col" title="${esc(g.visual_id)}">${esc(g.catalogue_id)}</th>`).join('')}</tr></thead><tbody>${current.labels.map((label,i) => `<tr><th scope="row">${esc(label.given_text)}</th>${current.values[i].map((v,j) => `<td><button class="${v === 1 ? 'wind-one' : v === 0 ? 'wind-zero' : 'wind-na'} ${i === j ? 'wind-self' : ''}" data-row="${i}" data-column="${j}" aria-label="${esc(label.given_text)}，说明${esc(current.groups[j].catalogue_id)}：${status(v)}${i === j ? '，自身对应' : ''}">${v == null ? '?' : v}</button></td>`).join('')}</tr>`).join('')}</tbody></table>`;
    $('wind-matrix').onclick = event => {const b=event.target.closest('button[data-row]');if(b) detail(Number(b.dataset.row),Number(b.dataset.column));};
    const stats=current.statistics;
    $('wind-phases').innerHTML=stats.phases.map(p=>`<div class="wind-phase"><div class="wind-phase-track" role="img" aria-label="${p.shift===0?'自身对应':'错位'+p.shift}：${frac(p.lower)}至${frac(p.upper)}"><div class="wind-phase-range" style="height:${number(p.upper)*100}%"></div><div class="wind-phase-known" style="height:${number(p.lower)*100}%"></div></div><small>${p.known_hits}${p.measurement_unknowns?`–${p.known_hits+p.measurement_unknowns}`:''}/12</small><strong>${p.shift===0?'自身':'错位 '+p.shift}</strong></div>`).join('');
    const delta=stats.Delta_nonself_primary, auxiliary=stats.Delta_all_phases_auxiliary;
    $('wind-statistics').innerHTML=`<h3>自身对应是否有优势？</h3><p>自身出现比例：${stats.self_point ? `${stats.phases[0].known_hits}/12` : `${stats.phases[0].known_hits}–${stats.phases[0].known_hits+stats.phases[0].measurement_unknowns}/12`}。</p><p><strong>主量：自身比例 − 十一种错位的平均比例</strong><br>${delta.point ? frac(delta.point) : `保守范围 ${frac(delta.lower)} 至 ${frac(delta.upper)}；完整点估计未识别。`}</p><p>辅助量（减去含自身的十二相位平均）：${auxiliary.point ? frac(auxiliary.point) : `${frac(auxiliary.lower)} 至 ${frac(auxiliary.upper)}`}。主量是辅助量的 12/11 倍，两个分母不混用。</p><p>${stats.ties ? `自身描述性名次范围 ${stats.ties.self_rank_interval.join('–')}；所有最高相位：${stats.ties.maximizing_shifts.join('、')}。不是 p 值。` : '存在未知单元，不编造精确名次或唯一最高相位。'}</p>`;
    const source=data.images.find(x=>x.folio===current.folio);
    $('wind-image').width=source.width;$('wind-image').height=source.height;if($('wind-image').getAttribute('src')!==source.url){$('wind-image-state').textContent='正在等待馆方原图加载；可点击图片区域打开馆藏页。';$('wind-image').src=source.url;}$('wind-image').alt=`Walters W.73 ${current.folio} 官方风图`;$('wind-image-link').href=source.item_url;
    $('wind-image-caption').textContent=source.caption;
    detail(0,0);
  }
  const version=document.querySelector('meta[name="wind-snapshot"]').content;
  fetch(`data/wind-calibration.json?v=${encodeURIComponent(version)}`,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('Result unavailable');return r.json();}).then(value=>{
    data=value;
    $('wind-image').addEventListener('load',()=>{$('wind-image-state').textContent='馆方原图已完整载入。';});
    $('wind-image').addEventListener('error',()=>{$('wind-image-state').textContent='馆方图片暂未载入；点击图片区域可查看官方馆藏页。计算结果来自已冻结文本，不以图片加载状态替代。';});
    $('wind-findings').innerHTML=data.findings.map(p=>`<p class="wind-finding">${esc(p)}</p>`).join('');
    $('wind-links').innerHTML=data.links.map(l=>`<a href="${esc(l.href)}">${esc(l.label)} ↗</a>`).join('');
    for(const id of ['wind-leaf','wind-regime']){$(id).disabled=false;$(id).addEventListener('change',render);}
    render();$('wind-state').textContent='已载入两页、两种给定读法的完整条件结果；所有未知单元保留。';
    $('wind-snapshot').textContent=`发布快照 ${data.snapshot_utc}。这是冻结结果展示，不监视后台任务。`;
  }).catch(()=>{$('wind-state').textContent='冻结结果暂未完整载入；不使用示例数值替代，请查看研究进度页的报告。';});
})();
