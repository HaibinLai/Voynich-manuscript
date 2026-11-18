'use strict';

const GallowsContext = (() => {
  const metrics={matched:'匹配 DF 的总收益',fixed:'固定 λ 的收益',retune:'重新匹配 λ 的变化'};
  const splits={confirm_reserve:'旧 confirm + reserve',confirm:'旧 confirm',reserve:'旧 reserve',dev:'旧 dev · 诊断'};
  const axes={history:'最近三位是否含配对字形',position:'词内预测位置',event:'首字 / 正文单位 / EOS',history_event:'历史 × 事件类型',history_nearest:'最近相关历史的位置',target:'当前预测目标',hand:'Davis 书手标签',section:'插图类别',currier:'Currier A/B 标签',line_role:'行位角色',folio:'转写页面',leaf:'叶组'};
  const axisNotes={history:'按最近三个已生成历史单位分组。这里描述保存模型在哪些上下文节省费用，不等于把输入符号删掉或替换后再评分。',position:'按当前预测位置分组。位置由已经生成的前缀确定；该分组并不向模型提供最终词长。具体分箱沿用保存记录。',event:'把首字预测、词内单位与 EOS 等事件分开看。EOS 是完整词概率的一部分；不能只保留有收益的字形事件。',history_event:'交叉分组沿用保存记录；组内可能很少。只在该轴内比较事件数，不与其他分组轴相加。',history_nearest:'按相关历史与当前预测之间的距离分组。分组定义以保存方案为准，不把相关历史自动解释为语义关系。',target:'按被预测的原单位分组；原输出身份仍然分别计费。某一输出的改善不等于它的读音已识别。',hand:'这些是项目保存的书手元数据标签。分层不自动控制插图类别、Currier 类别、叶组或上下文分布。',section:'插图类别按保存元数据分组；插图类型不是真实词义标签，且与书手、叶组可能混杂。',currier:'Currier 类别是文本分类标签，不是已经识别的自然语言；不能由本表鉴定语言。',line_role:'行位标签描述预测发生的版面位置；这不是在未见手稿上的独立确认。',folio:'逐转写页面描述。展开页分面与物理叶不是同一计数单位。',leaf:'按物理叶组描述。这里的逐叶数值不是置信区间，也没有重新训练模型。'};
  const cases={true_alias:'真条件等价',non_alias:'未来分布不同',position_confound:'位置混杂',frequency_confound:'频率与位置难例',iid:'独立序列'};
  const pairOrder=['f/k','f/p','f/t','k/p','k/t','p/t'];
  const groupNames={history:{absent:'absent · 最近三位均无配对字形',contains:'contains · 最近三位含配对字形'},event:{first:'first · 首单位',continuation:'continuation · 后续原单位',eos:'eos · 词尾'},history_nearest:{'1':'1 · 前一个单位','2':'2 · 前两个单位','3':'3 · 前三个单位',absent:'absent · 最近三位均未出现'}};
  const esc=x=>String(x??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite=x=>typeof x==='number'&&Number.isFinite(x);
  const fmt=(x,d=6)=>!finite(x)?'未提供':x!==0&&Math.abs(x)<.000001?x.toExponential(3):x.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
  const count=x=>finite(x)?x.toLocaleString('en-US'):'未提供';
  const label=x=>typeof x==='object'?JSON.stringify(x):String(x??'未提供');
  const pair=x=>String(x??'').split('/').join(' / ');
  const canonical=x=>String(x??'').split('/').sort().join('/');
  const rank=x=>{const i=pairOrder.indexOf(canonical(x));return i<0?pairOrder.length:i;};
  const safeLink=(href,text)=>typeof href==='string'&&/^(https?:\/\/|downloads\/|data\/)/.test(href)?`<a href="${esc(href)}"${href.startsWith('http')?' target="_blank" rel="noopener noreferrer"':''}>${esc(text)}</a>`:esc(text);
  const empty=text=>`<div class="gc-empty">${esc(text)}</div>`;
  const table=(heads,rows,caption,cls='')=>`<div class="gc-table-wrap" role="region" tabindex="0" aria-label="${esc(caption)}，可横向滚动"><table class="gc-table ${cls}"><caption>${esc(caption)}</caption><thead><tr>${heads.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  const cell=x=>`<td class="gc-num">${fmt(x)}</td>`;
  const eventCell=(row,key)=>row.events===0?'<td class="gc-num">无事件</td>':cell(row[key]);

  function readState(params){return {version:params.get('version')==='IT'?'IT':'ZL',df:params.get('df')==='150'?150:50,split:Object.hasOwn(splits,params.get('split'))?params.get('split'):'confirm_reserve',metric:Object.hasOwn(metrics,params.get('metric'))?params.get('metric'):'matched',axis:Object.hasOwn(axes,params.get('axis'))?params.get('axis'):'history',pair:params.get('pair')||'k/t'};}
  function selectPairs(data,state){return (data?.pairs||[]).filter(r=>r.version===state.version&&Number(r.df)===state.df&&r.split===state.split).sort((a,b)=>rank(a.pair)-rank(b.pair)||String(a.pair).localeCompare(String(b.pair)));}
  function selectContext(data,state){return (data?.context||[]).filter(r=>r.version===state.version&&Number(r.df)===state.df&&r.split===state.split&&canonical(r.pair)===canonical(state.pair)&&r.axis===state.axis);}
  function normalizeState(data,state){
    const available=(data?.context||[]).filter(r=>r.version===state.version&&Number(r.df)===state.df&&r.split===state.split);
    const pairs=[...new Set(available.map(r=>r.pair))].sort((a,b)=>rank(a)-rank(b));
    if(pairs.length&&!pairs.some(p=>canonical(p)===canonical(state.pair)))state.pair=pairs.find(p=>canonical(p)==='k/t')||pairs[0];
    else if(pairs.length)state.pair=pairs.find(p=>canonical(p)===canonical(state.pair));
    const allowedAxes=[...new Set(available.filter(r=>canonical(r.pair)===canonical(state.pair)).map(r=>r.axis))];
    if(allowedAxes.length&&!allowedAxes.includes(state.axis))state.axis=allowedAxes.includes('history')?'history':allowedAxes[0];
    return {state,pairs,allowedAxes};
  }
  function chart(rows,metric){
    if(!rows.some(r=>finite(r[metric])))return empty('当前比较没有可用数值；没有把缺失或失败转换成零。');
    const extent=Math.max(.000001,...rows.map(r=>Math.abs(r[metric])).filter(finite))*1.15;
    const width=900,height=rows.length*48+65,left=190,right=150,plot=width-left-right,x=value=>left+(value+extent)/(extent*2)*plot;
    return `<div class="gc-chart-wrap" role="region" tabindex="0" aria-label="${esc(metrics[metric])}，六配对完整词费用差，可横向滚动"><svg class="gc-chart" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="gc-chart-title"><title id="gc-chart-title">${esc(metrics[metric])}，bits / 完整词；正数表示节省费用。点值为保存均值，没有绘制置信区间。</title>${[-extent,0,extent].map(value=>`<line x1="${x(value)}" x2="${x(value)}" y1="18" y2="${height-33}" class="${value===0?'gc-zero':'gc-grid'}"/><text class="gc-axis-label" x="${x(value)}" y="${height-12}" text-anchor="middle">${fmt(value,4)}</text>`).join('')}${rows.map((r,i)=>{const y=35+i*48;return `<text x="6" y="${y+4}">${esc(pair(r.pair))}</text>${finite(r[metric])?`<circle cx="${x(r[metric])}" cy="${y}" r="${canonical(r.pair)==='k/t'?5:3.8}" class="${r[metric]<0?'gc-negative':'gc-positive'}"/>`:''}<text x="${width-4}" y="${y+4}" text-anchor="end">${fmt(r[metric])}</text>`;}).join('')}</svg></div>`;
  }
  function renderPairs(data,state){
    const rows=selectPairs(data,state);if(!rows.length)return empty('这一版本、DF 与分区尚无保存结果。不会显示另一分区或另一模型的数值作为替代。');
    return `<div class="gc-result-panel"><h3>${esc(state.version)} · DF ${state.df} · ${esc(splits[state.split])}</h3>${chart(rows,state.metric)}<p class="gc-muted">图为 ${esc(metrics[state.metric])}；主值按词次加权。没有置信区间或新显著性判断。下面始终保留全部三项，避免只选有利的比较。</p>${table(['配对','完整词数','预测事件','页 / 叶','匹配 DF 收益','固定 λ 收益','重新匹配变化'],rows.map(r=>`<tr class="${canonical(r.pair)==='k/t'?'gc-target':''}"><th scope="row">${esc(pair(r.pair))}</th><td>${count(r.words)}</td><td>${count(r.events)}</td><td>${count(r.pages)} / ${count(r.leaves)}</td>${cell(r.matched)}${cell(r.fixed)}${cell(r.retune)}</tr>`),'全部配对 · bits / 完整词')}<details class="study-details"><summary>查看每个配对实际使用的 λ 与局部 DF</summary>${table(['配对','普通 ridge λ / 固定 λ','普通 ridge 实际 DF','匹配 DF 的融合 λ','固定 λ 后的实际 DF','匹配后的实际 DF'],rows.map(r=>`<tr><th scope="row">${esc(pair(r.pair))}</th>${cell(r.base_lambda)}${cell(r.base_df)}${cell(r.fused_lambda)}${cell(r.fixed_df)}${cell(r.matched_df)}</tr>`),'实际拟合强度与局部自由度；相同 λ 不保证相同 DF')}</details></div>`;
  }
  function renderContext(data,state){
    const rows=selectContext(data,state);if(!rows.length)return empty('此语境分组尚无保存结果。没有将其他分组或缺失标签补作本组样本。');
    return `<div class="gc-result-panel"><h3>${esc(pair(state.pair))} · ${esc(axes[state.axis]||state.axis)}</h3><p class="gc-muted">${esc(state.version)} · DF ${state.df} · ${esc(splits[state.split])}。每行的平均变化按该行预测事件数计算，总变化单列；涉及词数跨行可重叠。零事件格不计算均值。</p>${table(['分组（保存标签）','事件数','涉及词数','页 / 叶','匹配 DF / 事件','固定 λ / 事件','重新匹配 / 事件','匹配 DF 总 bits','固定 λ 总 bits','重新匹配总 bits'],rows.map(r=>`<tr><th scope="row">${esc(groupNames[state.axis]?.[r.group]||label(r.group))}</th><td>${count(r.events)}</td><td>${count(r.words)}</td><td>${count(r.pages)} / ${count(r.leaves)}</td>${eventCell(r,'matched')}${eventCell(r,'fixed')}${eventCell(r,'retune')}${cell(r.matched_total)}${cell(r.fixed_total)}${cell(r.retune_total)}</tr>`),'同一轴内事件分组；费用平均为 bits / 预测事件，末三列为总 bits','gc-context-table')}</div>`;
  }
  function renderSynthetic(data,state){
    const rows=(data?.synthetic||[]).filter(r=>Number(r.df)===state.df);
    if(!rows.length)return empty('当前 DF 尚无保存的合成比较。机制真值不能替代拟合结果。');
    return `<p class="gc-muted">沿用上方 DF ${state.df}；此处没有手稿转写版本之分。每行保留种子与实际配对，不把跨机制或两个 DF 当成独立重复。末列是硬合并历史的真值期望额外费用，不是有限测试样本均值，也不是软融合模型的损失；两种限制不同。</p>${table(['机制','种子','配对','词数','预测事件','匹配 DF 收益','固定 λ 收益','重新匹配变化','硬合并真值期望额外费用'],rows.map(r=>`<tr><th scope="row">${esc(cases[r.case]||r.case)}</th><td>${esc(r.seed)}</td><td>${esc(pair(r.pair))}</td><td>${count(r.words)}</td><td>${count(r.events)}</td>${cell(r.matched)}${cell(r.fixed)}${cell(r.retune)}${cell(r.oracle_hard_penalty)}</tr>`),'全部保存合成条件 · bits / 完整词')}`;
  }
  function renderSensitivity(data,state){
    const rows=(data?.sensitivity||[]).filter(r=>r.version===state.version&&Number(r.df)===state.df&&r.split===state.split).sort((a,b)=>rank(a.pair)-rank(b.pair));
    if(!rows.length)return empty('当前筛选尚无保存的追加比较。没有以主结果或其他分区代替。');
    const fused=r=>selectPairs(data,state).find(p=>canonical(p.pair)===canonical(r.pair))?.matched_df;
    const allHigher=rows.every(r=>finite(r.ridge_df)&&finite(fused(r))&&r.ridge_df>fused(r));
    return `<div class="gc-result-panel"><h3>${esc(state.version)} · 原 DF 目标 ${state.df} · ${esc(splits[state.split])}</h3><p class="gc-muted">所有费用差均为 bits / 完整词。原 ridge → 新 ridge 的收益，加上新 ridge → 融合模型的收益，对应原匹配 DF 的总收益。这里的“DF 目标”标识原模型，并非追加 ridge 的实际 DF。${allHigher?'本筛选下，新 ridge 的实际 DF 逐项高于融合模型；这不是相同 DF 的比较。':''}</p>${table(['配对','状态','完整词数','原 ridge → 新 ridge','同 λ 融合优势','新 ridge 实际 DF','融合模型实际 DF','共同使用的融合 λ'],rows.map(r=>`<tr><th scope="row">${esc(pair(r.pair))}</th><td>${esc(r.status==='converged'?'已收敛':r.status||'见保存记录')}</td><td>${count(r.words)}</td>${cell(r.ridge_from_base)}${cell(r.fusion_at_same_lambda)}${cell(r.ridge_df)}${cell(fused(r))}${cell(r.fused_lambda)}</tr>`),'结果后追加的全部六配对；实际 DF 不同')}</div>`;
  }
  function renderEvidence(data){
    const assets=Array.isArray(data.assets)?data.assets:[];
    const limits=Array.isArray(data.limitations)?data.limitations:[];
    const hashes=data.source_hashes&&typeof data.source_hashes==='object'?data.source_hashes:{};
    const scope=typeof data.scope==='string'?`<p class="gc-muted">${esc(data.scope)}</p>`:'';
    return `${scope}${limits.length?`<ul class="gc-evidence-list">${limits.map(t=>`<li>${esc(label(t))}</li>`).join('')}</ul>`:''}<div class="gc-downloads"><a href="data/gallows-context.json" download="gallows-context-complete.json">下载全部公开快照 JSON</a>${assets.map(a=>safeLink(a.href,a.label||a.title||a.href)).join('')}</div>${Object.keys(hashes).length?`<details class="study-details gc-hashes"><summary>查看来源文件哈希</summary>${Object.entries(hashes).map(([p,h])=>`<p>${esc(p)}<br><code>${esc(label(h))}</code></p>`).join('')}</details>`:''}<p class="gc-muted">网页下载不受筛选影响。本页只读取已保存汇总；核验通过的具体范围以原始收据为准。</p>`;
  }
  async function mount(){
    const $=selector=>document.querySelector(selector);let data;
    try{const response=await fetch('data/gallows-context.json');if(response.status===404){$('#gc-state').textContent='研究页结构已准备，公开结果快照尚未接入。当前没有展示实验数值或完成结论。';return;}if(!response.ok)throw new Error(`HTTP ${response.status}`);data=await response.json();if(!Array.isArray(data.pairs)||!Array.isArray(data.context)||!Array.isArray(data.synthetic))throw new Error('快照字段与页面约定不符');}
    catch(error){$('#gc-state').classList.add('gc-status-failed');$('#gc-state').textContent=`保存快照未能载入：${error.message}。没有显示替代数值。`;return;}
    let state=readState(new URLSearchParams(location.search));const selectors={version:'#gc-version',df:'#gc-df',split:'#gc-split',metric:'#gc-metric',axis:'#gc-axis',pair:'#gc-context-pair'};
    const render=()=>{const options=normalizeState(data,state);state=options.state;$('#gc-context-pair').innerHTML=(options.pairs.length?options.pairs:['k/t']).map(p=>`<option value="${esc(p)}">${esc(pair(p))}</option>`).join('');$('#gc-axis').innerHTML=(options.allowedAxes.length?options.allowedAxes:Object.keys(axes)).map(a=>`<option value="${esc(a)}">${esc(axes[a]||a)}</option>`).join('');Object.entries(selectors).forEach(([k,selector])=>{$(selector).value=String(state[k]);$(selector).disabled=(k==='axis'||k==='pair')?!options.allowedAxes.length:!data.pairs.length;});$('#gc-pair-results').innerHTML=renderPairs(data,state);$('#gc-context-results').innerHTML=renderContext(data,state);$('#gc-context-title').textContent=`${pair(state.pair)}：哪些预测事件发生变化？`;$('#gc-axis-description').textContent=axisNotes[state.axis]||'标签含义以保存方案为准。';$('#gc-sensitivity').hidden=!Array.isArray(data.sensitivity)||!data.sensitivity.length;if(!$('#gc-sensitivity').hidden)$('#gc-sensitivity-results').innerHTML=renderSensitivity(data,state);$('#gc-synthetic-results').innerHTML=$('#gc-synthetic-details').open?renderSynthetic(data,state):'<p class="gc-muted">展开后按当前 DF 显示全部保存条件。</p>';};
    const statusNames={complete:'保存结果齐全',completed:'保存结果齐全',verified:'保存结果已核验',partial:'保存结果未齐',running:'仍有任务在运行',failed:'存在失败记录'};
    $('#gc-state').textContent=`已载入保存快照；不是实时监控。${data.status?`记录状态：${statusNames[data.status]||data.status}。`:''}页面只展示保存值，不把部分结果称为完成研究。`;
    $('#gc-findings').innerHTML=(Array.isArray(data.findings)?data.findings:[]).map(t=>`<article class="gc-finding">${typeof t==='object'&&t.title?`<h3>${esc(t.title)}</h3>`:''}<p>${esc(typeof t==='object'?t.text: t)}</p></article>`).join('');
    $('#gc-evidence-content').innerHTML=renderEvidence(data);$('#gc-snapshot').textContent=data.created_utc?`保存快照：${data.created_utc}`:'保存快照 · 来源未提供时间';
    Object.entries(selectors).forEach(([k,selector])=>$(selector).addEventListener('change',()=>{state[k]=k==='df'?Number($(selector).value):$(selector).value;render();const params=new URLSearchParams(state);history.pushState(null,'',`${location.pathname}?${params}${location.hash}`);}));
    $('#gc-synthetic-details').addEventListener('toggle',()=>{if($('#gc-synthetic-details').open)$('#gc-synthetic-results').innerHTML=renderSynthetic(data,state);});
    addEventListener('popstate',()=>{state=readState(new URLSearchParams(location.search));render();});render();
  }
  return {readState,selectPairs,selectContext,normalizeState,renderPairs,renderContext,renderSynthetic,renderSensitivity,renderEvidence,mount};
})();
if(typeof document!=='undefined')GallowsContext.mount();
if(typeof module!=='undefined'&&module.exports)module.exports=GallowsContext;
