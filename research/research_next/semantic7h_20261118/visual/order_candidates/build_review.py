"""Serialize guided visual observations, never compare herbal body strings."""
from pathlib import Path
from collections import Counter
import datetime,hashlib,json

HERE=Path(__file__).resolve().parent

# These are human-readable visual observations from the official images.
# Coordinates are approximate native-canvas xywh reading regions, not segmentation.
OBSERVATIONS=[
 dict(pair_id='f88r_8__f15v',asset='f88r_8',row=2,ordinal=3,status='clear',
      label_bbox=[1315,1230,280,130],object_bbox=[1170,1220,675,590],
      relative='候选字串位于第二行第三个片段的上左侧、两条弯曲叶柄之间的空白。该片段有截面状根冠、下垂根束及左右两片绿色叶形。左邻片段另有dary标签，右邻另有sorory标签。',
      caveat='根束和邻近图形在局部接近；判断依完整行序和根冠/叶柄连续关系，不由形似某物种作出。'),
 dict(pair_id='f88r_11__f90r2',asset='f88r_11',row=3,ordinal=2,status='clear',
      label_bbox=[1960,2195,270,135],object_bbox=[1450,2160,1100,1120],
      relative='第三行右侧片段有多个圆裂绿叶和向右、向下延展的宽根。候选字串在其上方枝根间空白、上方两片叶的右侧；左侧同一行的另一片段另有标签。',
      caveat='ZL保留otor,am不确定词界，IT保留otor.am两词；本核对不把它压成一个确定名称。'),
 dict(pair_id='f88v_22__f94v',asset='f88v_22',extra_asset='f88v_22_label_complete',row=3,ordinal=3,status='clear',
      label_bbox=[2590,2790,250,120],object_bbox=[1400,2150,1400,1500],
      relative='展开画布左面f88v的底行最右片段。候选文字在根冠右侧、f88v与f89r1接缝的左侧；根部向左下长距离展开。接缝右方已是下一面容器，不能将此词移到中面。',
      caveat='最初对象裁区未含标签最右端，另取官方完整标签裁区。靠缝处字迹不清；ZL dararda[?:]与IT dararda原样保留，不裁决尾部。'),
 dict(pair_id='f89r1_25__f57r',asset='f89r1_25_26',row=1,ordinal=3,status='clear',
      label_bbox=[4050,340,260,130],object_bbox=[3730,170,500,760],
      relative='展开画布中面顶部第三个片段，有较细分枝和小绿叶团、下方分叉根。otoldy在该片段右侧，位于右邻长弯根片段左端之上；右邻有独立长标签。',
      caveat='定位由顶部四个对象及四个Lf次序辅助；不独立认证字形读法或对应大植物身份。'),
 dict(pair_id='f89r1_26__f43v',asset='f89r1_25_26',row=1,ordinal=4,status='clear',
      label_bbox=[4460,360,410,150],object_bbox=[4080,150,1100,820],
      relative='中面顶部最右片段为横向长弯根/茎形，右上和右下有绿色叶形。ararchodaiin处在长曲线包围的内部空白，其左侧另见第三对象的短标签。',
      caveat='只核#26的源对象与字串位置；文献中的跨页关系带待核性质，本任务未提升该关系或识别物种。'),
 dict(pair_id='f89r1_28__f30r',asset='f89r1_28',row=2,ordinal=2,status='clear',
      label_bbox=[3860,1370,330,140],object_bbox=[3380,1260,650,620],
      relative='中面第二行三个对象中的中间片段，细茎自根冠向上伸出，根束向左下展开；otorain就在其根冠右上方。左边块状卷根和右边长回环根各有另一标签。',
      caveat='相邻根线局部接近，但三个根冠及各自字串行序可区分；无意义判读。'),
 dict(pair_id='f89r1_31__f33r',asset='f89r1_31',row=3,ordinal=2,status='ambiguous',
      label_bbox=[4150,3000,330,145],object_bbox=[3610,2560,570,1110],
      relative='中面底行中间片段为细茎与数条长红棕根。候选.26可明确定位在该根束右侧，但同时紧靠右邻#32垂下的绿色叶片下方。三对象/三标签的次序支持#31，单靠邻近几何却不能排除与#32局部的关系。',
      caveat='locator定位清楚，标签附着对象仍含混；无连接线、且邻叶覆盖候选上方。保留原候选，不另换一个有利词。ZL[s:r]ydarary与IT sydarary不裁决。'),
 dict(pair_id='f89r2_35__f35v',asset='f89r2_35',row=1,ordinal=3,status='clear',
      label_bbox=[7020,540,400,145],object_bbox=[6200,170,1400,830],
      relative='展开画布右面顶部第三个片段，有宽绿色冠状叶群和粗短横向根部。候选文字在其茎/根冠右侧、树冠下方空白；右边第四对象的字串更靠右。右面内部折线穿过附近，但不是f89r1/f89r2分面边界。',
      caveat='ZL saloiinsheol与IT saloiin.sheol的分词差异完整保留；视觉定位不解决一个词还是两个词。'),
 dict(pair_id='f89v2_50__f10v',asset='f89v2_50',row=1,ordinal=1,status='clear',
      label_bbox=[1100,920,250,150],object_bbox=[800,280,530,820],
      relative='f89v2顶部容器右侧的第一个片段，根冠向下分出多条弯根。okam位于其下右方、正文上方；左侧容器另有一串文字，右侧下一片段另有标签。',
      caveat='较淡底色/透印不作为新增字形；只定位候选字串与第一片段的相对位置。'),
 dict(pair_id='f89v2_52__f40v',asset='f89v2_52',extra_asset='f89v2_top_label_context',row=1,ordinal=3,status='clear',
      label_bbox=[2180,880,330,140],object_bbox=[2140,220,350,650],
      relative='顶部第三个片段由相邻的几处红棕根冠和细长根组成，作为来源编号中的一个片段计数。chokaro在其正下方；右侧细根片段和最右大根各有自己的标签。',
      caveat='只确认源#52位置；f40v有双植物这一目标歧义保持，不打开目标正文，也不决定对应哪株。'),
 dict(pair_id='f89v2_54__f48v',asset='f89v2_54',extra_asset='f89v2_top_label_context',row=1,ordinal=5,status='clear',
      label_bbox=[2810,840,330,150],object_bbox=[3070,310,860,1090],
      relative='顶部最右片段有两团裂叶和相连的上下根冠，根束向下延长。chokam在上部根束的左下边；拓宽的官方标签带同时显示前两标签，可区分它与左邻细根片段。',
      caveat='未独立验证其与f48v的图像相同关系；这里只提高源对象—标签定位的可信度。'),
 dict(pair_id='f89v2_56__f24r',asset='f89v2_56',row=2,ordinal=2,status='clear',
      label_bbox=[1920,1610,400,150],object_bbox=[1500,1300,1170,850],
      relative='第二行中间片段的根冠在折线附近，多条红棕根横向和回环延伸。候选文字位于根冠右上侧、右邻大绿叶左侧空白；左右对象均另有各自标签。',
      caveat='ZL dykaran与IT dydariin明显不同，仍记为同一原像位置的两种转写；不按将来命中结果选择读法。'),
]

