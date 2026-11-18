(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const states = {active:'窗口进行中',running:'进行中',planned:'计划',awaiting_review:'待复核',partial:'部分记录已保存',complete:'已完成',completed:'已完成',blocked:'待解决条件',paused:'已暂停'};
  const badge = state => `<span class="s7-badge" data-state="${esc(state)}">${esc(states[state] || state)}</span>`;
  const utc = value => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : d.toISOString().replace('T',' ').replace(/\.\d{3}Z$/,' UTC');
  };
  const links = rows => rows.map(r=>`<a href="${esc(r.href)}">${esc(r.label)} ↗</a>`).join('');

  function moduleMarkup(key, module) {
    let body = `<article class="s7-module" id="s7-${esc(key)}"><div class="s7-module-head"><h3>${esc(module.title)}</h3>${badge(module.status)}</div><p class="s7-module-summary">${esc(module.summary)}</p>`;
    if (module.metrics?.length) body += `<div class="s7-module-metrics">${module.metrics.map(r=>`<div class="s7-module-metric"><strong>${esc(r.value)}</strong><span>${esc(r.label)}</span></div>`).join('')}</div>`;
    if (module.details?.length) body += `<ul class="s7-module-details">${module.details.map(text=>`<li>${esc(text)}</li>`).join('')}</ul>`;
    if (module.table?.rows?.length) body += `<div class="s7-table-wrap"><table class="s7-table"><thead><tr>${module.table.headers.map(x=>`<th scope="col">${esc(x)}</th>`).join('')}</tr></thead><tbody>${module.table.rows.map(row=>`<tr>${row.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    if (module.links?.length) body += `<div class="s7-links">${links(module.links)}</div>`;
    return body + '</article>';
  }

  async function init() {
    try {
      const response = await fetch('data/semantic7h.json');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.schema_version !== 1) throw new Error('Unsupported snapshot');
      $('s7-window-time').textContent = `${utc(data.window.start_utc)} → ${utc(data.window.deadline_utc)}`;
      $('s7-local-time').textContent = `芝加哥时间：${data.window.local_window}`;
      $('s7-window-status').textContent = states[data.window.status] || data.window.status;
      $('s7-window-status').dataset.state = data.window.status;
      $('s7-snapshot-time').textContent = `快照生成于 ${utc(data.snapshot_utc)}`;
      const hours = Math.floor(data.snapshot_elapsed_seconds / 3600);
      const minutes = Math.floor(data.snapshot_elapsed_seconds % 3600 / 60);
      $('s7-elapsed').textContent = `该快照距登记开始约 ${hours} 小时 ${minutes} 分钟；不是完成比例。`;
      $('s7-stage-list').innerHTML = data.stages.map(s=>`<li><span class="s7-stage-number">${s.stage}</span><h3>${esc(s.title)}</h3>${badge(s.status)}</li>`).join('');
      $('s7-findings').innerHTML = data.findings.map(x=>`<p class="s7-finding">${esc(x)}</p>`).join('');
      $('s7-modules').innerHTML = Object.entries(data.modules).map(([key,value])=>moduleMarkup(key,value)).join('');
      $('s7-plan-text').textContent = data.plan;
      $('s7-download-list').innerHTML = data.downloads.length ? links(data.downloads) : '<span class="s7-muted">下载文件尚在整理，可先查看下方研究目录。</span>';
      $('s7-load-state').textContent = '已载入保存记录。未审核的实验结果不会在此快照中预填。';
    } catch (error) {
      $('s7-load-state').textContent = '快照未能加载。请查看本页底部的研究目录；页面不会推测任务状态或填入示例结果。';
      $('s7-load-state').classList.add('s7-error');
    }
  }
  init();
})();
