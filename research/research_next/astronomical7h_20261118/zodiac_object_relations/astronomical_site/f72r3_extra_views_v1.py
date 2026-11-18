"""Prepare explicit native follow-up contexts after V4 revealed cropped or competing paths. No receipts."""
from record_helpers import *
from PIL import Image
workspace=SOURCE.parents[3].parent
original=workspace/'output/voynich/research_next/astronomical7h_20261118/zodiac_visual/1006203.jpg'
root=workspace/'output/voynich/research_next/astronomical7h_20261118/zodiac_object_relations/astronomical_site/f72r3'
items=[('V5:O04-O05',[7740,1150,8150,1990],['f72r3:O04/pointed_shape','f72r3:O05/body'],'A thin line below O04 star leaves its local V4 crop toward the raised hand of O05; inspect the full intervening gap, not infer continuation.'),('V5:O08-M07',[6250,1990,6960,2460],['f72r3:O08/body','f72r3:O08/pointed_shape','f72r3:M07/body','f72r3:M07/pointed_shape'],'O08 seed pointed box has no securely distinct pointed figure in V4; inspect neighboring M07 star and both hands without substituting its identity.'),('V5:O09-M08',[5940,1660,6570,2090],['f72r3:O09/body','f72r3:O09/pointed_shape','f72r3:M08/body','f72r3:M08/pointed_shape'],'Curved strand from O09 star approaches neighboring M08 neighborhood beyond local crop; inspect full path and competing endpoint.')]
p=HERE/'f72r3_prepared_views_v1.json';d=read(p);im=Image.open(original)
for short,box,uids,reason in items:
 vid='f72r3:'+short;assert vid not in [x['view_id'] for x in d['views']]
 out=root/(vid.replace(':','_')+'.png');crop=im.crop(box);crop.save(out)
 d['views'].append({'view_id':vid,'plan_view_id':vid,'original_sha256':sha(original),'crop_xyxy_original':box,'rotation_degrees':0,'native_dimensions_px':list(crop.size),'view_file_sha256':sha(out),'display_mode':'native_detail','planned_region_uids':uids,'private_file_workspace_relative':str(out.relative_to(workspace)),'preparation_status':'prepared_not_viewed','followup_reason':reason})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
(HERE/'f72r3_view_plan_addendum_v1.json').write_text(json.dumps({'schema':'native_context_expansion_v1','prepared_utc':datetime.now(timezone.utc).isoformat(),'panel':'f72r3','reason':'Expand paths that reach initial V4 crop limits and retain competing objects; original fixed plan and seeds unchanged.','views':d['views'][-3:],'preparation_is_not_viewing':True},ensure_ascii=False,indent=2)+'\n')
