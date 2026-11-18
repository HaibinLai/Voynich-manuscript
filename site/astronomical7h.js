(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const stateLabels = {active:'窗口进行中',running:'进行中',planned:'计划中',awaiting_review:'待复核',partial:'部分已记录',complete:'已完成',completed:'已完成',blocked:'支持不足',paused:'已暂停',not_eligible:'资格未通过',unresolved:'未决'};
  const names = {roles:'圆图文字角色',transcriptions:'十二处双版原文',spatial:'空间映射与闭环次序',calibration:'已知语言圆图资格核验',zodiac:'完整十二个黄道图面'};
  const resolved = new Set(['complete','completed','not_eligible']);
  const badge = state => `<span class="a7-badge" data-state="${esc(state)}">${esc(stateLabels[state] || '待复核')}</span>`;
  const valueText = value => value == null ? '待核／尚无已批准记录' : typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value);
  function validHref(href) {
    if (typeof href !== 'string' || !href || href.includes('\\')) return false;
    if (/^https:\/\//.test(href)) return true;
    return !/^[a-z][a-z0-9+.-]*:/i.test(href) && !href.startsWith('/') && !href.split(/[?#]/)[0].split('/').includes('..');
  }
  const links = rows => (rows || []).filter(row => validHref(row.href)).map(row => `<a href="${esc(row.href)}">${esc(row.label)} ↗</a>`).join('');
  const table = (headers, rows) => `<table class="a7-table"><thead><tr>${headers.map(x => `<th scope="col">${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr>${row.map(x => `<td>${esc(valueText(x))}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
  function record(row) {
    const details = Array.isArray(row.details) ? row.details : row.details ? [row.details] : [];
    const labels = {folio:'图面',role:'文字角色',relation:'空间关系',sequence:'次序',eligibility:'资格',uncertainty:'不确定性'};
    const fields = Object.entries(labels).filter(([key]) => Object.hasOwn(row, key));
    const originals = row.original_lines == null ? '' : `<details class="a7-details"><summary>查看原始行与标记</summary><pre class="a7-original">${esc(valueText(row.original_lines))}</pre></details>`;
    return `<details class="a7-record"><summary><strong>${esc(row.title || row.id)}</strong>${badge(row.status || 'awaiting_review')}</summary>${details.map(p => `<p>${esc(p)}</p>`).join('')}${Object.hasOwn(row,'zl') || Object.hasOwn(row,'it') ? `<div class="a7-transcriptions"><div><small>ZL · 原转写</small><code>${esc(valueText(row.zl))}</code></div><div><small>IT · 原转写</small><code>${esc(valueText(row.it))}</code></div></div>` : ''}${fields.length ? `<dl>${fields.map(([key,label]) => `<dt>${label}</dt><dd>${esc(valueText(row[key]))}</dd>`).join('')}</dl>` : ''}${originals}${validHref(row.source_url) ? `<a href="${esc(row.source_url)}">查看具体来源 ↗</a>` : ''}</details>`;
  }
  function setupGeometry(geometry, reportImageState) {
    if (!geometry) return;
    const ns = 'http://www.w3.org/2000/svg';
    const colors = ['#12625e','#a33d6d','#264fa0','#9a6420','#8f3625','#683d9b'];
    const layerMap = new Map(geometry.layers.map((layer,index) => [layer.id,{...layer,color:colors[index % colors.length]}]));
    const primary = $('a7-layer-primary'), compare = $('a7-layer-compare'), selector = $('a7-box-select');
    const svg = $('a7-geometry-svg'), group = $('a7-svg-boxes'), canvas = geometry.canvas;
    let visible = [], selected = '';
    const key = box => `${box.layer}:${box.id}`;
    const option = (value,label) => { const node = document.createElement('option'); node.value = value; node.textContent = label; return node; };
    for (const layer of geometry.layers) {
      const count = geometry.boxes.filter(box => box.layer === layer.id).length;
      primary.add(option(layer.id, `${layer.label} · ${count}框`));
      compare.add(option(layer.id, `${layer.label} · ${count}框`));
    }
    const svgImage = $('a7-svg-image');
    // Listen before assigning href, including when the official image is cached.
    svgImage.addEventListener('load', () => reportImageState('svg', 'loaded'));
    svgImage.addEventListener('error', () => reportImageState('svg', 'failed'));
    svgImage.setAttribute('width',canvas.width); svgImage.setAttribute('height',canvas.height);
    svgImage.setAttribute('href',canvas.url);
    $('a7-geometry-controls').hidden = false;
    $('a7-geometry-provenance').hidden = false;
    $('a7-geometry-limits').innerHTML = geometry.limits.map(limit => `<li>${esc(limit)}</li>`).join('');
    $('a7-geometry-sources').innerHTML = table(['观察来源（仅溯源）','SHA-256 核验标识'], geometry.inputs.map(input => [input.path,input.sha256]));
    function detail() {
      const box = visible.find(item => key(item) === selected);
      for (const node of group.children) {
        const active = node.dataset.box === selected;
        node.classList.toggle('is-selected', active);
        node.setAttribute('aria-pressed',String(active));
      }
      $('a7-box-detail').hidden = false;
      if (!box) {
        $('a7-box-detail').innerHTML = '<p>选择一个图层，再通过下拉列表、前后按钮或图上的框查看具体位置。选择不表示认可该框。</p>';
        return;
      }
      const [x1,y1,x2,y2] = box.bbox;
      $('a7-box-detail').innerHTML = `<h3>${esc(box.id)} <span>${esc(layerMap.get(box.layer).label)}</span></h3><p>${esc(box.detail)}</p><dl><dt>原画布位置</dt><dd>左上 (${x1}, ${y1}) → 右下 (${x2}, ${y2}) 像素</dd><dt>阅读框大小</dt><dd>${x2-x1} × ${y2-y1} 像素；完整画布 ${canvas.width} × ${canvas.height} 像素</dd></dl><p class="a7-muted">近似阅读范围；不是字形分割、名称认证或正确性评分。</p>`;
    }
    function choose(value) { selected = value; selector.value = value; detail(); }
    function setView() {
      const right = $('a7-view').value === 'right';
      const x = right ? Math.floor(canvas.width/2) : 0;
      const width = canvas.width-x;
      svg.setAttribute('viewBox',`${x} 0 ${width} ${canvas.height}`);
      svg.style.aspectRatio = `${width} / ${canvas.height}`;
      const useSvg = right || visible.length > 0;
      $('a7-image-link').hidden = useSvg;
      $('a7-geometry-frame').hidden = !useSvg;
      reportImageState();
      $('a7-geometry-state').textContent = `${right ? `右半画布阅读视口：x=${x}–${canvas.width}，保留完整高度` : '完整画布'}；${visible.length ? `显示 ${visible.length} 个近似阅读框` : '无框原图'}。框与原图使用同一像素坐标。`;
    }
    function draw() {
      const active = new Set([primary.value,compare.value].filter(Boolean));
      visible = geometry.boxes.filter(box => active.has(box.layer));
      if (!visible.some(box => key(box) === selected)) selected = '';
      selector.replaceChildren(option('',visible.length ? '选择记录查看位置与限定说明' : '先选择图层'));
      for (const box of visible) selector.add(option(key(box),`${box.id} · ${layerMap.get(box.layer).label}`));
      selector.disabled = visible.length === 0;
      selector.value = selected;
      $('a7-box-prev').disabled = $('a7-box-next').disabled = visible.length === 0;
      group.replaceChildren();
      for (const box of visible) {
        const [x1,y1,x2,y2] = box.bbox;
        const rect = document.createElementNS(ns,'rect');
        rect.setAttribute('x',x1); rect.setAttribute('y',y1); rect.setAttribute('width',x2-x1); rect.setAttribute('height',y2-y1);
        rect.setAttribute('vector-effect','non-scaling-stroke');
        rect.setAttribute('tabindex','0'); rect.setAttribute('role','button');
        rect.setAttribute('aria-label',`${box.id}，${layerMap.get(box.layer).label}，近似阅读框`);
        rect.setAttribute('class','a7-reading-box'); rect.style.setProperty('--box-color',layerMap.get(box.layer).color);
        rect.dataset.box = key(box);
        const title = document.createElementNS(ns,'title'); title.textContent = `${box.id} · ${box.detail}`; rect.append(title);
        const activate = () => choose(key(box));
        rect.addEventListener('click',activate); rect.addEventListener('focus',activate);
        rect.addEventListener('keydown',event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(); } });
        group.append(rect);
      }
      $('a7-geometry-legend').innerHTML = [...active].map(id => { const layer = layerMap.get(id); return `<span><i style="--layer-color:${layer.color}" aria-hidden="true"></i>${esc(layer.label)}</span>`; }).join('');
      detail(); setView();
    }
    primary.addEventListener('change',draw); compare.addEventListener('change',draw);
    selector.addEventListener('change',() => choose(selector.value));
    $('a7-view').addEventListener('change',setView);
    for (const [id,delta] of [['a7-box-prev',-1],['a7-box-next',1]]) $(id).addEventListener('click',() => {
      const current = visible.findIndex(box => key(box) === selected);
      const index = current < 0 ? (delta > 0 ? 0 : visible.length-1) : (current+delta+visible.length)%visible.length;
      choose(key(visible[index]));
    });
    $('a7-return-full').addEventListener('click',() => { primary.value = compare.value = ''; $('a7-view').value = 'full'; selected = ''; draw(); });
    draw();
  }
  let payload;
  function renderSections() {
    const filter = $('a7-filter').value;
    const previous = new Set(Array.from(document.querySelectorAll('.a7-evidence[open]')).map(el => el.dataset.section));
    const first = !$('a7-sections').hasChildNodes();
    let shown = 0, total = 0;
    $('a7-sections').innerHTML = Object.entries(names).map(([key,title]) => {
      const section = payload.sections[key];
      const rows = section.records || [];
      const visible = rows.filter(row => filter === 'all' || (filter === 'resolved' ? resolved.has(row.status) : !resolved.has(row.status)));
      shown += visible.length; total += rows.length;
      return `<details class="a7-evidence" data-section="${key}" ${previous.has(key) || (first && key === 'roles') ? 'open' : ''}><summary><span>${title}</span>${badge(section.status)}</summary><div class="a7-evidence-body"><p>${esc(section.summary || '')}</p>${visible.length ? visible.map(record).join('') : `<p class="a7-empty">${rows.length ? '当前筛选下没有记录；切回“全部状态”可查看所有已登记项目。' : '尚无可发布的逐项复核记录。这里保留待核状态，不预填结果。'}</p>`}${section.table ? `<div class="a7-table-wrap">${table(section.table.headers, section.table.rows)}</div>` : ''}${section.sources?.length ? `<details class="a7-details"><summary>具体分析来源</summary><div class="a7-links">${links(section.sources)}</div></details>` : '<p class="a7-source-note">当前范围依据本轮计划与测量协议；后续逐项记录需另附其具体来源。</p>'}</div></details>`;
    }).join('');
    $('a7-filter-state').textContent = `显示 ${shown} / ${total} 条已登记记录；记录数量不是研究完成度。`;
  }
  function render(data) {
    payload = data;
    $('a7-window-status').textContent = stateLabels[data.window.status] || '窗口状态待核';
    $('a7-window-status').dataset.state = data.window.status;
    const timestamp = new Date(data.snapshot_utc);
    if (Number.isNaN(timestamp.getTime())) throw new Error('Invalid snapshot time');
    $('a7-snapshot-time').textContent = `发布记录生成于 ${timestamp.toISOString().replace('T',' ').replace(/\.\d{3}Z$/,' UTC')}`;
    $('a7-status-note').textContent = data.status_note;
    $('a7-findings').innerHTML = data.findings.map(text => `<li>${esc(text)}</li>`).join('');
    $('a7-stages').innerHTML = data.stages.map(s => `<li><span class="a7-stage-number">0${esc(s.stage)}</span><h3>${esc(s.title)}</h3>${badge(s.status)}</li>`).join('');
    $('a7-plan-text').textContent = data.plan;
    $('a7-protocol-text').textContent = data.protocol;
    $('a7-downloads').innerHTML = links(data.downloads);
    $('a7-sources').innerHTML = table(['发布采用的文件','SHA-256 核验标识'], data.sources.map(row => [row.path,row.sha256]));
    const image = $('a7-official-image');
    if (!data.image.official_url.startsWith('https://collections.library.yale.edu/iiif/2/')) throw new Error('Unexpected image source');
    $('a7-image-link').href = $('a7-full-image').href = data.image.official_url;
    const imageStates = {img:'pending', svg:'pending'};
    function reportImageState(surface, state) {
      if (surface) imageStates[surface] = state;
      const active = $('a7-geometry-frame').hidden ? 'img' : 'svg';
      const activeState = imageStates[active];
      $('a7-image-state').textContent = activeState === 'loaded'
        ? data.image.description
        : activeState === 'failed'
          ? '当前原图视图暂时未能载入；可用右侧链接直接查看完整画布。'
          : Object.values(imageStates).includes('loaded')
            ? '官方图源已读取，当前视图正在载入。'
            : '正在读取官方图源。';
    }
    image.addEventListener('load', () => reportImageState('img', 'loaded'));
    image.addEventListener('error', () => reportImageState('img', 'failed'));
    image.src = data.image.official_url;
    // A completed cached image is independently verifiable; assigning src is not.
    if (image.complete && image.naturalWidth > 0) reportImageState('img', 'loaded');
    setupGeometry(data.geometry, reportImageState);
    $('a7-filter').disabled = false;
    $('a7-filter').addEventListener('change', renderSections);
    renderSections();
    $('a7-load-state').textContent = '已读取本次发布记录。未决位置与未审核数据均保留其状态。';
  }
  const version = document.querySelector('meta[name="astronomical7h-snapshot"]').content;
  fetch(`data/astronomical7h.json?v=${encodeURIComponent(version)}`, {cache:'no-store'})
    .then(response => { if (!response.ok) throw new Error(`HTTP ${response.status}`); return response.json(); })
    .then(render)
    .catch(() => {
      $('a7-load-state').textContent = '本轮记录未能完整载入。请刷新，或使用下方计划与原图链接；页面不会以示例替代缺失的数据。';
      $('a7-window-status').textContent = '发布记录载入失败';
      $('a7-filter').disabled = true;
    });
})();
