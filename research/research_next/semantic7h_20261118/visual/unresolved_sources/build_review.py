# -*- coding: utf-8 -*-
"""Record human-readable, result-informed AI image observations; no lexical scoring."""
from pathlib import Path
from collections import Counter
import json, hashlib, datetime
from PIL import Image

P=Path(__file__).resolve().parent
REPO=P.parents[4]
sha=lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
write=lambda name,obj: (P/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
queue=json.loads((P/'queue_v1.json').read_text())['records']
objects=[]
def add(folio,n,iid,bbox,assets,status,obs,candidate=None):
    objects.append(dict(source_object_id=f'{folio}_{n}',folio=folio,fragment_id=n,image_id=iid,object_approx_bbox_xywh=bbox,bbox_scope='Approximate object extent, not an ink segmentation; context crops may contain adjacent objects.',crop_files=['assets/'+a+'.jpg' for a in assets],object_localization='clear',label_observation=status,observation_zh=obs,new_candidate=candidate,label_bbox_xywh=candidate.get('label_bbox_xywh') if candidate else None,pair_ids=[q['pair_id'] for q in queue if q['pharma_folio']==folio and q['fragment_id']==n],target_body_read_or_scored=False,old_support_modified=False))
add('f89r2',40,'1006233',[5560,1920,430,610],['f89r2_row3','f89r2_40_41_context','f89r2_sodar_candidate'],'unresolved',
    '按 q15 第3排顺序，#40 是容器右侧第1个扇状绿叶、黄褐分叉根对象。sodar 短字组在它与右邻 #41 之间；能定位字组，但无指示线或唯一贴附，不能用六对象五标签的数量差机械补位。左边 korainy / korain.y 在容器与 #40 之间，来源标成 Lc16，未借给植物。上下连续行属正文。',
    dict(locator='f89r2.17',versions={'ZL':'sodar','IT':'sodar'},label_bbox_xywh=[5905,2065,175,80],attachment='ambiguous between objects 40 and 41',eligible_in_old_analysis=False,classification='new spatial candidate only'))
add('f101r',150,'1006249',[3180,1000,650,750],['f101r_upper','f101r_150'],'no_independently_attributable_label',
    'q19 第2排第2个对象：未着满色的分叉叶丛和横向根，位于两组高绿叶之间。周围留白中未见可独立归属短标签；下方是跨整面的连续正文。两个目标关系共用该对象，只记一次来源观察。')
add('f101r',155,'1006249',[3310,2730,500,820],['f101r_lower','f101r_155'],'no_independently_attributable_label',
    'q19 第3排第2对象为大片圆团绿色叶冠、细长直茎；旁有未涂满容器和下一对象。对象周围及容器内未见可归属短字组；上方是连续正文。不能把最近一行当标签。')
add('f101r',168,'1006249',[5030,2560,570,950],['f101r_lower','f101r_168'],'no_independently_attributable_label',
    'q19 第3排在 #157 后的 #168，位于原折线附近，是直立交替绿叶枝。上方字为横跨折线的正文，没有可独立归属短标签；折线和较淡笔迹限制了绝对缺失判断。')
add('f101v',188,'1006251',[950,240,590,910],['f101v_right_top','f101v_188_label'],'clear_short_label_visible',
    'q19 将右历史面顶排列为186、187、188、189、190；#188 是第3个、两侧大片下垂绿叶与细分叉茎的对象。其右上与 #189 之间有独立短字组；与该排其余对象右侧短标签形成一致布局。该组定位到 f101v.7 可作为新候选，EVA版本差异保留。不是植物名认证或独立转写。',
    dict(locator='f101v.7',versions={'ZL':'otarar','IT':'otorar'},label_bbox_xywh=[1510,365,220,95],attachment='clear layout-supported candidate; no semantic identity claim',eligible_in_old_analysis=False,classification='new spatial candidate only'))
add('f102r1',203,'1006251',[2930,2260,1200,1300],['f102r1_lower'],'no_independently_attributable_label',
    'q19 第3排左对象，大红色分叉根与成对绿色叶。上方是整段正文，左侧红容器内有较淡字迹；未见对象自己的独立短标签。容器字不借给根。底部受折叠、透印和纸面状态限制。')
add('f102r1',204,'1006251',[3890,2160,1180,1130],['f102r1_lower'],'no_independently_attributable_label',
    'q19 第3排右对象，直立茎配三组宽叶，下部蓝绿区域靠近折叠边。上端紧邻正文，底部可见折叠/透印背景；未见可与正文分开的独立短标签。底部背景字不擅认成新标签。')
add('f102r2',205,'1006251',[5530,320,1410,650],['f102r2_top_whole','f102r2_upper_middle'],'no_independently_attributable_label',
    'q19 顶排左对象为黄褐多分叉根和两片大片绿叶。左侧容器内有字，下方为连续正文；对象外缘没有可独立归属短标签。容器字不可自动附给植物。')
add('f102r2',206,'1006251',[6700,320,1430,1600],['f102r2_top_whole','f102r2_upper_middle'],'no_independently_attributable_label',
    'q19 顶排右对象跨内部折线，长弯茎连蓝色花和远右绿色星状端，黄褐根部下垂。附近正文避开其根与茎；未见独立短标签。折线磨损和淡墨限制可见性；不能断言原本未写名称。')
add('f102r2',209,'1006251',[6515,1315,510,335],['f102r2_upper_middle','f102r2_209_context'],'no_independently_attributable_label',
    'q19 第2排第3对象为小黄褐三向根块、弯茎与右侧窄绿叶。上下一行都延续整排正文，左右邻物之间没有分离短标签。不能将最近正文单词抽作该物标签。')
assert len(objects)==10 and sum(len(x['pair_ids']) for x in objects)==11
relations=[dict(pair_id=q['pair_id'],source_object_id=f"{q['pharma_folio']}_{q['fragment_id']}",original_status=q['status'],source_observation=next(x['label_observation'] for x in objects if x['folio']==q['pharma_folio'] and x['fragment_id']==q['fragment_id'])) for q in queue]
index=dict(q15_url='https://www.voynich.nu/q15/index.html',q19_url='https://www.voynich.nu/q19/index.html',retrieval='Read webpage text through search-service browser. Direct HTML retrieval returned HTTP 406; no raw HTML SHA claimed. Modern thumbnails were not saved or republished.',rows={'f89r2_row3':[40,41,42,43,44,45],'f101r_row2':[149,150,151,152,153,163,164,165,166,167],'f101r_row3':[154,155,156,157,168,169,170,171,172],'f101v_row1':[173,174,175,176,186,187,188,189,190],'f102r1_row3':[203,204],'f102r2_row1':[205,206],'f102r2_row2':[207,208,209,210,211]},panel_notes=['1006233: f88v/f89r1/f89r2 from left to right; #40 lies on rightmost face.','1006249: f100v at left, f101r across the rest; f101r is not split into independent samples.','1006251: left panel is right historical half of f101v (old f101v1), middle f102r1, right f102r2. #188 is on left image panel, although it is the right half of the complete f101v face.'])
write('numbering_index.json',index)
source_lines={}
for version,file in [('ZL','ZL3b-n.txt'),('IT','IT2a-n.txt')]:
    path=REPO/'research/sources'/file
    source_lines[version]=dict(source_file='research/sources/'+file,sha256=sha(path),candidate_and_neighbor_lines=[line for line in path.read_text().splitlines() if any(line.startswith(prefix) for prefix in ['<f101v.5,','<f101v.6,','<f101v.7,','<f101v.8,','<f101v.9,','<f89r2.16,','<f89r2.17,','<f89r2.18,'])])
write('source_loci.json',source_lines)
manifest=REPO/'research/research7h/visual_audit/yale_manifest.json'
canvases=[]
for item in json.loads(manifest.read_text())['items']:
    body=item['items'][0]['items'][0]['body'];iid=body['id'].split('/iiif/2/')[1].split('/')[0]
    if iid not in ['1006233','1006249','1006251']: continue
    if iid=='1006233': f=REPO.parent/'output/voynich/research_next/semantic7h_20261118/order_candidates/1006233_native.jpg'
    else: f=P.parent/'crossplant/assets'/(iid+'.jpg')
    canvases.append(dict(image_id=iid,label=item['label'],official_full_url=body['id'],native_dimensions=[body['width'],body['height']],existing_full_cache_sha256=sha(f),cached_dimensions=list(Image.open(f).size)))
write('source_receipt.json',dict(manifest_sha256=sha(manifest),canvases=canvases,all_public_images='Unaltered JPEG response bytes from official Yale IIIF region URLs, recorded in crop receipts.'))
result=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='Separate, result-informed AI source-layout review, not blinded independent transcription or a confirmatory dataset.',count_unique_objects=10,count_relationships=11,object_counts=dict(Counter(x['label_observation'] for x in objects)),relationship_counts=dict(Counter(x['source_observation'] for x in relations)),objects=objects,relationships=relations,
    correction_to_generic_old_reason_zh='旧表 f101r 的说明提到邻近 Lc 容器字，这只是笼统理由；本次原图观察及 q19 页面显示该面没有独立标签。新报告改为连续正文与未标字容器，不更改旧支持表。',
    limitations=['No herbal target body was inspected or scored in this task.','Objects 150 to two targets are one source observation, not independent replications.','No apparent label means none independently attributable in these scans; not proof that the manuscript never named it.','Only the #188 and #40 new candidates are recorded; neither is backfilled or scored.','Approximate boxes are descriptive; no false precise label boxes for absent or unlocalized writing.','Known prior results and prior canvas exposure prevent a blind-review claim.'],numbering='numbering_index.json',source_transcription_context='source_loci.json')