CANVASES={
 'f88r':dict(image_id='1037112',width=2714,height=3735,panel='single f88r surface',panel_bbox=[0,0,2714,3735]),
 'f88v':dict(image_id='1006233',width=9078,height=3777,panel='left panel of 88v and 89r canvas',panel_bbox=[0,0,2850,3777]),
 'f89r1':dict(image_id='1006233',width=9078,height=3777,panel='middle panel of 88v and 89r canvas',panel_bbox=[2850,0,2380,3777]),
 'f89r2':dict(image_id='1006233',width=9078,height=3777,panel='right wide panel of 88v and 89r canvas; contains internal vertical fold',panel_bbox=[5230,0,3848,3777]),
 'f89v2':dict(image_id='1006234',width=4204,height=3809,panel='wide f89v2 surface; Yale label 89v (part)',panel_bbox=[0,0,4204,3809]),
}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    queue=json.loads((HERE/'queue.json').read_text())['records']
    assert [r['pair_id'] for r in queue]==[r['pair_id'] for r in OBSERVATIONS]
    assets={}
    for name in ['crop_receipt_v1.json','crop_receipt_v2.json']:
        for a in json.loads((HERE/name).read_text())['assets']:
            assert sha(HERE/a['path'])==a['sha256'];assets[a['name']]=a
    full={a['image_id']:a for a in json.loads((HERE/'acquisition_v1.json').read_text())['assets'] if a['size']=='full'}
    rows=json.loads((HERE/'q15_inventory.json').read_text())['rows_left_to_right']
    result=[]
    for prior,obs in zip(queue,OBSERVATIONS):
        folio=prior['pharma_folio'];canvas=CANVASES[folio]
        assert rows[folio][obs['row']-1][obs['ordinal']-1]==prior['fragment_id']
        names=[obs['asset']]+([obs['extra_asset']] if 'extra_asset' in obs else [])
        for name in names:assert assets[name]['image_id']==canvas['image_id']
        for key in ['label_bbox','object_bbox']:
            x,y,w,h=obs[key];assert 0<=x<x+w<=canvas['width'] and 0<=y<y+h<=canvas['height']
        result.append(dict(pair_id=prior['pair_id'],source_folio=folio,fragment_id=prior['fragment_id'],
            target_folio_identifier_only=prior['herbal_folio'],source_crossplant_grade_unchanged=prior['source_grade'],
            original_candidate_locators=prior['candidate_locators'],reviewed_label_locators=prior['candidate_locators'],
            original_label_records=prior['label_records'],status=obs['status'],
            locator_visual_status='clear',object_attachment_status=obs['status'],
            candidate_revision='none; original retained' if obs['status']=='clear' else 'none; object attachment remains ambiguous',
            confirmed_wrong_candidate=False,corrected_locator=None,
            q15_row=obs['row'],q15_ordinal_in_row=obs['ordinal'],q15_row_object_ids=rows[folio][obs['row']-1],
            image=dict(**canvas,source=full[canvas['image_id']],catalog_url='https://collections.library.yale.edu/catalog/2002046?child_oid='+canvas['image_id']),
            approximate_native_label_bbox_xywh=obs['label_bbox'],approximate_native_object_bbox_xywh=obs['object_bbox'],
            coordinates_scope='Approximate reading regions in native official canvas; not pixel-accurate segmentation. Panel boundaries also approximate.',
            official_crops=[assets[n] for n in names],relative_position=obs['relative'],uncertainty=obs['caveat'],
            transcription_adjudicated=False,species_identified=False,target_body_accessed=False,
            target_body_match_computed=False,crossplant_outcomes_read=False))
    review=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        review_type='Candidate-text-guided visual localization by one AI reviewer; not independent blind transcription or expert consensus.',
        protocol_sha256=sha(HERE/'protocol.txt'),queue_sha256=sha(HERE/'queue.json'),
        counts=dict(Counter(r['status'] for r in result)),all_twelve_retained=True,records=result,
        conclusions=['Eleven candidates have clear spatial/order localization at the source drawing; one attachment remains ambiguous.',
                     'No candidate was silently changed or removed. Clear means source localization only, not a plant name, phonetic reading, species or cross-page identity.',
                     'ZL/IT uncertainty, word boundaries and different readings remain intact. f40v target-plant choice remains unmade.'],
        access_scope=dict(source_surfaces=list(CANVASES),official_full_canvases=3,
            source_label_loci_only=True,herbal_target_body_not_read=True,future_crossplant_outcomes_not_read=True),
        sources=[dict(title='Yale University Library, Beinecke MS 408',url='https://collections.library.yale.edu/catalog/2002046'),
                 dict(title='Zandbergen q15 numbered layout inventory',url='https://www.voynich.nu/q15/index.html')],
        rights_note='Official Yale historical-manuscript image region bytes, unedited. Transcription licensing is not asserted as an image license.')
    p=HERE/'review.json';assert not p.exists();p.write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')
    text=['十二个次序推定标签：原图空间定位复核','',
          '结果：12条全部保留；11条源对象—候选文字定位清楚，1条对象附着仍含混。没有据后续词形得分换标签，也没有确认任何词义。',
          '本次看过候选转写引导定位，不是盲转写；clear只指源图空间/行序对应，不能升级为植物名、物种、跨页同植物或已知音值。',
          '5个转写面实际来自3个Yale画布：f88r为1037112；f88v/f89r1/f89r2是1006233左/中/右面；f89v2为1006234。所有框为原生画布近似阅读区。','']
    for r in result:
        text.extend([r['pair_id']+' | '+r['status']+' | '+','.join(r['original_candidate_locators']),
            '源对象：第'+str(r['q15_row'])+'行、第'+str(r['q15_ordinal_in_row'])+'个。',
            'ZL：'+' / '.join(x['raw'] for x in r['original_label_records']['ZL']),
            'IT：'+' / '.join(x['raw'] for x in r['original_label_records']['IT']),
            r['relative_position'],r['uncertainty'],
            '文字框 xywh：'+str(r['approximate_native_label_bbox_xywh']),
            '官方上下文图：'+r['official_crops'][0]['url'],''])
    text.extend(['主要未决',
        'f89r1 #31：.26字串位置可以指出，但它处于中间长根右侧、又紧贴右邻#32垂下的叶片下方；行序支持原候选，几何附着尚不唯一。保留ambiguous，不以“找到了词”代替对象认证。',
        'f88v #22的词尾靠接缝且不清；f88r #11、f89r2 #35的词界差异、f89r1 #31备选首字、f89v2 #56不同读法全保留。源#52对应f40v的具体哪株植物，本任务没有判定。','',
        '访问边界与来源',
        '只读取上述5个来源面的L类相邻标签，未提取目标大植物页正文，未读取未来crossplant评分。本任务结果不自动扩充任何词形实验；若使用这些新定位，须另行冻结范围和规则。',
        'q15编号/行序：https://www.voynich.nu/q15/index.html；通过网页工具核对。直接HTML归档请求返回406，因此不声称保存原HTML字节哈希。',
        'Yale馆藏页面在网页工具返回403，但公开IIIF图像请求成功；所有全图和裁片URL、实际字节SHA及时间见acquisition_v1.json和两份crop_receipt。',
        '全图在仓库外保存；公开assets仅官方IIIF裁片原字节，不含现代重绘。完整来源字符串、候选与不确定性见queue.json/source_labels.json/review.json。'])
    (HERE/'review.txt').write_text('\n'.join(text)+'\n')
    files=[p for p in sorted(HERE.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='receipt.json']
    receipt=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        records=12,status_counts=review['counts'],official_full_canvases=3,official_crop_files=len(assets),
        label_text_guided=True,herbal_body_match_computed=False,crossplant_outcomes_read=False,
        files=[dict(path=str(p.relative_to(HERE)),sha256=sha(p),bytes=p.stat().st_size) for p in files])
    (HERE/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:receipt[k] for k in ['records','status_counts','official_full_canvases','official_crop_files']},ensure_ascii=False))

if __name__=='__main__':main()
