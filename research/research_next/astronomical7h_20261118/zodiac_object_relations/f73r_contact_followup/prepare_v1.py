"""Prepare fixed native crops for an informed contact review; preparation is not observation."""
from pathlib import Path
import argparse,json,hashlib
from datetime import datetime,timezone
from PIL import Image
P=Path(__file__).resolve().parent;R=P.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path,required=True);ap.add_argument('--output-root',type=Path,required=True);args=ap.parse_args()
 a=json.loads((R/'aggregation_v1.json').read_text());p=next(x for x in a['panels'] if x['panel']=='f73r');r=p['full_frozen_report'];s=p['full_original_seed'];assert sha(args.image)==p['original_image']['sha256'];im=Image.open(args.image);assert list(im.size)==p['original_image']['dimensions_px']
 texts={x['region_uid']:x for x in s['text_records']};components={x['component_uid']:x['original_box_xyxy'] for x in s['object_components']}
 for x in r['discovered_supplements']:components[x['component_uid']]=x.get('box_xyxy')
 obs={x['region_uid']:x for x in r['text_records']};positives=sorted({x['source_uid'] for x in r['relation_edges'] if x['edge_kind']=='text_to_object' and x['evidence_level']=='P'})
 used=set();pairs=[]
 for uid in positives:
  band=texts[uid]['ring_assignment_original'];eligible=sorted(k for k in texts if k not in positives and k not in used and texts[k]['ring_assignment_original']==band)
  after=[k for k in eligible if k>uid];control=(after or eligible or [None])[0]
  if control:used.add(control)
  pairs.append({'candidate':uid,'original_band':band,'control':control,'no_control_reason':'No other fixed text record in central band' if control is None else None})
 assert len(positives)==5 and len(used)==4
 ids=sorted(set(positives)|used);sources=[{'path':'../aggregation_v1.json','sha256':sha(R/'aggregation_v1.json')},{'path':'../circle_spatial_observer/f73r/observer_report_v1.json','sha256':sha(R/'circle_spatial_observer/f73r/observer_report_v1.json')},{'path':'protocol_v1.txt','sha256':sha(P/'protocol_v1.txt')},{'path':'prepare_v1.py','sha256':sha(Path(__file__))}]
 plan={'schema':'f73r_contact_followup_fixed_input_v1','utc':datetime.now(timezone.utc).isoformat(),'original_image':p['original_image'],'sources':sources,'pairs':pairs,'fixed_region_ids':ids,'preserve_all_existing_candidates':True,'selection_is_posthoc_informed':True,'prepared_crops_are_not_observations':True}
 dump(P/'input_freeze_v1.json',plan)
 args.output_root.mkdir(parents=True,exist_ok=True);views=[]
 def pad(b,n):return [max(0,b[0]-n),max(0,b[1]-n),min(im.width,b[2]+n),min(im.height,b[3]+n)]
 for uid in ids:
  t=texts[uid];box=t['original_box_xyxy'];boxes=[box]+[components[k] for k in obs[uid]['candidate_object_ids'] if components.get(k)]
  u=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
  for mode,b in [('original',box),('expanded80',pad(box,80)),('candidate_context',pad(u,40))]:
   name=uid.replace(':','_')+'_'+mode+'.png';out=args.output_root/name;im.crop(b).save(out)
   views.append({'view_id':uid+':'+mode,'region_uid':uid,'mode':mode,'crop_xyxy_original':b,'dimensions_px':[b[2]-b[0],b[3]-b[1]],'filename':name,'sha256':sha(out),'prepared_only_not_viewed':True})
 dump(P/'prepared_views_v1.json',{'schema':'fixed_f73r_native_views_v1','input_freeze_sha256':sha(P/'input_freeze_v1.json'),'views':views})
 dump(P/'preparation_output_freeze_v1.json',{'utc':datetime.now(timezone.utc).isoformat(),'files':[{'path':n,'sha256':sha(P/n)} for n in ['protocol_v1.txt','prepare_v1.py','input_freeze_v1.json','prepared_views_v1.json']],'view_count':len(views),'images_observed_by_preparation':False})
 print(json.dumps({'pairs':pairs,'regions':len(ids),'prepared_views':len(views)},ensure_ascii=False))
if __name__=='__main__':main()
