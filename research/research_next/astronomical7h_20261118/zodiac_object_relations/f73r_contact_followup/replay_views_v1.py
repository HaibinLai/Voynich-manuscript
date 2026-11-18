"""Recreate frozen views without reselecting regions or modifying research inputs."""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image
P=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path,required=True);ap.add_argument('--output-dir',type=Path,required=True);a=ap.parse_args()
 if a.output_dir.resolve()==P.resolve() or P.resolve().is_relative_to(a.output_dir.resolve()):raise ValueError('Choose a separate new crop output directory')
 plan=json.loads((P/'input_freeze_v1.json').read_text());v=json.loads((P/'prepared_views_v1.json').read_text());assert v['input_freeze_sha256']==sha((P/'input_freeze_v1.json').read_bytes());assert sha(a.image.read_bytes())==plan['original_image']['sha256'];im=Image.open(a.image);assert list(im.size)==plan['original_image']['dimensions_px']
 a.output_dir.mkdir(parents=True,exist_ok=True);receipts=[]
 for x in v['views']:
  out=a.output_dir/x['filename'];assert not out.exists(),out
  im.crop(x['crop_xyxy_original']).save(out);assert sha(out.read_bytes())==x['sha256'],out
  receipts.append({'view_id':x['view_id'],'sha256':x['sha256'],'original_xyxy':x['crop_xyxy_original']})
 print(json.dumps({'schema':'fixed_contact_views_replay_v1','all_native_crops_byte_equal':True,'count':len(receipts),'new_observations':False,'views':receipts},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
