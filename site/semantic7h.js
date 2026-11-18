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
  let gallery = [], galleryGeneration = 0;
  const grades = {A:'作者认为看似同一植物',S:'作者认为有些形态相似',P:'经 Zandbergen 转述 Petersen',U:'转述 Petersen，来源明确仍待核查'};

  function renderGallery() {
    const row=gallery.find(r=>r.pair_id===$('s7-pair').value) || gallery[0];
    if (!row) return;
    const index=gallery.indexOf(row), generation=++galleryGeneration;
    $('s7-pair-prev').disabled=index===0; $('s7-pair-next').disabled=index===gallery.length-1;
    const partial=row.comparison_decision==='suitable_for_partial_shape_comparison';
    let meta=`<div class="s7-gallery-meta"><span class="s7-badge" data-state="partial">观察已记录</span><strong>${partial?'可作局部形态比较':'证据有限或含混'}</strong><span>来源等级 ${esc(row.prior_grade)}：${esc(grades[row.prior_grade] || row.prior_grade)}</span><a href="${esc(row.prior_source)}">看作者原假说 ↗</a></div>`;
    if (row.fragment_id===110) meta+='<p class="s7-gallery-warning">#110 保留为同一个图像假说；标签由两个位置、三个词组成（otal / chor.olekor），整组未进入单词标签的主分析。没有从中挑一个词救回匹配。</p>';
    if (row.canvas_note) meta+='<p class="s7-gallery-warning">#136 的工作目标页号为 f90v2，但耶鲁画布标题为 90r。记录保留这一标题冲突；本轮按来源链接与图像对应采用该画布，没有裁决历史正反页编号。</p>';
    $('s7-gallery-meta').innerHTML=meta;
    $('s7-gallery-state').textContent=`第 ${index+1} / ${gallery.length} 对：正在加载当前两张官方裁区。`;
    $('s7-gallery-images').innerHTML=['source','target'].map(side=>{
      const a=row[side],source=side==='source';
      return `<figure><a class="s7-image-frame" href="${esc(a.native_crop_url)}" aria-label="打开${source?'来源片段':'目标图像'}的官方原尺寸裁区"><img id="s7-image-${side}" src="${esc(a.crop_url)}" alt="${source?'来源片段 #'+row.fragment_id+'，'+row.source_folio:'文献指定目标 '+row.target_folio}：耶鲁原图的近似对象阅读裁区" decoding="async"></a><figcaption><strong>${source?'来源片段 #'+row.fragment_id+' · '+esc(row.source_folio):'文献目标 · '+esc(row.target_folio)}</strong><p>馆藏画布标题：${esc(a.manifest_label)}</p>${source?`<p>候选标签位置：${row.candidate_locators.map(esc).join('、')}</p>`:''}<div class="s7-links"><a href="${esc(a.source_url)}">查看完整原图</a><a href="${esc(a.native_crop_url)}">原尺寸裁区</a></div></figcaption></figure>`;
    }).join('');
    $('s7-gallery-notes').innerHTML=`<article><h3>观察到的相似处</h3><p>${esc(row.similarity_zh)}</p></article><article><h3>差异与缺失的信息</h3><p>${esc(row.difference_zh)}</p></article><details class="s7-image-original"><summary>查看冻结记录中的原始英文描述</summary><p>Similarities</p><ul>${row.original_similarities.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>Differences and missing evidence</p><ul>${row.original_differences.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`;
    const imageStates=new Map();
    const settled=()=>{if(generation!==galleryGeneration)return;const loaded=[...imageStates.values()].filter(x=>x==='loaded').length,failed=[...imageStates.values()].filter(x=>x==='failed').length;const prefix=`第 ${index+1} / ${gallery.length} 对：`;$('s7-gallery-state').textContent=failed?prefix+'官方裁图暂未全部加载，可打开完整原图或原尺寸裁区。':loaded===2?prefix+'两张官方裁区已加载。相似处不认证对象身份。':prefix+`已加载 ${loaded} / 2 张官方裁区。`;};
    for (const side of ['source','target']) {
      const img=$('s7-image-'+side);
      img.addEventListener('load',()=>{imageStates.set(side,'loaded');settled();},{once:true});
      img.addEventListener('error',()=>{imageStates.set(side,'failed');settled();},{once:true});
      if(img.complete)imageStates.set(side,img.naturalWidth>0?'loaded':'failed');
    }
    settled();
    const url=new URL(location.href);url.searchParams.set('pair',row.pair_id);history.replaceState(null,'',url);
  }

  function setupGallery(rows) {
    gallery=rows || [];
    if(!gallery.length)return;
    $('s7-gallery').hidden=false;
    $('s7-pair').innerHTML=gallery.map(r=>`<option value="${esc(r.pair_id)}">#${r.fragment_id} · ${esc(r.source_folio)} → ${esc(r.target_folio)}${r.fragment_id===110?' · 多词组，未入主分析':''}</option>`).join('');
    const requested=new URL(location.href).searchParams.get('pair');
    $('s7-pair').value=gallery.some(r=>r.pair_id===requested)?requested:gallery[0].pair_id;
    $('s7-pair').disabled=false;
    $('s7-pair').addEventListener('change',renderGallery);
    $('s7-pair-prev').addEventListener('click',()=>{const i=gallery.findIndex(r=>r.pair_id===$('s7-pair').value);if(i>0){$('s7-pair').value=gallery[i-1].pair_id;renderGallery();}});
    $('s7-pair-next').addEventListener('click',()=>{const i=gallery.findIndex(r=>r.pair_id===$('s7-pair').value);if(i<gallery.length-1){$('s7-pair').value=gallery[i+1].pair_id;renderGallery();}});
    renderGallery();
    if(location.hash==='#s7-gallery') $('s7-gallery').scrollIntoView();
  }

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
      setupGallery(data.gallery);
      $('s7-load-state').textContent = '已载入保存记录。未审核的实验结果不会在此快照中预填。';
    } catch (error) {
      $('s7-load-state').textContent = '快照未能加载。请查看本页底部的研究目录；页面不会推测任务状态或填入示例结果。';
      $('s7-load-state').classList.add('s7-error');
    }
  }
  init();
})();
