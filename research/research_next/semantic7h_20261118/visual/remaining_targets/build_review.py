"""Freeze one observer's full 11-pair geometry record; no lexical scoring.

Manual descriptions and approximate target regions follow actual image review.
This records observations, not automated image classification or plant identity.
"""
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter
import hashlib, json

HERE=Path(__file__).resolve().parent
BASE=HERE.parents[1]
ROOT=HERE.parents[4]
CACHE=ROOT.parent/'output/voynich/research_next/semantic7h_20261118/remaining_targets'

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

# Boxes below were estimated on the unretouched, 1000-pixel-wide overview.
# They are deliberately coarse reading regions, not segmentation boundaries.
OBS={
 'f89r2_40__f87v':('limited_or_ambiguous',[180,140,770,1100],
  '来源扇状绿叶与黄褐分叉根，和目标两株相互交错的粗根只有宽泛形态相似。',
  '目标左株是较圆长叶和单个浅色花形，右株有深裂叶及多个顶端花形；来源的窄叶扇无法唯一对应其中一株。根部互相缠绕，不能因目标页号已知而选定一个对象。'),
 'f101r_150__f30v':('limited_or_ambiguous',[270,210,690,1090],
  '两图都能看到叶缘锯齿和横向伸展的褐色根部。',
  '来源窄叶呈扇状集中；目标宽尖叶分列茎的不同高度，上方还有许多小椭圆端部。来源短横根和目标长横根的结节、分支比例不同。'),
 'f101r_150__f55v':('limited_or_ambiguous',[180,20,710,1220],
  '来源叶簇与目标大叶冠都有向上尖齿的轮廓，根部都有侧向延伸。',
  '来源是分开的细窄未着色叶，目标是大片绿色叶形与粗红色中央茎。目标上方细小端部和底部密集须状笔画在来源未见对应。两条文献关系共用同一个来源#150，不能当两份独立证据。'),
 'f101r_155__f49r':('limited_or_ambiguous',[130,150,800,1150],
  '来源绿色圆团状叶冠与目标的大块圆边叶片在外轮廓上可作有限比较。',
  '来源几乎只有一大片横向叶冠、细长直茎和少量下端笔画；目标有分开的多块叶片、反复弯曲的枝与多处红蓝端部、粗大环状根。补看来源上下文后，仍没有足够对应部件。'),
 'f101r_168__f4v':('limited_or_ambiguous',[395,45,550,1285],
  '两者都有直立或斜立分枝与绿色叶状部分。',
  '来源叶片较长宽、成簇分列；目标叶片多为小钩状，另有星状绿色端部和大蓝色花形。目标串珠状膨大根与来源短根不同；来源折线磨损也限制观察。'),
 'f101v_188__f37r':('suitable_for_partial_shape_comparison',[365,225,435,1090],
  '两图都在中央细茎两侧反复画下垂尖叶，若干叶片上缘有内卷的钩状弯曲。',
  '目标有明显的上端成簇小圆花形和较长的成束基部线条，来源没有同样完整的上端部分；根部的数量和弯曲程度不同。只能比较叶片组织与轮廓。'),
 'f102r1_203__f37v':('suitable_for_partial_shape_comparison',[435,65,505,1200],
  '两图都画圆边叶片、弯曲叶柄、茎根交界的点状圈边，以及向下伸出多条长尖分支的膨大根部。目标下部两片圆叶尤可与来源比较。',
  '目标上方还有多层细长弯叶和三个蓝色端部，来源只保留低处叶片与根部。两图根的色彩、分叉数量和比例不同，不能据这些相似处认证同种植物。'),
 'f102r1_204__f1v':('suitable_for_partial_shape_comparison',[165,145,785,1145],
  '两图有分枝上带基部缺口的宽尖叶，底部均画成横向隆起、内部有重复短线的宽大结构。',
  '来源叶片少，部分更横展；目标叶片数量、着色和排列不同，并有顶端花形。来源底部带外缘尖刺而目标以内部短曲线为主，轮廓亦不一致。'),
 'f102r2_205__f47v':('suitable_for_partial_shape_comparison',[205,65,770,1185],
  '两图根部都有近水平的上缘及短尖突，从粗基部向两侧和下方伸出多条长而尖的分叉；来源旁的大绿叶可与目标宽大叶片作局部比较。',
  '来源对象靠近画布上沿，叶和茎的信息不完整，原小框又截去部分上缘，已另看上下文。目标有多层叶与三个蓝色花形，来源不能逐项对应；不能因根相似补画缺失部分。'),
 'f102r2_206__f32v':('suitable_for_partial_shape_comparison',[225,55,715,1235],
  '蓝色张开的端部、绿色星状部分，以及一侧褐色、另一侧有分段笔画的弯曲长根，在两图中都有可比形状。',
  '来源枝叶数量少且与邻物重叠，长根近水平延伸；目标为直立长茎、多个星状部分和三个花形，根主要向下后转横。额外上下文用于区分邻物，不能将原框内所有笔画都归给#206。'),
 'f102r2_209__f53r':('suitable_for_partial_shape_comparison',[205,35,655,1290],
  '来源狭长绿叶边缘有密集尖齿，与目标狭长叶状部分的刺状边缘有具体局部相似。',
  '来源只有少量弯茎和小三向根块；目标有许多大型花形、多种叶轮廓和复杂环状根。目标全株并未由这片刺缘叶的相似而得到确认。'),
}

