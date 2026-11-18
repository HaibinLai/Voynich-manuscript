(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const states = {usageLimited:'用量受限 · 窗口未完成',active:'窗口进行中',running:'进行中',planned:'计划',awaiting_review:'待复核',partial:'部分记录已保存',complete:'已完成',completed:'已完成',blocked:'待解决条件',paused:'已暂停'};
  const badge = state => `<span class="s7-badge" data-state="${esc(state)}">${esc(states[state] || state)}</span>`;
  const utc = value => {
    const d = new Date(value);
    return Number.isNaN(d.getTime()) ? value : d.toISOString().replace('T',' ').replace(/\.\d{3}Z$/,' UTC');
  };
  const links = rows => rows.map(r=>`<a href="${esc(r.href)}">${esc(r.label)} ↗</a>`).join('');
  let gallery = [], galleryGeneration = 0;
  let boundary;
  const percentPoint = value => value == null ? 'NA' : `${value.value>0?'+':''}${(value.value*100).toFixed(5)}`;
  const signedClass = value => value == null ? '' : value.value>0 ? 's7-positive' : value.value<0 ? 's7-negative' : '';
  const ruleName = rule => `标签 ${rule.label_cut.join('/')}；正文 ${rule.body_cut.join('/')}`;
  const simpleTable = (headers,rows,extra='') => `<table class="s7-table ${extra}"><thead><tr>${headers.map(x=>`<th scope="col">${esc(x)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table>`;

  function renderBoundaryRules() {
    const version=$('s7-boundary-version').value,filter=$('s7-boundary-filter').value;
    const all=boundary.rules.filter(r=>r.version===version);
    const rows=all.filter(r=>filter==='all'||(filter==='hit'&&r.target_hit_candidates>0)||(filter==='invalid'&&r.invalid_labels>0));
    $('s7-boundary-state').textContent=`${version}：显示 ${rows.length} / ${all.length} 条固定规则。未按分数排序；切换筛选不会改变原结果。`;
    $('s7-boundary-rules').innerHTML=rows.length?simpleTable(['规则','标签左／右','正文左／右','有效标签 / 11','目标命中','命中源叶／目标叶','主差（百分点）','条件率差（百分点）','条件支持'],rows.map(r=>`<tr class="${r.target_hit_candidates?'s7-has-hit':''}"><th scope="row"><code>${esc(r.rule.id)}</code></th><td>${r.rule.label_cut.join(' / ')}</td><td>${r.rule.body_cut.join(' / ')}</td><td>${r.valid_labels} / ${r.candidates}</td><td>${r.target_hit_candidates}</td><td>${r.source_leaves_hit.length} / ${r.target_leaves_hit.length}</td><td class="${signedClass(r.delta)}">${percentPoint(r.delta)}</td><td class="${signedClass(r.conditional_delta)}">${percentPoint(r.conditional_delta)}</td><td>${r.conditional_candidates}</td></tr>`),'s7-boundary-table'):'<p class="s7-boundary-empty">该版本没有符合当前筛选的规则。请切回“全部36条”查看零命中与其他结果。</p>';
  }

  function setupBoundary(record) {
    if(!record?.rules?.length)return;
    boundary=record;$('s7-boundary').hidden=false;
    $('s7-boundary-version').disabled=false;$('s7-boundary-filter').disabled=false;
    $('s7-boundary-version').addEventListener('change',renderBoundaryRules);$('s7-boundary-filter').addEventListener('change',renderBoundaryRules);
    renderBoundaryRules();
    const differences={95:'IT 把 f44r.3 的第 4 个词转写为 otol，ZL 为 otal；两版整行都通过严格空格筛选。这是实质读字差异，不能默认为 IT 正确。',133:'两版 f13v.10 的第 5 个词均为 kchor。ZL 行首 y,ol 含不确定空格，按冻结规则整行排除；IT 的 y.ol 保留。不能说 ZL 原转写不存在 kchor。'};
    $('s7-boundary-hit-cards').innerHTML=boundary.hits.map(hit=>{
      const trace=boundary.image_traces.find(t=>t.fragment_id===hit.fragment_id),label=hit.label.flatMap(x=>x.words).join(' '),core=hit.core.join(''),position=hit.positions[0];
      return `<article><h4>#${hit.fragment_id} · 仅 IT · ${esc(hit.rule)}</h4><div class="s7-core-pair"><span>标签 ${esc(label)} → ${esc(core)}</span><span>正文 ${esc(position.word)} → ${esc(core)}</span></div><p>位置 ${esc(position.locator)}，第 ${position.slot+1} 词。每条规则只覆盖一个来源叶和一个目标叶。</p><p>${esc(differences[hit.fragment_id])}</p><p class="s7-muted">这是结果后的定位线索，未据此更改转写或拼出统一映射。</p><div class="s7-links"><a href="${esc(trace.official_image_url)}">耶鲁完整原图</a><a href="downloads/semantic7h/boundary-hit-traces.json">原行与定位记录</a></div></article>`;
    }).join('');
    $('s7-boundary-cv').innerHTML=simpleTable(['版本','平均测试差（百分点）','完整词基线（百分点）','平均测试增益（百分点）'],Object.entries(boundary.loo).map(([version,r])=>`<tr><th scope="row">${esc(version)}</th><td>${percentPoint(r.test_delta)}</td><td>${percentPoint(r.baseline_delta)}</td><td>${percentPoint(r.gain_vs_baseline)}</td></tr>`));
    const folds=[];
    for(const [version,r] of Object.entries(boundary.loo))for(const f of r.folds)folds.push(`<tr><th scope="row">${version} / ${esc(f.held_source_leaf)}</th><td><code>${esc(f.selected_rule.id)}</code></td><td>${percentPoint(f.train_delta)}</td><td>${percentPoint(f.test_delta)}</td><td>${percentPoint(f.baseline_delta)}</td><td class="${signedClass(f.gain_vs_baseline)}">${percentPoint(f.gain_vs_baseline)}</td><td>${f.train_candidates} / ${f.test_candidates}</td><td>${f.purged_pair_ids.length}</td></tr>`);
    $('s7-boundary-folds').innerHTML=simpleTable(['版本／留出源叶','训练中选出的规则','训练差（百分点）','测试差（百分点）','测试基线（百分点）','测试增益（百分点）','训练／测试候选','清除重复目标候选'],folds,'s7-boundary-table');
    if(boundary.visual){
      const visual=boundary.visual,host=$('s7-boundary-visual-status');
      const labels={f99v_upper:'95 · 标签所在对象与上下文',f100v_upper_panel:'133 · 标签所在左侧图面',f44r_upper_text:'95 · 目标上部正文',f13v_lower_text:'133 · 目标下部正文',f99v_otoldy:'95 · 来源标签 otoldy',f44r_line3:'95 · 目标第3行',f44r_otal_otol:'95 · 争议词 otal / otol',f44r_ao_context:'95 · a/o 争议和相邻字形',f100v_opchor:'133 · 来源标签 opchor',f13v_line10:'133 · 目标第10行',f13v_kchor:'133 · 目标词 kchor',f13v_y_ol_gap:'133 · 行首 y / ol 间距'};
      host.innerHTML=`<strong>原图细查已保存：</strong><p>${esc(visual.overall_zh)}</p><p>这是依据已知命中定位的一次 AI 观察，不是独立盲转写；近似裁框用于阅读，不是自动字形分割。</p>${visual.items.map(r=>`<details class="s7-plan-details"><summary>#${r.q15_number} 的可见笔画与解释边界</summary><p>${esc(r.source_observation_zh)}</p><p>${esc(r.target_observation_zh)}</p><p>${esc(r.consequence_zh)}</p></details>`).join('')}<details id="s7-boundary-crop-open" class="s7-plan-details"><summary>展开官方原图裁区（一次只加载当前一张）</summary><label for="s7-boundary-crop">阅读位置</label><select id="s7-boundary-crop">${visual.crops.map((r,i)=>`<option value="${i}">${esc(labels[r.name]||r.name)}</option>`).join('')}</select><div id="s7-boundary-crop-frame"></div></details><div class="s7-links"><a href="downloads/semantic7h/boundary-image-review.txt">完整原图观察</a><a href="downloads/semantic7h/boundary-image-receipt.json">文件与裁图核验记录</a></div>`;
      const renderCrop=()=>{
        const frame=$('s7-boundary-crop-frame');
        if(!$('s7-boundary-crop-open').open){frame.innerHTML='';return;}
        const r=visual.crops[Number($('s7-boundary-crop').value)||0];
        const width=Math.min(950,r.size[0]),url=r.url.replace('/full/0/default.jpg',`/${width},/0/default.jpg`);
        frame.innerHTML=`<figure><a href="${esc(r.url)}"><img src="${esc(url)}" alt="${esc(labels[r.name]||r.name)}，耶鲁官方原图近似阅读裁区" decoding="async"></a><figcaption>${esc(labels[r.name]||r.name)} · 原尺寸 ${r.size.join(' × ')}。<div class="s7-links"><a href="${esc(r.url)}">原尺寸裁区</a><a href="https://collections.library.yale.edu/iiif/2/${esc(r.image_id)}/full/full/0/default.jpg">完整原图</a></div></figcaption></figure>`;
      };
      $('s7-boundary-crop-open').addEventListener('toggle',renderCrop);
      $('s7-boundary-crop').addEventListener('change',renderCrop);
    }
    if(location.hash==='#s7-boundary')$('s7-boundary').scrollIntoView();
  }
  const grades = {A:'作者认为看似同一植物',S:'作者认为有些形态相似',P:'经 Zandbergen 转述 Petersen',U:'转述 Petersen，来源明确仍待核查'};

  const galleryBatch=()=>gallery.filter(r=>r.batch===$('s7-batch').value);
  function setGalleryOptions(requested) {
    const rows=galleryBatch();
    $('s7-pair').innerHTML=rows.map(r=>`<option value="${esc(r.pair_id)}">#${r.fragment_id} · ${esc(r.source_folio)} → ${esc(r.target_folio)}${r.fragment_id===110?' · 多词组，未入主分析':''}${r.target_regions?.length>1?' · 两目标未决':''}</option>`).join('');
    $('s7-pair').value=rows.some(r=>r.pair_id===requested)?requested:rows[0].pair_id;
  }
  function renderGallery() {
    const rows=galleryBatch(),row=rows.find(r=>r.pair_id===$('s7-pair').value) || rows[0];
    if (!row) return;
    const index=rows.indexOf(row), generation=++galleryGeneration;
    $('s7-pair-prev').disabled=index===0; $('s7-pair-next').disabled=index===rows.length-1;
    const partial=row.comparison_decision==='suitable_for_partial_shape_comparison';
    let meta=`<div class="s7-gallery-meta"><span class="s7-badge" data-state="partial">观察已记录</span><strong>${partial?'可作局部形态比较':'证据有限或含混'}</strong><span>来源等级 ${esc(row.prior_grade)}：${esc(grades[row.prior_grade] || row.prior_grade)}</span><a href="${esc(row.prior_source)}">看作者原假说 ↗</a></div>`;
    if (row.fragment_id===110) meta+='<p class="s7-gallery-warning">#110 保留为同一个图像假说；标签由两个位置、三个词组成（otal / chor.olekor），整组未进入单词标签的主分析。没有从中挑一个词救回匹配。</p>';
    if (row.canvas_note) meta+='<p class="s7-gallery-warning">#136 的工作目标页号为 f90v2，但耶鲁画布标题为 90r。记录保留这一标题冲突；本轮按来源链接与图像对应采用该画布，没有裁决历史正反页编号。</p>';
    if(row.batch==='order'){
      meta+='<p class="s7-gallery-warning">次序定位批次：12 对均未执行正文词形匹配，不属于原 11 条已评分查询。来源集中在 f88 与 f89 两个物理叶，不能看成 12 次独立确认。</p>';
      if(!row.target_unique)meta+='<p class="s7-gallery-warning">该目标页有两个分离植物状图形，下面同时保留两者；尚未确定来源片段对应哪一个，没有替研究选择唯一目标。</p>';
      if(row.attachment_status==='ambiguous')meta+='<p class="s7-gallery-warning">#31 来源标签附着仍有歧义；可定位图形不等于已确定文字属于它。</p>';
      if(row.notes?.length)meta+=`<p class="s7-muted">${row.notes.map(esc).join(' ')}</p>`;
    }
    if(row.batch==='remaining'){
      meta+='<p class="s7-gallery-warning">剩余图像关系批次：11 对均未执行正文词形匹配；包含 10 个来源对象，#150 对应两个不同目标。图像比较不改变旧标签资格或 11 条主查询。</p>';
      if(row.label_scope_zh)meta+=`<p class="s7-gallery-warning">${esc(row.label_scope_zh)}</p>`;
      if(!row.target_unique)meta+='<p class="s7-gallery-warning">目标页有两个植物状图形，下面同时保留两者；没有确定来源片段对应哪一个。</p>';
      if(row.notes?.length)meta+=`<p class="s7-muted">${row.notes.map(esc).join(' ')}</p>`;
      if(row.source_context_links?.length)meta+=`<div class="s7-links">${links(row.source_context_links)}</div>`;
    }
    if(row.exact_check)meta+=`<div class="s7-exact-check"><strong>完整词主检查 · exact / strict_space / page_HI</strong><p>${Object.entries(row.exact_check).map(([v,r])=>`${v}：同长度机会 N=${r.opportunities}，命中 m=${r.matches}，条件率 ${r.opportunities?r.matches+'/'+r.opportunities:'NA（零机会）'}`).join('；')}</p><p class="s7-muted">N 是该页通过筛选的同长度词位数，不是独立实验次数；这里没有使用另行研究的短边界规则，也不等于对象名称已被确定。</p></div>`;
    $('s7-gallery-meta').innerHTML=meta;
    const pictures=[{a:row.source,side:'source'},...(row.target_regions||[row.target]).map((a,i)=>({a,side:'target'+i}))];
    $('s7-gallery-images').dataset.count=pictures.length;
    $('s7-gallery-state').textContent=`本批第 ${index+1} / ${rows.length} 对：正在加载当前 ${pictures.length} 张官方裁区。`;
    $('s7-gallery-images').innerHTML=pictures.map(({a,side})=>{
      const source=side==='source';
      return `<figure><a class="s7-image-frame" href="${esc(a.native_crop_url)}" aria-label="打开${source?'来源片段':'目标图像'}的官方原尺寸裁区"><img id="s7-image-${side}" src="${esc(a.crop_url)}" alt="${source?'来源片段 #'+row.fragment_id+'，'+row.source_folio:'文献指定目标 '+row.target_folio}：耶鲁原图的近似对象阅读裁区" decoding="async"></a><figcaption><strong>${source?'来源片段 #'+row.fragment_id+' · '+esc(row.source_folio):'文献目标 · '+esc(row.target_folio)}</strong>${a.description?`<p>${esc(a.description)}</p>`:''}<p>馆藏画布标题：${esc(a.manifest_label)}</p>${source?`<p>${row.candidate_locators.length?'候选标签位置：'+row.candidate_locators.map(esc).join('、'):(row.source_caption_zh || '次序定位候选；正文匹配未运行')}</p>`:''}<div class="s7-links"><a href="${esc(a.source_url)}">查看完整原图</a><a href="${esc(a.native_crop_url)}">原尺寸裁区</a></div></figcaption></figure>`;
    }).join('');
    $('s7-gallery-notes').innerHTML=`<article><h3>观察到的相似处</h3><p>${esc(row.similarity_zh)}</p></article><article><h3>差异与缺失的信息</h3><p>${esc(row.difference_zh)}</p></article><details class="s7-image-original"><summary>查看冻结记录中的原始描述</summary><p>相似处</p><ul>${row.original_similarities.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><p>差异与缺失</p><ul>${row.original_differences.map(x=>`<li>${esc(x)}</li>`).join('')}</ul></details>`;
    const imageStates=new Map();
    const settled=()=>{if(generation!==galleryGeneration)return;const loaded=[...imageStates.values()].filter(x=>x==='loaded').length,failed=[...imageStates.values()].filter(x=>x==='failed').length;const prefix=`本批第 ${index+1} / ${rows.length} 对：`;$('s7-gallery-state').textContent=failed?prefix+'官方裁图暂未全部加载，可打开完整原图或原尺寸裁区。':loaded===pictures.length?prefix+`${pictures.length} 张官方裁区已加载。相似处不认证对象身份。`:prefix+`已加载 ${loaded} / ${pictures.length} 张官方裁区。`;};
    for (const {side} of pictures) {
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
    const batches=[...new Set(gallery.map(r=>r.batch))];
    const batchNames={numbered:'来源编号支持',order:'次序定位候选',remaining:'剩余图像关系'};
    $('s7-batch').innerHTML=batches.map(batch=>`<option value="${esc(batch)}">${esc(batchNames[batch]||batch)} · ${gallery.filter(r=>r.batch===batch).length}对 / ${batch==='numbered'?'11条已评分':'均未评分'}</option>`).join('');
    $('s7-gallery-link').textContent=`查看${gallery.length}组原图`;
    $('s7-gallery-count').textContent=`04 / ${batches.length} BATCHES / ${gallery.length} IMAGE PAIRS`;
    const requested=new URL(location.href).searchParams.get('pair');
    $('s7-batch').value=gallery.find(r=>r.pair_id===requested)?.batch || 'numbered';
    $('s7-batch').disabled=false;
    setGalleryOptions(requested);
    $('s7-batch').addEventListener('change',()=>{setGalleryOptions();renderGallery();});
    $('s7-pair').disabled=false;
    $('s7-pair').addEventListener('change',renderGallery);
    $('s7-pair-prev').addEventListener('click',()=>{const rows=galleryBatch(),i=rows.findIndex(r=>r.pair_id===$('s7-pair').value);if(i>0){$('s7-pair').value=rows[i-1].pair_id;renderGallery();}});
    $('s7-pair-next').addEventListener('click',()=>{const rows=galleryBatch(),i=rows.findIndex(r=>r.pair_id===$('s7-pair').value);if(i<rows.length-1){$('s7-pair').value=rows[i+1].pair_id;renderGallery();}});
    renderGallery();
    if(location.hash==='#s7-gallery') $('s7-gallery').scrollIntoView();
  }

  function setupChoice(record) {
    if(!record?.questions?.length)return;
    $('s7-choice').hidden=false;
    const outcome={unique_highest:'唯一最高',tied_highest:'并列最高',below_other:'低于其他候选',not_comparable:'NA'};
    $('s7-choice-table').innerHTML=simpleTable(['题目／来源片段','A：页号／分数','B：页号／分数','C：页号／分数','文献目标','相对位置'],record.questions.map(q=>`<tr><th scope="row">${esc(q.question_id)} / #${q.fragment_id}</th>${q.candidates.map(c=>`<td>${esc(c.folio)} / ${c.observation.score==null?'NA':c.observation.score}${c.prior_hypothesis?'（文献）':''}</td>`).join('')}<td>${esc(q.prior_hypothesis_code)}</td><td>${esc(outcome[q.comparison_status]||q.comparison_status)}</td></tr>`));
    $('s7-choice-question').innerHTML=record.questions.map(q=>`<option value="${esc(q.question_id)}">${esc(q.question_id)} · #${q.fragment_id} · ${esc(outcome[q.comparison_status])}</option>`).join('');
    $('s7-choice-question').disabled=false;
    $('s7-choice-question').value=record.questions[0].question_id;
    let generation=0;
    const render=()=>{
      const current=++generation;
      if(!$('s7-choice-open').open){$('s7-choice-images').innerHTML='';$('s7-choice-state').textContent='';return;}
      const q=record.questions.find(q=>q.question_id===$('s7-choice-question').value)||record.questions[0];
      const images=[{...q.source,code:'source'},...q.candidates];
      $('s7-choice-state').textContent=`${q.question_id}：正在加载当前四张官方裁区。`;
      $('s7-choice-images').innerHTML=images.map(c=>{
        const source=c.code==='source',o=c.observation;
        const native=c.crop_url.replace(/\/\d+,\/0\/default.jpg$/,'/full/0/default.jpg');
        return `<article><h3>${source?'来源 #'+q.fragment_id:c.code+' · '+(c.prior_hypothesis?'文献目标':'固定对照')}</h3><p class="s7-muted">${esc(c.folio)}${source?'':` · ${o.score==null?'NA':o.score+' / 3 分'}`}</p><a class="s7-choice-image-frame" href="${esc(native)}"><img id="s7-choice-image-${esc(c.code)}" src="${esc(c.crop_url)}" alt="${source?'来源片段 #'+q.fragment_id:'候选 '+c.code+'，'+c.folio}，耶鲁官方近似对象裁区" decoding="async"></a><div class="s7-links"><a href="${esc(c.url)}">完整原图</a><a href="${esc(native)}">原尺寸裁区</a></div>${source?`<p>${esc(q.source_observation)}</p><ul>${q.uncertainties.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:`<h4>相似处</h4><ul>${o.similarities.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>差异</h4><ul>${o.differences.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><h4>评分理由</h4><p>${esc(o.reason)}</p>`}</article>`;
      }).join('');
      const imageStates=new Map();
      const settled=()=>{if(current!==generation)return;const loaded=[...imageStates.values()].filter(v=>v==='loaded').length,failed=[...imageStates.values()].filter(v=>v==='failed').length;$('s7-choice-state').textContent=`${q.question_id}：`+(failed?'裁区尚未全部载入，可打开完整原图。':loaded===4?'四张官方裁区已载入。评分是可比程度，不是同种概率。':`已加载 ${loaded} / 4 张裁区。`);};
      for(const c of images){const img=$('s7-choice-image-'+c.code);img.addEventListener('load',()=>{imageStates.set(c.code,'loaded');settled();},{once:true});img.addEventListener('error',()=>{imageStates.set(c.code,'failed');settled();},{once:true});if(img.complete)imageStates.set(c.code,img.naturalWidth>0?'loaded':'failed');}
      settled();
    };
    $('s7-choice-question').addEventListener('change',render);
    $('s7-choice-open').addEventListener('toggle',render);
    if(location.hash==='#s7-choice')$('s7-choice').scrollIntoView();
  }

  function setupRepeated(record) {
    if(!record?.records?.length)return;
    const rows=record.records;
    $('s7-repeated').hidden=false;
    $('s7-repeat-locus').innerHTML=rows.map((r,i)=>`<option value="${i}">${esc(r.query_from_frozen_roster)} · ${esc(r.locator)}</option>`).join('');
    let currentRow=rows[0],generation=0;
    const renderContext=()=>{
      const r=currentRow,c=r.display_contexts[Number($('s7-repeat-context').value)||0],current=++generation;
      $('s7-repeat-image-state').textContent='正在加载所选官方阅读裁区。';
      $('s7-repeat-image').innerHTML=`<figure><a class="s7-repeat-image-frame" href="${esc(c.url)}"><img id="s7-repeat-active-image" src="${esc(c.display_url)}" alt="${esc(r.locator)} · ${esc(c.canvas_label)}，官方原图的近似阅读裁区" decoding="async"></a><figcaption>馆藏画布：${esc(c.canvas_label)} · ${esc(c.image_id)}。${c.is_working_canvas?'当前工作归属画布。':'延续画布对照，不是当前归属画布。'}<div class="s7-links"><a href="${esc(c.url)}">原尺寸阅读裁区</a><a href="https://collections.library.yale.edu/iiif/2/${esc(c.image_id)}/full/full/0/default.jpg">该画布完整原图</a></div></figcaption></figure>`;
      const img=$('s7-repeat-active-image');
      const update=()=>{if(current!==generation)return;$('s7-repeat-image-state').textContent=img.naturalWidth>0?'官方裁区已加载。页面使用官方缩放版本；记录中的哈希对应原尺寸裁区。':'官方裁区暂未载入，可打开原尺寸裁区或完整原图。';};
      img.addEventListener('load',update,{once:true});img.addEventListener('error',update,{once:true});if(img.complete)update();
    };
    const renderLocus=()=>{
      const r=rows[Number($('s7-repeat-locus').value)||0];currentRow=r;
      $('s7-repeat-context').innerHTML=r.display_contexts.map((c,i)=>`<option value="${i}">${esc(c.canvas_label)} · 裁区 ${i+1}${c.is_working_canvas?' · 工作画布':' · 延续对照'}</option>`).join('');
      const working=r.display_contexts.map((c,i)=>c.is_working_canvas?i:-1).filter(i=>i>=0);
      $('s7-repeat-context').value=String(working[working.length-1]);
      const same=rows.filter(x=>x.query_from_frozen_roster===r.query_from_frozen_roster).map(x=>x.locator).join('、');
      $('s7-repeat-observation').innerHTML=`<h3>${esc(r.query_from_frozen_roster)} · ${esc(r.locator)}</h3><p>${esc(r.observation_zh)}</p><p class="s7-muted">物理叶 ${esc(r.physical_leaf)}；原注释 ${r.raw_fragment_annotation==null?'无':esc(r.raw_fragment_annotation)}。该簇完整位置：${esc(same)}。</p><p class="s7-gallery-warning">原工作定位 clear；未见明确指示线。现已有知晓转写的第二观察者复查，仍是暂定归属，不是盲定位认证、对象名称或同种植物认证。</p>`;
      if(r.second_guided_review){const q=r.second_guided_review;$('s7-repeat-observation').innerHTML+=`<div class="s7-gallery-warning"><strong>第二次已知转写观察 · 全部九处保留</strong><p>${esc(q.local_support)}</p><p>${esc(q.neighbor_ink)}</p><p>${esc(q.clipping)}</p><p>${esc(q.qualification)}</p><a href="downloads/semantic7h/repeat-guided_second_review_v1.txt">全部九处追加记录与限制</a></div>`;}
      $('s7-repeat-original').innerHTML=`<details class="s7-plan-details"><summary>核对两版原行、近似框与原始观察</summary><h4>冻结的原行</h4><pre>${Object.entries(r.original_raw_lines).map(([v,line])=>esc(v+': '+line)).join('\n')}</pre><p>标签近似框（x, y, 宽, 高）：${esc(r.label_approx_bbox_xywh.join(', '))}。工作画布：${esc(r.image.canvas_label)} / ${esc(r.image.image_id)}。</p>${r.object_candidates.map(o=>`<p>对象 ${esc(o.object_id)} 的近似框：${esc(o.approx_bbox_xywh.join(', '))}。</p>`).join('')}<p>这些坐标包含阅读上下文，不是像素分割或无邻物的单株图。</p><h4>空间证据（冻结英文原文）</h4><p>${esc(r.spatial_evidence)}</p><h4>限制</h4><p>${esc(r.uncertainty_and_crop_limitations)}</p>${r.existing_box_recheck?`<p>${esc(r.existing_box_recheck)}</p>`:''}${r.panel_resolution?`<p>${esc(r.panel_resolution)}</p>`:''}</details>`;
      renderContext();
    };
    $('s7-repeat-locus').disabled=false;$('s7-repeat-context').disabled=false;
    $('s7-repeat-locus').addEventListener('change',renderLocus);$('s7-repeat-context').addEventListener('change',renderContext);
    renderLocus();
  }

  function moduleMarkup(key, module) {
    let body = `<article class="s7-module" id="s7-${esc(key)}"><div class="s7-module-head"><h3>${esc(module.title)}</h3>${badge(module.status)}</div><p class="s7-module-summary">${esc(module.summary)}</p>`;
    if (module.metrics?.length) body += `<div class="s7-module-metrics">${module.metrics.map(r=>`<div class="s7-module-metric"><strong>${esc(r.value)}</strong><span>${esc(r.label)}</span></div>`).join('')}</div>`;
    if (module.details?.length) body += `<ul class="s7-module-details">${module.details.map(text=>`<li>${esc(text)}</li>`).join('')}</ul>`;
    if (module.table?.rows?.length) body += `<div class="s7-table-wrap"><table class="s7-table"><thead><tr>${module.table.headers.map(x=>`<th scope="col">${esc(x)}</th>`).join('')}</tr></thead><tbody>${module.table.rows.map(row=>`<tr>${row.map(x=>`<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    if (module.figure) body += `<figure class="s7-evidence-figure"><a href="${esc(module.figure.full)}"><img src="${esc(module.figure.src)}" alt="${esc(module.figure.alt)}" loading="lazy" decoding="async"></a><figcaption>${esc(module.figure.caption)}</figcaption></figure>`;
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
      $('s7-elapsed').textContent = `该快照距登记开始约 ${hours} 小时 ${minutes} 分钟；不是连续计算时长或完成比例。`;
      $('s7-continuity').textContent = data.continuity_note_zh || '';
      $('s7-continuity').hidden = !data.continuity_note_zh;
      $('s7-stage-list').innerHTML = data.stages.map(s=>`<li><span class="s7-stage-number">${s.stage}</span><h3>${esc(s.title)}</h3>${badge(s.status)}</li>`).join('');
      $('s7-findings').innerHTML = data.findings.map(x=>`<p class="s7-finding">${esc(x)}</p>`).join('');
      $('s7-modules').innerHTML = Object.entries(data.modules).map(([key,value])=>moduleMarkup(key,value)).join('');
      $('s7-plan-text').textContent = data.plan;
      $('s7-download-list').innerHTML = data.downloads.length ? links(data.downloads) : '<span class="s7-muted">下载文件尚在整理，可先查看下方研究目录。</span>';
      setupGallery(data.gallery);
      setupBoundary(data.boundary);
      setupChoice(data.choice);
      setupRepeated(data.repeated);
      if(location.hash.startsWith('#s7-')) document.getElementById(location.hash.slice(1))?.scrollIntoView();
      $('s7-load-state').textContent = '已载入保存记录。未审核的实验结果不会在此快照中预填。';
    } catch (error) {
      $('s7-load-state').textContent = '快照未能加载。请查看本页底部的研究目录；页面不会推测任务状态或填入示例结果。';
      $('s7-load-state').classList.add('s7-error');
    }
  }
  init();
})();
