'use strict';

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const number = (n, digits = 2) => Number(n).toLocaleString('en-US', {maximumFractionDigits: digits, minimumFractionDigits: digits});
const groups = {herbal:'草药图', cosmological:'宇宙图', zodiac:'黄道图', pharmaceutical:'药材图', bathing:'沐浴图'};
const splits = {discovery:'探索组', validation:'验证组'};
const state = {folio:'f2v', group:'all', split:'all', metric:'H2', representation:'primary', experimentSplit:'validation', diffOnly:false, raw:false, literatureQuery:'', literatureCategory:'all', folioCache:new Map()};
let data;
const highres = {page:null, record:null, loaded:false, request:0, timer:null, zoom:1};

const metrics = {
  H1: {key:'H1_conditional_entropy_ratio', title:'词内排列的约束', short:'词内条件熵', subtitle:'前一个编码单位，能在多大程度上预测后一个？', unit:'条件熵比值', format:n=>number(n,3), null:'逐词打乱编码单位，保留每个词形的长度与单位频数。', interpretation:'比值较低，表示相邻编码单位的排列更受限制。EVA 单位不等于已知语言的字母或音素。', conclusion:'在两种转写与合并编码单位的检查中，词内约束都存在。这不提供词义，也不能单独判断语言或密码。'},
  H2: {key:'H2_adjacent_edit_le1_rate', title:'相邻词形的相似性', short:'相邻词形相似', subtitle:'相邻片段是否更常完全相同，或仅差一次编辑？', unit:'相邻相似率', format:n=>number(n*100,2)+'%', null:'页内随机重排词形，保留该页词频、各行槽位和缺失位置。', interpretation:'相似包含完全相同，或插入、删除、替换一个 EVA 单位。不跨不可读片段连接词形。', conclusion:'验证组为 6.53%，页内打乱中位数为 3.64%。探索组的行内打乱检验未获支持，不能描述为所有对照都一致显著。'},
  H3: {key:'H3_line_start_gallows_delta', title:'行首高笔画字形', short:'行首字形富集', subtitle:'以 k / t / p / f 开头的词形，是否更集中于行首？', unit:'行首 − 其他位置的比例差', format:n=>number(n*100,2)+' pp', null:'同一物理行内随机重排，保留各行词袋与缺失位置。', interpretation:'以转写中的 k / t / p / f 为高笔画字形指标；比较行首与其他位置的比例差。pp 表示百分点。', conclusion:'整体信号集中在段首的可能性值得追查：验证组去掉段落首行后差值为 −3.50 个百分点，p=0.378，不支持普遍行首富集。'},
  H4: {key:'H4_line_end_length_delta', title:'行末词形的长度', short:'行末词形长度', subtitle:'行末的编码片段，是否比其他位置更短？', unit:'行末 − 其他位置的编码长度', format:n=>number(n,3), null:'同一物理行内随机重排，保留各行词袋与缺失位置。', interpretation:'负值表示行末平均更短。统计的是所选转写方案的编码长度，不是真实语言的字母数。', conclusion:'主检验未支持“行末更短”（p=0.1115）。换成 IT 转写会改变判断，因此不能只展示支持假说的版本。'}
};
const representations = {primary:'ZL · EVA（主分析）', merged_units:'ZL · 合并常见组合', IT_version:'IT · EVA（版本对照）', join_uncertain_spaces:'ZL · 合并不确定空格', first_alternatives:'ZL · 采用首个备选'};

async function getJSON(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
  return response.json();
}
function externalLink(url, label, className = '') {
  if (!/^https:\/\//.test(url ?? '')) return esc(label);
  return `<a class="${esc(className)}" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} ↗</a>`;
}
function asText(value) {
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) return value.map(asText).join('；');
  if (value && typeof value === 'object') return Object.entries(value).map(([k,v]) => `${k}：${asText(v)}`).join('；');
  return value == null ? '' : String(value);
}
function dateText(value) {
  if (!value) return '未记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString('zh-CN', {timeZone:'UTC', hour12:false}) + ' UTC';
}


