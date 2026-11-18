'use strict';
(() => {
const $=id=>document.getElementById('zr-'+id), NS='http://www.w3.org/2000/svg';
const S={data:null,panels:[],panel:null,records:[],selected:null,page:0,pageSize:18,imageToken:0};
const names={reviewed:'已复核',NA_after_review:'复核后仍未定（NA）',not_reviewed:'未复核',in_progress:'复核中',writing_like:'文字状区域',uncertain_or_graphic:'文字或图形未定',indeterminate:'未定',single_layout_candidate:'单一局部布局候选',multiple_layout_candidates:'多个布局候选',no_local_layout_candidate:'未见局部候选',partial_connection_seen:'部分连接可见',explicit_connection_seen:'记录到可见连接',no_explicit_connection_observed_in_reviewed_views:'已查看范围未见明确连接',N:'N · 布局/无明确连接',P:'P · 部分可见，仍未决',E:'E · 可见图形连接',NA:'NA · 复核后未定'};
const downloadLabels={'aggregation.json':'全量冻结汇编 JSON','input-freeze.json':'汇编输入冻结','output-freeze.json':'汇编输出冻结','publication-approval.json':'限定发布批准','independent-audit.json':'独立汇编审核 JSON','independent-audit.txt':'独立汇编审核全文','sequence-qualification.json':'科学资格账本 JSON','sequence-qualification.txt':'科学资格账本全文','qualification-output-freeze.json':'资格账本输出冻结','root-input-review.json':'根协调来源核对','f72v2-zi01-followup.json':'f72v2 ZI01 知情补查','f72v2-zi01-followup-freeze.json':'f72v2 补查冻结','report.txt':'全十二图汇编说明','public-manifest.json':'完整公开来源清单'};
const label=v=>names[v]||String(v??'未提供');
const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
const add=(parent,tag,text,cls)=>{const n=el(tag,text,cls);parent.append(n);return n;};
const jsonDetails=(parent,title,value)=>{const d=add(parent,'details');add(d,'summary',title);d.addEventListener('toggle',()=>{if(d.open&&!d.querySelector('pre'))add(d,'pre',JSON.stringify(value,null,2));});return d;};
const box=b=>Array.isArray(b)&&b.length===4&&b.every(Number.isFinite)&&b[2]>b[0]&&b[3]>b[1]?b:null;
const coord=b=>box(b)?`[${b.join(', ')}]（原画布 x₀, y₀, x₁, y₁）`:'null / 无可绘制框；不画零框，也不自动回填';
const facts=(parent,title,list)=>{if(!list?.length)return;add(parent,'h4',title);const ul=add(parent,'ul');for(const x of list)add(ul,'li',typeof x==='string'?x:JSON.stringify(x));};
function component(p,id){return p.full_frozen_report.object_component_reviews.find(x=>x.component_uid===id)||p.full_frozen_report.discovered_supplements.find(x=>x.component_uid===id);}
function componentBox(p,id){const r=component(p,id);return box(r?.reviewed_component_box_xyxy)||box(r?.box_xyxy);}
function makeRecords(p){
 const r=p.full_frozen_report,s=p.full_original_seed,original=new Map(s.object_components.map(x=>[x.component_uid,x]));
 const out=p.text_rows.map(x=>({kind:'text',id:x.region_uid,panel:p.panel,raw:x,ob:x.observation,seed:x.original_seed_record}));
 for(const x of r.object_component_reviews)out.push({kind:'component',id:x.component_uid,panel:p.panel,raw:x,ob:x,seed:original.get(x.component_uid)||null,added:!original.has(x.component_uid)});
 for(const x of r.relation_edges)if(x.edge_kind!=='text_to_object')out.push({kind:x.edge_kind==='body_to_pointed'?'body':'other',id:x.edge_uid,panel:p.panel,raw:x,ob:x});
 for(const x of s.fine_alternatives_original)out.push({kind:'fine',id:p.panel+':'+x.id,panel:p.panel,raw:x,ob:x});
 for(const x of r.discovered_supplements)out.push({kind:'alias',id:x.component_uid,panel:p.panel,raw:x,ob:x});
 for(const category of ['continuous_ring_writing_original','context_regions_original','gaps_and_damage_original'])for(const x of s[category]||[])out.push({kind:'context',id:p.panel+':'+category+':'+x.id,panel:p.panel,raw:x,ob:x,category});
 for(const x of out)x.search=(x.id+' '+JSON.stringify(x.raw)).toLowerCase();return out;
}
function filterOptions(){
 const kind=$('kind').value;const opts=[['','全部状态']];
 if(kind==='text')opts.push(['multiple_layout_candidates','多个布局候选'],['single_layout_candidate','单一局部布局候选'],['no_local_layout_candidate','未见局部候选'],['indeterminate','布局未定'],['partial_connection_seen','部分接触/连接'],['connection_indeterminate','连接可见性未定'],['NA_after_review','复核后 NA'],['uncertain_text','文字或图形未定']);
 if(kind==='component')opts.push(['original','原组件'],['added','新增组件'],['NA_after_review','复核后 NA'],['null_original','原框为 null']);
 if(['body','other'].includes(kind))for(const x of ['E','P','N','NA'])opts.push([x,label(x)]);
 $('filter').replaceChildren(...opts.map(([v,t])=>{const o=el('option',t);o.value=v;return o;}));
}
function matches(r){const f=$('filter').value,o=r.ob;if(!f)return true;if(f==='added')return r.added;if(f==='original')return !r.added;if(f==='null_original')return !!r.seed&&r.seed.original_box_xyxy===null;if(f==='uncertain_text')return ['uncertain_or_graphic','indeterminate'].includes(o.text_status);if(['single_layout_candidate','multiple_layout_candidates','no_local_layout_candidate','indeterminate'].includes(f))return o.layout_association===f;if(f==='partial_connection_seen')return o.line_visibility_state===f;if(f==='connection_indeterminate')return o.line_visibility_state==='indeterminate';return [o.review_status,o.evidence_level].includes(f);}
function summary(r){if(r.kind==='text')return [label(r.ob.review_status),label(r.ob.layout_association),label(r.ob.line_visibility_state)].join(' · ');if(r.kind==='component')return `${r.added?'新增组件':'原组件'} · ${label(r.ob.review_status)}`;if(['body','other'].includes(r.kind))return `${label(r.ob.evidence_level)} · ${r.ob.source_uid} → ${r.ob.target_uid}`;if(r.kind==='alias')return '单独登记的补充别名；不增加原分母';if(r.kind==='fine')return '原细分备选；不是已认证词界';return r.category.replace('_original','');}
function list(){
 const q=$('search').value.trim().toLowerCase();const rows=S.records.filter(r=>r.kind===$('kind').value&&($('scope').value==='all'||r.panel===S.panel.panel)&&matches(r)&&(!q||r.search.includes(q)));
 const pages=Math.max(1,Math.ceil(rows.length/S.pageSize));S.page=Math.min(S.page,pages-1);$('list').replaceChildren();
 for(const r of rows.slice(S.page*S.pageSize,(S.page+1)*S.pageSize)){const b=el('button',undefined,'zr-record');b.type='button';b.setAttribute('aria-pressed',String(S.selected===r));add(b,'strong',r.id);add(b,'span',summary(r));b.onclick=()=>select(r);$('list').append(b);}
 if(!rows.length)add($('list'),'p','没有符合筛选条件的条目。','zr-empty');
 $('result-count').textContent=`显示范围：${$('scope').value==='all'?'全 12 图':S.panel.panel}；符合条件 ${rows.length} 条。登记类别分开计数，不是命名通过数。`;
 $('page').textContent=`${S.page+1} / ${pages}`;$('prev').disabled=S.page===0;$('next').disabled=S.page>=pages-1;
}
function setPanel(id){
 S.panel=S.panels.find(p=>p.panel===id);$('panel').value=id;S.selected=null;const im=S.panel.original_image;const token=++S.imageToken;
 $('official').href=im.official_url;$('image').replaceChildren();$('image-state').textContent='正在读取馆方完整图像。';
 const img=document.createElementNS(NS,'image');img.setAttribute('width',im.dimensions_px[0]);img.setAttribute('height',im.dimensions_px[1]);img.addEventListener('load',()=>{if(token===S.imageToken)$('image-state').textContent=`${id} · 馆方原图已加载，${im.dimensions_px.join(' × ')} 原画布像素。`;});img.addEventListener('error',()=>{if(token===S.imageToken)$('image-state').textContent='图源未加载成功，请使用上方官方完整画布链接。';});img.setAttribute('href',im.official_url);$('image').append(img);
 $('detail').replaceChildren(el('p','选择登记条目，查看原框、候选、观察限制与来源。'));$('full-report').textContent=$('full-report').parentElement.open?JSON.stringify(S.panel.full_frozen_report,null,2):'';$('view').value='full';for(const id of ['box-text','box-components','box-fine','box-context','box-path'])$(id).checked=false;draw();
}
function select(r){
 if(r.panel!==S.panel.panel)setPanel(r.panel);S.selected=r;
 $('box-text').checked=r.kind==='text';$('box-components').checked=['text','component','body','alias','other'].includes(r.kind);$('box-fine').checked=r.kind==='fine';$('box-context').checked=r.kind==='context';$('box-path').checked=false;
 detail();draw();list();
}
function jump(id){const r=S.records.find(x=>x.panel===S.panel.panel&&x.id===id&&['text','component','alias'].includes(x.kind));if(r){$('kind').value=r.kind;filterOptions();S.page=0;select(r);}}
function jumpButton(parent,id){const b=add(parent,'button',id,'zr-jump');b.type='button';b.onclick=()=>jump(id);return b;}
function edgesFor(r){return r.kind==='text'?r.raw.text_edges:['body','other'].includes(r.kind)?[r.raw]:S.panel.full_frozen_report.relation_edges.filter(e=>e.source_uid===r.id||e.target_uid===r.id);}
function edgeDetail(parent,e){const d=add(parent,'details');add(d,'summary',`${e.edge_kind==='text_to_object'?'文字—对象':e.edge_kind==='body_to_pointed'?'身体—星形':'其他图形'} · ${label(e.evidence_level)} · ${e.target_uid}`);d.addEventListener('toggle',()=>{if(!d.open||d.dataset.filled)return;d.dataset.filled='1';const p=add(d,'p');p.append('起点：');jumpButton(p,e.source_uid);p.append('；终点：');jumpButton(p,e.target_uid);facts(d,'可见事实',e.observed_endpoint_facts);facts(d,'竞争组件',e.competing_object_ids);add(d,'p',e.crossing_resolution||'');facts(d,'限制',e.limitations);jsonDetails(d,'完整边记录',e);});}
function detail(){
 const r=S.selected,p=S.panel,d=$('detail');d.replaceChildren();add(d,'h3',r.id);add(d,'p',summary(r),'zr-note');
 if(r.kind==='text'){
  const dl=add(d,'dl');for(const [k,v] of [['原文字框',coord(r.seed.original_box_xyxy)],['本次复核',label(r.ob.review_status)],['文字状况',label(r.ob.text_status)],['布局候选',label(r.ob.layout_association)],['连接可见性',label(r.ob.line_visibility_state)]]){add(dl,'dt',k);add(dl,'dd',v);}
  if(r.ob.review_status==='NA_after_review')add(d,'p','此条已实际复核，结论仍为 NA；不是未查看，也不等于不存在文字。','zr-note');
  if(r.ob.layout_association==='single_layout_candidate'&&S.data.assessment)add(d,'p','此 ID 属于资格账本事后关联的中央普通字母样注记候选；属于源知情角色核对，不是外围标签的命名成功。','zr-note');
  facts(d,'本次观察',r.ob.observation_facts);facts(d,'布局约束',r.ob.candidate_constraints);if(r.ob.no_candidate_reason)add(d,'p',r.ob.no_candidate_reason);
  add(d,'h4','候选组件（不排序、不认证归属）');for(const id of r.ob.candidate_object_ids||[])jumpButton(d,id);
  const fine=p.full_original_seed.fine_alternatives_original.filter(x=>x.coarse_parent_id===r.seed.original_id);add(d,'p',`原细分备选 ${fine.length} 项；保留原分组与未定字界，不作为额外词数。`);jsonDetails(d,'全部细分与本次分组说明',{original_fine_alternatives:fine,reviewed_subgroups:r.ob.subgroup_candidates});
  jsonDetails(d,'原始种子（含初始化状态与 null）',r.seed);jsonDetails(d,'本次完整文字复核',r.ob);
 } else if(r.kind==='component'){
  add(d,'p',`${r.added?'新增复核组件；原 606 分母不变。':'原始组件；原始框与复核框分别保留。'}`);add(d,'p','原框：'+(r.seed?coord(r.seed.original_box_xyxy):'无原组件种子'));add(d,'p','复核框：'+coord(r.ob.reviewed_component_box_xyxy));
  add(d,'p',r.ob.missing_component_state||'');facts(d,'本次观察',r.ob.observation_facts);add(d,'p',r.ob.completion_or_NA_reason||'');if(r.seed)jsonDetails(d,'原始组件种子',r.seed);jsonDetails(d,'本次完整组件记录',r.ob);
 } else {if(r.kind==='alias')add(d,'p','这是单独登记的补充别名。可能与新增组件指向同一观察区域，不可再加到 606 原组件或 40 新增组件上。','zr-note');if(r.kind==='fine')add(d,'p','原细分备选原坐标：'+coord(r.raw.box_xyxy));jsonDetails(d,'完整原记录',r.raw);}
 const edges=edgesFor(r);if(edges.length){add(d,'h4',`相关关系边 · ${edges.length} 条`);for(const e of edges)edgeDetail(d,e);}
 const viewids=new Set(r.ob.viewed_view_ids||r.ob.view_ids||[]);for(const e of edges)for(const id of e.view_ids||[])viewids.add(id);
 jsonDetails(d,'实际查看收据（重复查看不构成独立样本）',p.full_frozen_report.view_receipts.filter(v=>viewids.has(v.view_id)));
 jsonDetails(d,'来源与观察者',{observer:p.observer,report_path:p.report_path,report_sha256:p.report_sha256,freeze_path:p.freeze_path,freeze_sha256:p.freeze_sha256,original_image:p.original_image,exposure_statement:p.full_frozen_report.exposure_statement});
}
function geometry(){
 const r=S.selected,p=S.panel,items=[],paths=[];if(!r)return {items,paths};
 const push=(b,type,id)=>{if(box(b))items.push({b,type,id});};
 if(r.kind==='text'){push(r.seed.original_box_xyxy,'text',r.id);for(const id of r.ob.candidate_object_ids||[]){const original=p.full_original_seed.object_components.find(c=>c.component_uid===id);if(original)push(original.original_box_xyxy,'component',id+' 原框');const current=componentBox(p,id);if(JSON.stringify(current)!==JSON.stringify(original?.original_box_xyxy))push(current,'component',id+' 复核/别名框');}for(const f of p.full_original_seed.fine_alternatives_original.filter(x=>x.coarse_parent_id===r.seed.original_id))push(f.box_xyxy,'fine',f.id);}
 if(r.kind==='component'){if(r.seed)push(r.seed.original_box_xyxy,'component',r.id+' 原框');if(JSON.stringify(r.ob.reviewed_component_box_xyxy)!==JSON.stringify(r.seed?.original_box_xyxy))push(r.ob.reviewed_component_box_xyxy,'component',r.id+' 复核框');}
 if(r.kind==='alias')push(r.raw.box_xyxy,'component',r.id+' 补充别名');
 if(r.kind==='fine')push(r.raw.box_xyxy,'fine',r.id);
 if(r.kind==='context'){push(r.raw.box_xyxy,'context',r.id);push(r.raw.inner_envelope_xyxy,'context',r.id+' 内包络');}
 push(r.ob.reviewed_context_extent_xyxy,'context','已查看上下文');
 const edges=edgesFor(r),segments=new Set();for(const e of edges){if(['body','other'].includes(r.kind)){push(componentBox(p,e.source_uid),'component',e.source_uid);push(componentBox(p,e.target_uid),'component',e.target_uid);for(const id of e.competing_object_ids||[])push(componentBox(p,id),'component',id+' 竞争');push(e.reviewed_context_extent_xyxy,'context','已查看上下文');}for(const id of e.segment_ids||[])segments.add(id);}
 for(const s of p.full_frozen_report.line_segments.filter(s=>segments.has(s.segment_uid))){for(const b of s.endpoint_boxes_xyxy||[])push(b,'path',s.segment_uid+' 端点示意');if(s.visible_polyline_original_xy?.length>1)paths.push({points:s.visible_polyline_original_xy,id:s.segment_uid});}
 for(const c of p.full_frozen_report.context_reviews)if(segments.has(c.segment_uid))for(const b of c.visible_segment_boxes_xyxy||[])push(b,'path',c.segment_uid+' 线段范围');
 return {items,paths};
}
function draw(){
 if(!S.panel)return;const {items,paths}=geometry(),[w,h]=S.panel.original_image.dimensions_px;let vb=[0,0,w,h];
 if($('view').value==='panel')vb=box(S.panel.full_original_seed.original_panel_box_xyxy)||vb;
 if($('view').value==='selection'&&items.length){const bs=items.map(x=>x.b);vb=[Math.max(0,Math.min(...bs.map(b=>b[0]))-90),Math.max(0,Math.min(...bs.map(b=>b[1]))-90),Math.min(w,Math.max(...bs.map(b=>b[2]))+90),Math.min(h,Math.max(...bs.map(b=>b[3]))+90)];}
 $('svg').setAttribute('viewBox',[vb[0],vb[1],vb[2]-vb[0],vb[3]-vb[1]].join(' '));$('overlay').replaceChildren();
 const controls={text:'box-text',component:'box-components',fine:'box-fine',context:'box-context',path:'box-path'},colors={text:'#b95918',component:'#11699a',fine:'#8c3ca5',context:'#5f6258',path:'#b12c47'};
 const seen=new Set();for(const x of items){if(!$(controls[x.type]).checked)continue;const key=JSON.stringify([x.b,x.type,x.id]);if(seen.has(key))continue;seen.add(key);const rect=document.createElementNS(NS,'rect');for(const [k,v] of Object.entries({x:x.b[0],y:x.b[1],width:x.b[2]-x.b[0],height:x.b[3]-x.b[1],fill:'none',stroke:colors[x.type],'stroke-width':2,'vector-effect':'non-scaling-stroke'}))rect.setAttribute(k,v);if(['context','path','fine'].includes(x.type))rect.setAttribute('stroke-dasharray','6 4');const title=document.createElementNS(NS,'title');title.textContent=x.id+' '+coord(x.b);rect.append(title);$('overlay').append(rect);}
 if($('box-path').checked)for(const p of paths){const line=document.createElementNS(NS,'polyline');line.setAttribute('points',p.points.map(x=>x.join(',')).join(' '));line.setAttribute('fill','none');line.setAttribute('stroke',colors.path);line.setAttribute('stroke-width','2');line.setAttribute('stroke-dasharray','5 5');line.setAttribute('vector-effect','non-scaling-stroke');const t=document.createElementNS(NS,'title');t.textContent=p.id+'：原记录观察示意，非墨迹路径';line.append(t);$('overlay').append(line);}
}
async function init(){
 try{const v=document.querySelector('meta[name="zodiac-relations-snapshot"]').content;const res=await fetch('data/zodiac-relations.json?v='+encodeURIComponent(v),{cache:'no-store'});if(!res.ok)throw new Error('记录读取失败 '+res.status);S.data=await res.json();if(S.data.schema!=='zodiac_relations_site_v1')throw new Error('记录格式不符');S.panels=S.data.aggregation.panels;S.records=S.panels.flatMap(makeRecords);
 $('audit').textContent=S.data.status_note;$('panel').replaceChildren(...S.panels.map(p=>{const o=el('option',p.panel);o.value=p.panel;return o;}));
 for(const id of ['panel','kind','scope','filter','search','view','reset','layers'])$(id).disabled=false;
 filterOptions();setPanel(S.panels[0].panel);list();$('load').textContent='12 图完整登记已载入。选择原图或条目开始查看；审核状态以页面上方说明为准。';
 for(const x of S.data.downloads){const a=add($('downloads'),'a',downloadLabels[x.url.split('/').pop()]||x.label||x.name);a.href=x.url;a.download='';}
 if(S.data.assessment){
  const a=S.data.assessment,d=$('assessment');d.replaceChildren();add(d,'p',a.scientific_status,'zr-note');
  add(d,'p',`记录汇编经过独立实现的 ${a.record_audit.operations.toLocaleString('zh-CN')} 次字段/容器比较，差异 ${a.record_audit.differences}。这些操作不是独立统计样本，审核也没有重新认证原图观察。`);
  facts(d,'保留的正面支持',a.sequence_qualification.positive_results_retained);facts(d,'完整序列仍缺什么',a.sequence_qualification.specific_missing_evidence);
  add(d,'p','9 个 single_layout_candidate 均落在普通字母样中央场景注记候选中，没有外围短串，也不含 f70v2:ZC02。这是源知情、事后按固定 ID 关联的角色核对，不是盲分类、独立预测或 9 次命名成功。','zr-note');
  jsonDetails(d,'9 个 ID 与资格账本原始依据',a.single_layout_candidate_role_check);
  add(d,'p','不足不等于没有语义：未知词义、未见直接引线或历史共同起点未知，本身都不是排除全部图像比较的理由。');
  $('release-note').textContent='限定发布已批准，完整报告与补查可下载。f72v2 ZI01 补查为已知原分歧后的查看，不能作为盲复认；初始判断与分歧继续保留。';
  const sources=add($('public-sources'),'details');add(sources,'summary',`完整公开来源清单 · ${a.public_sources.files.length} 个文件`);
  add(sources,'p','所有路径相对于仓库根目录。下载仓库后，在根目录运行下列复算命令；清单列明每个依赖的 SHA-256。');
  add(sources,'pre',typeof a.public_sources.rebuild_command==='string'?a.public_sources.rebuild_command:JSON.stringify(a.public_sources.rebuild_command,null,2));
  const ul=add(sources,'ul');for(const file of a.public_sources.files){const li=add(ul,'li'),link=add(li,'a',file.path);link.href='https://github.com/HaibinLai/Voynich-manuscript/blob/main/'+file.path.split('/').map(encodeURIComponent).join('/');add(li,'span',' · '+file.sha256,'zr-muted');}
 }
 $('source').textContent='全量汇编 SHA-256：'+S.data.source_sha256+'；页面状态：'+S.data.publication_status;
 $('panel').onchange=()=>{setPanel($('panel').value);S.page=0;list();};$('kind').onchange=()=>{filterOptions();S.page=0;list();};for(const id of ['scope','filter'])$(id).onchange=()=>{S.page=0;list();};$('search').oninput=()=>{S.page=0;list();};$('prev').onclick=()=>{S.page--;list();};$('next').onclick=()=>{S.page++;list();};$('view').onchange=draw;for(const id of ['box-text','box-components','box-fine','box-context','box-path'])$(id).onchange=draw;
 $('reset').onclick=()=>{$('view').value='full';for(const id of ['box-text','box-components','box-fine','box-context','box-path'])$(id).checked=false;draw();};
 $('full-report').parentElement.addEventListener('toggle',e=>{if(e.target.open)$('full-report').textContent=JSON.stringify(S.panel.full_frozen_report,null,2);});
 }catch(e){$('load').textContent='无法读取完整记录：'+e.message+'。可使用下方原始汇编下载链接。';}
}
init();
})();
