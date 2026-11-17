'use strict';

const Concordance = (() => {
  const PAGE_SIZE = 50;
  const labels = {ZL:'ZL3b', IT:'IT2a'};
  const boundaryNames = {start:'行位起点',end:'行位终点',certain:'明确空格',uncertain:'不确定空格',illustration:'插图中断'};
  let loading;
  let request = 0;
  const own = (obj, key) => Object.prototype.hasOwnProperty.call(obj || {}, key) ? obj[key] : undefined;
  const lower = value => String(value ?? '').replace(/[A-Z]/g, c => c.toLowerCase());
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const count = value => Number(value).toLocaleString('zh-CN');
  const uncertain = slot => slot.left_boundary === 'uncertain' || slot.right_boundary === 'uncertain';

  function parseParams(params) {
    const p = params instanceof URLSearchParams ? params : new URLSearchParams(params || '');
    return {v:p.get('v') === 'IT' ? 'IT' : 'ZL', mode:p.get('mode') === 'literal' ? 'literal' : 'exact',
      q:p.get('q') || '', folio:p.get('folio') || 'all', type:p.get('type') || 'all',
      uncertain:p.get('uncertain') !== '0', page:Math.max(1, Math.floor(Number(p.get('page')) || 1))};
  }

  function query(dataset, options = {}) {
    const input = {v:'ZL',mode:'exact',q:'',folio:'all',type:'all',uncertain:true,page:1,...options};
    input.v = input.v === 'IT' ? 'IT' : 'ZL';
    input.mode = input.mode === 'literal' ? 'literal' : 'exact';
    input.q = String(input.q ?? '');
    input.uncertain = input.uncertain !== false;
    const normalized = lower(input.q);
    const result = {input,normalized,status:'ready',error:'',groups:[],
      counts:{occurrences:input.mode === 'exact' ? 0 : null,records:0,folios:0,leaf_groups:0,uncertain_occurrences:input.mode === 'exact' ? 0 : null},
      page:1,page_count:0,page_size:PAGE_SIZE,page_items:[]};
    if (!normalized) {result.status = 'empty'; return result;}
    if (input.mode === 'exact' && !/^(?:[a-z']|@[0-9]{3};)+$/.test(normalized)) {
      result.status = 'invalid';
      result.error = '精确模式只接受一个完整 EVA 规范词形：a–z、直撇号及 @000;–@999;。空格、括号、?、* 等记号请用「逐行文字」查找；不会自动删字或改拼写。';
      return result;
    }
    const eligible = r => r.version === input.v && (input.folio === 'all' || r.folio === input.folio) && (input.type === 'all' || r.locus_type === input.type);
    if (input.mode === 'exact') {
      const hits = own(own(dataset.postings, input.v), normalized) || [];
      const groups = new Map();
      for (const [recordId, slotIndex] of hits) {
        const r = dataset.records[recordId], slot = r?.slots[slotIndex];
        if (!r || r.id !== recordId || !slot || slot.normalized !== normalized) throw new Error('索引位置与保存记录不一致。');
        if (!eligible(r) || (!input.uncertain && uncertain(slot))) continue;
        if (!groups.has(recordId)) groups.set(recordId, {record_id:recordId,slots:[]});
        groups.get(recordId).slots.push(slotIndex);
        result.counts.occurrences++;
        if (uncertain(slot)) result.counts.uncertain_occurrences++;
      }
      result.groups = [...groups.values()];
    } else {
      for (const r of dataset.records) {
        if (eligible(r) && lower(r.display).includes(normalized)) result.groups.push({record_id:r.id,slots:[]});
      }
    }
    result.counts.records = result.groups.length;
    result.counts.folios = new Set(result.groups.map(g => dataset.records[g.record_id].folio)).size;
    result.counts.leaf_groups = new Set(result.groups.map(g => dataset.records[g.record_id].leaf_group)).size;
    result.page_count = Math.ceil(result.groups.length / PAGE_SIZE);
    result.page = Math.min(Math.max(1, Math.floor(Number(input.page)) || 1), Math.max(1,result.page_count));
    result.page_items = result.groups.slice((result.page - 1) * PAGE_SIZE, result.page * PAGE_SIZE);
    return result;
  }

  function counterparts(dataset, record) {
    const other = record.version === 'ZL' ? 'IT' : 'ZL';
    return (own(own(dataset.by_locator, record.locator), other) || []).map(id => dataset.records[id]);
  }

  function buildExport(dataset, result, now = new Date().toISOString()) {
    const folios = [...new Set(result.groups.map(g => dataset.records[g.record_id].folio))];
    return {schema_version:1,tool:'Voynich manuscript concordance',exported_utc:now,
      sources:dataset.sources,metadata:dataset.metadata,
      query:{...result.input,normalized:result.normalized,uncertain_filter_applied:result.input.mode === 'exact'},
      status:result.status,counts:result.counts,
      export_scope:{all_filtered_matches:true,pagination_unit:'record',page_size:PAGE_SIZE,exported_records:result.groups.length},
      notes:['资料阅读索引，不是译文或新的统计检验。','槽号属于本索引；同 locator 的另一版仅作整行位对照，不按槽对齐。',
        '精确模式计词次；逐行文字模式每条命中记录计一次，不计重叠子串词次。','已包括先前揭晓的预留资料，不是新的未见测试集。'],
      folios:Object.fromEntries(folios.map(f => [f,own(dataset.folios,f) || null])),
      results:result.groups.map(g => {const r=dataset.records[g.record_id];return {record:r,matching_slots:g.slots,counterparts:counterparts(dataset,r)};})};
  }

  function hrefFor(input, changes = {}) {
    const o = {...input,...changes};
    const p = new URLSearchParams({q:o.q,v:o.v,mode:o.mode,folio:o.folio,type:o.type,uncertain:o.uncertain ? '1' : '0',page:String(o.page)});
    return '#concordance?' + p.toString();
  }

  function highlighted(record, group, result) {
    const chars = Array.from(record.display), ranges = [];
    if (result.input.mode === 'exact') {
      for (const index of group.slots) {const s=record.slots[index];ranges.push([s.display_start,s.display_end]);}
    } else {
      const text = lower(record.display), q = result.normalized;
      let pos = text.indexOf(q);
      while (pos !== -1) {ranges.push([Array.from(text.slice(0,pos)).length,Array.from(text.slice(0,pos+q.length)).length]);pos=text.indexOf(q,pos+1);}
    }
    const flags = new Uint8Array(chars.length);
    for (const [start,end] of ranges) {
      if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end < start || end > chars.length) throw new Error('展示区间超出保存的行位文字。');
      flags.fill(1,start,end);
    }
    let html='',marked=false;
    chars.forEach((char,i) => {if(Boolean(flags[i])!==marked){html+=flags[i]?'<mark>':'</mark>';marked=Boolean(flags[i]);}html+=escapeHTML(char);});
    return html+(marked?'</mark>':'');
  }

  function external(url,label) {
    return typeof url === 'string' && /^https:\/\//.test(url) ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer">${escapeHTML(label)} ↗</a>` : '';
  }

  function imageLinks(dataset, record) {
    const f = own(dataset.folios,record.folio) || {};
    const verified = f.image_mapping_status === 'exact_manifest_label' && typeof f.image_link === 'string' && /^https:\/\//.test(f.image_link);
    const study = typeof f.study20_url === 'string' && /^#manuscript\?folio=/.test(f.study20_url) ? `<a href="${escapeHTML(f.study20_url)}">20 页原图与复核 →</a>` : '';
    const evidence = verified && f.image_mapping_evidence ? `<details class="concordance-image-evidence"><summary>整页映射依据</summary><pre>${escapeHTML(typeof f.image_mapping_evidence === 'string' ? f.image_mapping_evidence : JSON.stringify(f.image_mapping_evidence,null,2))}</pre></details>` : '';
    return `<div class="concordance-image-links">${verified?external(f.image_link,'耶鲁整页原图'):external(f.collection_url,'馆藏入口')}${study}<span>${verified?'这是整页链接，不是命中词的定位框。':'没有已核验的整页映射；不猜测逐行坐标。'}</span>${evidence}</div>`;
  }

  function resultCard(dataset, group, result) {
    const r = dataset.records[group.record_id], other = r.version === 'ZL' ? 'IT' : 'ZL';
    const comparisons = counterparts(dataset,r);
    const slots = result.input.mode === 'exact' ? `<div class="concordance-slots"><span>命中槽（从 0 开始）</span>${group.slots.map(index => {
      const s=r.slots[index],isUncertain=uncertain(s);
      const title=`左：${boundaryNames[s.left_boundary]||s.left_boundary}；右：${boundaryNames[s.right_boundary]||s.right_boundary}`;
      return `<span class="concordance-slot ${isUncertain?'concordance-slot-uncertain':''}" title="${escapeHTML(title)}">${index}${isUncertain?' · 边界未定':''}<span class="concordance-boundaries">${escapeHTML(title)}</span></span>`;
    }).join('')}</div>` : '<p class="concordance-line-note">字面命中行位；高亮只用于阅读，不据此分词。</p>';
    return `<article class="panel concordance-card"><header><div><h2>${escapeHTML(r.locator)}</h2><span>${escapeHTML(r.folio)} · 叶组 ${escapeHTML(r.leaf_group)}</span></div><span class="pill">${escapeHTML(r.locus_type || '类型未记录')}</span></header>
      <div class="concordance-comparison"><div class="concordance-selected"><h3>${labels[r.version]} · 整理后展示串 <small>源文件第 ${escapeHTML(r.source_line)} 行</small></h3><code class="concordance-line">${highlighted(r,group,result)}</code>${slots}
      <details class="concordance-original"><summary>查看原始 IVTFF 串</summary><code class="concordance-line">${escapeHTML(r.raw)}</code></details></div>
      <div class="concordance-counterpart"><h3>${labels[other]} · 同定位键原串</h3>${comparisons.length?comparisons.map(c=>`<div class="concordance-other-record"><p>源文件第 ${escapeHTML(c.source_line)} 行 · ${escapeHTML(c.locus_type||'类型未记录')}</p><code class="concordance-line">${escapeHTML(c.raw)}</code></div>`).join(''):'<p class="concordance-missing">这一版没有收录相同定位键。</p>'}<p class="concordance-line-note">整行位并列，不按词槽配对。${comparisons.length>1?'此定位键有多条记录，全部保留。':''}</p></div></div>${imageLinks(dataset,r)}</article>`;
  }

  function selectOptions(values, current, allLabel) {
    const list = [...values];
    if (current !== 'all' && !list.includes(current)) list.push(current);
    return `<option value="all">${allLabel}</option>`+list.map(v=>`<option value="${escapeHTML(v)}" ${v===current?'selected':''}>${escapeHTML(v)}</option>`).join('');
  }

  function pagination(result) {
    if (!result.page_count) return '';
    return `<nav class="concordance-pagination" aria-label="检索结果分页"><button type="button" class="button secondary small" data-concordance-page="${result.page-1}" ${result.page===1?'disabled':''}>上一页</button><span>第 ${result.page} / ${result.page_count} 页 · 每页最多 ${PAGE_SIZE} 个命中行位</span><button type="button" class="button secondary small" data-concordance-page="${result.page+1}" ${result.page===result.page_count?'disabled':''}>下一页</button></nav>`;
  }

  function heading() {
    return '<div class="page-heading"><div><span class="eyebrow">CONCORDANCE / FIND THE ORIGINAL CONTEXT</span><h1 id="concordance-heading">一个词形，出现在哪里？</h1><p>检索 ZL 与 IT 的公开转写，回到同一位置的原始记号。EVA 是字形代号；找到相同拼写，并不等于知道它的含义。</p></div></div>';
  }

  function provenance(dataset) {
    return `<details class="concordance-method"><summary>分词规则、来源与范围</summary><p>句点是明确空格，逗号是不确定空格；逗号两侧的片段都标记边界未定。插图中断单独分隔，普通完整尖括号标记从展示与匹配层移除。有效成对花括号可从匹配层消去；备选、缺字及不合法片段仍保留原串，不提取其中可读子串。</p><p>槽号从 0 开始，包含空槽与未决槽；属于本索引，不能替代其他实验的槽号。转写分区指 folio（含展开页面分面），不是 train/dev 等研究划分；f85/f86 沿用合并叶组。行位不必等于一条物理书写行。</p><p>本索引包括已经揭晓的预留资料。它是公开转写的阅读工具，不是新的独立 OCR、逐字认证、译文或统计检验。</p>${Object.entries(dataset.sources).map(([version,s])=>`<p><strong>${escapeHTML(labels[version]||version)} · ${escapeHTML(s.source_file)}</strong><br>${external(s.url,'转写来源')}<br><span class="concordance-hash">SHA-256 ${escapeHTML(s.sha256)}</span></p>`).join('')}<div class="paper-links"><a href="downloads/concordance-ZL.txt" download>ZL 全部逐行文字 ↓</a><a href="downloads/concordance-IT.txt" download>IT 全部逐行文字 ↓</a><a href="downloads/concordance-guide.txt" download>资料与规则说明 ↓</a><a href="downloads/concordance-summary.json" download>数据清单与计数 ↓</a><a href="downloads/concordance-audit.json" download>独立数据核验 ↓</a></div></details>`;
  }

  function markup(dataset,result) {
    const o=result.input;
    const records=dataset.records.filter(r=>r.version===o.v);
    const folios=[...new Set(records.map(r=>r.folio))],types=[...new Set(records.map(r=>r.locus_type))].sort();
    const summary=result.status==='ready'?`<div class="concordance-counts" role="status" aria-live="polite">${o.mode==='exact'?`<div><strong>${count(result.counts.occurrences)}</strong><span>词次</span></div>`:''}<div><strong>${count(result.counts.records)}</strong><span>命中行位</span></div><div><strong>${count(result.counts.folios)}</strong><span>转写分区</span></div><div><strong>${count(result.counts.leaf_groups)}</strong><span>叶组</span></div></div><p class="concordance-count-note">${o.mode==='exact'?`${count(result.counts.uncertain_occurrences)} 个命中词次涉及不确定边界。同一行位的命中槽合并展示。`:'同一记录只计一次命中行位，不把重叠子串算成词次。'}计数包含全部筛选结果，不随分页改变。</p>`:'';
    let content='';
    if(result.status==='empty') content='<div class="panel concordance-empty"><h2>先输入想查的字形</h2><p>例如 <code>daiin</code>。点击「填入示例」只填写输入框，提交后才会查询。寻找 <code>?</code>、<code>[a:b]</code> 等未决记号时，切换「逐行文字」。</p></div>';
    else if(result.status==='invalid') content=`<div class="notice error" role="status">${escapeHTML(result.error)}</div>`;
    else if(!result.groups.length) content='<div class="panel concordance-empty"><h2>没有匹配结果</h2><p>检查所选版本、转写分区和行位类型，或用「逐行文字」查看原有记号。系统不会自动替换字形或放宽查询。</p></div>';
    else content=pagination(result)+`<div class="concordance-results">${result.page_items.map(g=>resultCard(dataset,g,result)).join('')}</div>`+pagination(result);
    return `${heading()}<form id="concordance-form" class="panel concordance-form" role="search" aria-label="公开转写词形检索"><div class="concordance-query-row"><div class="field"><label for="concordance-query">EVA 词形或原有记号</label><input id="concordance-query" name="q" type="search" value="${escapeHTML(o.q)}" placeholder="例如 daiin" spellcheck="false" autocapitalize="off" autocomplete="off" aria-describedby="concordance-query-help"></div><button class="button" type="submit">查找位置</button><button class="button secondary" type="button" id="concordance-example">填入示例</button></div>
      <div class="concordance-filters"><div class="field"><label for="concordance-version">转写版本</label><select id="concordance-version" name="v"><option value="ZL" ${o.v==='ZL'?'selected':''}>ZL3b</option><option value="IT" ${o.v==='IT'?'selected':''}>IT2a</option></select></div><div class="field"><label for="concordance-mode">查询方式</label><select id="concordance-mode" name="mode"><option value="exact" ${o.mode==='exact'?'selected':''}>精确词形</option><option value="literal" ${o.mode==='literal'?'selected':''}>逐行文字</option></select></div><div class="field"><label for="concordance-folio">转写分区</label><select id="concordance-folio" name="folio">${selectOptions(folios,o.folio,'全部分区')}</select></div><div class="field"><label for="concordance-type">原行位类型</label><select id="concordance-type" name="type">${selectOptions(types,o.type,'全部类型')}</select></div></div>
      <label class="concordance-boundary-filter"><input id="concordance-uncertain" type="checkbox" ${o.uncertain?'checked':''} ${o.mode==='literal'?'disabled':''}>保留不确定空格两侧的词形 <span>${o.mode==='literal'?'逐行文字不按词边界过滤':'默认保留；取消后排除任一侧边界未定的片段'}</span></label><p id="concordance-query-help">${o.mode==='exact'?'精确匹配完整规范词形；大小写视为相同，保留直撇号及三位扩展编码。':'按展示串作字面子串查询，只忽略 ASCII 大小写；不使用正则或模糊匹配。'}</p></form>
      ${summary}<div class="concordance-actions"><button class="button secondary small" type="button" id="concordance-copy">复制查询链接</button><button class="button secondary small" type="button" id="concordance-download" ${result.status!=='ready'?'disabled':''}>下载全部匹配 JSON</button><span id="concordance-action-status" role="status" aria-live="polite"></span><input id="concordance-copy-fallback" readonly hidden aria-label="可复制的查询链接"></div>${content}${provenance(dataset)}`;
  }

  async function load() {
    if (!loading) loading = fetch('data/concordance.json').then(response=>{if(!response.ok)throw new Error(`HTTP ${response.status}`);return response.json();}).then(dataset=>{
      if(dataset.schema_version!==1 || !Array.isArray(dataset.records) || !dataset.sources?.ZL || !dataset.sources?.IT || !dataset.postings || !dataset.by_locator) throw new Error('不支持的索引数据格式。');
      return dataset;
    }).catch(error=>{loading=undefined;throw error;});
    return loading;
  }

  async function render(params) {
    const target=document.getElementById('concordance');
    if(!target)return;
    const current=++request,options=parseParams(params);
    target.classList.add('concordance-view');
    target.innerHTML=heading()+'<div class="panel concordance-empty" role="status">正在载入双版词形索引…</div>';
    try {
      const dataset=await load();
      if(current!==request)return;
      const result=query(dataset,options);
      target.innerHTML=markup(dataset,result);
      const find=selector=>target.querySelector(selector);
      const navigate=next=>{const hash=hrefFor(next);if(location.hash===hash)render(new URLSearchParams(hash.split('?')[1]));else location.hash=hash;};
      const formOptions=()=>({q:find('#concordance-query').value,v:find('#concordance-version').value,mode:find('#concordance-mode').value,folio:find('#concordance-folio').value,type:find('#concordance-type').value,uncertain:find('#concordance-uncertain').checked,page:1});
      find('#concordance-form').addEventListener('submit',event=>{event.preventDefault();navigate(formOptions());});
      for(const id of ['version','mode','folio','type','uncertain'])find('#concordance-'+id).addEventListener('change',()=>navigate(formOptions()));
      find('#concordance-example').addEventListener('click',()=>{find('#concordance-query').value='daiin';find('#concordance-query').focus();});
      target.querySelectorAll('[data-concordance-page]').forEach(button=>button.addEventListener('click',()=>navigate({...result.input,page:Number(button.dataset.concordancePage)})));
      find('#concordance-copy').addEventListener('click',async()=>{
        const url=location.href.split('#')[0]+hrefFor(result.input,{page:result.page});
        try {if(!navigator.clipboard?.writeText)throw new Error('clipboard unavailable');await navigator.clipboard.writeText(url);find('#concordance-action-status').textContent='查询链接已复制。';}
        catch {const input=find('#concordance-copy-fallback');input.hidden=false;input.value=url;input.focus();input.select();find('#concordance-action-status').textContent='请复制下方已选中的链接。';}
      });
      find('#concordance-download').addEventListener('click',()=>{
        const blob=new Blob([JSON.stringify(buildExport(dataset,result),null,2)+'\n'],{type:'application/json;charset=utf-8'});
        const url=URL.createObjectURL(blob),anchor=document.createElement('a');anchor.href=url;anchor.download=`voynich-concordance-${result.input.v}-${result.input.mode}.json`;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
        find('#concordance-action-status').textContent=`已导出全部 ${count(result.counts.records)} 个匹配行位${result.input.mode==='exact'?'、'+count(result.counts.occurrences)+' 个词次':''}。`;
      });
    } catch(error) {
      if(current!==request)return;
      target.innerHTML=heading()+`<div class="notice error" role="status"><p>索引未能载入。现有研究页面仍可阅读。</p><p>${escapeHTML(error.message)}</p><button type="button" class="button secondary small" id="concordance-retry">重试载入</button></div>`;
      target.querySelector('#concordance-retry').addEventListener('click',()=>render(params));
    }
  }

  return {parseParams,query,buildExport,render};
})();

async function renderConcordance(params) { return Concordance.render(params); }
