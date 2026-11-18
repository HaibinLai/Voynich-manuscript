'use strict';
(() => {
const $=id=>document.getElementById('fc-'+id),NS='http://www.w3.org/2000/svg';
const modes={original:'原文字框',expanded80:'原框四向扩 80 像素',candidate_context:'全部原候选的上下文'};
let data=null,index=0,renderToken=0;
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
const detailNotesZh={
 'f73r:ZC01':['两路均保留动物腿端附近的接触，未确认文字独立引线。','根另记原框上方与左端截笔；另一方没有对应完整度字段，省略不等于否认。','中央普通注记不能充当外围文字的同角色对照。'],
 'f73r:ZE01':['两路均保留末端与手臂的局部接触；细缝及笔画先后仍未定。'],
 'f73r:ZE02':['根描述首端降笔旁的窄浅缝；另一方对主要墨迹与轮廓的分离作较宽范围说明。','两份N相容不等于所有细小边界都得到相同分割。'],
 'f73r:ZI08':['两路均将疑点定位在短串上端与弯曲手部邻域，未把人物连星线交给文字。'],
 'f73r:ZI09':['两路均记文字和邻近人体轮廓之间可见纸面，历史指代关系仍未检验。'],
 'f73r:ZO01':['两路均保留字尾与后伸手臂接触候选；浅墨的具体角色与先后仍未定。'],
 'f73r:ZO02':['两路均未可靠分离末端浅字与手部轮廓，P没有升级为明确引线。'],
 'f73r:ZO03':['根描述短串下方空白处的弯笔；另一方明确保留它属于文字尾笔还是图形的未定。','粗N相容不能解决笔画身份问题，也不说明像素判断完全相同。'],
 'f73r:ZO04':['两路都未确认文字接线。根另记原框截笔及框外圆样墨迹；另一方谈上部浅笔和手臂。文字完整度缺少共同测量字段。']
};
function comparisonFor(r){
 if(!r.comparison)return;
 const original=$('original'),root=$('root'),other=$('other'),c=r.comparison;
 for(const box of [original,root,other])box.replaceChildren();
 original.append(el('p','原候选边逐条保留，不取最高等级：'));
 for(const edge of r.original_record.edges)original.append(el('p',`${edge.target_uid} · ${edge.evidence_level}`));
 for(const fact of r.original_record.text.observation_facts)original.append(el('p',fact));
 root.append(el('p',`区域级接触诊断：${c.root_region_level}。并非独立逐边重评全部原候选。`));
 for(const fact of r.root_repeat.observed_facts)root.append(el('p',fact));
 root.append(el('p','限制：'+r.root_repeat.limitation));
 other.append(el('p','接触诊断：'+(c.peer_mapped_region_level==='P'?'局部接触或叠压仍未定（P）':'未观察到明确接触（N）')));
 for(const fact of r.other_repeat.observation.visible_facts)other.append(el('p',fact));
 other.append(el('p','空隙：'+r.other_repeat.observation.gap),el('p','交叠：'+r.other_repeat.observation.overprint));
 const details=el('details'),summary=el('summary','另一代理逐边复核与原等级');details.append(summary,el('pre',JSON.stringify(r.other_repeat.edge_grade_comparison,null,2)));other.append(details);
 const note=$('disagreement');note.replaceChildren();
 note.append(el('p',c.region_categories_compatible?'按已冻结的描述映射，区域粗类别相容。不是原始字段完全相同，也不认证逐笔相同。':'两路区域粗类别存在差异，原记录均保留。'));
 note.append(el('p','完整文字侧引线：根与另一方均未确认。没有确认不等于历史上没有指代。'));
 for(const text of (detailNotesZh[r.region_uid]||c.detail_scope_notes))note.append(el('p',text));
 const raw=el('details');raw.append(el('summary','完整冻结比较与范围说明'),el('pre',JSON.stringify(c,null,2)));note.append(raw);
}
function svgFor(crop,original,caption,token){
 const svg=document.createElementNS(NS,'svg'),[x0,y0,x1,y1]=crop;
 svg.setAttribute('viewBox',`${x0} ${y0} ${x1-x0} ${y1-y0}`);svg.setAttribute('width',x1-x0);svg.setAttribute('height',y1-y0);svg.setAttribute('role','img');
 const title=document.createElementNS(NS,'title');title.textContent=`官方完整原图裁视口，原画布范围 ${crop.join(', ')}`;svg.append(title);
 const image=document.createElementNS(NS,'image');image.setAttribute('width',data.original_image.dimensions_px[0]);image.setAttribute('height',data.original_image.dimensions_px[1]);
 image.addEventListener('load',()=>{if(token===renderToken)caption.textContent=`图像已显示。原画布范围 [${crop.join(', ')}]；裁区 ${x1-x0} × ${y1-y0} 像素。`;});
 image.addEventListener('error',()=>{if(token===renderToken)caption.textContent='馆方图源加载失败；可使用官方完整原图链接。';});
 image.setAttribute('href',data.original_image.official_url);svg.append(image);
 if($('outline').checked&&original){const rect=document.createElementNS(NS,'rect');for(const [k,v] of Object.entries({x:original[0],y:original[1],width:original[2]-original[0],height:original[3]-original[1],fill:'none',stroke:'#a84920','stroke-width':'1.5','stroke-dasharray':'4 3','vector-effect':'non-scaling-stroke'}))rect.setAttribute(k,v);svg.append(rect);}
 return svg;
}
function show(){
 const token=++renderToken,r=data.records[index],pair=r.pairing;const candidate=r.fixed_role==='P_source';$('region').value=r.region_uid;
 const band={central:'中央普通注记',external:'外附带',inner:'内带',outer:'外带'}[pair.original_band]||pair.original_band;
 $('pair').textContent=`${r.region_uid} · ${candidate?'原 P 来源诊断区':'同带 N 对照'} · ${band}。`+(pair.control?`固定配对：${pair.candidate} ↔ ${pair.control}；仅为事后固定的诊断选择，不是语义配对。`:'中央同带对照：NA。没有其他合格的中央原文字区，不跨角色补入。');
 $('crops').replaceChildren();const original=r.views.find(v=>v.mode==='original').crop_xyxy_original;
 for(const v of r.views){const f=el('figure');f.className='fc-crop';f.append(el('h3',modes[v.mode]));const stage=el('div');stage.className='fc-image-stage';const cap=el('figcaption','正在读取馆方图源。');cap.setAttribute('role','status');stage.append(svgFor(v.crop_xyxy_original,v.mode==='original'?null:original,cap,token));f.append(stage,cap);$('crops').append(f);}
 $('crop-source').textContent=JSON.stringify({region_uid:r.region_uid,original_image:data.original_image,views:r.views,hash_note:'prepared views 的 sha256 属于研究准备阶段的 PNG 文件；本页直接裁馆方完整 JPEG，不把两个文件哈希混同，也不声称网页图像已经逐字节验证。',observation_note:'prepared_only_not_viewed 保留准备清单原值，不代表任一补查最终是否看过。'},null,2);
 $('prev').disabled=index===0;$('next').disabled=index===data.records.length-1;
 $('full').replaceChildren();if(!$('full').hidden){const cap=el('p','正在读取完整画布。');cap.className='fc-muted';$('full').append(svgFor([0,0,...data.original_image.dimensions_px],original,cap,token),cap,el('p','完整画布用于导航，屏幕适配显示不等于原生细节复核。'));}
 comparisonFor(r);
}
async function init(){try{
 const v=document.querySelector('meta[name="f73r-contacts-snapshot"]').content;const res=await fetch('data/f73r-contacts.json?v='+encodeURIComponent(v),{cache:'no-store'});if(!res.ok)throw Error(`HTTP ${res.status}`);data=await res.json();if(!['f73r_contact_site_preview_v1','f73r_contact_site_v1'].includes(data.schema))throw Error('数据版本不符');
 const approved=data.publication_status==='APPROVED_INFORMED_DIAGNOSTIC';
 if(approved){document.querySelector('.fc-notice').textContent='固定诊断补查已公开：两路各查看27张原生细节，均未确认完整文字引线。5个预定接触目标仍保留P，4个固定同带N对照未见明确连接。粗类别相容不消除淡笔归属、细缝及截框范围的未决；原全12图汇编不变。';document.querySelector('.site-footer span').textContent='固定诊断样本 · 两路知情补查 · 原记录保留';}
 $('region').replaceChildren(...data.records.map(r=>{const o=el('option',r.region_uid+' · '+(r.fixed_role==='P_source'?'原 P 来源':'同带 N 对照'));o.value=r.region_uid;return o;}));
 $('official').href=data.original_image.official_url;$('protocol').textContent=data.protocol;
 const labels={'independent-audit.json':'独立记录复算数据','independent-audit.txt':'独立记录复算报告','audit-replay-manifest.json':'独立复算的明确依赖清单','audit-release.json':'复算报告范围核对','report.txt':'补查报告与解释边界','comparison.json':'三列完整比较数据','comparison-freeze.json':'比较输出冻结','comparison-mapping.json':'字段对应与细节范围','root-observation.json':'根协调原始记录','root-observation.txt':'根协调观察全文','peer-observation.json':'另一代理原始记录','peer-observation.txt':'另一代理观察全文','peer-output-freeze.json':'另一代理输出冻结','publication-approval.json':'限定发布批准','protocol.txt':'固定协议','input-freeze.json':'固定输入与配对','prepared-views.json':'全部 27 个预定裁图范围','root-output-freeze.json':'根补查输出冻结（非结果内容）'};
 for(const d of data.downloads){const a=el('a',labels[d.name]||d.name);a.href=d.url;a.download='';$('downloads').append(a);}
 $('source').textContent='冻结源图 SHA-256：'+data.original_image.sha256+(approved?'。结果来自分别冻结的两份知情补查及明确字段映射；所有原候选和细节未决保留。':'。本预览只读取协议、固定输入、预制视图清单及根输出冻结；未接入观察判断。');
 for(const id of ['region','prev','next','outline','full-toggle'])$(id).disabled=false;
 $('region').onchange=()=>{index=data.records.findIndex(r=>r.region_uid===$('region').value);show();};$('prev').onclick=()=>{if(index>0){index--;show();}};$('next').onclick=()=>{if(index<data.records.length-1){index++;show();}};$('outline').onchange=show;
 $('full-toggle').onclick=()=>{$('full').hidden=!$('full').hidden;$('full-toggle').textContent=$('full').hidden?'显示完整画布':'收起完整画布';show();};
 $('load').textContent=approved?'固定9区、27裁图范围及三列冻结记录已载入。':'固定9区、27裁图范围已载入；三列结果与分歧待批准后接入。';show();
 }catch(e){$('load').textContent='预览读取失败：'+e.message+'。可下载固定协议及预定坐标。';}}
init();
})();
