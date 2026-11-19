'use strict';
(()=>{
 const $=id=>document.getElementById('r4-'+id),el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
 const add=(p,tag,text)=>{const n=el(tag,text);p.append(n);return n;};
 const link=(p,text,url)=>{const n=add(p,'a',text);n.href=url;return n;};
 const details=(p,title,value)=>{const d=add(p,'details');add(d,'summary',title);add(d,'pre',typeof value==='string'?value:JSON.stringify(value,null,2));};
 let data;
 function show(locator){const r=data.rows.find(r=>r.locator===locator);if(!r)return;$('locus').value=locator;const p=$('detail');p.replaceChildren();add(p,'h3',r.label+' · '+r.locator+' · 物理叶 '+r.physical_leaf);const q=add(p,'p','本轮逐位置资格结论：尚未接入。候选单位、可见边界、邻物交叉、文字遮盖、部件粒度与特征可观察性均待本轮审查；形态评分未执行。');q.className='r4-caution';
 const links=add(p,'div');links.className='r4-links';link(links,'旧工作画布完整原图',r.prior_first_localization.image.url);link(links,'上一轮九处定位页面',r.prior_review_page);
 for(const c of r.prior_roster_record.official_canvas_candidates)if(c.image_url!==r.prior_first_localization.image.url)link(links,'原名册保留画布：'+c.canvas_label,c.image_url);
 const old=add(p,'p','以下是旧知情定位：第一份 '+data.prior_observation_times.first+'；第二份 '+data.prior_observation_times.second+'。不是本轮新增观察。');old.className='r4-muted';
 add(p,'h4','第二次旧观察的局部依据与限制');const b=r.prior_second_localization;for(const [key,label] of [['local_support','局部依据'],['neighbor_ink','邻物与交叉'],['clipping','截断与上下文'],['qualification','资格限制']]){const t=add(p,'p');add(t,'strong',label+'：');t.append(document.createTextNode(b[key]));}
 const contexts=add(p,'div');contexts.className='r4-links';for(const c of r.prior_first_localization.native_context_regions||[])link(contexts,'既有原尺寸阅读区 · '+c.name,c.url);
 add(p,'p','以上原图与阅读区地址来自旧冻结记录；上下文矩形不等于独立对象或墨迹分割。完整画布入口始终保留。');
 details(p,'两版原行（保留原分隔与数字注释）',Object.entries(r.prior_roster_record.versions).map(([v,x])=>v+' · 原文件第 '+x.line_number+' 行\n'+x.original_line).join('\n\n'));
 details(p,'旧第一定位：全部原字段、近似框与图源哈希',r.prior_first_localization);details(p,'旧第二定位：全部原字段与限制',r.prior_second_localization);details(p,'旧矩形交集复算：原值，不是墨迹交集',r.prior_geometry_record);details(p,'本轮资格字段预留（null 表示尚无本轮裁定）',r.qualification);
 }
 async function init(){try{const version=document.querySelector('meta[name="repeated-labels-snapshot"]').content;const res=await fetch('data/repeated-labels7h.json?v='+encodeURIComponent(version),{cache:'no-store'});if(!res.ok)throw Error('HTTP '+res.status);data=await res.json();if(data.schema!=='repeated_labels_fourth_window_page_v1'||data.rows.length!==9||data.session.morphology_scoring_authorized!==false)throw Error('页面输入范围不符');
 if(data.phase_input){
 $('approved-work').textContent='按固定九处顺序，查看所需完整画布与原生坐标局部，核对候选图形组、确定与可能成员、邻物竞争、文字影响和可观察范围。允许可追溯且不重绘的阅读裁区。当前仅报告观察正在进行；逐处结论尚未接入。';
 $('not-approved').textContent='形态特征赋值、对象对相似度和显著性检验均未批准。具体特征定义与测量方案仍在审查；观察完毕后需另冻合同，不预填特征数或真实分数。';
 const explanation=$('measurement-distinction');explanation.hidden=false;explanation.className='r4-method-note';add(explanation,'h3','人工可见特征，不等于逐像素分割');add(explanation,'p','若能追踪属于候选图形组的结构，并与邻物或书写区分，某些人工观察问题可有答案，不必先取得完美像素掩膜。无法归属的线仍保留未知；这不是宣布九处或全部特征已经可测。');add(explanation,'p','原上下文框只提供阅读范围，不是对象成员清单或分割。新的人工特征口径不能自动放行匿名整图图卡或像素相似度，也不回溯改变旧门槛未通过的记录。');
 $('footer-stage').textContent='固定九处 · 原图资格核对进行中 · 编码与评分未批准';
 }
 if(data.literature){$('literature-section').hidden=false;const titles={L01:'相似可能只在某个部件',L02:'重复标签已有直接统计',L03:'正规化会改变重复关系',L04:'检验对象与漏检边界要分开',L05:'同一历史名称可以有不同画法',L06:'已知文字也需先核所指范围'};for(const e of data.literature.entries){const card=add($('literature'),'article');add(card,'h3',titles[e.id]||e.title);add(card,'p',e.authors.join('、')+' · '+e.source_type).className='r4-muted';add(card,'strong','文献观点与有限支持');add(card,'p',e.supports);add(card,'strong','不能支持');add(card,'p',e.cannot_support);link(card,'直接来源',e.url);if(e.pdf_url)link(card,'作者论文 PDF',e.pdf_url);details(card,'文献题名、具体证据与实际阅读范围',{id:e.id,title:e.title,year:e.year,date_basis:e.date_basis,version:e.version,historical_date:e.historical_date,location:e.location,author_evidence:e.author_evidence,actual_read_scope:e.actual_read_scope,reproducible_inputs:e.reproducible_inputs,prediction_for_our_design:e.prediction_for_our_design,related_urls:e.related_urls});}}
 $('stage').textContent=data.publication.stage_zh;$('rows').replaceChildren();$('locus').replaceChildren();for(const r of data.rows){const row=add($('rows'),'tr');add(row,'th',r.label).scope='row';const pos=add(row,'td',r.locator);add(pos,'span','物理叶 '+r.physical_leaf).className='r4-muted-inline';add(row,'td','本轮待审查');add(row,'td','未执行');const target=add(row,'td');const button=add(target,'button','看旧定位与待核项');button.type='button';button.onclick=()=>{show(r.locator);$('detail-section').scrollIntoView({behavior:'smooth',block:'start'});$('locus').focus({preventScroll:true});};link(target,'馆方完整原图',r.prior_first_localization.image.url);const option=add($('locus'),'option',r.label+' · '+r.locator);option.value=r.locator;}
 $('locus').disabled=false;$('locus').onchange=()=>show($('locus').value);show(data.rows[0].locator);$('plan').textContent=data.plan_text;$('gate').textContent=JSON.stringify(data.prior_comparison_gate,null,2);$('result').textContent='未执行。'+data.results.reason+' 缺失结果不是零分或阴性结论。';$('source-records').textContent=JSON.stringify(data.sources,null,2);for(const src of data.sources)link($('sources'),src.label,src.url);$('load').textContent='全部九处已列出。当前表为资格待审快照；不据加载或时间推断研究进展。';
 }catch(e){$('load').textContent='固定资料未载入：'+e.message+'。不据缺失数据生成结果。';}}
 init();
})();
