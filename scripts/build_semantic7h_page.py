"""Build a static semantic-research window snapshot, never a job monitor.

Run again after session.json and approved records change. Optional research
publication.json may provide reviewed public `findings` (list of strings) and
`modules` overrides keyed images/literature/leaf_controls/abbreviations/crossplant/known_herbal/boundary_bridge, with
status/title/summary/details/links/metrics/table. This builder deliberately does
not discover result files or infer that a computation or audit has passed.
Status values: planned, running, awaiting_review, partial, complete, blocked.
links: [{label,href}]; metrics: [{value,label}];
table: {headers:[...],rows:[[...],...]}. All values are plain text.
Only links to existing local site files or https URLs are published.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import gzip
import json

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT/'research/research_next/semantic7h_20261118'
SITE = ROOT/'site'
seen = []

def read(name, default=None):
    p = SOURCE/name
    if not p.exists(): return default
    raw = p.read_bytes()
    seen.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest()})
    return json.loads(raw) if p.suffix == '.json' else raw.decode()

def approved_link(item):
    href = item['href']
    if href.startswith('https://'):
        return item
    path = Path(href.split('#')[0].split('?')[0])
    if path.is_absolute() or '..' in path.parts or ':' in href: return None
    return item if (SITE/path).is_file() else None

session = read('session.json')
plan = read('plan.txt')
queue = read('visual/queue_v1.json', {})
geometry = read('visual/geometry_review_v1.json', {})
pairs = read('literature/plant_pairs.json', {})
support = read('design/leaf_controls/support_v1.json', {})
cross_visual = read('visual/crossplant/crossplant_visual_review_v1.json', {})
cross_receipt = read('visual/crossplant/verification_receipt.json', {})
publication = read('publication.json', {})
choice_result = read('visual/choice_controls/result_v1.json', {})
choice_audit = read('visual/choice_controls/audit_v1.json', {})
boundary_projection = read('design/boundary_bridge/publication_projection_v1.json', {})
boundary_audit = read('design/boundary_bridge/audit_v1.json', {})
boundary_visual = read('visual/boundary_hits/review.json', {})
boundary_visual_receipt = read('visual/boundary_hits/receipt.json', {})
order_visual = read('visual/order_targets/review_v1.json', {})
order_receipt = read('visual/order_targets/verification_receipt_v1.json', {})
remaining_visual = read('visual/remaining_targets/review_v1.json', {})
remaining_receipt = read('visual/remaining_targets/verification_receipt_v1.json', {})
snapshot = datetime.now(timezone.utc)
start = datetime.fromisoformat(session['start_utc'].replace('Z','+00:00'))
elapsed = max(0, int((snapshot-start).total_seconds()))
stage_titles = {
    1:'原图对象与证据设计',
    2:'整叶对照与固定变换',
    3:'跨页对象约束与候选读法',
    4:'独立复核、发布与窗口结题',
}
modules = {
    'herbal_context':{'title':'英文命中语境','status':'awaiting_review','details':[],'links':[],'metrics':[]},
    'herbal_space':{'title':'英文两词校准','status':'awaiting_review','details':[],'links':[],'metrics':[]},
    'remaining_targets':{'title':'剩余图像关系','status':'awaiting_review','details':[],'links':[],'metrics':[]},
    'space_bridge':{'title':'两词拼接','status':'awaiting_review','details':[],'links':[],'metrics':[]},
    'choice_controls':{
        'title':'三候选几何对照：原假说是否更可比？',
        'status':'awaiting_review','summary':'评分与编号映射须通过复核后展示。',
        'details':[],'metrics':[],'links':[],
    },
    'images': {
        'title':'十二个位置：文字属于哪个对象？',
        'status':'partial',
        'summary':'已保存不依据候选转写的几何观察；带转写引导的十二位置归属复核尚待完成。',
        'details':[
            '从上一轮既定队列保留六个双版命中与六个双版未命中位置；这是依结果选出的队列，不是确认样本。',
            '几何观察只记录图形、文字和空间邻接，不提供读法、对象身份或植物物种。图像中可见文字，不称完全盲审。',
            '后续需要将两个观察口径对照，并明确每个位置的对象归属、歧义和无法定位情形。AI 多次评审不是多位领域专家。',
        ],
        'metrics':[
            {'value':str(len(queue.get('selected',[]))),'label':'预定标签位置'},
            {'value':str(len(geometry.get('images',[]))),'label':'已记录几何观察的整页图'},
        ],
        'links':[{'label':f"耶鲁官方原图 · {r['folio']}",'href':r['source_url']} for r in queue.get('images',[])],
    },
    'literature':{
        'title':'跨页植物图：先核出处，再核标签',
        'status':'partial',
        'summary':'文献中的跨页图像候选已经整理；这些外部配对假说尚不是本轮认证的同一对象。',
        'details':[
            '来源的“看似同一植物”“有些相似”“转述 Petersen”“尚待核查”分开保留，不合并成一个可信度等级。',
            '尚需逐对检查对象坐标、图旁标签是否存在、标签范围及两版读法，才能决定哪些可参与比较。',
            '不把植物插图相似直接换成物种名称；没有可靠标签的配对不进入词义验证。',
        ],
        'metrics':[{'value':str(len(pairs.get('records',[]))),'label':'文献候选图像配对'}],
        'links':[{'label':'Zandbergen：相关植物图研究','href':'https://www.voynich.nu/q15/index.html'}],
    },
    'leaf_controls':{
        'title':'保留真实词频与整叶结构的对照',
        'status':'awaiting_review',
        'summary':'共同支持和协议已记录；整叶重新配对正在计算与复核，启动快照不公布未审核分数。',
        'details':[
            '按同书手、同插图类别的物理叶分块，保留实际词形、长度机会及整叶关联。',
            '只有各叶共同支持的长度参与重新配对。折页分面不冒充独立叶；可交换性仍须明确讨论。',
            '精确匹配与六种高杆变换使用同样的对照预算。复核完成后再说明结果及尾部概率可解释的范围。',
        ],
        'metrics':[],
        'links':[],
    },
    'abbreviations':{
        'title':'变长缩略：先固定规则，再看命中',
        'status':'planned',
        'summary':'一手来源与适用边界正在核对；固定变长缩略实验尚未运行。',
        'details':[
            '与等长 k/t 配对分开：有文献依据的缩略可能改变单位数，不能沿用等长词框的结论。',
            '先登记可展开的位置、组合字形例外、恢复原写法的方式与同预算替代对照。',
            '不按目标词临时加字；只公布完整规则对全部预定目标的结果，保留失败。',
        ],
        'metrics':[],
        'links':[],
    },
    'crossplant':{
        'title':'跨页图像假说：从标签到指定正文',
        'status':'awaiting_review',
        'summary':'预定图像配对的几何记录已保存；完整词形实验正在独立复核，本快照尚不填入数值结论。',
        'details':[
            '12 对均保留于下方图廊，6 对适合局部形态比较，6 对证据有限或含混。局部形似不是同一历史植物的认证。',
            '#110 是两个文本位置、三个词的完整组，未进入单词标签的主分析；图廊仍保留该对象。',
            '几何评审接触了作者假说、编号表与标签支持，但没有读取跨页词形分数；不是完全不看文字的盲审。',
        ],
        'metrics':[],
        'links':[],
    },
    'known_herbal':{
        'title':'已知英文草药书：匹配测量的校准',
        'status':'awaiting_review',
        'summary':'校准数据须通过独立复核后再展示；不能据此推断伏尼契语言或成功率。',
        'details':[], 'metrics':[], 'links':[],
    },
    'boundary_bridge':{
        'title':'固定短边界：统一规则能否跨来源复现？',
        'status':'awaiting_review',
        'summary':'完整结果须经独立复核后展示；无效标签与缺少机会不当作观察到的语义缺席。',
        'details':[], 'metrics':[], 'links':[],
    },
}
for version, vv in support.get('versions', {}).items():
    primary = vv.get('main_HI1', {})
    if primary:
        modules['leaf_controls']['metrics'].append({'value':str(primary['eligible_leaves']),'label':f'{version} 设计中可比物理叶'})

allowed = {'title','status','summary','details','links','metrics','table'}
states = {'planned','running','awaiting_review','partial','complete','blocked'}
for key, value in publication.get('modules', {}).items():
    assert key in modules, 'Unknown publication module'
    assert set(value)<=allowed, 'Unknown publication field'
    modules[key].update(value)
for item in modules.values():
    assert item['status'] in states
    item['links'] = [link for r in item.get('links',[]) if (link:=approved_link(r))]

download_names = [
    ('窗口起止与阶段记录','session.json'),('本轮研究计划','plan.txt'),
    ('当前阶段解释与下一步门槛','stage-assessment.txt'),
    ('原图几何观察','geometry-review.txt'),('外部植物配对候选','plant-pairs.json'),
    ('整叶对照协议','leaf-controls-protocol.txt'),('共同支持盘点','support.json'),
]
downloads = [link for label,name in download_names
             if (link:=approved_link({'label':label,'href':f'downloads/semantic7h/{name}'}))]
downloads += [link for r in publication.get('downloads',[]) if (link:=approved_link(r))]

# Display translations summarize the frozen English observations. Original
# statements remain available in the downloaded visual record; no new species
# or identity judgments are introduced by the page presentation.
visual_notes = {
    61: ('两边都有末端伸出细指状分叉的绿色圆叶形，并由细茎连到分枝。', '小图叶形少、根较粗；大图叶形更多，细根和上方淡色端部在小图中没有对应。'),
    80: ('两个向下延伸的根状带交叉成窄环，再分成尖端。', '小片段短而圆，大图根更粗长、红褐色更重；花和特殊叶缘没有对应。交叉尖根形态并不独特。'),
    94: ('两边都有基部带凹口的三角叶形、小红色末端簇和粗褐根。', '小图横向且叶少，根有斜向色带；大图竖向、长枝下垂、叶多，根较紧凑。红簇排列也不同。'),
    95: ('红色长主轴两侧长出许多细小钩状或尖状分枝。', '小片段短而近竖直，大图下轴长且弯曲；宽绿色／蓝色叶扇和上部端形在小图中缺失。'),
    110: ('两边都有粗横根段、向下弯的尖分枝和向上连接部。', '小图是少分枝的弯钩，大图根系向两边展开；圆盘叶列和上部结构没有对应，不能确定小钩对应大图哪一段。'),
    116: ('都有由短柄连接的绿色三角或箭头形叶。', '小图主茎形成明显环圈，大图中央直立并有两根长下垂枝；大图红簇与根系在小图中缺失。'),
    133: ('绿色叶单元呈圆形或月牙形、相互重叠，部分向连接处内卷。', '小图卷叶沿细柄分开，大图是密集层叠的月牙簇，伴有黄褐色块和蓝色端部；根形与比例也不同。'),
    136: ('窄长绿色小叶沿数条侧枝重复排列，枝叶喷散形比根部更可比。', '小图紧凑且根细淡，大图高大、根呈扇形，并有三个大淡色端部；叶距、分枝数和比例不同。'),
    212: ('横向褐色长体带重复的上下突起，一端有直立的交织状颈部，下方有长回弯。', '小图较小且受折痕／损伤影响，突起数与比例不同；大图的大量绿叶和大型端部完全缺失。'),
    213: ('长横筒带重复圆形／椭圆结节轮廓和向下细枝。', '小图墨色淡、横过折痕，结节细节受限；大图还有两根高叶茎和蓝色端部，结节也更大更规则。'),
    225: ('绿色叶轮廓深凹，中心周围有圆形次级叶瓣。', '小图只有一片小卷叶，大图有许多更大、更深裂的多臂叶；花、长茎、根系均无对应，局部还有变暗损伤。'),
    240: ('粗黄褐色根颈分出弯根，并有弓形绿色叶和长垂指状／梳状裂片。', '小图只有右上一片垂叶，大图下方有两大片，还多出高中央茎、小叶、侧簇和蓝色顶端；根的交叉细节不同。'),
}
gallery=[]
if cross_visual:
    visual_path=SOURCE/'visual/crossplant/crossplant_visual_review_v1.json'
    assert hashlib.sha256(visual_path.read_bytes()).hexdigest()==cross_receipt['files']['crossplant_visual_review_v1.json']
    assert cross_receipt['boxes_within_bounds']==24
    for row in cross_visual['records']:
        item={k:row[k] for k in ['pair_id','fragment_id','source_folio','target_folio','candidate_locators','comparison_decision']}
        item.update(batch='numbered',prior_grade=row['prior_hypothesis']['grade'],prior_source=row['prior_hypothesis']['source_url'],
                    similarity_zh=visual_notes[row['fragment_id']][0],difference_zh=visual_notes[row['fragment_id']][1],
                    original_similarities=row['visible_similarities'],original_differences=row['visible_differences_and_missing_evidence'],
                    lexical_scope='multiword_group_not_in_main' if row['fragment_id']==110 else 'singleword_candidate',
                    canvas_note=row.get('canvas_conflict'))
        for side in ['source','target']:
            original=row[side]
            oid=original['oid'];box=original['object_region_xywh'];width,height=original['full_image_size']
            x,y,w,h=box
            assert 0<=x<x+w<=width and 0<=y<y+h<=height
            base=f'https://collections.library.yale.edu/iiif/2/{oid}'
            assert original['source_url']==base+'/full/full/0/default.jpg'
            region=','.join(str(v) for v in box)
            item[side]={k:original[k] for k in ['oid','manifest_label','source_url','full_image_sha256','object_region_xywh']}
            display_width=min(700,w)
            item[side].update(crop_url=base+'/'+region+'/'+str(display_width)+',/0/default.jpg',native_crop_url=base+'/'+region+'/full/0/default.jpg')
        gallery.append(item)

if gallery:
    cross_root=SOURCE/'design/crossplant'
    complete=read('design/crossplant/run_v2/complete.json')
    audit=read('design/crossplant/audit_v1.json')
    assert audit['status']=='PASS' and audit['failure_count']==0
    assert hashlib.sha256((cross_root/'run_v2/complete.json').read_bytes()).hexdigest()==audit['complete_sha256']
    for version in ['ZL','IT']:
        name=f'{version}__strict_space__page_HI.json.gz'
        raw=(cross_root/'run_v2'/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==complete['files'][name]
        seen.append({'path':'design/crossplant/run_v2/'+name,'sha256':complete['files'][name]})
        scores=json.loads(gzip.decompress(raw))
        assert scores['boundary']=='strict_space' and scores['control']=='page_HI'
        for candidate in scores['candidates']:
            row=next(r for r in gallery if r['pair_id']==candidate['pair_id'])
            result=candidate['models']['exact']['target']
            row.setdefault('exact_check',{})[version]={k:result[k] for k in ['opportunities','matches','rate','query_length']}

if order_visual:
    order_root=SOURCE/'visual/order_targets'
    assert order_receipt['status']=='PASS_GEOMETRY_RECORD_INTEGRITY'
    assert order_receipt['pair_count']==12 and order_receipt['target_object_regions']==14
    assert hashlib.sha256((order_root/'review_v1.json').read_bytes()).hexdigest()==order_receipt['files']['review_v1.json']
    def image_region(original,box,source=False,description=None):
        full_url=original['official_image_url'];oid=full_url.split('/')[5]
        x,y,w,h=box; width,height=original['full_size']
        assert 0<=x<x+w<=width and 0<=y<y+h<=height
        base=f'https://collections.library.yale.edu/iiif/2/{oid}'
        assert full_url==base+'/full/full/0/default.jpg'
        region=','.join(map(str,box))
        label=original.get('manifest_label',{})
        label=' / '.join(v for values in label.values() for v in values) if isinstance(label,dict) else label
        return {'oid':oid,'manifest_label':label or '见完整画布','source_url':full_url,'full_image_sha256':original['full_sha256'],
                'object_region_xywh':box,'crop_url':f'{base}/{region}/{min(700,w)},/0/default.jpg',
                'native_crop_url':f'{base}/{region}/full/0/default.jpg','description':description}
    for row in sorted(order_visual['records'],key=lambda r:r['fragment_id']):
        item={k:row[k] for k in ['pair_id','fragment_id','source_folio','target_folio','comparison_decision']}
        item.update(batch='order',candidate_locators=[],prior_grade=row['prior_hypothesis']['source_grade'],
                    prior_source=row['prior_hypothesis']['source_url'],
                    similarity_zh=' '.join(row['visible_similarities']),difference_zh=' '.join(row['visible_differences_and_missing_parts']),
                    original_similarities=row['visible_similarities'],original_differences=row['visible_differences_and_missing_parts'],
                    lexical_scope='order_candidate_not_scored',attachment_status=row['source']['attachment_status_inherited'],
                    comparison_scope=row['comparison_scope'],target_unique=row['target_correspondence_unique'],
                    notes=row['notes'],canvas_note=None)
        item['source']=image_region(row['source'],row['source']['object_reading_bbox_xywh'],True)
        item['target']=image_region(row['target'],row['target']['object_reading_bbox_xywh'])
        item['target_regions']=[image_region(row['target'],r['bbox_xywh'],description=r['description']) for r in row['target']['visible_object_regions']]
        gallery.append(item)

if remaining_visual:
    remaining_root=SOURCE/'visual/remaining_targets'
    assert remaining_receipt['status']=='PASS_GEOMETRY_RECORD_INTEGRITY'
    assert remaining_receipt['pair_count']==11 and remaining_receipt['source_object_count']==10
    assert remaining_receipt['target_object_regions']==12
    assert hashlib.sha256((remaining_root/'review_v1.json').read_bytes()).hexdigest()==remaining_receipt['files']['review_v1.json']
    assert remaining_visual['summary']['new_lexical_scoring']==0 and remaining_visual['summary']['semantic_gold']==0
    contexts=read('visual/remaining_targets/additional_context_acquisition_v1.json')
    for row in sorted(remaining_visual['records'],key=lambda r:(r['fragment_id'],r['pair_id'])):
        item={k:row[k] for k in ['pair_id','fragment_id','source_folio','target_folio','comparison_decision']}
        item.update(batch='remaining',candidate_locators=[],prior_grade=row['prior_hypothesis']['source_grade'],
                    prior_source=row['prior_hypothesis']['source_url'],
                    similarity_zh=' '.join(row['visible_similarities']),difference_zh=' '.join(row['visible_differences_and_missing_parts']),
                    original_similarities=row['visible_similarities'],original_differences=row['visible_differences_and_missing_parts'],
                    lexical_scope='remaining_candidate_not_scored',attachment_status=row['source']['attachment_status_inherited'],
                    comparison_scope=row['comparison_scope'],target_unique=row['target_correspondence_unique'],
                    notes=row['notes'],canvas_note=None,label_scope_zh=row['label_scope_zh'],source_caption_zh=row['label_scope_zh'])
        item['source']=image_region(row['source'],row['source']['object_reading_bbox_xywh'],True)
        item['target']=image_region(row['target'],row['target']['object_reading_bbox_xywh'])
        item['target_regions']=[image_region(row['target'],r['bbox_xywh'],description=r['description']) for r in row['target']['visible_object_regions']]
        item['source_context_links']=[]
        for c in contexts['files']:
            if (row['fragment_id']==155 and '155' in c['file']) or (row['fragment_id'] in [205,206] and '205_206' in c['file']):
                assert c['url'].startswith('https://collections.library.yale.edu/iiif/2/')
                item['source_context_links'].append({'label':'补充来源上下文（保留邻物，不作新对象归属）','href':c['url']})
        gallery.append(item)

boundary={}
if boundary_projection:
    assert boundary_audit['status']=='PASS' and boundary_audit['failure_count']==0
    assert boundary_projection['independent_audit']['receipt_sha256']==hashlib.sha256((SOURCE/'design/boundary_bridge/audit_v1.json').read_bytes()).hexdigest()
    rules=[]
    for r in boundary_projection['rule_table']:
        rules.append({k:r[k] for k in ['version','rule','candidates','valid_labels','invalid_labels','target_hit_candidates','source_leaves_hit','target_leaves_hit','target_rate','control_rate','delta']} |
                     {'conditional_delta':r['conditional']['value'],'conditional_candidates':r['conditional']['candidates']})
    loo={}
    for version,record in boundary_projection['loo'].items():
        folds=[]
        for f in record['folds']:
            folds.append(dict(held_source_leaf=f['held_source_leaf'],selected_rule=f['selected_rule'],
                              train_delta=f['train']['source_leaf']['delta']['value'],
                              test_delta=f['test']['source_leaf']['delta']['value'],
                              baseline_delta=f['baseline_test']['source_leaf']['delta']['value'],
                              gain_vs_baseline=f['gain_vs_baseline'],purged_pair_ids=f['purged_pair_ids'],
                              train_candidates=f['train']['candidate_count'],test_candidates=f['test']['candidate_count']))
        loo[version]={'test_delta':record['test_delta'],'baseline_delta':record['baseline_delta'],
                      'gain_vs_baseline':boundary_audit['version_summaries'][version]['cv']['change'],'folds':folds}
    hits=[]
    for h in boundary_projection['target_hits']:
        hits.append({k:h[k] for k in ['version','rule','fragment_id','pair_id','label','core','target_folio','target_opportunities','positions']})
    boundary={'rules':rules,'loo':loo,'hits':hits,
              'image_traces':boundary_projection['image_traces']['records'],
              'scope':'Post-result exploration on exposed materials. Leave-one-source-leaf selection is an internal diagnostic, not blind confirmation.',
              'visual_review_status':'Four-word close image review pending; existing traces establish only approximate text-region localization.'}
    if boundary_visual:
        visual_root=SOURCE/'visual/boundary_hits'
        receipts={r['path']:r for r in boundary_visual_receipt['files']}
        assert hashlib.sha256((visual_root/'review.json').read_bytes()).hexdigest()==receipts['review.json']['sha256']
        assert boundary_visual['word_locations_reviewed']==4 and boundary_visual['target_lines_reviewed']==2
        crops=[]
        for filename in ['crop_receipt_v1.json','crop_receipt_v2.json']:
            assert hashlib.sha256((visual_root/filename).read_bytes()).hexdigest()==receipts[filename]['sha256']
            for crop in read('visual/boundary_hits/'+filename):
                assert crop['sha256']==receipts[crop['file']]['sha256']
                assert crop['url'].startswith('https://collections.library.yale.edu/iiif/2/')
                crops.append(crop)
        assert len(crops)==12
        boundary['visual']={'overall_zh':boundary_visual['overall_zh'],'items':boundary_visual['items'],'crops':crops}
        boundary['visual_review_status']='Four word locations and two target lines localized; a/o glyph and y/ol boundary remain ambiguous. Outcome-guided, not blinded; no transcription changes.'
choice={}
if choice_result:
    assert choice_audit['pass_all'] and choice_audit['check_count']==425
    assert all(row['passed'] for row in choice_audit['checks'])
    assert hashlib.sha256((SOURCE/'visual/choice_controls/result_v1.json').read_bytes()).hexdigest()==choice_audit['audited_file_sha256']['result_v1.json']
    assert len(choice_result['questions'])==12
    for row in choice_result['questions']:
        for picture in [row['source']]+row['candidates']:
            assert picture['crop_url'].startswith('https://collections.library.yale.edu/iiif/2/')
            assert picture['url'].startswith('https://collections.library.yale.edu/iiif/2/')
            x,y,w,h=picture['box'];width,height=picture['size']
            assert 0<=x<x+w<=width and 0<=y<y+h<=height
            assert int(picture['crop_url'].split('/')[-3].rstrip(','))<=w
        for candidate in row['candidates']:
            assert candidate['observation']['score'] in [0,1,2,3,None]
    choice={'questions':choice_result['questions'],'counts':choice_audit['counts'],'scope':choice_result['scope'],
            'review_frozen_utc':choice_result['review_frozen_utc'],'unblinded_utc':choice_result['unblinded_utc'],
            'audit_scope':choice_audit['scope'],'audit_checks':choice_audit['check_count']}
payload = {
    'schema_version':1,
    'snapshot_utc':snapshot.isoformat(),
    'snapshot_elapsed_seconds':elapsed,
    'window':{k:session[k] for k in ['start_utc','deadline_utc','duration_hours','local_timezone','local_window','status','stage']},
    'window_history':session.get('status_history',[]),
    'continuity_note_zh':session.get('continuity_note_zh',''),
    'stages':[{'stage':s['stage'],'title':stage_titles.get(s['stage'],s['title']),'status':s['status']} for s in session['stages']],
    'modules':modules,
    'findings':publication.get('findings',[
        '当前进展是把对象归属、外部图像假说和统计对照拆成可逐项复核的证据；尚未产生可靠译文。',
        '几何邻接不等于对象名称；文献配对不等于本轮确认；计算完成也不等于通过复核。',
    ]),
    'plan':plan,
    'downloads':downloads,
    'sources':seen,
    'gallery':gallery,
    'boundary':boundary,
    'choice':choice,
    'gallery_scope':'Three separately labeled batches, fragment number order within each, not ranked by lexical scores. Numbered:12 pairs/11 scored; order:12 unscored; remaining:11 unscored relationships/10 source objects. Only selected pair images load, two normally and three for unresolved two-target pages. No botanical gold or author overview images.',
    'scope':'Static saved evidence snapshot. No live monitoring, countdown, implied completion percentage, or semantic decoding claim.',
}
text = json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
assert '/Users/' not in text
(SITE/'data/semantic7h.json').write_text(text)
print('site/data/semantic7h.json:',len(text.encode()),'bytes; snapshot',payload['snapshot_utc'])
