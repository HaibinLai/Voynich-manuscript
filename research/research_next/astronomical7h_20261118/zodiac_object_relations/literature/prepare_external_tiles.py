from review_tools import *
f=sys.argv[1];d=OUT/f;ix=load(d/'prepared_index.json');im=Image.open(WORK/'output/voynich/research_next/astronomical7h_20261118/zodiac_visual'/(plan(f)['canvas_id']+'.jpg'))
for vid,v in list(ix.items()):
 if ':V2-extra:' not in vid or ':tile' in vid:continue
 x0,y0,x1,y1=v['box']
 if max(x1-x0,y1-y0)<=1536:continue
 xs=[x0] if x1-x0<=1536 else list(range(x0,x1-1536,1228))+[x1-1536]
 ys=[y0] if y1-y0<=1536 else list(range(y0,y1-1536,1228))+[y1-1536]
 for a,xx in enumerate(xs):
  for b,yy in enumerate(ys):
   vv=vid+f':tile{a+1}_{b+1}';box=[xx,yy,min(xx+1536,x1),min(yy+1536,y1)];name=vv.replace(':','_')+'.png';im.crop(box).save(d/name)
   ix[vv]=dict(v,file=name,sha256=sha(d/name),box=box,native_dimensions_px=[box[2]-xx,box[3]-yy],stored_dimensions_px=[box[2]-xx,box[3]-yy])
save(d/'prepared_index.json',ix)
print([vid for vid in ix if ':V2-extra:' in vid and (':tile' in vid or max(ix[vid]['native_dimensions_px'])<=1536)])
