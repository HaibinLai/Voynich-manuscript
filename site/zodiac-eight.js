(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const ns = 'http://www.w3.org/2000/svg';
  const colors = ['#14695d','#9c426d','#254fa4','#9c6520','#5d3999','#a33122','#565d27','#197586','#8d4e35','#675494'];
  const ringName = value => ({outer:'外环',inner:'内环'}[value] || text(value));
  const text = value => value == null ? '未确定' : Array.isArray(value) ? value.join('、') : String(value);
  const json = value => esc(JSON.stringify(value,null,2));
  const option = (value,label) => { const el=document.createElement('option');el.value=value;el.textContent=label;return el; };
  const table = (heads,rows) => `<table class="z8-table"><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${esc(text(cell))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  let data, panel, visible=[], selected='', generation=0;
  const layers = new Map();
  const findRecord = key => panel.records.find(row=>row.key===key);
  function originals(records) {
    return records.map(row=>`<h4>${esc(row.id)} · 完整双版原行</h4><div class="z8-originals">${['ZL','IT'].map(version=>{const source=row.raw.sources[version];return `<div><h4>${version}</h4><code>${esc(source.raw_line)}</code><p>来源行号 ${esc(source.source_line)}；保留原标点、标签、逗号和字形备选，不在这里规范化。</p></div>`;}).join('')}</div>`).join('');
  }
  const tableNames={short_coarse:'Lz × 粗区',short_fine:'Lz × 细分备选',guided_alternative_coarse:'额外候选 × 粗区',guided_alternative_fine:'额外候选 × 细分备选',continuous_ring_outer_envelopes:'Cc × 环文外包络',continuous_ring_inner_envelopes:'Cc × 环文内包络'};
  const coordinate = box => box ? `[${box.join(', ')}]` : 'NA · 未定位，未绘框';
  function related(row) {
    const names={lz:['short_coarse','short_fine'],alternative:['guided_alternative_coarse','guided_alternative_fine'],coarse:['short_coarse','guided_alternative_coarse'],fine:['short_fine','guided_alternative_fine'],cc:['continuous_ring_outer_envelopes','continuous_ring_inner_envelopes'],ring:['continuous_ring_outer_envelopes'],ring_inner:['continuous_ring_inner_envelopes']}[row.layer]||[];
    const imageSide=['coarse','fine','ring','ring_inner'].includes(row.layer), results=[];
    for(const name of names) {
      const t=panel.comparison[name];
      for(const pair of t.all_pairs.filter(p=>(imageSide?p.image_id:p.guided_id)===row.id))
        results.push({...pair,kind:name,guided_box:t.guided_regions.find(r=>r.id===pair.guided_id)?.box_xyxy,image_box:t.image_regions.find(r=>r.id===pair.image_id)?.box_xyxy});
    }
    const positives=results.filter(p=>p.positive===true), ids=new Set();
    if(row.raw.sources)ids.add(row.id);
    if(row.parent)ids.add(row.parent);
    for(const p of positives)ids.add(p.guided_id.split('#candidate')[0]);
    return {results,positives,sources:[...ids].map(id=>panel.records.find(r=>r.id===id&&['lz','cc'].includes(r.layer))).filter(Boolean)};
  }
  function selectRecord(key) {
    selected=key;$('z8-record').value=key;
    for(const rect of $('z8-boxes').children){const active=rect.dataset.record===key;rect.classList.toggle('selected',active);rect.setAttribute('aria-pressed',String(active));}
    const row=findRecord(key);
    if(!row){$('z8-detail').innerHTML='<p>选择图层与条目后查看原画布坐标、另一侧全部正交集候选及完整双版原行。NA 条目也可以选择。</p>';return;}
    const rel=related(row), raw=row.raw, isRing=['cc','ring','ring_inner'].includes(row.layer);
    const parent=row.layer==='fine'?panel.records.find(r=>r.layer==='coarse'&&r.id===raw.coarse_parent_id):row.layer==='coarse'?row:null;
    const candidateRows=row.parent?panel.records.filter(r=>r.id===row.parent&&r.layer==='lz'):panel.records.filter(r=>r.parent===row.id);
    const absent=rel.results.filter(p=>p.positive===null).length;
    const measured=rel.results.length-absent;
    const intersectionNote=measured ? `已测 ${measured} 个矩形对，其中 ${rel.positives.length} 个正交集；交集未定：${absent} 个 NA 配对。` : `交集未定：${absent} 个 NA 配对；没有可报告的已测交集。`;
    $('z8-detail').innerHTML=`<h3>${esc(row.id)}<small>${esc(layers.get(row.layer).label)}</small></h3>
      <dl><dt>完整画布坐标 xyxy</dt><dd class="${row.bbox?'':'z8-na'}">${esc(coordinate(row.bbox))}</dd><dt>原始 xywh</dt><dd>${esc(text(raw.working_bbox_xywh||raw.bbox_xywh||(row.bbox?[row.bbox[0],row.bbox[1],row.bbox[2]-row.bbox[0],row.bbox[3]-row.bbox[1]]:null)))}</dd><dt>画布 / 图面</dt><dd>${panel.dimensions.join(' × ')} / ${esc(panel.id)}</dd><dt>登记环层</dt><dd>${esc(text(raw.band||raw.ring_assignment||raw.ring))}</dd></dl>
      ${!row.bbox?'<p class="z8-boundary">NA：本来源条目没有已冻结主工作框。不会绘成零尺寸框，也不会用额外候选补成已定位。</p>':''}
      ${row.parent?`<p class="z8-boundary">独立备选：所属来源 ${esc(row.parent)}。候选框不改变该条目主框的 NA 状态；并非额外词或额外来源条目。</p>`:''}
      ${isRing?'<p class="z8-boundary">环文内外包络均为矩形几何范围，不是墨迹蒙版。嵌套包络的交集不能确定环文同一、起点、方向或词序。</p>':'<p class="z8-muted">近似工作阅读范围；不认证共同墨迹、字形、词界或对象归属。</p>'}
      ${parent?`<p class="z8-split">${esc(parent.id)} 的空间分组数量备选：${esc(text(parent.raw.grouping_count_options))}。这些不是语言学词数，也不是穷尽所有可能字界。</p>`:''}
      ${candidateRows.length?`<p>相关主框／额外候选：${candidateRows.map(r=>`${esc(r.id)} ${esc(coordinate(r.bbox))}`).join('；')}。</p>`:''}
      ${raw.description||raw.visual_notes||raw.basis?`<p>冻结观察说明：${esc(raw.description||raw.visual_notes||raw.basis)}</p>`:''}
      ${raw.nearby_complex_candidates?`<p>图像侧邻近复合体候选：${esc(text(raw.nearby_complex_candidates))}。仅为空间邻近线索，不认证文字归属。</p>`:''}
      ${rel.results.length?`<h4>另一侧全部正面积交集候选</h4><p class="z8-muted">${intersectionNote}不同粗细层分开登记，不合计为对象数。不按最大交集删去其他候选。未与已定位框相交不排除与未定位来源有关。</p><div class="z8-table-wrap">${table(['比较层','来源记录','图像记录','来源框 xyxy','图像框 xyxy','交集像素²'],rel.positives.map(p=>[tableNames[p.kind],p.guided_id,p.image_id,coordinate(p.guided_box),coordinate(p.image_box),p.intersection_area]))}</div>`:''}
      ${originals(rel.sources)}<details class="z8-fold"><summary>本条完整冻结观察、对象候选与不确定性（原文）</summary><pre class="z8-json">${json(raw)}</pre></details>`;
  }
  function view() {
    let box=[0,0,...panel.dimensions];
    if($('z8-view').value==='panel') {const [x1,y1,x2,y2]=panel.viewport;box=[x1,y1,x2-x1,y2-y1];}
    $('z8-svg').setAttribute('viewBox',box.join(' '));$('z8-svg').style.aspectRatio=`${box[2]} / ${box[3]}`;
    $('z8-view-note').textContent=`${$('z8-view').value==='full'?'完整画布':'图像观察已登记的图面阅读视口'}：x=${box[0]}，y=${box[1]}，宽=${box[2]}，高=${box[3]}。${visible.length?`可查 ${visible.length} 条记录，其中 ${visible.filter(r=>r.bbox).length} 个框、${visible.filter(r=>!r.bbox).length} 条 NA`:'无框原图'}；坐标始终属于原始完整画布。`;
  }
  function draw() {
    const active=new Set([$('z8-layer-a').value,$('z8-layer-b').value].filter(Boolean));
    visible=panel.records.filter(row=>active.has(row.layer));
    if(!visible.some(row=>row.key===selected))selected='';
    $('z8-record').replaceChildren(option('',visible.length?'选择一条记录':'先选择图层'));
    for(const row of visible)$('z8-record').add(option(row.key,`${row.id}${row.bbox?"":" · NA 未定位"} · ${layers.get(row.layer).label}`));
    $('z8-record').disabled=!visible.length;$('z8-prev').disabled=$('z8-next').disabled=!visible.length;
    $('z8-boxes').replaceChildren();
    for(const row of visible) {
      if(!row.bbox)continue;
      const [x1,y1,x2,y2]=row.bbox,rect=document.createElementNS(ns,'rect');
      for(const [name,value] of Object.entries({x:x1,y:y1,width:x2-x1,height:y2-y1,'vector-effect':'non-scaling-stroke',tabindex:'0',role:'button','aria-label':`${row.id}，${layers.get(row.layer).label}`,'class':'z8-box'}))rect.setAttribute(name,value);
      rect.dataset.record=row.key;rect.style.setProperty('--box',layers.get(row.layer).color);
      const activate=()=>selectRecord(row.key);rect.addEventListener('focus',activate);rect.addEventListener('click',activate);rect.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate();}});
      const title=document.createElementNS(ns,'title');title.textContent=`${row.id} · 工作阅读范围`;rect.append(title);$('z8-boxes').append(rect);
    }
    $('z8-legend').innerHTML=[...active].map(id=>`<span><i style="--layer:${layers.get(id).color}" aria-hidden="true"></i>${esc(layers.get(id).label)}</span>`).join('');
    selectRecord(selected);view();
  }
  function register() {
    $('z8-register-groups').innerHTML=data.layers.map(layer=>{
      const rows=panel.records.filter(row=>row.layer===layer.id);
      return `<details class="z8-fold"><summary>${esc(layer.label)} · ${rows.length} 条记录</summary>${rows.map(row=>`<div class="z8-entry"><div><strong>${esc(row.id)}</strong><p>原画布框 ${esc(coordinate(row.bbox))}${row.raw.grouping_count_options?`；空间分组备选 ${esc(text(row.raw.grouping_count_options))}`:''}</p>${row.raw.sources?`<p>ZL / IT 完整原行均已保存。</p>`:''}</div><button class="z8-show-record" type="button" data-show="${esc(row.key)}">在图中查看</button></div>`).join('')||'<p>本图此类无已登记记录。</p>'}</details>`;
    }).join('');
  }
  function pairs() {
    const rows=panel.comparison[$('z8-pair-kind').value].all_pairs;
    $('z8-pairs').innerHTML=table(['来源记录','图像记录','状态','交集像素²'],rows.map(row=>[row.guided_id,row.image_id,row.status==='measured'?'已计算':'NA · 缺框',row.intersection_area===null?'NA':row.intersection_area]));
  }
  function showPanel() {
    panel=data.panels.find(row=>row.id===$('z8-panel').value);selected='';$('z8-layer-a').value=$('z8-layer-b').value='';$('z8-view').value='full';
    for(const id of ['z8-layer-a','z8-layer-b']) {
      const select=$(id);select.replaceChildren(option('',id==='z8-layer-a'?'无框原图':'不叠加对照'));
      for(const layer of data.layers) select.add(option(layer.id,`${layer.label} · ${panel.records.filter(r=>r.layer===layer.id).length}`));
    }
    const ticket=++generation,img=document.createElementNS(ns,'image');
    img.setAttribute('x','0');img.setAttribute('y','0');img.setAttribute('width',panel.dimensions[0]);img.setAttribute('height',panel.dimensions[1]);
    img.addEventListener('load',()=>{if(ticket===generation)$('z8-image-state').textContent=`${panel.id} · 官方完整画布已载入；${panel.dimensions.join(' × ')} 原生像素。页面仅调整阅读视口和叠加框。`;});
    img.addEventListener('error',()=>{if(ticket===generation)$('z8-image-state').textContent='官方原图暂时未能载入，请使用上方“打开官方完整画布”链接。';});
    $('z8-image-state').textContent='正在载入当前图的官方完整画布。';$('z8-image-host').replaceChildren(img);img.setAttribute('href',panel.url);$('z8-full-link').href=panel.url;
    const sourceRows=panel.records.filter(r=>['lz','cc'].includes(r.layer));
    $('z8-panel-summary').innerHTML=`<p class="z8-count-note">${esc(panel.id)}：保留 ${sourceRows.filter(r=>r.layer==='lz').length} 条 Lz、${sourceRows.filter(r=>r.layer==='cc').length} 条 Cc；${sourceRows.filter(r=>!r.bbox).length} 条主框 NA；${panel.records.filter(r=>r.layer==='alternative').length} 个独立额外候选。<strong>这些是来源记录与候选的条数，不是词数。</strong></p><p>v2 未计算任何环序对照：来源侧没有独立登记的几何环序。来源清单顺序、框中心派生角序都不能补成认证的阅读顺序。人物复合框只在图像侧登记，另一侧没有相应对象框，不能展示两路对象对照结果。</p><details class="z8-fold"><summary>本图未填／不确定区域与来源侧限定（原文）</summary><pre class="z8-json">${json({unfilled_or_uncertain_areas:panel.unfilled_or_uncertain_areas,guided_panel:panel.guided_panel})}</pre></details>`;
    register();pairs();draw();
  }
  function render(value) {
    data=value;data.layers.forEach((layer,index)=>layers.set(layer.id,{...layer,color:colors[index]}));
    for(const p of data.panels)$('z8-panel').add(option(p.id,p.id));
    for(const id of ['z8-panel','z8-view','z8-reset','z8-layer-a','z8-layer-b'])$(id).disabled=false;
    $('z8-panel').addEventListener('change',showPanel);$('z8-view').addEventListener('change',view);
    for(const id of ['z8-layer-a','z8-layer-b'])$(id).addEventListener('change',draw);
    $('z8-record').addEventListener('change',()=>selectRecord($('z8-record').value));
    $('z8-reset').addEventListener('click',()=>{$('z8-layer-a').value=$('z8-layer-b').value='';$('z8-view').value='full';selected='';draw();});
    for(const [id,step] of [['z8-prev',-1],['z8-next',1]])$(id).addEventListener('click',()=>{const i=visible.findIndex(row=>row.key===selected);const next=i<0?(step>0?0:visible.length-1):(i+step+visible.length)%visible.length;selectRecord(visible[next].key);});
    $('z8-register-groups').addEventListener('click',event=>{const button=event.target.closest('[data-show]');if(!button)return;const row=findRecord(button.dataset.show);$('z8-layer-a').value=row.layer;$('z8-view').value='panel';selected=row.key;draw();$('z8-viewer').scrollIntoView({block:'start'});});
    $('z8-pair-kind').addEventListener('change',pairs);
    $('z8-report').textContent=data.report;
    $('z8-source-table').innerHTML=table(['明确采用的公开文件','SHA-256'],data.sources.map(row=>[row.name,row.sha256]));
    $('z8-audit-state').textContent=data.status;
    $('z8-downloads').innerHTML=data.sources.map(row=>`<a href="downloads/zodiac-eight/${esc(row.name)}">${esc({'image_observation_v1.json':'图像观察公开投影','guided_observation_v1.json':'全部来源定位与双版原行','comparison_v2.json':'v2 全部矩形对（含零与 NA）','cycle_scope_correction_v2.json':'环序执行范围更正','report_v2.txt':'完整冻结报告','public_manifest_v1.json':'公开复算清单','output_freeze_v1.json':'输入冻结清单','independent-audit-report.json':'独立算术审计完整结果','independent-audit-report.txt':'独立算术审计报告与范围'}[row.name]||row.name)} ↗</a>`).join('');
    $('z8-snapshot').textContent=`所用公开输入冻结于 ${data.frozen_utc}；${data.preview?'当前为本地预览，独立审核待完成。':'发布状态见页首。'} 报告保留冻结时状态，不自动追踪后来审核。`;
    const correction=document.createElement('details');correction.className='z8-fold';correction.innerHTML=`<summary>v1 范围错误与 v2 更正（保留历史）</summary><p>v1 将来源框中心派生角序误作独立已登记序列，超出了原协议范围；并非事后新增门槛。v2 所有环序均未计算，未改科学输入。旧版保留档案，不作协议内完整序列结论。</p><pre class="z8-json">${json(data.cycle_correction)}</pre>`;$('z8-panel-summary').parentElement.append(correction);
    showPanel();$('z8-load-state').textContent='已读取固定八图的完整公开记录。可选择无框原图、两路图层、全部来源条目与 NA；当前审核状态以页首为准。';

  }
  const version=document.querySelector('meta[name="zodiac-eight-snapshot"]').content;
  fetch(`data/zodiac-eight.json?v=${encodeURIComponent(version)}`,{cache:'no-store'}).then(response=>{if(!response.ok)throw new Error('load');return response.json();}).then(render).catch(()=>{$('z8-load-state').textContent='记录未能完整载入，请刷新或直接阅读下方下载文件；不会使用示例替代原记录。';});
})();