write('review.json',result)
lines=['剩余来源资格原图核对','完成时间：'+result['utc'],'','11关系对应10个不同来源对象；#150两目标共用一次观察。结果按对象：8无可独立归属短标签，1明确可见短标签的新候选（#188），1归属未决（#40）。这是看过研究结果后的补测，不是新增确认集。','',result['correction_to_generic_old_reason_zh']]
for o in objects:
    lines+=['',o['source_object_id']+'：'+o['label_observation'],o['observation_zh'],'官方裁区：'+', '.join(o['crop_files'])]
    if o['new_candidate']: lines+=['新候选（不回填、不评分）：'+o['new_candidate']['locator']+' / '+json.dumps(o['new_candidate']['versions'],ensure_ascii=False)]
lines+=['','编号索引已核：https://www.voynich.nu/q15/index.html 与 https://www.voynich.nu/q19/index.html。官方原图/哈希/面板由 source_receipt.json 和 numbering_index.json 记录。14张公开裁图均为官方IIIF返回原字节，坐标/尺寸/SHA见crop_receipt_v1/v2/v3.json。现代缩图未保存或发布。','原图无独立可归属标签≠原本无名称。邻近正文与容器字不自动成为对象名。f101v.7 两版 otarar/otorar 差异保留；f89r2.17 sodar 与#40/#41归属未决，Lc16不借用。旧数据、规则、结果未变，本任务未读取或评分对应草药正文。']
(P/'review.txt').write_text('\n'.join(lines)+'\n')
freeze=json.loads((P/'freeze_v1.json').read_text())
files=[f for f in P.rglob('*') if f.is_file() and f.name!='receipt.json']
write('receipt.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),frozen_files_match=all(sha(P/k)==v for k,v in freeze['files'].items()),old_label_support_hash_matches=sha(REPO/freeze['source'])==freeze['source_sha256'],all_14_public_crops_viewed=True,new_target_lexical_scoring=False,files=[dict(path=str(f.relative_to(P)),sha256=sha(f),bytes=f.stat().st_size) for f in sorted(files)]))
print(result['object_counts'],result['relationship_counts'])
