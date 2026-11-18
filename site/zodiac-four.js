(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const ns = 'http://www.w3.org/2000/svg';
  const colors = ['#14695d','#9c426d','#254fa4','#9c6520','#5d3999','#a33122','#565d27','#197586','#8d4e35'];
  const ringName = value => ({outer:'外环',inner:'内环'}[value] || text(value));
  const text = value => value == null ? '未确定' : Array.isArray(value) ? value.join('、') : String(value);
  const json = value => esc(JSON.stringify(value,null,2));
  const option = (value,label) => { const el=document.createElement('option');el.value=value;el.textContent=label;return el; };
  const table = (heads,rows) => `<table class="z4-table"><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${esc(text(cell))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  let data, panel, visible=[], selected='', generation=0;
  const layers = new Map();
  const findRecord = key => panel.records.find(row=>row.key===key);
  function originals(records) {
    return records.map(row=>`<h4>${esc(row.id)} · 完整双版原行</h4><div class="z4-originals">${['ZL','IT'].map(version=>{const source=row.raw.sources[version];return `<div><h4>${version}</h4><code>${esc(source.raw_line)}</code><p>来源行号 ${esc(source.source_line)}；保留原标点、标签、逗号和字形备选，不在这里规范化。</p></div>`;}).join('')}</div>`).join('');
  }
  function related(row) {
    const c=panel.comparison;
    let pairs=[], imageSide=false;
    if(row.layer==='lz') pairs=c.all_coarse_rectangle_pairs.filter(p=>p.guided_id===row.id);
    if(row.layer==='coarse') {pairs=c.all_coarse_rectangle_pairs.filter(p=>p.image_id===row.id);imageSide=true;}
    if(row.layer==='fine') {pairs=c.all_fine_alternative_rectangle_pairs.filter(p=>p.image_id===row.id);imageSide=true;}
    if(row.layer==='cc') pairs=c.all_ring_envelope_pairs.filter(p=>p.guided_id===row.id);
    if(row.layer==='ring') {pairs=c.all_ring_envelope_pairs.filter(p=>p.image_id===row.id);imageSide=true;}
    if(row.layer==='guided_objects') pairs=c.all_object_envelope_pairs.filter(p=>p.guided_id===row.id);
    if(row.layer==='objects') {pairs=c.all_object_envelope_pairs.filter(p=>p.image_id===row.id);imageSide=true;}
    const positive=pairs.filter(p=>p.intersection_px2>0);
    const sourceRecords=imageSide ? [...new Set(positive.map(p=>p.guided_id))].map(id=>panel.records.find(r=>r.id===id && ['lz','cc'].includes(r.layer))).filter(Boolean) : row.raw.sources ? [row] : [];
    return {pairs,positive,sourceRecords};
  }
  function selectRecord(key) {
    selected=key;
    $('z4-record').value=key;
    for(const rect of $('z4-boxes').children) { const active=rect.dataset.record===key;rect.classList.toggle('selected',active);rect.setAttribute('aria-pressed',String(active)); }
    const row=findRecord(key);
    if(!row) { $('z4-detail').innerHTML='<p>选择图层后，点击工作框或使用记录下拉列表，查看原坐标、双方候选和完整双版原行。</p>';return; }
    const raw=row.raw,[x1,y1,x2,y2]=row.bbox,rel=related(row);
    const coarseParent=row.layer==='fine' ? panel.records.find(r=>r.layer==='coarse' && r.id===raw.coarse_parent_id) : row.layer==='coarse' ? row : null;
    const grouping=coarseParent?.raw;
    const guideRows=rel.sourceRecords.filter(r=>r.layer==='lz');
    const imageRows=row.layer==='lz' ? rel.positive.map(p=>panel.records.find(r=>r.layer==='coarse'&&r.id===p.image_id)).filter(Boolean) : coarseParent ? [coarseParent] : [];
    const ownerLines=[...guideRows.map(r=>`<p><strong>来源侧 ${esc(r.id)}：</strong>工作候选 ${esc(text(r.raw.primary_candidate_complex))}；相邻备选 ${esc(text(r.raw.adjacent_alternative_complexes))}。人物／星形／容器等解释未唯一确定。</p>`),...imageRows.map(r=>`<p><strong>图像侧 ${esc(r.id)}：</strong>邻近复合体候选 ${esc(text(r.raw.nearby_complex_candidates))}，不排序、不认证文字归属；该粗区登记的空间分组备选为 ${esc(text(r.raw.grouping_count_options))}，词界仍未决。</p>`)];
    const ring=['cc','ring'].includes(row.layer);
    $('z4-detail').innerHTML=`<h3>${esc(row.id)}<small>${esc(layers.get(row.layer).label)}</small></h3><dl><dt>完整画布坐标</dt><dd>左上 (${x1}, ${y1}) → 右下 (${x2}, ${y2}) 像素</dd><dt>工作框大小</dt><dd>${x2-x1} × ${y2-y1} 像素；画布 ${panel.dimensions.join(' × ')}</dd><dt>当前图面</dt><dd>${esc(panel.id)}；${esc(ringName(raw.band||raw.ring_assignment||raw.ring))}</dd></dl>${ring?'<p class="z4-boundary">这是环文外接包络，矩形包含圆盘内部的其他内容。框的相交不能定位环上墨迹、首字或词序，也不用于自动配环。</p>':'<p class="z4-muted">近似工作阅读范围，不是精确字形轮廓或词界。</p>'}${grouping?`<div class="z4-split"><p><strong>分组仍未决：</strong>${esc(grouping.id)} 登记的空间分组数量备选为 ${esc(text(grouping.grouping_count_options))}。${grouping.finer_visible_subcluster_alternative_boxes_xyxy.length?'已保留具体细分框，可切换“细分备选”图层。':'未登记更细分框，也不等于确认只有一个词。'}这些选项不是所有可能词界的穷举。</p></div>`:''}${raw.description?`<p><strong>原始观察（保留原文）：</strong>${esc(raw.description)}</p>`:''}${ownerLines.join('')}${rel.pairs.length?`<h4>另一观察的全部正面积交集候选</h4><p class="z4-muted">${rel.positive.length} 个正交集 / ${rel.pairs.length} 个矩形对；${ring?'包络交集不用于唯一配环。':'不按最大交集删去其他候选。'}</p><div class="z4-table-wrap">${table(['来源记录','图像记录','来源框 xyxy','图像框 xyxy','交集像素²'],rel.positive.map(p=>[p.guided_id,p.image_id,p.guided_box_xyxy.join(', '),p.image_box_xyxy.join(', '),p.intersection_px2]))}</div>`:''}${originals(rel.sourceRecords)}<details class="z4-fold"><summary>本条记录的完整冻结观察（原文）</summary><pre class="z4-json">${json(raw)}</pre></details>`;
  }
  function view() {
    let box=[0,0,...panel.dimensions];
    if($('z4-view').value==='panel') {const [x1,y1,x2,y2]=panel.viewport;box=[x1,y1,x2-x1,y2-y1];}
    $('z4-svg').setAttribute('viewBox',box.join(' '));$('z4-svg').style.aspectRatio=`${box[2]} / ${box[3]}`;
    $('z4-view-note').textContent=`${$('z4-view').value==='full'?'完整画布':'图像观察已登记的图面阅读视口'}：x=${box[0]}，y=${box[1]}，宽=${box[2]}，高=${box[3]}。${visible.length?`叠加 ${visible.length} 条记录的框`:'无框原图'}；坐标始终属于原始完整画布。`;
  }
  function draw() {
    const active=new Set([$('z4-layer-a').value,$('z4-layer-b').value].filter(Boolean));
    visible=panel.records.filter(row=>active.has(row.layer));
    if(!visible.some(row=>row.key===selected))selected='';
    $('z4-record').replaceChildren(option('',visible.length?'选择一条记录':'先选择图层'));
    for(const row of visible)$('z4-record').add(option(row.key,`${row.id} · ${layers.get(row.layer).label}`));
    $('z4-record').disabled=!visible.length;$('z4-prev').disabled=$('z4-next').disabled=!visible.length;
    $('z4-boxes').replaceChildren();
    for(const row of visible) {
      const [x1,y1,x2,y2]=row.bbox,rect=document.createElementNS(ns,'rect');
      for(const [name,value] of Object.entries({x:x1,y:y1,width:x2-x1,height:y2-y1,'vector-effect':'non-scaling-stroke',tabindex:'0',role:'button','aria-label':`${row.id}，${layers.get(row.layer).label}`,'class':'z4-box'}))rect.setAttribute(name,value);
      rect.dataset.record=row.key;rect.style.setProperty('--box',layers.get(row.layer).color);
      const activate=()=>selectRecord(row.key);rect.addEventListener('focus',activate);rect.addEventListener('click',activate);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}});
      const title=document.createElementNS(ns,'title');title.textContent=`${row.id} · 工作阅读范围`;rect.append(title);$('z4-boxes').append(rect);
    }
    $('z4-legend').innerHTML=[...active].map(id=>`<span><i style="--layer:${layers.get(id).color}" aria-hidden="true"></i>${esc(layers.get(id).label)}</span>`).join('');
    selectRecord(selected);view();
  }
  function register() {
    $('z4-register-groups').innerHTML=data.layers.map(layer=>{
      const rows=panel.records.filter(row=>row.layer===layer.id);
      return `<details class="z4-fold"><summary>${esc(layer.label)} · ${rows.length} 条记录</summary>${rows.map(row=>`<div class="z4-entry"><div><strong>${esc(row.id)}</strong><p>原画布框 [${row.bbox.join(', ')}]${row.raw.grouping_count_options?`；空间分组备选 ${esc(text(row.raw.grouping_count_options))}`:''}</p>${row.raw.sources?`<p>ZL / IT 完整原行均已保存。</p>`:''}</div><button class="z4-show-record" type="button" data-show="${esc(row.key)}">在图中查看</button></div>`).join('')||'<p>本图此类无已登记记录。</p>'}</details>`;
    }).join('');
  }
  function pairs() {
    const rows=panel.comparison[$('z4-pair-kind').value];
    $('z4-pairs').innerHTML=table(['来源记录','图像记录','交集像素²'],rows.map(row=>[row.guided_id,row.image_id,row.intersection_px2]));
  }
  function showPanel() {
    panel=data.panels.find(row=>row.id===$('z4-panel').value);selected='';$('z4-layer-a').value=$('z4-layer-b').value='';$('z4-view').value='full';
    for(const id of ['z4-layer-a','z4-layer-b']) {
      const select=$(id);select.replaceChildren(option('',id==='z4-layer-a'?'无框原图':'不叠加对照'));
      for(const layer of data.layers) select.add(option(layer.id,`${layer.label} · ${panel.records.filter(r=>r.layer===layer.id).length}`));
    }
    const ticket=++generation,img=document.createElementNS(ns,'image');
    img.setAttribute('x','0');img.setAttribute('y','0');img.setAttribute('width',panel.dimensions[0]);img.setAttribute('height',panel.dimensions[1]);
    img.addEventListener('load',()=>{if(ticket===generation)$('z4-image-state').textContent=`${panel.id} · 官方完整画布已载入；${panel.dimensions.join(' × ')} 原生像素。页面仅调整阅读视口和叠加框。`;});
    img.addEventListener('error',()=>{if(ticket===generation)$('z4-image-state').textContent='官方原图暂时未能载入，请使用上方“打开官方完整画布”链接。';});
    $('z4-image-state').textContent='正在载入当前图的官方完整画布。';$('z4-image-host').replaceChildren(img);img.setAttribute('href',panel.url);$('z4-full-link').href=panel.url;
    const s=panel.comparison.summary;
    $('z4-panel-summary').innerHTML=`<p class="z4-count-note">${esc(panel.id)}：来源侧保留 ${s.guided_source_labels} 条 Lz、${s.guided_ring_records} 条 Cc；图像侧登记 ${s.image_coarse_areas} 个粗文字区、${s.image_fine_alternative_units} 个最细已登记替代单元。${s.explicit_split_areas} 个粗区保留细分备选。<strong>这些都是相应粒度下的记录数，不是词数。</strong></p><p>${panel.id==='f72r1'?'本图保留额外的跨环矩形交集，不能在当前规则下给出两环全部唯一对应；请对照 f72r1.10、ZO07 与 ZI05。':'本图的两环粗区域相邻次序在共同换起点后相同；这是几何次序诊断，不代表历史阅读次序或词义对应。'}</p><details class="z4-fold"><summary>环内几何次序及未决连接（完整诊断）</summary><pre class="z4-json">${json(panel.comparison.geometric_cycle_diagnostics)}</pre></details>`;
    register();pairs();draw();
  }
  function render(value) {
    data=value;data.layers.forEach((layer,index)=>layers.set(layer.id,{...layer,color:colors[index]}));
    for(const p of data.panels)$('z4-panel').add(option(p.id,p.id));
    for(const id of ['z4-panel','z4-view','z4-reset','z4-layer-a','z4-layer-b'])$(id).disabled=false;
    $('z4-panel').addEventListener('change',showPanel);$('z4-view').addEventListener('change',view);
    for(const id of ['z4-layer-a','z4-layer-b'])$(id).addEventListener('change',draw);
    $('z4-record').addEventListener('change',()=>selectRecord($('z4-record').value));
    $('z4-reset').addEventListener('click',()=>{$('z4-layer-a').value=$('z4-layer-b').value='';$('z4-view').value='full';selected='';draw();});
    for(const [id,step] of [['z4-prev',-1],['z4-next',1]])$(id).addEventListener('click',()=>{const i=visible.findIndex(row=>row.key===selected);const next=i<0?(step>0?0:visible.length-1):(i+step+visible.length)%visible.length;selectRecord(visible[next].key);});
    $('z4-register-groups').addEventListener('click',event=>{const button=event.target.closest('[data-show]');if(!button)return;const row=findRecord(button.dataset.show);$('z4-layer-a').value=row.layer;$('z4-view').value='panel';selected=row.key;draw();$('z4-viewer').scrollIntoView({block:'start'});});
    $('z4-pair-kind').addEventListener('change',pairs);
    $('z4-report').textContent=data.report;
    $('z4-source-table').innerHTML=table(['明确采用的公开文件','SHA-256'],data.sources.map(row=>[row.name,row.sha256]));
    $('z4-audit-state').textContent=data.status;
    $('z4-downloads').innerHTML=data.sources.map(row=>`<a href="downloads/zodiac-four/${esc(row.name)}">${esc({'image_observation_v1.json':'图像观察完整投影','guided_observation_v1.json':'来源定位与全部142原行','projection_receipt_v1.json':'投影内容核验收据','comparison_v1.json':'全部矩形对与候选','report_v1.txt':'完整协调报告','audit_v1.txt':'另一路实现审核','audit_v1.json':'审核完整数据','audit_addendum_v1.txt':'审核完成补记'}[row.name] || row.name)} ↗</a>`).join('');
    $('z4-snapshot').textContent=`发布快照生成于 ${data.snapshot_utc}。这是明确文件清单生成的静态记录，不监视后台审核状态。`;
    showPanel();$('z4-load-state').textContent='已读取四图记录：全部 60 条 Lz、11 条 Cc 与双版 142 原行保留；细分备选及损伤可逐图查看。';
  }
  const version=document.querySelector('meta[name="zodiac-four-snapshot"]').content;
  fetch(`data/zodiac-four.json?v=${encodeURIComponent(version)}`,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('load');return response.json();}).then(render).catch(()=>{$('z4-load-state').textContent='记录未能完整载入，请刷新或直接阅读下方下载文件；不会使用示例替代原记录。';});
})();