function renderManuscript() {
  $('#manuscript').innerHTML = `<div class="page-heading"><div><span class="eyebrow">01 / IMAGE & TRANSCRIPTION</span><h1 id="manuscript-heading">回到每一页的笔画</h1><p>对照原图与 ZL、IT 两份已发表转写。黄色只表示字符串不同；它不是错误判定，也不是我们提出的新读法。</p></div><a class="button secondary small" href="downloads/study20-audit.txt" download>下载校对记录</a></div>
  <div class="filters"><div class="field"><label for="folio-group">图像类别</label><select id="folio-group"><option value="all">全部类别</option>${Object.entries(groups).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div><div class="field"><label for="folio-split">样本分组</label><select id="folio-split"><option value="all">全部样本</option><option value="discovery">探索组</option><option value="validation">验证组</option></select></div><p class="legend" style="margin:0 0 8px"><span class="legend-dot gold"></span>字符串分歧 <span style="margin-left:15px">40 处重点复核</span></p></div>
  <p class="legend" style="margin:13px 0 0">编码说明：. 明确空格 · , 不确定空格 · [a:b] 备选读法 · ? 不可辨字形。字母是字形代号，不表示发音。</p>
  <div class="workspace"><aside class="folio-list" id="folio-list" aria-label="选择手稿页"></aside><div id="folio-detail" class="folio-detail" aria-live="polite"></div></div>`;
  $('#folio-group').value=state.group; $('#folio-split').value=state.split;
  $('#folio-group').addEventListener('change',e=>{state.group=e.target.value;renderFolioList(true)});
  $('#folio-split').addEventListener('change',e=>{state.split=e.target.value;renderFolioList(true)});
  renderFolioList(false);
}
function renderFolioList(reset) {
  const pages=data.overview.folios.filter(p=>(state.group==='all'||p.illustration_group===state.group)&&(state.split==='all'||p.split===state.split));
  if (!pages.length) {$('#folio-list').innerHTML='';$('#folio-detail').innerHTML='<div class="panel empty-state"><h2>当前筛选没有页面</h2><p>尝试选择其他类别或样本分组。</p></div>';return;}
  if (!pages.some(p=>p.folio===state.folio)) state.folio=pages[0].folio;
  $('#folio-list').innerHTML=pages.map(p=>`<button class="folio-button ${state.folio===p.folio?'selected':''}" data-folio="${p.folio}" aria-pressed="${state.folio===p.folio}"><span><strong>${p.folio}</strong><small>${groups[p.illustration_group]} · ${splits[p.split]}</small></span><span class="folio-badge">${p.loci} 行位</span></button>`).join('');
  $$('.folio-button').forEach(b=>b.addEventListener('click',()=>{state.folio=b.dataset.folio;history.replaceState(null,'',`#manuscript?folio=${state.folio}`);renderFolioList(false)}));
  loadFolio(state.folio);
}
async function loadFolio(folio) {
  $('#folio-detail').innerHTML='<div class="panel" style="padding:30px">正在载入 '+esc(folio)+'…</div>';
  try {
    if (!state.folioCache.has(folio)) state.folioCache.set(folio,await getJSON(`data/folios/${folio}.json`));
    if (state.folio!==folio) return;
    const p=state.folioCache.get(folio);
    $('#folio-detail').innerHTML=`<div class="panel"><div class="folio-title"><div><h2>${p.folio}</h2><p>PDF 第 ${p.pdf_page} 页 · ${p.loci} 个转写位置 · ${p.differences} 处字符串不同</p></div><div class="chips"><span class="pill">${groups[p.illustration_group]}</span><span class="pill">书手 ${p.attributes.H==='@'?'页内混合标签（@）':p.attributes.H??'未定'}</span>${p.attributes.L?`<span class="pill">Currier ${p.attributes.L}</span>`:''}</div></div>
      <div class="folio-columns"><div class="image-pane"><button class="image-button" id="open-folio-image" aria-label="放大查看 ${p.folio} 原图"><img src="${p.image}" alt="伏尼契手稿 ${p.folio}，${groups[p.illustration_group]}页"></button><div class="image-caption"><span>点击放大 · 保留原始扫描</span><span>${p.image_width} × ${p.image_height}</span></div>${p.yale_image?`<p class="small-text" style="margin:10px 0 0">${externalLink(p.yale_image.source_url,'耶鲁高清原图')} <span class="muted">${p.yale_image.width} × ${p.yale_image.height}</span></p>`:''}</div><div class="transcription-pane"><div class="transcription-controls"><label><input type="checkbox" id="differences-only" ${state.diffOnly?'checked':''}>仅看分歧</label><label><input type="checkbox" id="raw-notation" ${state.raw?'checked':''}>显示原始标记</label></div><div id="locus-rows"></div></div></div>
      <div class="folio-note"><strong>版面观察：</strong>${esc(p.layout_observation)}<br>此页已做版面与行位核对；未完成逐字终审。Currier A/B 是继承的结构分组，不是已识别的语言名。</div></div>
      ${highresReviewPanel(p)}
      ${repeatAlignmentPanel(p)}
      <div class="focus-grid">${p.focus_cases.map(c=>`<article class="panel focus-card" id="focus-${c.locator.replace('.','-')}"><h3>${esc(c.locator)} <span class="pill caution">保留分歧</span></h3><button class="image-button" data-crop="${esc(c.crop)}" data-title="${esc(c.locator)}" aria-label="放大 ${esc(c.locator)} 复核区域"><img src="${esc(c.crop)}" alt="${esc(c.locator)} 的近似阅读区域" loading="lazy"></button><p>${esc(c.note)}</p><p class="small-text">裁剪框是近似阅读区域，不是精确字形分割标注。</p></article>`).join('')}</div>`;
    renderLoci(p);
    $('#differences-only').addEventListener('change',e=>{state.diffOnly=e.target.checked;renderLoci(p)});
    $('#raw-notation').addEventListener('change',e=>{state.raw=e.target.checked;renderLoci(p)});
    $('#open-folio-image').addEventListener('click',()=>openImage(p.image,p.folio));
    $$('[data-crop]').forEach(b=>b.addEventListener('click',()=>openImage(b.dataset.crop,b.dataset.title)));
    $$('[data-highres-locus]').forEach(b=>b.addEventListener('click',()=>openHighres(p,b.dataset.highresLocus)));
    $$('[data-repeat-copy]').forEach(b=>b.addEventListener('click',()=>openRepeatCell(p,Number(b.dataset.repeatCopy))));
  } catch(error) {$('#folio-detail').innerHTML=`<div class="notice error">页面数据载入失败：${esc(error.message)}</div>`;}
}
function diffMarkup(a,b) {
  if (a==null) return ['未收录',esc(b)]; if (b==null) return [esc(a),'未收录'];
  if (a===b) return [esc(a),esc(b)];
  const m=a.length,n=b.length,dp=Array.from({length:m+1},()=>new Uint16Array(n+1));
  for(let i=m-1;i>=0;i--) for(let j=n-1;j>=0;j--) dp[i][j]=a[i]===b[j]?dp[i+1][j+1]+1:Math.max(dp[i+1][j],dp[i][j+1]);
  const sameA=new Set(),sameB=new Set();let i=0,j=0;
  while(i<m&&j<n){if(a[i]===b[j]){sameA.add(i++);sameB.add(j++);}else if(dp[i+1][j]>=dp[i][j+1])i++;else j++;}
  const mark=(str,same)=>{let out='',inside=false;[...str].forEach((c,k)=>{const different=!same.has(k);if(different&&!inside)out+='<mark>';if(!different&&inside)out+='</mark>';out+=esc(c);inside=different;});return out+(inside?'</mark>':'');};
  return [mark(a,sameA),mark(b,sameB)];
}
function renderLoci(p) {
  const rows=p.rows.filter(r=>!state.diffOnly||r.different);
  $('#locus-rows').innerHTML=rows.length?rows.map(r=>{const focus=p.focus_cases.some(c=>c.locator===r.locator);const [zl,it]=diffMarkup(state.raw?r.zl_raw:r.zl,state.raw?r.it_raw:r.it);return `<article class="locus ${r.different?'different':''} ${focus?'focused':''}"><div class="locus-header"><span>${esc(r.locator)} · ${esc(r.kind)}</span><span>${r.different?'两版不同':'两版一致'}</span></div><div class="locus-code"><span>ZL</span><code>${zl}</code></div><div class="locus-code"><span>IT</span><code>${it}</code></div>${focus?`<button class="locus-focus-button" data-focus="focus-${r.locator.replace('.','-')}">查看重点复核 ↓</button>`:''}${p.high_resolution_review?`<button class="locus-focus-button" data-locus-highres="${esc(r.locator)}">高清定位 ↗</button>`:''}</article>`;}).join(''):'<p style="padding:20px">此页没有符合筛选的字符串分歧。</p>';
  $$('[data-focus]').forEach(b=>b.addEventListener('click',()=>document.getElementById(b.dataset.focus).scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'})));
  $$('[data-locus-highres]').forEach(b=>b.addEventListener('click',()=>openHighres(p,b.dataset.locusHighres)));
}
function openImage(src,title) {$('#dialog-title').textContent=title;$('#dialog-image').src=src;$('#dialog-image').alt=`${title} 原图放大`;$('#original-download').href=src;$('#image-dialog').showModal();}

function reviewStatus(record) {
  return {normalized_agreement:'两版一致 · 未逐字认证',spacing_only:'空格分组未裁决',glyph_or_annotation_difference:'字形 / 标记分歧未裁决'}[record.category]||'已核对位置 · 读法未裁决';
}
function highresReviewPanel(p) {
  const review=p.high_resolution_review;if(!review?.records?.length||!p.yale_image)return '';
  return `<details class="panel highres-review"><summary><span>耶鲁高清逐位置复核</span><span>${review.records.length} 处 · 展开记录</span></summary><div class="highres-review-intro"><p>全套 <strong>20 页 / 332 处</strong>已核对位置。不是独立盲转写、逐字认证或译文；两版原始转写保持不变。阅读框是近似区域，可包含邻近笔画。</p><p>展开记录不会加载高清图；点击某一位置的按钮才从耶鲁加载该页。${externalLink(p.yale_image.source_url,'耶鲁官方原图')}</p><div class="paper-links"><a href="data/high-resolution-review.json" download>全部复核记录 ↓</a><a href="downloads/high-resolution-verification.json" download>覆盖与坐标检查 ↓</a></div></div><div class="highres-record-list">${review.records.map(r=>`<article class="highres-record"><div class="locus-header"><strong>${esc(r.locator)} · ${esc(r.locus_type)}</strong><span>${esc(reviewStatus(r))}</span></div><div class="review-code" tabindex="0" aria-label="${esc(r.locator)} 两版转写"><div><span>ZL</span><code>${esc(r.zl)}</code></div><div><span>IT</span><code>${esc(r.it)}</code></div></div><p>${esc(r.observation)}</p><button type="button" class="button secondary small" data-highres-locus="${esc(r.locator)}">加载高清图并定位 ${esc(r.locator)}</button><span class="legend"> ${r.approximate_regions_normalized.length} 个阅读框</span></article>`).join('')}</div>${review.additional_visible_text?.length?`<div class="highres-review-intro"><p class="small-text muted">补充可见内容：${review.additional_visible_text.map(r=>esc(r.description)).join('；')} 此项未计入 332 个转写位置。</p></div>`:''}</details>`;
}
function repeatAlignmentPanel(p) {
  const r=p.repeat_alignment;if(!r?.cells?.length)return '';
  return `<details class="panel repeat-review"><summary>f57v：四次重复逐位对照</summary><div class="repeat-content"><p>这一圈可按 ZL 的分组排成四行、每行 17 个比较格。这只是<strong>阅读对照，不是已证明的 17 字母表</strong>，也不是新发现。</p><p class="small-text muted">ZL 共 68 项，IT 共 69 项；末尾的 IT <code>r | n</code> 保留为同一比较格内的两项，没有擅自合并。第 9 格在两版中都是 <code>f, f, p, p</code>；它不证明同音、同值或全文可以自由合并。</p><div class="repeat-image-scroll" tabindex="0" aria-label="四次重复的 17 列对照图，可左右滚动"><img src="${esc(r.assets.figure_png)}" alt="f57v 四次重复逐位图，四行各 17 格，末尾 IT r 和 n 保留在同一格" loading="lazy"></div><p class="legend">左右滚动查看全部 17 列；图像经过环带展开与格内缩放，近似边界可能含邻笔画，仅作阅读辅助，不用于图形测量。</p><p class="small-text">第 9 格：点击后按需加载耶鲁高清原图，并查看近似位置。</p><div class="repeat-focus-buttons">${r.focus_cells.map(c=>`<button type="button" class="button secondary small" data-repeat-copy="${c.copy}">第 ${c.copy} 段 · ${esc(c.zl_raw)} ↗</button>`).join('')}</div><details class="study-details"><summary>分组依据、已有研究与下载</summary><p class="small-text muted">D’Imperio（1978，印刷页码 25；另见图 24）和 Stolfi 的 Notes 034 已讨论四次 17 项重复与变体。当前对齐参考既有转写，不是独立盲转写；“重复”本身也不能证实它是密码钥匙。</p><div class="paper-links">${(r.prior_art||[]).map(x=>externalLink(x.url,x.author+' · '+(x.year||'Notes 034'))).join('')}${externalLink(p.yale_image.source_url,'耶鲁官方原图')}</div>${studyAssetLinks(r.assets)}</details></div></details>`;
}
function openRepeatCell(p,copy) {
  const cell=p.repeat_alignment?.focus_cells.find(c=>c.copy===copy);if(!cell)return;
  const locator=`f57v.3 · 第 ${copy} 段第 9 格`;
  openHighres(p,locator,{locator,zl:cell.zl_raw,it:cell.it_raw_items.join(' | '),category:'normalized_agreement',approximate_regions_normalized:cell.approximate_regions_normalized,
    observation:'按四次 17 格对照的角度与半径范围定位。阅读框可能包含邻笔画，不是单字精确分割；这四个按钮不增加全套 332 个转写位置的计数。f / p 变化不证明同音、同值或可全篇合并。'});
}
function validHighresRegions(record) {
  return (record?.approximate_regions_normalized||[]).filter(b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[0]>=0&&b[1]>=0&&b[2]<=1&&b[3]<=1&&b[0]<b[2]&&b[1]<b[3]);
}
function regionUnion(regions) {
  return [Math.min(...regions.map(b=>b[0])),Math.min(...regions.map(b=>b[1])),Math.max(...regions.map(b=>b[2])),Math.max(...regions.map(b=>b[3]))];
}
function setHighresZoom(zoom,box=regionUnion(validHighresRegions(highres.record))) {
  if(!highres.loaded)return;
  const p=highres.page.yale_image,viewport=$('#highres-viewport');
  highres.zoom=Math.min(3,Math.max(.05,zoom));
  $('#highres-stage').style.width=`${p.width*highres.zoom}px`;
  $('#highres-stage').style.height=`${p.height*highres.zoom}px`;
  $('#highres-scale').textContent=`${Math.round(highres.zoom*100)}%`;
  requestAnimationFrame(()=>viewport.scrollTo({left:(box[0]+box[2])/2*p.width*highres.zoom-viewport.clientWidth/2,top:(box[1]+box[3])/2*p.height*highres.zoom-viewport.clientHeight/2,behavior:'instant'}));
}
function fitHighres(box=regionUnion(validHighresRegions(highres.record))) {
  if(!highres.loaded)return;
  const p=highres.page.yale_image,v=$('#highres-viewport');
  setHighresZoom(Math.min(2,(v.clientWidth-36)/((box[2]-box[0])*p.width),(v.clientHeight-36)/((box[3]-box[1])*p.height)),box);
}
function highresFailure(message) {
  highres.loaded=false;clearTimeout(highres.timer);
  $('#highres-viewport').hidden=true;$('#highres-retry').hidden=false;
  $('#highres-status').textContent=message+' 官方原图链接仍可打开，也可关闭窗口继续低清对照。';
  $$('.highres-zoom button').forEach(b=>b.disabled=true);
}
function loadHighresImage() {
  const id=++highres.request,p=highres.page.yale_image,img=$('#highres-image');
  highres.loaded=false;clearTimeout(highres.timer);$('#highres-viewport').hidden=true;$('#highres-retry').hidden=true;
  $('#highres-status').textContent='正在从耶鲁加载高清 JPEG，仅此页将被请求…';
  $$('.highres-zoom button').forEach(b=>b.disabled=true);
  img.onload=()=>{
    if(id!==highres.request)return;
    clearTimeout(highres.timer);
    if(img.naturalWidth!==p.width||img.naturalHeight!==p.height){highresFailure('收到的图片尺寸与已核对的原图不一致，已停用坐标叠加。');return;}
    highres.loaded=true;$('#highres-viewport').hidden=false;$('#highres-retry').hidden=true;
    $('#highres-status').textContent=`官方 JPEG · ${p.width} × ${p.height}；橙色框为 ${highres.record.locator} 的近似阅读区。`;
    $$('.highres-zoom button').forEach(b=>b.disabled=false);fitHighres();
  };
  img.onerror=()=>{if(id===highres.request)highresFailure('高清图暂时无法载入，可能是网络或图源限制。');};
  highres.timer=setTimeout(()=>{if(id===highres.request&&!highres.loaded)highresFailure('高清图加载时间较长，可以稍后重试。');},40000);
  img.alt=`耶鲁官方 ${highres.page.folio} 未经裁切的高清原图`;
  img.src=p.source_url;
}
function openHighres(p,locator,displayRecord=null) {
  const record=displayRecord||p.high_resolution_review?.records.find(r=>r.locator===locator);
  if(!record||!validHighresRegions(record).length||!/^https:\/\/collections\.library\.yale\.edu\/iiif\/2\/\d+\/full\/full\/0\/default\.jpg$/.test(p.yale_image?.source_url||''))return;
  const reuse=highres.page?.folio===p.folio&&highres.loaded;
  highres.page=p;highres.record=record;
  $('#highres-title').textContent=`${locator} · 高清定位`;
  $('#highres-source').href=p.yale_image.source_url;
  $('#highres-reading').innerHTML=`<p><span class="pill caution">${esc(reviewStatus(record))}</span> <span class="legend">位置核对，不是译文</span></p><div class="review-code" tabindex="0" aria-label="当前行位两版转写"><div><span>ZL</span><code>${esc(record.zl)}</code></div><div><span>IT</span><code>${esc(record.it)}</code></div></div><p class="highres-observation">${esc(record.observation)}</p>`;
  const regions=validHighresRegions(record);
  $('#highres-boxes').innerHTML=regions.map((b,i)=>`<div class="highres-box" style="left:${b[0]*100}%;top:${b[1]*100}%;width:${(b[2]-b[0])*100}%;height:${(b[3]-b[1])*100}%"><span>${i+1}</span></div>`).join('');
  $('#highres-region-buttons').innerHTML=regions.length>1?`<span>分区定位：</span>${regions.map((b,i)=>`<button type="button" class="button secondary small" data-region-index="${i}">第 ${i+1} 区</button>`).join('')}`:'';
  $$('[data-region-index]').forEach(b=>b.addEventListener('click',()=>fitHighres(regions[Number(b.dataset.regionIndex)])));
  if(!$('#highres-dialog').open)$('#highres-dialog').showModal();
  if(reuse){$('#highres-status').textContent=`官方 JPEG · ${p.yale_image.width} × ${p.yale_image.height}；橙色框为 ${locator} 的近似阅读区。`;fitHighres();}
  else loadHighresImage();
}

function renderExperiments() {
  $('#experiments').innerHTML=`<div class="page-heading"><div><span class="eyebrow">02 / CONTROLLED EXPERIMENTS</span><h1 id="experiments-heading">让规律接受对照</h1><p>选择指标、转写版本和样本分组，查看观察值与随机重排的分布。所有图形使用已保存的计算结果，切换选项不会重新拟合或生成数据。</p></div><a class="button secondary small" href="data/statistics.json" download>完整统计数据</a></div>
  <div class="filters"><div class="field"><label for="representation">转写与预处理</label><select id="representation">${Object.entries(representations).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></div><div class="field"><label for="experiment-split">样本分组</label><select id="experiment-split"><option value="validation">验证组 · 9 页</option><option value="discovery">探索组 · 8 页</option></select></div></div>
  <div class="experiment-layout"><aside class="metric-menu" aria-label="选择统计指标">${Object.entries(metrics).map(([k,m])=>`<button class="metric-tab ${k===state.metric?'active':''}" data-metric="${k}" aria-pressed="${k===state.metric}">${k} · ${m.short}<small>${k==='H1'?'词内打乱对照':k==='H2'?'页内打乱对照':'行内打乱对照'}</small></button>`).join('')}</aside><div class="experiment-content" id="experiment-content"></div></div><div id="calibration-section"></div>`;
  $('#representation').value=state.representation;$('#experiment-split').value=state.experimentSplit;
  $('#representation').addEventListener('change',e=>{state.representation=e.target.value;renderExperimentResult()});
  $('#experiment-split').addEventListener('change',e=>{state.experimentSplit=e.target.value;renderExperimentResult()});
  $$('.metric-tab').forEach(b=>b.addEventListener('click',()=>{state.metric=b.dataset.metric;$$('.metric-tab').forEach(t=>{t.classList.toggle('active',t===b);t.setAttribute('aria-pressed',t===b)});renderExperimentResult()}));
  renderExperimentResult();
  renderCalibration();
}
function histogramSVG(nulls,observed,median,metric) {
  const m=metrics[metric],w=760,h=270,left=55,right=24,top=24,bottom=48;
  const min=Math.min(...nulls,observed),max=Math.max(...nulls,observed),range=(max-min)||1;
  const lo=min-range*.08,hi=max+range*.08;
  const bins=34,counts=Array(bins).fill(0);
  nulls.forEach(v=>counts[Math.min(bins-1,Math.floor((v-lo)/(hi-lo)*bins))]++);
  const maxCount=Math.max(...counts),x=v=>left+(v-lo)/(hi-lo)*(w-left-right),y=v=>h-bottom-v/maxCount*(h-top-bottom);
  let svg=`<svg class="chart" role="img" aria-label="${esc(m.title)}：观察值 ${esc(m.format(observed))}；随机对照中位数 ${esc(m.format(median))}" viewBox="0 0 ${w} ${h}"><title>${esc(m.title)}的随机对照分布</title>`;
  for(let i=0;i<=3;i++){const count=Math.round(maxCount*i/3);svg+=`<line x1="${left}" y1="${y(count)}" x2="${w-right}" y2="${y(count)}" stroke="#e0e3d9"/><text x="${left-10}" y="${y(count)+4}" text-anchor="end">${count}</text>`;}
  counts.forEach((count,i)=>{if(!count)return;const bx=left+i*(w-left-right)/bins,bw=(w-left-right)/bins-1;svg+=`<rect x="${bx}" y="${y(count)}" width="${bw}" height="${h-bottom-y(count)}" fill="#8da99a"><title>${esc(m.format(lo+i*(hi-lo)/bins))} 至 ${esc(m.format(lo+(i+1)*(hi-lo)/bins))}：${count} 次</title></rect>`;});
  svg+=`<line x1="${x(median)}" y1="${top}" x2="${x(median)}" y2="${h-bottom}" stroke="#285b4d" stroke-width="2" stroke-dasharray="4 4"/><line x1="${x(observed)}" y1="${top+17}" x2="${x(observed)}" y2="${h-bottom}" stroke="#a94e31" stroke-width="2.5"/><circle cx="${x(observed)}" cy="${top+17}" r="4" fill="#a94e31"/><text class="observed-text" x="${Math.max(105,Math.min(w-105,x(observed)))}" y="${top+4}" text-anchor="middle">观察 ${esc(m.format(observed))}</text>`;
  for(let i=0;i<=4;i++){const v=lo+(hi-lo)*i/4;svg+=`<text x="${x(v)}" y="${h-bottom+22}" text-anchor="middle">${esc(m.format(v))}</text>`;}
  svg+=`<text x="${left}" y="13">随机重排次数</text><text class="label-strong" x="${w/2}" y="${h-5}" text-anchor="middle">${esc(m.unit)}</text></svg>`;return svg;
}
function renderExperimentResult() {
  const run=data.statistics.runs[`${state.representation}_${state.experimentSplit}`],m=metrics[state.metric],test=run.tests[m.key];
  const isMain=state.representation==='primary'&&state.experimentSplit==='validation';
  const pLabel=isMain?'Holm 校正 p':'经验 p（辅助 / 探索）',pValue=isMain?test.holm_adjusted_p:test.monte_carlo_p;
  const sameMetricRows=Object.entries(representations).map(([k,label])=>{const r=data.statistics.runs[`${k}_${state.experimentSplit}`],t=r.tests[m.key];return `<tr><td>${label}</td><td>${m.format(t.observed)}</td><td>${m.format(t.null_median)}</td><td>${number(t.monte_carlo_p,4)}</td></tr>`;}).join('');
  let supplemental='';
  if(state.metric==='H3'){const t=run.supplemental.H3_excluding_paragraph_starts;supplemental=`<div class="finding-callout"><strong>排除段落首行后：</strong>差值 ${m.format(t.observed)}，经验 p=${number(t.monte_carlo_p,4)}。此项为辅助检查；总体行首信号不能直接解释为每条行共有的规则。</div>`;}
  if(state.metric==='H2'){const t=run.supplemental.H2_line_shuffle;supplemental=`<div class="finding-callout"><strong>改用更严格的行内打乱：</strong>对照中位数 ${m.format(t.null_median)}，经验 p=${number(t.monte_carlo_p,4)}。这一对照同时保留每行词袋，结果应与页内打乱一并评估。</div>`;}
  if(state.metric==='H4'){const t=run.supplemental.H4_excluding_paragraph_ends;supplemental=`<div class="finding-callout"><strong>排除段落末行后：</strong>差值 ${m.format(t.observed)}，经验 p=${number(t.monte_carlo_p,4)}。主结论以预先确定的 ZL 验证组为准，不从版本中挑选最小 p 值。</div>`;}
  $('#experiment-content').innerHTML=`<div class="panel chart-panel"><div class="chart-heading"><div><h2>${m.title}</h2><p>${m.subtitle}</p></div><span class="pill">${run.pages} 页 · ${run.tokens.toLocaleString()} 词形</span></div><div class="chart-key"><span><i class="legend-dot"></i>${test.replicates.toLocaleString()} 次随机对照</span><span><i class="legend-dot rust"></i>观察值</span></div>${histogramSVG(run.raw_nulls[state.metric],test.observed,test.null_median,state.metric)}<div class="stat-row"><div><strong>${m.format(test.observed)}</strong><span>观察值</span></div><div><strong>${m.format(test.null_median)}</strong><span>对照中位数</span></div><div><strong>${number(pValue,4)}</strong><span>${pLabel}</span></div><div><strong style="font-size:17px">${m.format(test.null_95_interval[0])} — ${m.format(test.null_95_interval[1])}</strong><span>对照 95% 参考区间</span></div></div></div>
  ${supplemental}<div class="method-grid"><article class="panel method-card"><h3>这个对照保留了什么</h3><p>${m.null} ${state.metric==='H1'?'条件熵汇总词内相邻单位。':'先在各页计算，再对页面等权平均。'}</p></article><article class="panel method-card"><h3>怎样阅读这个量</h3><p>${m.interpretation} 图中区间是随机对照分布，<strong>不是效应置信区间</strong>。</p></article></div><div class="sensitivity-table-wrap"><h3 style="font-size:14px">同一分组下的版本与处理对照</h3><table class="data-table"><thead><tr><th>版本 / 处理</th><th>观察值</th><th>对照中位数</th><th>未校正经验 p</th></tr></thead><tbody>${sameMetricRows}</tbody></table><p class="legend" style="margin-top:10px">ZL 主分析使用 1,999 次置换；敏感性版本使用 399 次。只有主验证组的四项检验做 Holm 校正。</p></div><div class="note-strip"><strong>第一轮结论：</strong>${m.conclusion}</div>`;
}

function renderCalibration() {
  const c=data.calibration;
  if(!c||!Array.isArray(c.summary)||!c.summary.length){$('#calibration-section').innerHTML='';return;}
  const treatments={P1_mono:'一一替换',A1_sorted:'词内排序后替换',A2_shuffled:'词内乱序后替换',N1_global:'全局打乱对照'};
  const w=900,h=330,left=170,right=70,top=28,bottom=35,scale=v=>left+v*(w-left-right);
  let chart=`<svg class="chart" role="img" aria-label="已知答案密码校准：正确语言模型在不同扰动下的字母对应恢复准确率" viewBox="0 0 ${w} ${h}"><title>合成密码测试，非伏尼契手稿译文</title>`;
  for(let i=0;i<=4;i++){const x=scale(i/4);chart+=`<line x1="${x}" y1="${top-5}" x2="${x}" y2="${h-bottom}" stroke="#dfe3d9"/><text x="${x}" y="${h-bottom+20}" text-anchor="middle">${i*25}%</text>`;}
  Object.entries(treatments).forEach(([t,label],i)=>{
    const rowY=top+i*66;
    chart+=`<text class="label-strong" x="${left-15}" y="${rowY+24}" text-anchor="end">${label}</text>`;
    ['ordered','bag'].forEach((model,j)=>{
      const row=c.summary.find(r=>r.model===model&&r.treatment===t);if(!row)return;
      const y=rowY+j*23,color=model==='ordered'?'#285b4d':'#b28b49';
      chart+=`<rect x="${left}" y="${y}" height="17" width="${scale(row.accuracy_mean)-left}" fill="${color}"><title>${label} · ${model==='ordered'?'顺序模型':'词袋模型'}：均值 ${number(row.accuracy_mean*100,2)}%；范围 ${number(row.accuracy_min*100,2)}–${number(row.accuracy_max*100,2)}%</title></rect><line x1="${scale(row.accuracy_min)}" x2="${scale(row.accuracy_max)}" y1="${y+8.5}" y2="${y+8.5}" stroke="#25312b"/><line x1="${scale(row.accuracy_min)}" x2="${scale(row.accuracy_min)}" y1="${y+4}" y2="${y+13}" stroke="#25312b"/><line x1="${scale(row.accuracy_max)}" x2="${scale(row.accuracy_max)}" y1="${y+4}" y2="${y+13}" stroke="#25312b"/><text x="${scale(row.accuracy_mean)+8}" y="${y+13}">${number(row.accuracy_mean*100,1)}%</text>`;
    });
  });chart+='</svg>';
  $('#calibration-section').innerHTML=`<div class="section-heading" style="margin-top:55px"><div><span class="eyebrow">METHOD CALIBRATION / SYNTHETIC CIPHERS</span><h2>先读回我们知道答案的密码</h2></div><span class="pill caution">合成测试 · 非手稿译文</span></div><div class="panel chart-panel"><p class="muted small-text">英文 Alice 与拉丁 Caesar 各 3 个不重叠测试窗口，每个 400 词。训练、开发与测试分开，但同属这两本书；它们不是跨作者的独立样本。</p><div class="chart-key"><span><i class="legend-dot"></i>顺序模型</span><span><i class="legend-dot gold"></i>词袋模型</span><span>条形＝6 窗口均值；细线＝最小至最大</span></div>${chart}<p class="legend">恢复率按测试中每次字母出现加权，比较找回的字母对应与已知密钥。词内排序或乱序时，找回字母对应不等于找回原词序或原句。</p></div><div class="method-grid">${c.findings.map(f=>`<article class="panel method-card"><h3>${esc(f.claim)}</h3><p>${esc(f.evidence)}</p><p style="margin-top:10px">边界：${esc(f.scope)}</p></article>`).join('')}</div><div class="note-strip">${esc(c.limits.join('；'))}。${externalLink('https://github.com/HaibinLai/Voynich-manuscript','代码与完整实验')} · <a href="downloads/cipher-calibration-report.txt" download>下载校准报告</a></div>`;
}

function literatureItems() {return Array.isArray(data.literature)?data.literature:(data.literature.items||data.literature.papers||data.literature.entries||[]);}
const paperStatus = {
  abstract_checked_generative_hypothesis:'已核摘要 · 生成假说',
  bibliographic_lead_full_text_unavailable:'书目线索 · 未取得全文',
  peer_reviewed_control_study:'同行评审 · 对照研究',
  peer_reviewed_exploratory_analysis:'同行评审 · 探索分析',
  peer_reviewed_induced_structure:'同行评审 · 归纳结构',
  peer_reviewed_method_unverified_voynich_reading:'同行评审 · 手稿解读未验证',
  peer_reviewed_positional_analysis:'同行评审 · 位置分析',
  peer_reviewed_review:'同行评审 · 综述',
  peer_reviewed_structure_not_decipherment:'同行评审 · 结构研究',
  preprint_structure_not_decipherment:'预印本 · 结构研究',
  preprint_with_public_data:'预印本 · 有公开数据',
  primary_laboratory_report:'原始实验室报告',
  published_author_method_exposition:'已发表 · 作者方法说明',
  published_constructed_positive_control:'已发表 · 人工构造对照',
  published_hypothesis_unvalidated:'已发表 · 假说未验证',
  published_model_author_code_available:'已发表模型 · 作者代码可用',
  published_palaeographic_attribution:'已发表 · 古文字书手归属',
  recent_preprint_not_independently_reproduced:'近期预印本 · 尚未独立复现',
  self_published_provisional_unvalidated:'作者自行发表 · 暂拟未验证'
};
function metadataScopeNotice(compact=false) {
  if(!data.audits?.metadata_scope?.assets?.report)return '';
  const a=data.audits.metadata_scope.assets;
  const completed=data.audits.metadata_sensitivity?.status==='independently_verified_exploratory';
  return `<div class="note-strip metadata-scope"><strong>既有书手条件的范围：使用页级 H 标签。</strong>原模型未展开训练页 f115r 的页内 H=2 / H=3 覆盖，页头 <code>@</code> 被当作独立标签类别，<strong>不是第六位书手</strong>。${compact?'':'因此，这些是条件于冻结页级标签的预测比较，并非完整 Davis 行级书手归属的检验。'}原数值与冻结方案保留；${completed?'已见确认集上的完整词模型敏感性已完成独立复算。保留集当前状态见阶段快照。':'修正后的敏感性正在独立计算。'}${compact?'':`<br><a href="${esc(a.report)}" download>范围与影响审查 ↓</a> · <a href="${esc(a.summary)}" download>逐位置标签证据 ↓</a>`}</div>${!compact&&completed?metadataSensitivityPanel():''}`;
}
function metadataSensitivityPanel() {
  const m=data.audits?.metadata_sensitivity;if(!m?.primary_table)return '';
  const names={ZL_EVA:'ZL / EVA',ZL_merged:'ZL / 合并单位',IT_EVA:'IT / EVA'};
  return `<details class="panel candidate-panel metadata-sensitivity" id="metadata-sensitivity"><summary><strong>展开页内书手标签后，24 项平均增益改变了多少？</strong> · 已完成探索性敏感性</summary><p style="margin-top:18px">固定所有旧参数，只按原转写明确记录的行内 H 重新归类训练词。24 项<strong>等叶平均增益</strong>的最大绝对变化为 <strong>${number(m.max_abs_leaf_gain_change,9)} bits / 目标词</strong>，没有均值正负号翻转。<strong>这不是单词或单页影响的上限。</strong></p><p>原始完整词模型的数值保留，下表另列修正版本。使用的是已经见过的确认页；没有重新选参数、计算新显著性或新区间；本项敏感性未使用预留集。确认页本身没有行内覆盖，变化来自训练计数的重新分配。</p><p class="small-text muted">表格可横向滑动。Δ = 行内标签版 − 原页级标签版；正值表示该项预测增益增加。最后一列是相关模型的最大逐词成本变化，与增益平均值属于不同指标。</p><div class="sensitivity-table-wrap" tabindex="0" aria-label="24项书手标签敏感性，可横向滚动"><table class="data-table"><thead><tr><th>表示</th><th>比较</th><th>目标词数</th><th>原页级增益</th><th>行内标签增益</th><th>平均增益 Δ</th><th>最大逐词成本变化</th></tr></thead><tbody>${m.primary_table.map(r=>`<tr><td>${names[r.representation]}</td><td>${esc(r.label)}</td><td>${r.targets.toLocaleString()}</td><td>${number(r.old_leaf_gain,6)}</td><td>${number(r.inline_leaf_gain,6)}</td><td>${r.delta_leaf_gain>=0?'+':''}${number(r.delta_leaf_gain,9)}</td><td>${number(r.max_abs_per_token_model_cost_change,6)}</td></tr>`).join('')}</tbody></table></div><p class="note-strip"><strong>IT 的“变异复制相对精确复制”仍为负。</strong>标签修正没有消除转写敏感性；段首四种模型 × 三种表示的 12 组逐词数组完全不变。小幅预测收益也不能证明同音、字形同值或词义。</p><p>训练页 f115r 的 ZL 保留 456 词分为 H2 的 128 词和 H3 的 328 词；IT 的 444 词分为 120 和 324。仅恢复来源中明确给出的标签，不重新判断古文字书手，也不是完整真实归属的金标准。</p>${studyFigure(m.assets,'展开行内书手标签前后，24 项等叶平均增益的变化')}${studyAssetLinks(m.assets)}<div class="paper-links"><a href="${esc(m.assets.aggregation)}" download>24 项独立汇总核验 ↓</a><a href="${esc(m.assets.public_replay)}" download>公开新目录复算记录 ↓</a></div><p class="legend">独立标量概率复算最大误差约 1.42 × 10⁻¹⁴ bits；24 项汇总也已独立核查。这验证实现与数值，不把已见确认集变成新的独立证据。复核时间：${esc(dateText(m.verified_utc))}。</p></details>`;
}
function anchorAuditPanel() {
  const a=data.audits?.anchor;if(!a?.coverage?.groups?.length)return '';
  const pct=n=>`${number(n*100,2)}%`;
  const groups=a.coverage.groups, names={ZL_EVA:'ZL / EVA',IT_EVA:'IT / EVA'};
  const splits={train_legacy:'训练 + 既有样本',dev:'开发集'};
  const bounds={conservative_m_excluded:'禁用 m',optimistic_m_allowed:'无条件允许 m'};
  const rowName=r=>`${names[r.representation]} · ${splits[r.split_group]}`;
  const titles={taurus:'f68r3.11 · 星群右侧短词',nigella:'f29v.1 · 首行前两个词',coriander:'f41v.1 · 正文上方独立标签'};
  const statuses={taurus:'末端较支持现代 o；非专家字形认证',nigella:'o / a 未裁决',coriander:'e / o 未裁决；末尾 l 保留，音值未定'};
  return `<details class="study-details anchor-audit" id="anchor-audit"><summary><strong>14条已列规则覆盖保留正文词</strong> · 展开规则覆盖与三处原图核查</summary><p><strong>约 28%–30% 能被现有表项完整覆盖；这不是译文率。</strong>Bax 原文是暂拟的部分解读。下表不替作者补规则，也不据候选植物或星名倒推字形。</p><p>m 的适用条件尚不明确，因此分别计算“禁用 m”和“无条件允许 m”。这只是固定表内该条件的两个界限，不是置信区间，也不是对未来完整假说的上下界。保留 ee 与 e+e 等不同切分及候选音值；单一路径仍不意味着正确发音或词义。</p><div class="sensitivity-table-wrap" tabindex="0" aria-label="四组规则覆盖结果，可横向滚动"><table class="data-table"><thead><tr><th>数据组</th><th>保留词形出现次数</th><th>m 处理</th><th>有完整映射路径</th><th>仅一条符号路径</th><th>最少未解释单位</th></tr></thead><tbody>${groups.flatMap(r=>Object.entries(bounds).map(([k,label])=>{const b=r.bounds[k];return `<tr><td>${rowName(r)}</td><td>${r.tokens.toLocaleString()}</td><td>${label}</td><td>${b.full_coverable_tokens.toLocaleString()} / ${pct(b.full_coverable_fraction)}</td><td>${b.single_symbolic_path_tokens.toLocaleString()} / ${pct(b.single_symbolic_path_fraction)}</td><td>${b.min_unexplained_units.toLocaleString()} / ${pct(b.min_unexplained_unit_fraction)}</td></tr>`})).join('')}</tbody></table></div><p class="legend">完整映射与单一路径比例的分母都是该组保留正文词形出现次数；末列比例的分母是该组保留单位数。多个符号路径未必对应不同读音。两界下，仍约七成保留词形无法完整覆盖。</p><details class="study-details"><summary>查看分母、排除项与独立复算范围</summary><p>固定解析器只保留正文位置；含问号或备选读法的整词作为缺失，独立标签、圆环等不进入这里的分母。已知 EVA 单位若不在部分规则表中，仍留在分母并计为未解释。下面三处标签/短词的图像核查与这张数值表是不同对象。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>数据组</th><th>页数</th><th>正文词槽</th><th>缺失排除</th><th>保留出现次数</th></tr></thead><tbody>${a.population.groups.map(r=>`<tr><td>${rowName(r)}</td><td>${r.pages}</td><td>${r.parsed_prose_slots.toLocaleString()}</td><td>${r.excluded_missing_slots}</td><td>${r.retained_words.toLocaleString()}</td></tr>`).join('')}</tbody></table></div><p>13,482 条版本/分区词形记录 × 两种 m 处理，共 26,964 项，已由独立多项式路径计数和公开前向算法复算；冻结来源同解析器重建的词频表也完全匹配。这验证计算口径，不验证发音、词义或植物身份。本项未读取确认集与保留集作覆盖计算。</p><div class="paper-links"><a href="${esc(a.assets.population)}" download>分母来源核验 ↓</a><a href="${esc(a.assets.replay)}" download>公开复算记录 ↓</a><a href="${esc(a.assets.scope)}" download>范围补充 ↓</a></div></details><h3 style="margin-top:24px">三处锚点：先看原图，再保留分歧</h3><p>以下裁图只来自耶鲁官方手稿影像。已看过现代转写和论文写法，因此不是盲转写或专家字形认证；作者的植物、星名只是候选，不能作为正确答案。</p><div class="anchor-crop-grid">${a.visual_records.map(r=>`<article class="anchor-crop"><h3>${titles[r.id]}</h3><a href="${esc(r.crop)}" target="_blank" rel="noopener noreferrer"><img src="${esc(r.crop)}" alt="${esc(titles[r.id])}的耶鲁手稿裁图，含邻近笔画" loading="lazy"></a><p><span class="pill caution">${statuses[r.id]}</span></p><dl><dt>现代 ZL</dt><dd><code>${esc(r.modern_transcription.ZL)}</code></dd><dt>现代 IT</dt><dd><code>${esc(r.modern_transcription.IT)}</code></dd><dt>Bax 表项（第 ${esc(r.author_page)} 页）</dt><dd><code>${esc(r.author_table_eva)}</code></dd></dl><p>${esc(r.observation)}</p><div class="paper-links">${externalLink(r.source.url,'打开耶鲁完整原图')}<a href="${esc(r.crop)}" download>下载此裁图 ↓</a></div></article>`).join('')}</div><p class="legend">阅读裁框可能含邻近笔画，不是精确字符分割；没有公开现代论文截图，完整高清图仅按需链接。f15v 属预留叶，本次没有新增图像检查。</p>${studyAssetLinks(a.assets)}<div class="paper-links"><a href="${esc(a.assets.visual)}" download>图像来源、坐标与观察 ↓</a><a href="${esc(a.assets.visual_second)}" download>第二次视觉核查 ↓</a><a href="${esc(a.assets.clarification)}" download>f41v 状态措辞修订记录 ↓</a></div></details>`;
}
function sectionHandPanel() {
  const s=data.audits?.section_hand;if(!s?.comparisons)return '';
  const count=x=>`${x.pages} 页 / ${x.leaves} 叶`;
  return `<section class="panel candidate-panel" id="section-hand-audit"><span class="eyebrow">DESIGN AUDIT / NO SEMANTIC RESULT</span><h2>插图类别和书手，能分开比较吗？</h2><p><strong>仅凭目前的分组，尚不足以把章节效应和书手、册帖差异可靠分开。</strong>这里完成的是数据支持审查，没有新增预测结果，也没有从词频聚类推断词义。</p><details class="study-details"><summary>展开共同支持表与后续研究限制</summary><p>仅使用训练、既有样本与开发集元数据；训练词来自已保存材料，未计算确认集或保留集结果。下表只给页/叶数量；“叶”把同一物理叶及折页面归为一组，不能把每面当独立样本。类别来自插图惯称，不是已确认的文本主题。</p><div class="sensitivity-table-wrap" tabindex="0" aria-label="插图与书手共同支持表，可横向滚动"><table class="data-table"><thead><tr><th>页级 H</th><th>插图对比（左 / 右）</th><th>训练 + 既有：左 / 右</th><th>开发集：左 / 右</th></tr></thead><tbody>${s.comparisons.map(r=>`<tr><td>H=${esc(r.hand)}</td><td>${r.illustrations.map(i=>esc(s.labels[i])).join(' / ')}</td><td>${r.fit.map(count).join(' ｜ ')}</td><td>${r.dev.map(count).join(' ｜ ')}</td></tr>`).join('')}</tbody></table></div><p>前三组有同一页级书手标签内的两类材料，但开发集仅有 1–2 叶的少数组。H=4 的开发集没有宇宙图；训练中部分天文/宇宙图还是同一 f68 折叶。H=5 没有开发集。四组都缺乏“固定书手且固定册帖”后在训练与开发两边共同支持的比较。</p><p>训练的“书手 × 插图”支持关系分成两块；排除无插图文本后，没有两名书手都覆盖相同两种插图的完整交叉。把词频差异归为章节，仍可能混入册帖、生产过程与版面差异。</p><p><strong>后续只宜先作有限的条件预测：</strong>在同一书手标签及位置基线下，检验插图类别能否额外预测完整词形；双方计入完整概率与新增参数，并在同一数据预算下选参。若做随机对照，按整叶在同一书手/分区内重配类别，保留词序、局部重复和版面；若训练标签改变，需重跑相同拟合流程。更严格的书手 + 册帖对照缺少共同支持，当前应报告“不可辨识”，不能靠模型先验补成证据。</p><p>这条计划没有加入已冻结的十项保留集方案。相关语义结构和书手/插图/主题比较已有 Montemurro–Zanette、Sterneck 等直接先例；统计关联不能直接命名词义。</p>${metadataScopeNotice(true)}${studyAssetLinks(s.assets)}<p class="legend">下载的完整支持表还含训练词数，来自密码实验的基本字母过滤版本；它与完整词预测模型的词数不同，不能混用。本面板因此只展示页和叶。</p></details></section>`;
}
function candidatePanel() {
  const c=data.candidates;if(!c||!c.bax)return '';
  const source=literatureItems().find(p=>p.id===c.bax.source_id);
  return `<section class="panel candidate-panel"><span class="eyebrow">CLAIM AUDIT / NOT A TRANSLATION</span><h2>把“破解”拆成可检查的主张</h2><p><strong>这些候选规则尚不完整，不能直接用于翻译。</strong></p><div class="method-grid"><div><h3>Bax：10 个词，14 个符号或组合</h3><p>这是作者原文的暂拟读法；中文维基所述“17 个”与原文摘要不同。名称识别、部分字形和音值选择仍有未定项。</p></div><div><h3>“80%”是词典命中，不是语法准确</h3><p>${esc(c.hauer_kondrak.correction)} 这一结果不等于连续文本已经被可靠翻译。</p></div></div><details><summary>查看 Bax 候选词的位置与未解决问题 <span>${c.bax.anchors.length} 条记录</span></summary><p class="legend">以下“候选名称”均为原作者提案，不是本站确认的词义。ZL / IT 为当前公开转写，不能为了得到期望名称而删除未知字形。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>位置</th><th>ZL 转写</th><th>作者候选名称</th><th>尚需解决</th></tr></thead><tbody>${c.bax.anchors.map(a=>`<tr><td>${esc(a.locus)}</td><td><code>${esc(a.zl)}</code></td><td>${esc(a.proposed_name)}</td><td>${esc(a.issue)}</td></tr>`).join('')}</tbody></table></div><p class="small-text muted" style="margin-top:16px">${esc(c.bax.testability)}</p><p class="small-text">${source?externalLink(source.url,'Bax 原文'):''} · <a href="data/candidate_claims.json" download>下载完整映射、位置与未定项</a></p></details><p class="small-text muted" style="margin:18px 0 0">${esc(c.tucker_talbert.caution)}</p>${anchorAuditPanel()}</section>`;
}
function renderLiterature() {
  const items=literatureItems(),cats=[...new Set(items.map(p=>asText(p.category)).filter(Boolean))];
  $('#literature').innerHTML=`<div class="page-heading"><div><span class="eyebrow">03 / LITERATURE & HYPOTHESES</span><h1 id="literature-heading">沿着前人的证据继续</h1><p>把论文的主张、方法和局限放在同一处。候选解读需要固定映射与跨页预测；论文发表、词典命中和语言模型得分都不自动等于破译。</p></div><a class="button secondary small" href="data/literature.json" download>文献数据 JSON</a></div><div class="note-strip"><strong>正在核查的两项说法：</strong>Bax 的植物与星名候选读法；Hauer / Kondrak 的语言识别及字母重排假说。请以原始论文和下列核查记录为准，不把新闻标题中的“破解”当作已验证结果。</div><div class="library-tools"><div class="filters"><div class="field"><label for="literature-search">搜索作者、标题或研究内容</label><input id="literature-search" type="search" placeholder="例如：Bax、熵、复制"></div><div class="field"><label for="literature-category">研究方向</label><select id="literature-category"><option value="all">全部方向</option>${cats.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('')}</select></div></div><div id="literature-count" class="library-count"></div></div><div id="literature-list" class="literature-list"></div>`;
  const pendingNote=$('#literature .note-strip');
  if(data.candidates?.bax)pendingNote.outerHTML=candidatePanel()+sectionHandPanel();
  $('#literature-search').value=state.literatureQuery;$('#literature-category').value=state.literatureCategory;
  $('#literature-search').addEventListener('input',e=>{state.literatureQuery=e.target.value;renderPaperList()});
  $('#literature-category').addEventListener('change',e=>{state.literatureCategory=e.target.value;renderPaperList()});renderPaperList();
}
function renderPaperList() {
  const all=literatureItems(),query=state.literatureQuery.trim().toLowerCase();
  const items=all.filter(p=>(state.literatureCategory==='all'||asText(p.category)===state.literatureCategory)&&(!query||asText(p).toLowerCase().includes(query))).sort((a,b)=>(Number(b.year)||0)-(Number(a.year)||0));
  $('#literature-count').textContent=`${items.length} / ${all.length} 篇`;
  if(!all.length){$('#literature-list').innerHTML='<div class="panel empty-state"><span class="eyebrow">SOURCE REVIEW IN PROGRESS</span><h2>文献核查尚未发布</h2><p>此处将收录原始论文、方法、证据边界与可复现实验。当前没有用占位条目冒充完成的文献调研。</p><a href="https://github.com/HaibinLai/Voynich-manuscript" target="_blank" rel="noopener noreferrer">查看仓库更新 ↗</a></div>';return;}
  $('#literature-list').innerHTML=items.length?items.map(p=>`<article class="panel paper"><div class="paper-year">${esc(p.year)}</div><div><h2>${esc(p.title)}</h2><p class="authors">${esc(asText(p.authors))}</p><span class="pill">${esc(paperStatus[p.status]||asText(p.status)||'文献主张')}</span>${p.category?` <span class="pill neutral">${esc(asText(p.category))}</span>`:''}<div class="paper-detail"><div><strong>作者主张 / 方法</strong><p>${esc(asText(p.claim))}</p></div><div><strong>证据与核查</strong><p>${esc(asText(p.evidence))}</p></div><div><strong>局限</strong><p>${esc(asText(p.limitations))}</p></div><div><strong>可继续的实验</strong><p>${esc(asText(p.reproduction_plan))}</p></div></div><div class="paper-links">${externalLink(p.url,'原始来源')}${p.doi?externalLink(p.doi.startsWith('https://')?p.doi:'https://doi.org/'+p.doi,'DOI'):''}</div></div></article>`).join(''):'<div class="panel empty-state"><h2>没有匹配的文献</h2><p>试试更短的关键词，或切换为全部方向。</p></div>';
}

function studyAssetLinks(assets) {
  const labels={report:'完整报告',figure_png:'结果图 PNG',figure_svg:'矢量图 SVG',protocol:'冻结方案',checks:'独立核验',notices:'第三方来源与许可',summary:'详细数值'};
  return `<div class="paper-links">${Object.entries(labels).filter(([k])=>assets?.[k]).map(([k,label])=>`<a href="${esc(assets[k])}" download>${label} ↓</a>`).join('')}</div>`;
}
function studyFigure(assets,title) {
  return assets?.figure_png?`<figure class="study-figure"><a href="${esc(assets.figure_png)}" target="_blank" rel="noopener noreferrer"><img src="${esc(assets.figure_png)}" alt="${esc(title)}" loading="lazy"></a><figcaption class="legend">点击查看完整结果图；统计范围与区间定义见报告。</figcaption></figure>`:'';
}
function boundaryPriorArtPanel(prior) {
  const items=(prior?.items||[]).filter(p=>p.relation_to_current!=='not_boundary_prior_art');
  if(!items.length)return '';
  return `<details class="study-details"><summary>这项规律的已有研究与本轮复核</summary><p>前词末尾与后词开头的依赖已有直接先例，包括 Currier 和 Smith–Ponzi 的研究。本轮增加限定模型下的预测与归一化对照，属于复核和模型外推，不能称为首次发现。</p>${items.map(p=>`<p class="small-text"><strong>${esc(p.year)} · ${esc(asText(p.authors))}</strong><br>${externalLink(p.url,p.title)}<br><span class="muted">${esc(p.claim)}</span></p>`).join('')}${studyAssetLinks(prior.assets)}</details>`;
}
function boundaryCalibrationPanel(c) {
  if(!c?.groups?.length)return '';
  const names={latin:'自然拉丁文本',naibbe_strict:'Naibbe 严格适配',timm:'Timm A 分支适配'};
  const rows=c.groups.filter(g=>g.order==='original'&&g.representation==='eva');
  return `<article class="panel journal-panel stage2-wide"><span class="eyebrow">SENSITIVITY CALIBRATION / ARTIFICIAL LINES</span><h2>边界指标也会漏掉已知语言</h2><p>同预算预测器在小样本拉丁原文上没有检出正优势。这提醒我们：弱结果可能来自检验灵敏度，不能据此排除语言或语义。</p><p class="small-text muted">${esc(c.task_count)} 次运行；每次 1,665 / 830 / 830 个训练、开发、测试词对，统一为 12 词人工行。此处已知目标词长，仅预测下一词首单位，<strong>不与真实手稿叶均完整词结果共轴比较</strong>。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>原顺序 / EVA</th><th>运行数</th><th>平均节省 bits / 首单位</th><th>选择零权重次数</th></tr></thead><tbody>${rows.map(g=>`<tr><td>${esc(names[g.generator]||g.generator)}</td><td>${g.n}</td><td>${number(g.metrics.last.gain.mean,4)}</td><td>${g.metrics.last.zero_weight_count} / ${g.n}</td></tr>`).join('')}</tbody></table></div><div class="note-strip">Naibbe 的 20 个种子共用一段拉丁明文，不能当作 20 篇独立语言样本。零权重是开发集选择的结果，表示此配置下未采用该特征。Timm 的部分关联也不证明语义；各次运行内校正不控制全部 ${esc(c.task_count)} 次比较。</div>${studyFigure(c.assets,'人工12词行中边界预测器的灵敏度校准，独立于真实手稿叶均分析')}${studyAssetLinks(c.assets)}<details class="study-details"><summary>完整适用范围与限制</summary>${(c.caveats||[]).map(t=>`<p class="small-text muted">${esc(t)}</p>`).join('')}</details></article>`;
}
function copyPredictionPanel(c) {
  if(!c?.verification?.all_passed||!c.primary_table?.length)return '';
  const names={ZL_EVA:'ZL / EVA',ZL_merged:'ZL / 合并单位',IT_EVA:'IT / EVA'};
  const labels={base__minus__edit_HV:'复制 + 单编辑，相对书手/位置基线',exact_HV_matched__minus__edit_HV:'单编辑，相对精确复制',edit_H_matched__minus__edit_HV:'增加上一行来源'};
  const interval=x=>`[${number(x[0],4)}, ${number(x[1],4)}]`;
  const rows=c.primary_table.filter(r=>r.comparison==='base__minus__edit_HV');
  const secondary=c.primary_table.filter(r=>r.comparison!=='base__minus__edit_HV');
  const resultTable=(items,withComparison=false)=>`<div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>转写 / 表示</th>${withComparison?'<th>增量比较</th>':''}<th>叶均节省</th><th>95% 区间</th><th>保守 98.333% 区间</th></tr></thead><tbody>${items.map(r=>`<tr><td>${esc(names[r.representation]||r.representation)}</td>${withComparison?`<td>${esc(labels[r.comparison]||r.label)}</td>`:''}<td>${number(r.mean_leaf_bits_saved,4)}</td><td>${interval(r.ci95)}</td><td>${interval(r.ci98_333)}</td></tr>`).join('')}</tbody></table></div>`;
  return `<article class="panel journal-panel stage2-wide" id="copy-prediction"><span class="eyebrow">FULL-WORD COPY PREDICTION</span><h2>复制模型有响应，手稿证据仍弱</h2><p><span class="pill good">预测实验已复算</span></p><p>${esc(c.main_result)}</p><p class="small-text muted">模型从先前已写词形作精确复制或一次单位插入、删除、替换；计算包含词尾、非空条件化和未知单位身份成本的完整词概率。节省越大，表示在当前条件下预测更好，不表示读出了词义。</p>
  <h3>正控：能否检测到已知复制生成结构？</h3><p class="small-text muted">Timm 作者程序的真实行/页布局，20 个固定种子、EVA 与合并单位共 80 次运行。每个原顺序及打乱条件都重新训练，并独立选择基线参数。以下是各自测试集的总预测增益中位数，单位为 bits / 完整词。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>表示</th><th>原顺序中位数</th><th>打乱中位数</th><th>原顺序优于打乱</th></tr></thead><tbody>${(c.calibration?.groups||[]).map(g=>{const m=g.metrics.base__minus__edit_HV;return `<tr><td>${g.representation==='eva'?'EVA':'合并单位'}</td><td>${number(m.original.median,4)}</td><td>${number(m.shuffled.median,4)}</td><td>${m.positive_paired_seeds} / ${m.original.n} 个种子</td></tr>`;}).join('')}</tbody></table></div><p class="small-text muted">打乱在各训练/开发/测试划分内进行，保留布局；正控证明观察器会响应这些生成配置。20 个种子共用同一作者配置与起始短句，不构成手稿置信区间，也不是已经验证的语义分类器。</p>
  <h3>手稿：总改善较小，转写版本影响结论</h3><p class="small-text muted">同一 28 页 / 13 叶确认集，ZL 5,025 词、IT 5,047 词。下表为“复制 + 单编辑”相对书手/位置完整词基线的叶等权节省，单位 bits / 完整词。</p>${resultTable(rows)}<div class="note-strip"><strong>IT 的 95% 区间跨零；单编辑也没有稳定胜过精确复制。</strong>主 ZL 总增益约 0.0258 bits / 词。增加上一行来源的普通 95% 区间为正，但保守区间跨零。这些结果不足以认定历史上采用了复制生成法。</div>
  <details class="study-details"><summary>查看单编辑与上一行来源的全部增量比较</summary><p class="small-text muted">相对精确复制的比较保持候选来源窗口相同；上一行比较保持横向窗口相同。横向坐标是词形槽位，不是真实像素。独立在开发集选择的横向/精确复制配置，本次恰与匹配配置一致。</p>${resultTable(secondary,true)}</details>
  <p class="small-text muted" style="margin-top:18px">95% 与 98.333% 区间均按叶组重采样；较保守区间针对每种表示的三个预定主差，不控制全部历史研究和敏感性比较。方案是在看过此前确认集发现后冻结，不能称全项目盲测；上述确认集实验未使用 22 页保留集；后续独立复核状态见阶段快照。</p>
  ${studyFigure(c.assets,'完整词复制预测：Timm正控响应与手稿三种表示的预测增益，普通及保守区间')}${studyAssetLinks(c.assets)}<p class="updated-label">实验快照：${esc(dateText(c.completed_utc))}。独立逐编辑路径与标量概率复算误差不超过 1.43 × 10⁻¹⁴ bits，未重新读取确认集选参。</p><details class="study-details"><summary>完整方法限制</summary>${(c.limitations||[]).map(t=>`<p class="small-text muted">${esc(t)}</p>`).join('')}</details></article>`;
}
function positionSpecificityPanel(c) {
  if(!c?.verification?.all_passed||!c.manuscript?.length)return '';
  const names={ZL_EVA:'ZL / EVA',ZL_merged:'ZL / 合并单位',IT_EVA:'IT / EVA'};
  const main=c.manuscript.filter(r=>r.stratum==='exact');
  return `<article class="panel journal-panel stage2-wide" id="position-specificity"><span class="eyebrow">PREVIOUS-LINE POSITION</span><h2>把上一行的词换个位置，改善还在吗？</h2><p><span class="pill good">位置对照已独立复算</span></p><p>同长度词形换位后，约 <strong>77%–91%</strong> 的上一行预测改善仍然保留。三种表示、两种长度约束的 <strong>6 项结果，都没有给出“正上方词形身份”独特作用的清晰证据</strong>。</p><p class="small-text muted">我们只调整模型看到的上一行来源（V 通道），固定目标词、横向来源、已有模型与行槽位。这是条件干预，<strong>不是把全篇文字洗牌</strong>；也没有重新拟合参数。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>相同长度换位</th><th>原位置改善</th><th>换位后平均改善</th><th>保留比例</th></tr></thead><tbody>${main.map(r=>`<tr><td>${names[r.representation]}</td><td>${number(r.observed_V_gain,5)}</td><td>${number(r.null_mean,5)}</td><td>${number(100*r.null_mean/r.observed_V_gain,1)}%</td></tr>`).join('')}</tbody></table></div><p class="legend">改善单位：bits / 完整词，按叶等权；同一 28 页、13 叶确认集。数值越高，仅表示当前模型预测稍好，不表示读出了词义。</p><div class="method-grid"><div><h3>能检测强位置复制吗？</h3><p class="small-text muted">Timm 作者程序的 3 种位置配置 × 20 个种子 × 2 种表示，共 120 条件，强位置复制条件产生明显响应；最高配置相对最低配置的差值，在两种表示中均为 20 / 20 个种子为正。它说明检验有一定检测能力，不能据此把手稿判为某种生成机制。</p></div><div><h3>没有检出，不代表排除复制</h3><p class="small-text muted">相同长度限制下，约四分之一来源槽没有可交换伙伴，实际移动约 44%–46%。放宽长度约束的敏感性对照仍无清晰证据；当前方法不能排除其他位置规则、局部复制或无语义生成。</p></div></div><details class="study-details"><summary>查看全部 6 项数值、校准图与方法边界</summary><p class="small-text muted">每项使用 1,999 次条件换位。D = 原位置改善 − 换位后的平均改善；p 仅是探索性参考，不是机制概率，也未对项目历次探索统一校正。“分段长度”按 1–3 / 4–6 / 7–9 / ≥10 单位分组，是放松长度限制的敏感性对照。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>表示</th><th>长度约束</th><th>D / bits</th><th>参考 p</th><th>来源词身份移动</th></tr></thead><tbody>${c.manuscript.map(r=>`<tr><td>${names[r.representation]}</td><td>${r.stratum==='exact'?'相同长度':'分段长度'}</td><td>${number(r.alignment_specificity_D,6)}</td><td>${number(r.monte_carlo_reference_p,4)}</td><td>${number(100*r.source_identity_moved_mean,1)}%</td></tr>`).join('')}</tbody></table></div>${studyFigure(c.assets,'上一行位置对照：生成器校准与手稿原位置、换位后的预测改善')}<p class="small-text muted">图中手稿对照的横线是换位分布中间 95% 范围，<strong>不是手稿估计量的置信区间</strong>。作者配置 0 并非完全关闭位置分支；原程序普通 LOCALY 分支实际为 1% / 29% / 100%，行首为 11% / 15% / 51%。生成器的同种子对照也不是逐词反事实。</p>${(c.limitations||[]).map(t=>`<p class="small-text muted">${esc(t)}</p>`).join('')}</details><div class="note-strip">这项设计是在看过此前确认集结果后冻结的探索复核，不能称全项目盲测。上述探索实验未使用 22 页保留集；后续固定复核另列。当前没有恢复词义、语言或原文。</div>${studyAssetLinks(c.assets)}<p class="updated-label">实验快照：${esc(dateText(c.completed_utc))}。独立复算覆盖全部 11,994 次手稿换位，最大逐项差异小于 1.5 × 10⁻¹⁶ bits。</p></article>`;
}
function allographFactorPanel(c) {
  if(!c?.verification?.all_passed||!c.primary_table?.length)return '';
  const names={ZL_EVA:'ZL / EVA',ZL_merged:'ZL / 合并单位',IT_EVA:'IT / EVA'};
  const merges={FP:'f / p',KT:'k / t',both:'两组同时'};
  const interval=x=>`[${number(x[0],4)}, ${number(x[1],4)}]`;
  const kt=c.primary_table.find(r=>r.representation==='ZL_EVA'&&r.merge==='KT');
  const syntheticNames={iid:'独立变化',position:'依位置变化',correlated:'相关变化难例'};
  return `<article class="panel journal-panel stage2-wide" id="allograph-factor"><span class="eyebrow">REVERSIBLE GLYPH FACTORING</span><h2>合并字形，付清恢复费用后怎样？</h2><p><span class="pill good">完整成本已独立复算</span></p><p>合并并付费恢复原字形后的预测有小收益；<strong>k / t 尤其依赖位置等条件，不能证明它们是同一个字母</strong>。字形选择仍携带信息，当前只支持限定模型中的统计参数共享。</p><p class="small-text muted">先预测合并后的词形，再为每处恢复原来是哪个字形付费。下表完整报告三种表示 × 三种合并的 9 组结果，含只按总体比例恢复的对照；单位为 bits / 完整词，按 13 个叶组等权。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>表示</th><th>合并组</th><th>条件恢复净收益</th><th>95% 区间</th><th>仅总体比例恢复</th></tr></thead><tbody>${c.primary_table.map(r=>`<tr><td>${names[r.representation]}</td><td>${merges[r.merge]}</td><td>${number(r.mean_leaf_bits_saved,5)}</td><td>${interval(r.ci95)}</td><td>${number(r.global_restore_gain.mean_leaf_bits_saved,5)}</td></tr>`).join('')}</tbody></table></div><div class="note-strip"><strong>k / t 的总体比例恢复，在三种表示中都是负收益。</strong>加入书手、词位置、词内角色与合并后相邻单位等信息，恢复才更有效。这些差别不能被免费抹去，也不证明同音、同义、历史异体字或破译。</div><p class="small-text muted">这三个表示来自同一批手稿，不是三份独立证据。两边词形模型各有 15 个开发集候选配置，但合并模型额外选择 12 个恢复配置，总调参预算与模型容量并不相等。</p><details class="study-details"><summary>查看完整成本、保守区间和已知机制校准</summary><p>以主 ZL 的 k / t 为例：合并词成本 ${number(kt.quotient_bits_per_word,5)} + 恢复费用 ${number(kt.restoration_bits_per_word,5)} = ${number(kt.complete_bits_per_word,5)}，接近原模型的 ${number(kt.raw_bits_per_word,5)} bits / 词。仅看合并部分会大幅夸大改善。</p><p class="small-text muted">以下成本按所有词形合并加权，与上表按叶等权不同，不能直接相减来重建上表。完整词概率计入词尾、非空条件化与未知单位身份费用；未知身份总费用本次与各自原模型相同。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>表示 / 合并</th><th>原模型成本</th><th>合并词成本</th><th>恢复费用</th><th>完整成本</th><th>叶均收益 98.333% 区间</th></tr></thead><tbody>${c.primary_table.map(r=>`<tr><td>${names[r.representation]} · ${merges[r.merge]}</td><td>${number(r.raw_bits_per_word,5)}</td><td>${number(r.quotient_bits_per_word,5)}</td><td>${number(r.restoration_bits_per_word,5)}</td><td>${number(r.complete_bits_per_word,5)}</td><td>${interval(r.ci98_333)}</td></tr>`).join('')}</tbody></table></div><p class="small-text muted">98.333% 区间仅针对每种表示三个预定合并差作保守展示，不控制历次探索、全部表示或敏感性比较；仅有 13 个叶组。</p><h3 style="margin-top:22px">已知机制也有反例</h3><p class="small-text muted">5 个固定种子、3 类已知生成条件与 3 种合并，共 45 次校准。下表为完整净收益中位数；独立变化和位置变化能改善预测，相关变化难例则因恢复器漏掉关联而变差。这是检测检查，不是通用语义分类器。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>生成条件</th><th>f / p</th><th>k / t</th><th>两组同时</th></tr></thead><tbody>${Object.entries(syntheticNames).map(([k,label])=>`<tr><td>${label}</td>${['FP','KT','both'].map(m=>`<td>${number(c.calibration.groups.find(g=>g.mechanism===k&&g.merge===m).gain_median,3)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>${studyFigure(c.assets,'支付字形恢复费用后的九组预测结果、已知机制反例与成本分解')}${(c.limitations||[]).map(t=>`<p class="small-text muted">${esc(t)}</p>`).join('')}</details><p class="small-text muted" style="margin-top:18px">这项探索复核受既有确认集发现与 <a href="#manuscript?folio=f57v">f57v 重复序列先例</a>启发，未改原转写；该项探索未请求或评分 22 页保留集。f / p 变体并非本项目首次发现。</p>${studyAssetLinks(c.assets)}<p class="updated-label">实验快照：${esc(dateText(c.completed_utc))}。45 组合成条件及 9 组手稿完整概率独立复算通过，手稿最大逐词成本差约 1.43 × 10⁻¹⁴ bits。</p></article>`;
}
function stage2Panel() {
  const s=data.stage2;if(!s)return '';
  const directPrior=literatureItems().find(p=>p.id==='rozanova_temerev_2026_units');
  const f=s.paragraph_factor||{},g=s.generator_controls||{},b=s.boundary_fullword||{},diagnostic=s.boundary_diagnostic||{};
  if(!f.primary&&!g.models&&!b.variants)return '';
  const factorModels={body_full:'正文完整词基线',position_full:'位置条件完整词',gallows_selected:'Gallows 前缀因子',any_first_selected:'任意首单位分离'};
  const variantName=v=>v.name.includes('_IT')?'IT / EVA':v.name.includes('merged')?'ZL / 合并单位':v.name.includes('join')?'ZL / 合并不确定空格':'ZL / EVA';
  const bw=b.variants?.find(v=>v.name==='boundary_word_confirm');
  const improvement=bw?.results.last.improvement;
  const generatorNames={naibbe:'Naibbe（原规则）',naibbe_strict_unique:'Naibbe（严格唯一适配）',timm:'Timm（A 分支适配）'};
  const generatorRows=g.models?[{...g.manuscript,name:'手稿训练/既有样本'},...g.models.filter(m=>Object.hasOwn(generatorNames,m.name)).map(m=>({...m,name:generatorNames[m.name]}))]:[];
  return `<section class="stage2-section"><div class="section-heading"><div><span class="eyebrow">STAGE 2 / MECHANISM TESTS</span><h2>进一步区分几种解释</h2></div><span class="pill caution">${s.stage_complete?'第二阶段已完成':s.overall_status==='active'?'第二阶段进行中':'研究状态见阶段快照'}</span></div>${stageSnapshot(true)}${directPrior?`<div class="note-strip"><strong>直接研究先例：</strong>Rozanova 与 Temerev（2026）已研究跨词边界、段首及 Naibbe / 自复制校准。本项目复核相关现象，并使用不同的冻结预测与原实现对照，不主张这些规律首次发现；不同协议的数值不直接排名。<br>${externalLink(directPrior.url,'阅读原论文')} · <a href="#literature">查看原始证据与代码口径</a></div>`:''}<div class="stage2-grid">
  ${f.primary?`<article class="panel journal-panel" id="paragraph-factor"><span class="eyebrow">REVERSIBLE PREFIX FACTOR</span><h2>段首字形能直接去掉吗？</h2><p class="small-text muted">${esc(f.scope)}</p><p>计入完整前缀身份成本后，Gallows 因子仍未超过位置完整词模型。段首需要特殊建模，并不意味着这些字形可以免费删除。</p><table class="data-table"><thead><tr><th>模型</th><th>bits / 段首完整词</th></tr></thead><tbody>${Object.entries(factorModels).map(([k,label])=>`<tr><td>${label}</td><td>${number(f.primary.complete_token_bits[k],3)}</td></tr>`).join('')}</tbody></table><div class="note-strip">root ${number(f.primary.factor_cost_components.body_raw_bits,3)} + 前缀 ${number(f.primary.factor_cost_components.prefix_bits,3)} + 归一化 ${number(f.primary.factor_cost_components.support_normalization_bits,3)} = <strong>${number(f.primary.factor_cost_components.total_bits,3)} bits</strong>。只计算删字后的 root 会产生虚假改善。root 指剩余单位串，不代表已识别的语义词根。</div><p class="small-text muted">G 因子对位置模型的主 ZL 叶均差为 −0.950 bits，描述性区间 [−1.986, +0.017]，略跨零；两个敏感性版本点估计同向。它比任意首单位对照略好，仍不提供词义。</p>${studyFigure(f.assets,'段首可逆前缀因子的完整成本与按叶对照')}${studyAssetLinks(f.assets)}</article>`:''}
  ${bw?`<article class="panel journal-panel" id="boundary-fullword"><span class="eyebrow">CROSS-TOKEN BOUNDARY</span><h2>前词结尾有多少预测信息？</h2><p class="small-text muted">主 ZL：${bw.pairs.toLocaleString()} 个不重叠词对，28 页 / 13 叶。后续模型不以目标词长为输入，并计算含 EOS 的完整词概率。</p><p>加入前词末单位后，主 ZL 叶均节省 <strong>${number(improvement.mean_leaf_bits_saved,3)} bits / 完整词</strong>，区间 [${number(improvement.bootstrap95[0],3)}, ${number(improvement.bootstrap95[1],3)}]。</p><table class="data-table"><thead><tr><th>版本 / 处理</th><th>叶均节省</th><th>95% 区间</th></tr></thead><tbody>${b.variants.map(v=>{const x=v.results.last.improvement;return `<tr><td>${variantName(v)}</td><td>${number(x.mean_leaf_bits_saved,3)}</td><td>[${number(x.bootstrap95[0],3)}, ${number(x.bootstrap95[1],3)}]</td></tr>`;}).join('')}</tbody></table><div class="note-strip">IT 点估计同向，但区间略跨零。后续设计使用了同一确认集的已有发现，<strong>不是独立复现</strong>；未知单位合并为 UNK，仍没有恢复明文。</div>${studyFigure(b.assets,'不输入目标词长的完整词形边界预测结果')}${studyAssetLinks(b.assets)}${boundaryPriorArtPanel(s.boundary_prior_art)}<details class="study-details"><summary>先前诊断：已知词长时预测下一词首单位</summary><p class="small-text muted">该诊断使用目标词长作为已知信息，预测的是一个首单位，不能把它的 bits 与上面的完整词成本直接比较。严格条件置换实际移动的上下文比例有限。</p>${studyFigure(diagnostic.assets,'已知目标长度的跨词首单位诊断')}${studyAssetLinks(diagnostic.assets)}</details></article>`:''}
  ${g.models?`<article class="panel journal-panel stage2-wide" id="generator-controls"><span class="eyebrow">GENERATIVE CONTROLS</span><h2>有明文和无指定明文，都能产生低熵</h2><p>${esc(g.headline)}</p><p class="small-text muted">20 个预定随机种子；下表为当前 EVA 描述值。手稿参照为 train+legacy 的前 8,000 个确定词形，未使用 confirm / reserve 调参或评分。</p><div class="sensitivity-table-wrap"><table class="data-table"><thead><tr><th>材料 / 机制</th><th>词内条件熵比值</th><th>平均编码长度</th><th>人工分行近形相邻超额</th></tr></thead><tbody>${generatorRows.map(m=>`<tr><td>${esc(m.name)}</td><td>${number(m.h2_ratio,3)}</td><td>${number(m.length_mean,3)}</td><td>${number(m.near_excess*100,2)} pp</td></tr>`).join('')}</tbody></table></div><div class="method-grid"><div><h3>有明确明文的构造</h3><p class="small-text muted">Naibbe 原解密器的真值候选覆盖率为 100%，逐词唯一解约 99.14%–99.41%。额外拒绝多解词形的<strong>严格适配版</strong>，20 份各 24,000 个归一化拉丁字母全部唯一往返；不能把这一结论归给未经修改的原规则。</p></div><div><h3>没有输入明文的构造</h3><p class="small-text muted">Timm 对照从既有起始片段进入作者的 A 分支，不编码指定明文，也产生低词内熵。它仍与手稿在词形数量等指标上不同；这不是证明手稿无意义。</p></div></div><div class="note-strip">这些固定表与规则本身来自手稿研究，不是独立盲验证。近形相邻指标来自<strong>保留词序、统一每行 12 词排版</strong>，不等于根任务对原生物理行的确认检验。模拟范围也不是等价性证明或历史参数区间。</div>${studyFigure(g.assets,'Naibbe、Timm与手稿参照的描述性生成机制对照')}${studyAssetLinks(g.assets)}</article>`:''}
  ${copyPredictionPanel(s.copy_prediction)}
  ${positionSpecificityPanel(s.position_specificity)}
  ${allographFactorPanel(s.allograph_factor)}
  ${boundaryCalibrationPanel(s.boundary_calibration)}
  ${syntheticBoundaryPanel(s.synthetic_boundary)}
  ${cipherSearchPanel(s.cipher_search)}
  </div><p class="small-text muted">已完成子实验与仍在计算的任务分开标记。压缩、低熵或字典命中均不自动构成破译；所有当前结果仍以规范化转写及限定模型为对象。</p></section>`;
}

function stage1Panel(summary,findings) {
  if(!findings.length)return '';
  const assets=data.research.stage1_assets||{};
  const overallStatus=data.research.session?.status;
  const overallLabel=overallStatus==='active'?'总研究仍在继续':'总研究状态见上方快照';
  return `<div class="panel journal-panel" style="margin-top:20px"><span class="eyebrow">STAGE 1 / NEW CONFIRMATION SET</span><h2 style="font-size:26px">${esc(summary.title||'扩展研究的新结果')}</h2><p><span class="pill good">阶段一已完成</span> <span class="pill caution">${overallLabel}</span></p><div class="note-strip"><strong>${esc(summary.confirmation_pages)} 页确认集 · ${esc(summary.confirmation_leaf_groups)} 个叶组 · ${Number(summary.confirmation_tokens).toLocaleString()} 个保留词形</strong><br>这是与旧 20 页研究不同的实验；样本、统计量与对照条件不同，结果不能直接当作同一检验前后比较。</div>${metadataScopeNotice(true)}${findings.map((f,i)=>`<article id="stage1-finding-${i+1}"><h3>${esc(f.title)}</h3><p class="small-text">${esc(f.summary)}</p>${f.evidence?`<p class="small-text muted">证据：${esc(asText(f.evidence))}</p>`:''}${f.limitation?`<p class="small-text muted">边界：${esc(asText(f.limitation))}</p>`:''}</article>`).join('')}${assets.figure_png?`<figure style="margin:25px 0 12px"><a href="${esc(assets.figure_png)}" target="_blank" rel="noopener noreferrer"><img src="${esc(assets.figure_png)}" alt="阶段一结果：段首格式、严格相邻词形对照与确认集预测模型比较" loading="lazy"></a><figcaption class="legend">28 页确认集的阶段一结果。点击查看完整图；图中区间定义与统计范围见报告。</figcaption></figure>`:''}<div class="hero-actions" style="margin-top:18px">${assets.report?`<a class="button secondary small" href="${esc(assets.report)}" download>下载阶段一报告</a>`:''}${assets.figure_svg?`<a class="button secondary small" href="${esc(assets.figure_svg)}" download>下载矢量图 SVG</a>`:''}${assets.figure_png?`<a class="button secondary small" href="${esc(assets.figure_png)}" download>下载图 PNG</a>`:''}</div><p class="updated-label">阶段快照：${esc(dateText(summary.updated_at))}<br>${esc(summary.scope||'')}</p></div>`;
}

function renderJournal() {
  const session=data.research.session||{},summary=data.research.summary||{};
  const status={active:'研究进行中',complete:'本阶段已完成',blocked:'等待外部条件',paused:'已暂停'}[session.status]||'状态未记录';
  const findings=Array.isArray(summary.findings)?summary.findings:[];
  $('#journal').innerHTML=`<div class="page-heading"><div><span class="eyebrow">04 / RESEARCH LOG & REPRODUCIBILITY</span><h1 id="journal-heading">保留过程，也保留负结果</h1><p>研究记录标明哪些工作已完成，哪些仍是计划。下载的数据与代码用于复查处理规则、随机对照和结论，而不是把统计相似误称为译文。</p></div><span class="pill caution">快照记录：${status}</span></div>
  ${finalReservePanel(data.finalReserve)}${releaseVerificationPanel()}${metadataScopeNotice()}
  ${stage2Panel()}
  <div class="journal-grid"><div><div class="panel journal-panel"><h2 style="font-size:26px">研究进展</h2><ol class="timeline"><li><h3>原始资料与已发表转写整理</h3><p>建立 PDF 页码关联，保留 ZL3b / IT2a 的版本信息。正文沿用学术转写；现代附文未在此公开。</p></li><li><h3>20 页核对与 40 处重点复核</h3><p>核查版面、转写位置与重点疑难处，保留未决读法。未宣称逐字符终审或双专家独立转写。</p></li>${data.overview.high_resolution_review?`<li><h3>20 页 / 332 处高清对应核对</h3><p>逐位置保留 ZL/IT、未决观察和耶鲁原图近似阅读框；有 32 处交叉抽查并修订 11 个框。不是独立盲转写、逐字认证或译文。<a href="#manuscript">打开逐位置复核</a></p></li>`:''}<li><h3>四项结构检验完成</h3><p>17 页、188 行、1,648 个保留词形。固定随机种子，保存对照分布；主要数值和随机数组已完整复现。</p></li><li class="pending"><h3>7 小时扩展研究</h3><p>窗口：${esc(dateText(session.start_utc))} 至 ${esc(dateText(session.deadline_utc))}。全书分层验证、历史文献核查与已知答案密码校准并行推进。</p></li></ol><div class="note-strip" style="margin-bottom:0">${esc(data.research.snapshot_note)}<br>数据整理时间：${esc(dateText(data.overview.updated_at))}</div></div>
  ${stage1Panel(summary,findings)}</div>
  <div><div class="panel journal-panel"><h2 style="font-size:26px">数据与研究记录</h2><div class="downloads"><a class="download-item" href="downloads/study20-report.txt" download>第一轮完整研究报告 <span>TXT ↗</span></a><a class="download-item" href="downloads/study20-protocol.txt" download>实验方案与预处理约定 <span>TXT ↗</span></a><a class="download-item" href="downloads/study20-audit.json" download>20 页 / 40 处校对记录 <span>JSON ↗</span></a><a class="download-item" href="data/statistics.json" download>全部统计与随机对照 <span>JSON ↗</span></a><a class="download-item" href="downloads/study20-verification.json" download>复现与一致性检查 <span>JSON ↗</span></a><a class="download-item" href="data/literature.json" download>原始论文证据表 <span>JSON ↗</span></a><a class="download-item" href="data/candidate_claims.json" download>候选解读核查记录 <span>JSON ↗</span></a><a class="download-item" href="data/sources.json" download>原始材料来源与许可 <span>JSON ↗</span></a><a class="download-item" href="data/manifest.json" download>公开文件校验值 <span>SHA-256 ↗</span></a></div></div><div class="panel journal-panel" style="margin-top:20px"><h3>怎样独立复查</h3><p class="small-text muted">研究脚本、数据来源和复现说明随仓库维护。网页是结果的阅读入口；原始假设、清洗规则与失败结果同样属于研究输出。</p><a href="https://github.com/HaibinLai/Voynich-manuscript" target="_blank" rel="noopener noreferrer">进入代码与复现说明 ↗</a><p class="small-text muted" style="margin-top:20px">一一符号替换会保留熵与相似关系。仅凭这些指标无法确定读音、语言或词义；可靠解读必须提供固定规则与跨页可重复预测。</p></div></div></div>`;
}

function route() {
  if(!data)return;
  const [routeName,query='']=(location.hash.slice(1)||'overview').split('?');
  const view=['overview','manuscript','experiments','literature','journal'].includes(routeName)?routeName:'overview';
  const params=new URLSearchParams(query),folio=params.get('folio');
  if(folio&&data.overview.folios.some(p=>p.folio===folio)){state.folio=folio;state.group='all';state.split='all';}
  $$('.view').forEach(v=>{v.hidden=v.id!==view});
  $$('[data-route]').forEach(a=>{a.classList.toggle('active',a.dataset.route===view);if(a.dataset.route===view)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current')});
  if(view==='manuscript')renderManuscript();
  if(view==='experiments')renderExperiments();
  if(view==='literature')renderLiterature();
  if(view==='journal')renderJournal();
  document.title=({overview:'研究概览',manuscript:'原图与转写',experiments:'结构实验',literature:'文献地图',journal:'进展与复现'}[view])+' · 伏尼契手稿研究台';
  const targetId=params.get('study'),target=targetId?document.getElementById(targetId):null;
  if(target&&document.getElementById(view).contains(target)) {
    for(let node=target;node&&node.id!==view;node=node.parentElement)if(node.tagName==='DETAILS')node.open=true;
    target.tabIndex=-1;target.focus({preventScroll:true});target.scrollIntoView({block:'start',behavior:'auto'});
  } else window.scrollTo({top:0,behavior:'auto'});
}
window.addEventListener('hashchange',route);
$('#close-dialog').addEventListener('click',()=>$('#image-dialog').close());
$('#image-dialog').addEventListener('click',e=>{if(e.target===$('#image-dialog'))$('#image-dialog').close()});
$('#close-highres').addEventListener('click',()=>$('#highres-dialog').close());
$('#highres-dialog').addEventListener('click',e=>{if(e.target===$('#highres-dialog'))$('#highres-dialog').close()});
$('#highres-fit').addEventListener('click',()=>fitHighres());
$('#highres-page').addEventListener('click',()=>fitHighres([0,0,1,1]));
$('#highres-native').addEventListener('click',()=>setHighresZoom(1));
$('#highres-out').addEventListener('click',()=>setHighresZoom(highres.zoom/1.4));
$('#highres-in').addEventListener('click',()=>setHighresZoom(highres.zoom*1.4));
$('#highres-retry').addEventListener('click',loadHighresImage);

async function init() {
  try{
    const [overview,statistics,literature,research,calibration,candidates,stage2,audits,homepage,finalReserve]=await Promise.all(['overview','statistics','literature','research','calibration','candidate_claims','stage2','interpretation-audit','homepage','final-reserve'].map(name=>getJSON(`data/${name}.json`)));
    data={overview,statistics,literature,research,calibration,candidates,stage2,audits,homepage,finalReserve};
    renderOverview();$('#loading').hidden=true;
    $('#updated-date').textContent='资料快照 '+dateText(overview.updated_at);
    route();
  }catch(error){$('#loading').hidden=true;$('#error').hidden=false;$('#error').innerHTML=`研究资料未能载入。请通过网站地址访问，或在本地启动静态文件服务。<br><span class="small-text">${esc(error.message)}</span><br><a href="downloads/study20-report.txt">仍可下载研究报告</a>`;}
}
init();