def main():
    assert not (HERE/'review_v1.json').exists(), 'Do not overwrite a frozen review'
    queue=read(HERE/'queue_v1.json')['records']
    freeze=read(HERE/'freeze_v1.json')
    for name,h in freeze['files'].items(): assert sha(HERE/name)==h,name
    for name,h in freeze['inputs'].items(): assert sha(BASE/name)==h,name
    acquisitions=read(HERE/'acquisition_v1.json')['files']+read(HERE/'additional_context_acquisition_v1.json')['files']
    assets={x['file']:x for x in acquisitions}
    for name,a in assets.items():
        assert sha(CACHE/name)==a['sha256'],name
        assert (CACHE/name).stat().st_size==a['bytes'],name
    prior_sources=read(BASE/'visual/unresolved_sources/source_receipt.json')
    canvases={x['image_id']:x for x in prior_sources['canvases']}
    rows=[]
    for q in queue:
        pid=q['pair_id']; o=q['source_object']; h=q['hypothesis']; t=q['target_canvas']
        decision,box,similar,different=OBS[pid]
        w,ht=t['width'],t['height']
        def native(b):
            z=[round(v*w/1000) for v in b]
            assert 0<=z[0]<z[0]+z[2]<=w and 0<=z[1]<z[1]+z[3]<=ht,(pid,z)
            return z
        regions=[{'bbox_xywh':native(box),'description':'全株近似阅读区域；不是像素分割或物种确认'}]
        unique=True
        if pid=='f89r2_40__f87v':
            unique=False
            regions=[{'bbox_xywh':native([185,410,420,825]),'description':'左侧植株及根部；根区与右株相交'},
                     {'bbox_xywh':native([390,140,555,1090]),'description':'右侧植株及根部；未决定哪株对应来源'}]
        sc=canvases[o['image_id']]
        source_crop=assets[o['source_object_id']+'_source.jpg']
        label_scope=('新空间候选 #188：f101v.7 的两版读法不同；未评分、未加入旧主集。' if o['fragment_id']==188 else
                     '候选 sodar 在 #40/#41 之间，唯一附着未决；未评分。' if o['fragment_id']==40 else
                     '未见可独立归属此对象的短标签；未评分，不借用容器字或连续正文。')
        rows.append({'pair_id':pid,'fragment_id':o['fragment_id'],'source_folio':o['folio'],'target_folio':h['herbal_folio'],
          'prior_hypothesis':h,'source_object_id':o['source_object_id'],
          'source':{'official_image_url':sc['official_full_url'],'full_sha256':sc['existing_full_cache_sha256'],
            'full_hash_provenance':'Inherited unchanged from unresolved_sources/source_receipt.json; new crop hash verified separately.',
            'full_size':sc['native_dimensions'],'manifest_label':sc['label'],
            'object_reading_bbox_xywh':o['object_approx_bbox_xywh'],'bbox_provenance':'Unchanged frozen source box; may truncate details or contain adjacent objects.',
            'attachment_status_inherited':o['label_observation'],'official_region_evidence':[source_crop]},
          'target':{'official_image_url':t['image_url'],'full_sha256':assets[h['herbal_folio']+'_full.jpg']['sha256'],
            'full_size':[w,ht],'manifest_label':t['label'],'object_reading_bbox_xywh':native(box),
            'visible_object_regions':regions,'viewed_file':h['herbal_folio']+'_overview.jpg',
            'viewing_scope':'Official 1000-pixel overview actually viewed; full-resolution download hash checked, not claimed as full native pixel inspection.'},
          'comparison_decision':decision,'visible_similarities':[similar],
          'visible_differences_and_missing_parts':[different],
          'comparison_scope':'One AI observer, exposed to earlier project evidence; descriptive geometry only, not a blind botanical review.',
          'target_correspondence_unique':unique,'label_scope_zh':label_scope,
          'notes':[label_scope,'来源文献等级未改。形态可比不等于同一对象或植物名称。'],
          'target_body_transcribed_or_scored':False,'eligible_as_semantic_gold':False,'original_label_support_modified':False})
    counts=Counter(x['comparison_decision'] for x in rows)
    viewed=[a['file'] for a in acquisitions if a.get('kind')!='target_full']
    assert len(viewed)==23 and len(rows)==11 and len({x['source_object_id'] for x in rows})==10
    payload={'report':'remaining_targets_geometry_v1','utc':datetime.now(timezone.utc).isoformat(),
      'protocol_sha256':sha(HERE/'protocol_v1.txt'),'queue_sha256':sha(HERE/'queue_v1.json'),
      'reviewer':'One AI-assisted observer, not a historical botanist; prior research exposed.',
      'summary':{'relationships':11,'unique_source_objects':10,'all_retained':True,**dict(counts),
         'multiple_target_objects_unresolved':1,'new_lexical_scoring':0,'semantic_gold':0},
      'actual_viewed_files':viewed,'viewing_scope':'11 target overviews, 10 source crops and 2 added source contexts viewed. Native target files acquired and hashed but not claimed fully inspected at native scale.',
      'coordinate_definition':'Approximate [x,y,width,height] native-canvas reading boxes, estimated from full-page overviews; not segmentation.',
      'records':rows}
    (HERE/'review_v1.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['剩余11关系的目标图像检查','',
      '11关系、10来源对象全部保留：6关系可作局部形态比较，5关系有限或含混。仍无任何植物身份或名称认证。',
      '已看11张目标全页概览、10张来源对象裁图、2张新增来源上下文；目标原尺寸文件已下载校验，但未声称逐原生像素检查。',
      '#150的两个目标共用同一个来源对象；#40目标页两株保留，未选定其一。',
      '#188候选与#40附着歧义维持原记录，另外9条关系未见独立归属标签。没有新增词形评分或修改旧主集。','']
    for x in rows:
        lines += [x['pair_id']+' | '+x['comparison_decision'],
                  '相似：'+x['visible_similarities'][0], '差异/限制：'+x['visible_differences_and_missing_parts'][0],x['label_scope_zh'],'']
    (HERE/'review_v1.txt').write_text('\n'.join(lines)+'\n')
    files=['protocol_v1.txt','queue_v1.json','freeze_v1.json','acquisition_v1.json','additional_context_acquisition_v1.json','build_review.py','review_v1.json','review_v1.txt']
    receipt={'utc':datetime.now(timezone.utc).isoformat(),'status':'PASS_GEOMETRY_RECORD_INTEGRITY',
      'scope':'Hash, completeness and coordinate checks, not an independent image re-review.',
      'pair_count':11,'source_object_count':10,'target_object_regions':12,'viewed_files':viewed,
      'acquired_assets_verified':len(assets),'old_inputs_unchanged':True,'new_lexical_scoring':False,
      'files':{f:sha(HERE/f) for f in files}}
    (HERE/'verification_receipt_v1.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(payload['summary']))

if __name__=='__main__':main()
