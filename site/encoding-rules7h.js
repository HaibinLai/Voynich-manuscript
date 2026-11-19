/* Read-only artificial-certificate interface. No fetch, fixture, or scientific solver. */
(()=>{'use strict';
const $=id=>document.getElementById(id);
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);return n;};
function validate(x){
 if(!x||x.artificial!==true||typeof x.id!=='string'||!Array.isArray(x.nodes)||!Array.isArray(x.edges))throw Error('需要明确人工标记、ID、节点与边');
 const ids=new Set(x.nodes);if(ids.size!==x.nodes.length||x.nodes.some(n=>typeof n!=='string'))throw Error('节点应是唯一字符串');
 for(const e of x.edges)if(!e||!ids.has(e.from)||!ids.has(e.to))throw Error('边须引用已列节点');
 if(!x.certificate||typeof x.certificate.kind!=='string')throw Error('缺少冻结证书类型');
 if(x.certificate.orders!==undefined&&(!Array.isArray(x.certificate.orders)||x.certificate.orders.length>2))throw Error('最多展示两个既有全序');
 return x;
}
function render(x,targetId="er-example-result"){
 validate(x);const box=$(targetId);box.replaceChildren();box.append(el('h3',x.title||x.id),el('p','人工例子 · '+x.id));if(x.purpose)box.append(el('p',x.purpose));box.append(el('p','节点：'+(x.nodes.join('、')||'空节点集（原记录）')));
 const wrap=el('div');wrap.className='er-table-wrap';const table=el('table');table.className='er-table';const head=el('thead'),hr=el('tr');['起点','终点','证据／生成规则'].forEach(t=>hr.append(el('th',t)));head.append(hr);table.append(head);const body=el('tbody');for(const edge of x.edges){const r=el('tr');[edge.from,edge.to,edge.reason??'未提供文字说明'].forEach(t=>r.append(el('td',t)));body.append(r);}table.append(body);wrap.append(table);box.append(wrap);if(!x.edges.length)box.append(el('p','原例未列有向边；不能由此推断手稿规则通过。'));
 const cert=el('div');cert.className='er-certificate';cert.append(el('strong','冻结证书类型：'+x.certificate.kind));if(x.certificate.cycle?.length)cert.append(el('p','循环记录：'+x.certificate.cycle.join(' → ')));if(x.certificate.orders)x.certificate.orders.forEach((o,i)=>cert.append(el('p','全序见证 '+(i+1)+'：'+o.join(' < '))));if(x.certificate.explanation)cert.append(el('p',x.certificate.explanation));box.append(cert);
 const details=el('details'),pre=el('pre');pre.className='er-raw';pre.textContent=JSON.stringify(x,null,2);details.append(el('summary','完整人工记录与来源'),pre);box.append(details);
}
function attachArtificialCases(cases){if(!Array.isArray(cases)||!cases.length)throw Error('人工集合尚未建立');cases.forEach(validate);if(new Set(cases.map(x=>x.id)).size!==cases.length)throw Error('人工ID重复');const select=$('er-example');select.replaceChildren();for(const x of cases){const option=el('option',x.title||x.id);option.value=x.id;select.append(option);}select.disabled=false;select.onchange=()=>render(cases.find(x=>x.id===select.value));select.value=cases[0].id;render(cases[0]);}
const statusLabel={COMPATIBLE_STRICT_CONDITION:'完全已知人工输入满足严格条件',COMPATIBLE_NO_CROSS_SYMBOL_INFORMATION:'完全已知输入相容，但没有跨符号顺序信息',INCOMPATIBLE_KNOWN_CONSTRAINTS:'已知约束有循环，严格条件不相容',UNDETERMINED_MISSING_WORDS:'存在未知词，完整输入仍未定'};
function adaptNativeCase(x){
 const reason=e=>e.witnesses.map(w=>'词号 '+w.word_index+'，字符位置 '+w.positions_zero_based.join(' → ')+'（均从0起）').join('；');
 return {id:x.id,title:x.id+' · '+statusLabel[x.status],artificial:x.artificial,nodes:x.nodes,edges:x.edges.map(e=>({...e,reason:reason(e)})),purpose:'人工输入：'+x.words.map(w=>w===null?'[整词未知]':w).join(' / ')+'。未知整词 '+x.unknown_word_count+'；完整输入相容性：'+(x.full_input_compatibility===null?'未定':x.full_input_compatibility?'相容':'不相容')+'。全序只针对已知子集。',certificate:{kind:statusLabel[x.status]||x.status,cycle:x.cycle,orders:x.at_most_two_orders_of_known_subset.map(o=>Array.from(o)),explanation:'未枚举所有全序；页面仅显示冻结记录，不重新求解。'},original_record:x};
}
function rawDetails(label,value){const d=el('details'),pre=el('pre');pre.className='er-raw';pre.textContent=JSON.stringify(value,null,2);d.append(el('summary',label),pre);return d;}
function renderFinal(d){
 if(d.schema!=='encoding_rules_page_v1')throw Error('未支持的页面数据版本');
 $('er-status').textContent='研究资料已冻结：严格归属检验不适用；未运行新的手稿排序检验。公开验收时间另见记录。';
 const conclusion=$('er-conclusion');conclusion.replaceChildren(el('p','NOT_APPLICABLE 的对象，是把当前转写逐词零例外的共同排序检查，作为对作者更宽、容许噪声的历史假说的必要条件反驳。它不是手稿已违反此严格条件的实测结论。'),el('p','作者确实提出 fixed-order 猜想；本轮不判定这个猜想真或假，也不排除自由重排或其他编码。'));
 const reportLink=el('a','阅读一页中文研究结论');reportLink.href=d.sources.find(r=>r.key==='report_text').url;conclusion.append(reportLink,rawDetails('根资格决定与报告原字段', {qualification_decision:d.qualification_decision,research_report:d.research_report}));
 const demo=d.artificial_demo;attachArtificialCases(demo.cases.map(adaptNativeCase));
 const auditBox=$('er-demo-audit');auditBox.replaceChildren(el('p','当前外部人工审计：'+d.artificial_audit.status+'。另一实现枚举30个小字母表全序，核22个原位置见证和3个显式自由置换；这是固定人工逻辑审核，不是手稿样本或独立历史证据。'),el('p','原demo生成时状态 '+demo.status+'、independent_audit_pending=true 均原样保留；后到的审计单独绑定。'),rawDetails('外部审计完整范围与逐例记录',d.artificial_audit));
 const free=$('er-free');free.replaceChildren(el('p','另列 F01：'+demo.free_reordering_witness.observed_words.join('、')+' 都能由 '+demo.free_reordering_witness.source_word+' 自由重排得到。相同字母袋允许这些串，共同严格顺序却不能；这不是手稿反证或作者机制认证。'));
 const button=el('button','查看 F01 的严格循环与全部位置边');button.type='button';button.id='er-free-button';button.onclick=()=>render(adaptNativeCase(demo.free_reordering_witness.strict_joint),'er-free-result');free.append(button,rawDetails('自由重排原位置置换及严格记录',demo.free_reordering_witness));
 const review=d.rule_review,source=d.source_rule_eligibility,sourceBox=$('er-sources');sourceBox.replaceChildren(el('h3',review.primary_source.title),el('p',source.paper.authors.join('、')+' · '+source.paper.year));const link=el('a','一手论文：ACL 原文与PDF');link.href=source.paper.landing_url;sourceBox.append(link,el('p',source.actual_read_scope.text_read),el('p','来源审查实际显示的论文印刷页：'+source.actual_read_scope.visually_displayed_printed_pages.join('、')+'。公开包只含元数据、短引文及审查；论文全文和渲染图不转载。'),el('p','论文脚注所指作者主页的一次普通请求返回 HTTP '+source.author_material_access.http_status+'；未取得作者代码，不外推为所有代码均不可得。'));
 for(const q of source.shared_short_excerpts)sourceBox.append(el('blockquote',q.location+'：'+q.text));sourceBox.append(el('p','两段共同引文按空白计16词；另一审查原计数18保留为历史元数据，根决定已明确更正为16，文字与结论未改。'),rawDetails('完整一手读取范围、访问记录及八条来源原件',source));
 const rb=$('er-rules');rb.replaceChildren(el('h3','来源规则：全部八条'));
 for(const row of source.source_rule_matrix){const x=el('details');x.dataset.ruleId=row.id;x.append(el('summary',row.id+' · '+row.dimension),el('p','出处：'+row.location),el('p','作者材料：'+row.source_observation),el('p','严格条件适用状态：'+(row.strict_rule_eligibility==='NOT_APPLICABLE'?'不适用':'未定')),el('p',row.why),rawDetails('逐条原字段',row));rb.append(x);}
 const labels=['固定字母单位','共同单射替换','词界与读向','观测串共同全序','内部规范化与历史排序','零误差阈值及例外'];
 const explanations=['原实验使用Currier转写，未认证现代ZL/IT单位映射。','理想替换定义为一对一，不等于整部现代转写已具备单一精确密钥。','词界和分割仍不确定，不能直接当历史事实。','固定顺序猜想确实存在，但不是逐词零例外的观测合同。','算法内部主动排序不能证明写手已按相同顺序书写。','噪声容许的宽假说不自动承诺零容忍拒绝规则。'];
 const rr=$('er-review');rr.replaceChildren(el('h3','必要前提复核：全部六条'),el('p','另一知情 AI 直接阅读原文后审查；与来源审查有沟通，不是独立盲专家认证。'));
 review.eligibility_matrix.forEach((row,i)=>{const x=el('details');x.dataset.ruleId=row.id;x.append(el('summary',row.id+' · '+labels[i]),el('p','出处：'+row.source_location),el('p',explanations[i]),rawDetails('复核原字段与理由',row));rr.append(x);});rr.append(rawDetails('严格条件定理、启发式限度与完整复核',review));
 const prior=$('er-prior');prior.replaceChildren(el('p','旧候选主张记录已指出模型族和实现缺口；Bax局部规则覆盖及三个锚点图像检查不重做。既有976个英/拉丁固定键 ordered/bag 拟合及留页评分，也不是本轮新的共同排序证书或完整希伯来流水线。'),el('p','有限查重未发现已执行的同类精确顺序证书分析，不等于穷尽证明或世界首次。'),rawDetails('旧工作清单与全部引用',d.prior_inventory));
 const downloads=$('er-downloads');downloads.replaceChildren();for(const r of d.sources){const line=el('p'),a=el('a',r.key);a.href=r.url;line.append(a,el('span',' · '+r.path+' · SHA256 '+r.sha256));downloads.append(line);}
 downloads.append(el('p','先前七例预检另列 earlier_seven 文件，不并入九例或F01。公开复算只需Python标准库，不需要网络、手稿词库或私有图片。'),rawDetails('最小公开目录复算范围',d.clean_public_replay),rawDetails('最终科学范围复核（不是浏览器验收）',d.final_scope_review));
 $('er-time').textContent='计划窗口：'+d.session_times.planned_start_utc+' 至 '+d.session_times.deadline_utc+'；实际目标创建：'+d.session_times.actual_goal_creation_utc+'。这是最多七小时预算，可以提前完成，不代表持续运行满七小时。';
}
window.EncodingRulesViewer=Object.freeze({validateArtificialCase:validate,attachArtificialCases,renderArtificialCase:render,adaptNativeCase,renderFinal});
const meta=document.querySelector('meta[name="encoding-rules-snapshot"]');
if(meta&&meta.content!=='interface-preview')fetch('data/encoding-rules7h.json?v='+encodeURIComponent(meta.content),{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('数据读取失败');return r.json();}).then(renderFinal).catch(e=>{$('er-status').textContent='资料暂未载入：'+e.message+'。未载入不代表零结果或通过。';});
})();
