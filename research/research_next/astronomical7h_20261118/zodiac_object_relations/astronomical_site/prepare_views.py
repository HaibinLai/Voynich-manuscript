"""Prepare unaltered crops only. This script never creates a viewed receipt."""
from pathlib import Path
import hashlib,json,sys
from PIL import Image
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent
ROOT=SOURCE.parents[3]
WORKSPACE=ROOT.parent
PRIVATE=WORKSPACE/'output/voynich/research_next/astronomical7h_20261118/zodiac_object_relations/astronomical_site'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
def prepare(panel):
    freeze=read(SOURCE/'execution_freeze_v1.json')
    assert sha(SOURCE/'execution_freeze_v1.json')=='71e3d951eb9ec6117bf679dab20f0500e48ad0a0eacaf6fd39365a45f071ed5d'
    for row in freeze['files']:assert sha(SOURCE/row['path'])==row['sha256']
    inputs=read(SOURCE/'inputs_v1.json');assert panel in inputs['assignments_fixed_order']['astronomical_site']
    plan=next(p for p in read(SOURCE/'view_plan_v1.json')['panels'] if p['panel']==panel)
    source=next(r for r in inputs['allowed_original_images'] if r['canvas_id']==plan['canvas_id'])
    original=WORKSPACE/source['local_path_workspace_relative'];assert sha(original)==source['sha256']
    image=Image.open(original);assert list(image.size)==source['dimensions_px']
    dest=PRIVATE/panel;dest.mkdir(parents=True,exist_ok=True);rows=[]
    def starts(lo,hi,side=1536):
        if hi-lo<=side:return [lo]
        result=list(range(lo,hi-side+1,1228))
        if result[-1]!=hi-side:result.append(hi-side)
        return result
    for p in plan['view_plans']:
        x1,y1,x2,y2=p['crop_xyxy_original'];boxes=[(x1,y1,x2,y2)]
        if p['intended_display_mode']=='native_detail' and max(x2-x1,y2-y1)>1536:
            boxes=[(x,y,min(x+1536,x2),min(y+1536,y2)) for y in starts(y1,y2) for x in starts(x1,x2)]
        for j,b in enumerate(boxes):
            vid=p['plan_view_id']+(f':tile{j+1}' if len(boxes)>1 else '')
            target=dest/(vid.replace(':','_')+'.png')
            image.crop(b).save(target)
            rows.append({'view_id':vid,'plan_view_id':p['plan_view_id'],'crop_xyxy_original':list(b),'rotation_degrees':0,'native_dimensions_px':[b[2]-b[0],b[3]-b[1]],'view_file_sha256':sha(target),'original_sha256':source['sha256'],'display_mode':p['intended_display_mode'],'planned_region_uids':p['planned_region_uids'],'private_file_workspace_relative':str(target.relative_to(WORKSPACE)),'status':'prepared_not_viewed'})
    out={'schema':'prepared_views_not_observations_v1','panel':panel,'source':source,'views':rows}
    (HERE/f'{panel}_prepared_views_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(panel,len(rows),'views prepared; zero observation receipts generated.')
if __name__=='__main__':prepare(sys.argv[1])
