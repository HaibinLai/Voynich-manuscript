"""Serialize the recorded guided image observations; this is not an OCR program."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timezone
HERE=Path(__file__).resolve().parent
queue=json.loads((HERE/'queue_v1.json').read_text())
records=[]
specs={
 'f68r1.26':([430,2160,180,130],'located_adjacency_clear','左侧星图区靠下的一枚独立星形旁短串；旁边有相邻星形，但该短串局部邻接较清楚。','原图短串与给定 otor 相容；正文第一行对应形也已并看，属于转写引导核图，非独立释读。','f68r1_otor_region.jpg'),
 'f75v.25':([1200,1480,220,90],'located_referent_unclear','上方十组两行文字中自左第四组的下行；上行是同组文字。两侧图线向人物和共同装置延伸，不能把下行单独认作一个人物名字。','与 qokal 的给定字形相容；没有独立逐笔转写。','f75v_upper_labels.jpg'),
 'f75v.31':([1650,1540,220,90],'located_referent_unclear','同一上方文字带自左第七组下行；短串与上行构成空间组，文字没有明确的一对一指物引线。','与 dal 的给定字形相容；正文命中未逐一核图。','f75v_upper_labels.jpg'),
 'f75v.52':([1100,2645,160,80],'located_referent_unclear','下方浴池左上边沿、人像头部附近的短串；周边文字与池、人和管道空间交错。','与 olol 的给定字形相容；原转写已提示这一带行对齐不确定。','f75v_lower_left.jpg'),
 'f75v.54':([490,2910,210,100],'located_referent_unclear','下方浴池左边、管道转折下方竖向排列短串中的一行；可能关联共同管道或池，也可能对应邻近人物。','与 otedy 的给定字形相容；不把短串行切分当真实单独词义。','f75v_lower_left.jpg'),
 'f75v.55':([490,2980,230,110],'located_referent_unclear','紧接上一短串下方的下一行；上下文为同一浴池和管道区域，不能独立指认命名对象。','与 oteey 的给定字形相容；正文对应位置仍只保留转写索引。','f75v_lower_left.jpg'),
 'f68r1.8':([780,760,260,160],'located_adjacency_clear','左侧星图区上部圆脸左邻星形右侧的短串。空间上可提出星形—短串邻接候选；星的身份未知。','给定 okodaly 用于定位；未独立识别其全部笔画。','f68r1_left.jpg'),
}
for q in queue['selected']:
 loc=q['locator']
 if loc in specs:
  box,status,geom,reading,asset=specs[loc]
 else:
  box=None;status='individual_locus_unresolved';asset='f67r2_inner.jpg'
  geom='右侧圆图内圈的月脸圆盘旁有旋转文字。原转写按扇区顺序提示此位置；本次只确认这一类空间关系，未可靠识别该单独 locator 对应的完整短串。'
  reading='不把按扇区顺序推定的方位当作独立字形核验；不提供看似精确的单词框。'
 records.append({'locator':loc,'supplied_EVA':q['word'],'historical_group':q['group'],'status':status,'approx_bbox_xywh':box,'coordinate_frame':'full official source image, no rotation; reading region only' if box else None,'geometry':geom,'reading_scope':reading,'asset':asset,'body_hits_from_prior_transcription':{v:q[v]['body_hits'] for v in ['ZL','IT']},'body_visual_check':'first line guided comparison only' if loc=='f68r1.26' else 'not independently checked in this review'})
payload={'created_utc':datetime.now(timezone.utc).isoformat(),'method':'Guided visual inspection by the root AI with supplied transcription and prior hit status. Approximate boxes are reading regions, not segmentation.','protocol_deviation':'The root received interim and final geometric summaries from the separated-context reviewer before freezing this guided review. Therefore the planned two-observation pre-reconciliation freeze was not achieved. The separated-context geometry review was frozen before its author received linguistic/statistical inputs; the root review is informed by those summaries and is not an independent replication.','queue_sha256':hashlib.sha256((HERE/'queue_v1.json').read_bytes()).hexdigest(),'geometry_sha256':hashlib.sha256((HERE/'geometry_review_v1.json').read_bytes()).hexdigest(),'source_images':queue['images'],'records':records,'counts':{s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})},'interpretation':['2 adjacency candidates, 5 ambiguous referents, 5 unresolved individual loci. This is a measurement-feasibility review of a result-selected queue, not an accuracy estimate.','Two-line bath groups and uncertain lower alignment limit treating every transcription locator as one autonomous named object.','No object identity, species, personal name, stellar name, sound value or translation established.','The old label-body counts retain their original transcription-based definition; this review does not silently remove difficult loci or revise the frozen sample.']}
out=HERE/'root_review_v1.json'
if out.exists(): raise SystemExit('Refusing to overwrite frozen review')
out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
lines=['十二位置：带转写引导的核图记录','',payload['method'],'', '流程偏差：'+payload['protocol_deviation'],'']
for r in records:
 lines += [r['locator']+' / '+r['supplied_EVA']+' / '+r['status'],r['geometry'],r['reading_scope'],'近似框：'+str(r['approx_bbox_xywh']),'']
lines += ['范围：2个邻接清楚的候选、5个可定位但指物不清、5个单独行位未可靠定位。不是十二个已认证名称。','f75v 上方是两行一组；下方原转写本已提示行对齐非常不确定。','仅 otor 的标签与正文第一行已并看，其余正文命中保留为转写索引，不声称逐个核过原图。','旧统计按其冻结定义保持不变；本次困难例和未能识别的位置不删掉。']
(HERE/'root_review_v1.txt').write_text('\n'.join(lines)+'\n')
print(payload['counts'])
