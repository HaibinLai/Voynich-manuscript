'use strict';

const ParameterSharing = (() => {
  const conditionOrder = ['base','FP','KT','both',...['FP','KT','both'].flatMap(t=>[1,2,3].map(n=>`${t}_control${n}`))];
  const cases = ['true_alias','non_alias','position_confound','frequency_confound','iid'];
  const caseNames = {true_alias:'真条件等价',non_alias:'未来分布不同',position_confound:'位置混杂',frequency_confound:'频率与位置难例',iid:'IID · 没有专属配对'};
  const caseNotes = {
    true_alias:'给定位置后，a/b 的未来分布相同；c/d 不同。输出仍保留 a 与 b 的身份费用。',
    non_alias:'a/b 和 c/d 的未来分布都不同。软融合仍保留区别，有限样本的正则化收益不能直接判为异体证据。',
    position_confound:'忽略位置时 a/b 的后继分布相同，给定位置却不同；含输入身份与位置的交互，主加性模型可能失配。',
    frequency_confound:'a/b 是条件等价，但输出身份与位置强相关；必须计原身份费用。普通位置系数可表达这类输出关联。',
    iid:'所有输入符号都不帮助预测未来，任意配对都可共享；不存在专属于 a/b 的真值。有限样本收益并不要求为零。'
  };
  const statuses = {available:'可比较',completed:'任务完成',complete:'汇总齐全',converged:'已收敛',failed:'运行失败',missing:'记录缺失',incomplete:'记录未齐',invalid:'记录无效',unmatched:'DF 未匹配',unavailable:'不可比较'};
  const populations = {confirm_reserve:'旧 confirm + reserve',confirm:'旧 confirm',reserve:'旧 reserve',dev:'旧 dev'};
  const esc = x => String(x ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const finite = x => typeof x==='number' && Number.isFinite(x);
  const fmt = (x,d=5) => !finite(x)?'未提供':(x!==0&&Math.abs(x)<.00001?x.toExponential(2):x.toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d}));
  const integer = x => finite(x)?x.toLocaleString('en-US'):'未提供';
  const interval = x => Array.isArray(x)&&x.length===2&&x.every(finite)?`[${fmt(x[0])}, ${fmt(x[1])}]`:'未提供';
  const statusText = x => statuses[x] || x || '状态未提供';
  const label = c => c==='base'?'普通 ridge':c==='FP'?'f / p':c==='KT'?'k / t':c==='both'?'两组一起':/^(.+)_control([123])$/.test(c)?`${label(c.split('_control')[0])} · 参照 ${c.at(-1)}`:c;
  const pairs = value => Array.isArray(value)&&value.length?value.map(p=>p.join(' / ')).join(' ＋ '):'无额外配对';
  const link = (href,text) => typeof href==='string'&&(/^(?:https?:\/\/|downloads\/|data\/|assets\/)/.test(href))?`<a href="${esc(href)}"${href.startsWith('http')?' target="_blank" rel="noopener noreferrer"':''}>${esc(text)}</a>`:esc(text);
  const table = (headers,rows,caption,extra='') => `<div class="sharing-table-wrap" tabindex="0" role="region" aria-label="${esc(caption)}，可横向滚动"><table class="sharing-table ${extra}"><caption>${esc(caption)}</caption><thead><tr>${headers.map(h=>`<th scope="col">${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
  const empty = text => `<div class="sharing-empty">${esc(text)}</div>`;

  function filtersFromParams(params) {
    return {version:['ZL','IT'].includes(params.get('version'))?params.get('version'):'ZL',df:params.get('df')==='150'?150:50,
      population:Object.hasOwn(populations,params.get('population'))?params.get('population'):'confirm_reserve',
      view:params.get('view')==='controls'?'controls':'ridge',case:cases.includes(params.get('case'))?params.get('case'):'all'};
  }
  function realRows(summary,f) {
    return (summary?.manuscript?.rows||[]).filter(r=>r.version===f.version&&r.df===f.df).sort((a,b)=>conditionOrder.indexOf(a.condition)-conditionOrder.indexOf(b.condition));
  }
  function chartRows(summary,f) {
    if(f.view==='ridge')return realRows(summary,f).map(r=>{const p=r.populations?.[f.population],a=p?.gain_vs_base;return {name:label(r.condition),value:p?.status==='available'?a?.word_mean_gain:null,range:a?.leave_one_leaf_out?.range,target:['FP','KT','both'].includes(r.condition),reason:p?.gain_reason||p?.reason||r.reason,status:p?.status==='available'&&!a?'unavailable':r.status};});
    const paired=condition=>pairs(realRows(summary,f).find(r=>r.condition===condition)?.pairs);
    return (summary?.manuscript?.target_control_comparisons||[]).filter(r=>r.version===f.version&&r.df===f.df).flatMap(r=>{
      const p=r.populations?.[f.population]||{};
      return [...(p.controls||[]),{condition:'mean_three_controls',...p.mean_three_controls}].map(c=>({name:`${paired(r.target)} vs ${c.condition==='mean_three_controls'?'三个参照均值':paired(c.condition)}`,value:c.status==='available'?c.comparison?.word_mean_gain:null,range:c.comparison?.leave_one_leaf_out?.range,target:c.condition==='mean_three_controls',reason:c.reason,status:c.status}));
    });
  }
  function gainChart(rows,description) {
    if(!rows.some(r=>finite(r.value)))return empty('当前筛选没有可比较的增益。请查看下表的失败、未匹配或缺失原因；没有将它们补成零。');
    const values=rows.flatMap(r=>[r.value,...(Array.isArray(r.range)?r.range:[])]).filter(finite);
    const extent=Math.max(.000001,...values.map(Math.abs))*1.12;
    const w=900,h=rows.length*34+65,left=300,right=145,plot=w-left-right;
    const x=v=>left+(v+extent)/(2*extent)*plot;
    return `<div class="sharing-chart-wrap" tabindex="0" role="region" aria-label="${esc(description)}，可横向滚动"><svg class="sharing-chart" viewBox="0 0 ${w} ${h}" role="img" aria-labelledby="gain-chart-title"><title id="gain-chart-title">${esc(description)}。正值表示目标比较节省完整词预测费用；细线是留一叶组范围，不是置信区间。</title>${[-extent,0,extent].map(v=>`<line x1="${x(v)}" x2="${x(v)}" y1="18" y2="${h-34}" class="${v===0?'chart-zero':'chart-grid'}"/><text x="${x(v)}" y="${h-13}" text-anchor="middle" class="chart-muted">${fmt(v,4)}</text>`).join('')}${rows.map((r,i)=>{const y=33+i*34;return `<text x="0" y="${y+4}">${esc(r.name)}</text>${finite(r.value)?`${Array.isArray(r.range)&&r.range.every(finite)?`<line x1="${x(r.range[0])}" x2="${x(r.range[1])}" y1="${y}" y2="${y}" class="chart-interval"/>`:''}<circle cx="${x(r.value)}" cy="${y}" r="${r.target?4.5:3.5}" class="${r.value<0?'chart-negative':r.target?'chart-target':'chart-control'}"/><text x="${w-4}" y="${y+4}" text-anchor="end">${fmt(r.value)}</text>`:`<text x="${left}" y="${y+4}" class="chart-missing">${esc(statusText(r.status))}</text>`}`;}).join('')}</svg></div><p class="sharing-chart-caption">圆点：逐词平均节省（bits / 完整词）。细线：固定模型，只删除评价叶组后重算的剩余词均值范围，<strong>只是稳定性描述，不是置信区间，也不重训模型</strong>。不新增 p 值，也不按结果排序。</p>`;
  }

  function realPanel(summary,f) {
    const rows=realRows(summary,f);
    if(!rows.length)return empty('尚无这组版本和 DF 的保存结果。这里不会用其他版本、DF 或预演数值替代。');
    let body;
    if(f.view==='ridge') {
      body=table(['条件 / 实际配对','状态','完整词费用','相对 ridge 节省','目标词数','页 / 叶组','留一叶组范围'],rows.map(r=>{
        const p=r.populations?.[f.population]||{},a=p.gain_vs_base;
        const cost=p.status==='available'?p.cost:null;
        return `<tr class="${['FP','KT','both'].includes(r.condition)?'target-row':''}"><th scope="row">${esc(label(r.condition))}<br><code>${esc(pairs(r.pairs))}</code></th><td class="${r.status==='available'?'':'failed'}">${esc(statusText(r.status))}${r.reason?`<br>${esc(r.reason)}`:''}${!a&&p.gain_reason?`<br>增益：${esc(p.gain_reason)}`:''}</td><td class="numeric">${fmt(cost?.mean_bits_per_word)}</td><td class="numeric">${fmt(a?.word_mean_gain)}</td><td>${integer(cost?.words)}</td><td>${a?`${integer(a.pages)} / ${integer(a.leaf_groups)}`:'未提供'}</td><td class="numeric">${interval(a?.leave_one_leaf_out?.range)}</td></tr>`;
      }),`${f.version} · DF ${f.df} · ${populations[f.population]}，全部 13 个预定条件`);
    } else {
      const comparisons=(summary.manuscript.target_control_comparisons||[]).filter(r=>r.version===f.version&&r.df===f.df);
      body=table(['目标','参照','状态','参照成本','目标成本','参照 − 目标','词 / 页 / 叶组','留一叶组范围'],comparisons.flatMap(r=>{
        const p=r.populations?.[f.population]||{};
        return [...(p.controls||[]),{condition:'mean_three_controls',...p.mean_three_controls}].map(c=>{const a=c.status==='available'?c.comparison:null;return `<tr class="${c.condition==='mean_three_controls'?'target-row':''}"><th scope="row">${esc(label(r.target))}</th><td>${esc(c.condition==='mean_three_controls'?'三个参照均值':label(c.condition))}${c.condition==='mean_three_controls'?'':`<br><code>${esc(pairs(rows.find(row=>row.condition===c.condition)?.pairs))}</code>`}</td><td class="${c.status==='available'?'':'failed'}">${esc(statusText(c.status))}${c.reason?`<br>${esc(c.reason)}`:''}</td><td class="numeric">${fmt(a?.reference_bits_per_word)}</td><td class="numeric">${fmt(a?.condition_bits_per_word)}</td><td class="numeric">${fmt(a?.word_mean_gain)}</td><td>${a?`${integer(a.words)} / ${integer(a.pages)} / ${integer(a.leaf_groups)}`:'未提供'}</td><td class="numeric">${interval(a?.leave_one_leaf_out?.range)}</td></tr>`;});
      }),`${f.version} · DF ${f.df} · ${populations[f.population]}，每个目标与三个参照逐个比较`);
    }
    const values=chartRows(summary,f);
    const sentence=f.view==='ridge'?'正数 = 普通 ridge 的费用 − 此条件的费用。':'正数 = 参照配对的费用 − 目标配对的费用。三个参照均值只有在三个参照及目标都成功时才提供，不用部分均值替代。';
    return `<div class="sharing-result-panel"><h3>${esc(f.version)} · DF ${f.df} · ${esc(populations[f.population])}</h3><p>${sentence} 每词包含全部原单位、EOS 和适用的稀有身份费用。</p>${gainChart(values,'固定条件的完整词预测费用差')}${body}<details class="study-details" id="sharing-leaf-details"><summary>展开各条件的全部页、叶组与稳定性记录</summary><div class="sharing-leaf-content"></div></details></div>`;
  }
  function leafDetails(summary,f) {
    return realRows(summary,f).filter(r=>r.condition!=='base'&&r.populations?.[f.population]?.gain_vs_base).map(r=>{
      const a=r.populations[f.population].gain_vs_base;
      return `<details class="study-details"><summary>${esc(label(r.condition))}：逐页、逐叶与留一叶组</summary><p>主值按全部词加权；等页、等叶是另外的描述，不能替代主分母。等页增益 ${fmt(a.secondary_equal_page_gain)}；先页均再叶等权 ${fmt(a.secondary_equal_leaf_page_mean_gain)}。</p>${table(['叶组','词数','页数','组内逐词增益','组内等页增益'],(a.leaf_rows||[]).map(l=>`<tr><th scope="row">${esc(l.leaf)}</th><td>${integer(l.words)}</td><td>${integer(l.pages)}</td><td>${fmt(l.word_mean_gain)}</td><td>${fmt(l.page_mean_gain)}</td></tr>`),'全部叶组描述')}${table(['转写分区','叶组','词数','增益'],(a.page_rows||[]).map(p=>`<tr><th scope="row">${esc(p.folio)}</th><td>${esc(p.leaf)}</td><td>${integer(p.words)}</td><td>${fmt(p.gain)}</td></tr>`),'全部逐页描述')}${table(['移除叶组','剩余词数','剩余词均增益'],(a.leave_one_leaf_out?.rows||[]).map(l=>`<tr><th scope="row">${esc(l.removed_leaf)}</th><td>${integer(l.remaining_words)}</td><td>${fmt(l.word_mean_gain)}</td></tr>`),'留一叶组稳定性，不是置信区间')}</details>`;
    }).join('');
  }

  function syntheticPanel(summary,f) {
    const allRows=summary?.synthetic?.rows||[];
    if(!allRows.length)return empty('尚无已汇总的合成模型得分。生成器的精确概率已经定义，但它不替代拟合模型的测试结果。');
    const chosen=f.case==='all'?cases:[f.case];
    const groups=(summary.synthetic.aggregates||[]).filter(r=>r.df===f.df&&chosen.includes(r.case));
    const groupTable=table(['机制','模型','有值种子 / 8','完整八种子均值增益','已有种子均值（仅描述）','已有种子范围'],groups.map(g=>{const m=g.metrics?.gain_vs_base||{};return `<tr><th scope="row">${esc(caseNames[g.case])}</th><td>${esc(g.condition)}</td><td>${integer(m.observed_n)} / ${integer(m.expected_n)}</td><td>${m.all_eight?fmt(m.full_eight_mean):'未齐八个种子'}</td><td>${fmt(m.mean_available)}</td><td>${interval(m.range_available)}</td></tr>`;}),`DF ${f.df} · 八个机制种子的保存汇总；增益 = base − condition`);
    const details=chosen.map(caseName=>{
      const rows=allRows.filter(r=>r.df===f.df&&r.case===caseName).sort((a,b)=>a.seed-b.seed||['base','AB','CD'].indexOf(a.condition)-['base','AB','CD'].indexOf(b.condition));
      const comparisons=(summary.synthetic.ab_vs_cd_rows||[]).filter(r=>r.df===f.df&&r.case===caseName);
      return `<article><p class="sharing-case-note"><strong>${esc(caseNames[caseName])}</strong>${esc(caseNotes[caseName])}</p>${table(['种子','模型','状态','测试词数','完整费用','相对 base 增益','同批真值费用','经验超额费用','硬 AB 期望损失','硬 CD 期望损失'],rows.map(r=>{const o=r.oracle||{};return `<tr><th scope="row">${esc(r.seed)}</th><td>${esc(r.condition)}</td><td class="${r.status==='available'?'':'failed'}">${esc(statusText(r.status))}${r.reason?`<br>${esc(r.reason)}`:''}</td><td>${integer(r.test_words)}</td><td>${fmt(r.status==='available'?r.test_bits_per_word:null)}</td><td>${fmt(r.gain_vs_base)}</td><td>${fmt(o.realized_test_original_bits_per_word)}</td><td>${fmt(r.empirical_excess_vs_realized_oracle)}</td><td>${fmt(o.expected_hard_ab_extra_bits_per_word)}</td><td>${fmt(o.expected_hard_cd_extra_bits_per_word)}</td></tr>`;}),`${caseNames[caseName]} · DF ${f.df} · 八种子 × base / AB / CD 全表（bits / 完整词）`,'sharing-seed-table')}<details class="study-details"><summary>八个种子的 AB 与 CD 直接比较</summary>${table(['种子','状态','CD 成本 − AB 成本'],comparisons.map(r=>`<tr><th scope="row">${esc(r.seed)}</th><td>${esc(statusText(r.status))}</td><td>${fmt(r.cd_minus_ab_test_bits_per_word)}</td></tr>`),'直接比较，仅描述；不由单次正收益判别别名')}</details></article>`;
    }).join('');
    return `<p class="sharing-caveat">本区与上方使用同一个 DF 筛选。切换 DF 可查看另一个固定规模；完整下载保留全部 240 行，不受当前筛选影响。经验超额费用是模型与同批真实概率的差，不是模型精确 KL；逐词或有限样本差可以为负。</p>${groupTable}${details}`;
  }

  function statePanel(data) {
    if(!data.available)return '尚无汇总文件。当前仅展示冻结方案、完整费用口径和已有核验来源；未显示任何拟合结果。';
    const inventory=data.summary?.inventory||{};
    const states=inventory.target_status_counts||{};
    return `<strong>已载入保存汇总；不是实时监控。</strong> 预定 ${integer(inventory.expected_target_solutions)} 个 DF 目标解：${Object.entries(states).map(([k,v])=>`${esc(statusText(k))} ${integer(v)}`).join('；')}。缺失或失败明确保留，未替换成其他 DF。<br><span class="small-text">主结论须同时考虑已知答案校准、完整参照与独立核验，不能单凭正收益认定字形同值。</span>`;
  }
  function auditPanel(data) {
    const assets=data.assets||[];
    const auditCards=(data.audits||[]).map(a=>`<article class="sharing-audit-card"><h3>${esc(a.label)}</h3><p>${a.passed===true?'该项记录通过':a.passed===false?'该项记录未通过':'状态见原收据'}。${a.id==='synthetic-audit'?'这是生成器作者的第二条计算路径，不称独立作者复算。':a.id==='aggregation-audit'?'这是汇总作者的第二套标量核对，不是重新训练。':a.id.includes('-score-audit')?'对全部保存逐词分数进行独立概率复算；没有重新优化或识别历史含义。':'固定人工词的数值核验；范围见收据，不代替完整训练复现。'}</p>${link(a.href,'打开核验记录 →')}<p class="hash">SHA-256 ${esc(a.sha256)}</p></article>`).join('');
    const jobs=data.summary?.jobs||[];
    const failures=jobs.flatMap(j=>Object.entries(j.targets||{}).filter(([,t])=>t.status!=='available').map(([df,t])=>({job:j.job?.id,df,status:t.status,reason:t.reason}))) ;
    const failureTable=failures.length?table(['任务','DF','状态','原因'],failures.map(r=>`<tr><th scope="row">${esc(r.job)}</th><td>${esc(r.df)}</td><td>${esc(statusText(r.status))}</td><td>${esc(r.reason)}</td></tr>`),'全部缺失、失败或未匹配目标'):data.available?'<p class="small-text">当前保存汇总未列出不可用的 DF 目标；这只描述执行记录，不等于解读成功。</p>':'<p class="small-text">尚无最终任务状态清单，不能把待汇总当作成功。</p>';
    return `<p class="sharing-caveat">正式模型以冻结方案为准：凸多项逻辑回归与输入参数软融合，<strong>本轮没有训练 GRU</strong>。早期文献审查中的网络讨论属于方案边界，不代表实际执行架构。</p>${data.runtime_note?`<div class="sharing-runtime">${esc(data.runtime_note)}</div>`:'<p>当前快照尚无运行修订说明。</p>'}<div class="sharing-audit-grid">${auditCards}</div><details class="study-details"><summary>全部不可用条件与原因</summary>${failureTable}</details>${data.generator_revision_note?`<details class="study-details"><summary>生成器开发修订：保留旧记录</summary><p style="white-space:pre-wrap">${esc(data.generator_revision_note)}</p></details>`:''}<div class="sharing-downloads">${assets.map(a=>link(a.href,a.label)).join('')}</div><details class="study-details sharing-sources"><summary>本页来源文件哈希</summary>${Object.entries(data.source_hashes||{}).map(([path,hash])=>`<p>${esc(path)}<br><code>${esc(hash)}</code></p>`).join('')}<p>${link('data/parameter-sharing-manifest.json','网页导出清单')}</p></details>`;
  }
  function literaturePanel(data) {
    return (data.literature||[]).map(r=>`<article class="sharing-literature-row"><div class="literature-year">${esc(r.year??'日期未定')}</div><div><h3>${link(r.url,r.title)}</h3><p>${esc((r.authors||[]).join(' · '))}</p><p>${esc(r.claim)}</p><ul>${(r.limitations||[]).map(l=>`<li>${esc(l)}</li>`).join('')}</ul><p class="small-text">${esc(r.status||'')}</p></div></article>`).join('')||'<p class="small-text">此快照尚未导出文献记录。</p>';
  }
  function exportPayload(data) { return {schema_version:1,scope:'Display projection preserving all outcome rows and aggregates, but omitting fit trajectories. Full unmodified summary is separately downloadable.',source_hashes:data.source_hashes,summary:data.summary}; }

  async function mount() {
    const $=selector=>document.querySelector(selector);
    let data;
    try { const response=await fetch('data/parameter-sharing.json');if(!response.ok)throw new Error(`HTTP ${response.status}`);data=await response.json();if(data.schema_version!==1)throw new Error('未知的数据格式'); }
    catch(error){$('#sharing-state').classList.add('loading-error');$('#sharing-state').textContent=`保存快照未能载入：${error.message}。页面没有显示替代结果；可稍后刷新或查看公开研究包。`;return;}
    let state=filtersFromParams(new URLSearchParams(location.search));
    const controls={version:'#sharing-version',df:'#sharing-df',population:'#sharing-population',view:'#sharing-view',case:'#sharing-case'};
    const render=()=>{
      Object.entries(controls).forEach(([key,selector])=>{$(selector).value=String(state[key]);});
      $('#sharing-real-results').innerHTML=realPanel(data.summary,state);
      $('#sharing-synthetic-results').innerHTML=syntheticPanel(data.summary,state);
      const details=$('#sharing-leaf-details');
      if(details)details.addEventListener('toggle',()=>{if(details.open&&!details.dataset.loaded){details.querySelector('.sharing-leaf-content').innerHTML=leafDetails(data.summary,state);details.dataset.loaded='true';}});
    };
    $('#sharing-state').innerHTML=statePanel(data);
    $('#sharing-findings').innerHTML=data.available?(data.findings_paragraphs||[]).map((p,i)=>`<article class="sharing-finding"><span class="eyebrow">${i===0?'手稿对照的边界':'已知答案校准的提醒'}</span><p>${esc(p)}</p></article>`).join(''):'';$('#sharing-audit-content').innerHTML=auditPanel(data);$('#sharing-literature-content').innerHTML=literaturePanel(data);
    const stamp=data.summary?.created_utc||data.frozen_utc;
    $('#sharing-snapshot-date').textContent=stamp?`${data.available?'汇总':'方案冻结'}快照：${stamp}`:'静态研究快照 · 时间未提供';
    Object.entries(controls).forEach(([key,selector])=>$(selector).addEventListener('change',()=>{
      const params=new URLSearchParams();Object.entries(controls).forEach(([k,s])=>params.set(k,$(s).value));state=filtersFromParams(params);history.pushState(null,'',`${location.pathname}?${params}${location.hash}`);render();
    }));
    addEventListener('popstate',()=>{state=filtersFromParams(new URLSearchParams(location.search));render();});
    $('#sharing-export').disabled=!data.available;
    $('#sharing-export').addEventListener('click',()=>{const asset=data.assets.find(a=>a.id==='summary');if(!asset)return;const a=document.createElement('a');a.href=asset.href;a.download='parameter-sharing-complete-summary.json';a.click();});
    render();
  }
  return {filtersFromParams,realRows,chartRows,realPanel,leafDetails,syntheticPanel,statePanel,auditPanel,literaturePanel,exportPayload,mount};
})();
if(typeof document!=='undefined')ParameterSharing.mount();
if(typeof module!=='undefined'&&module.exports)module.exports=ParameterSharing;
