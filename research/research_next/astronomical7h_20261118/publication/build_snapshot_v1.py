"""Explicit publication projection of reviewed observations and metadata."""
from pathlib import Path
import datetime as dt
import hashlib
import json

HERE=Path(__file__).resolve().parent
WINDOW=HERE.parent
ROOT=WINDOW.parents[2]
GH='https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'

def load(name):
    return json.loads((WINDOW/name).read_text())

def source(label,name):
    return {'label':label,'href':GH+name}

def row(id,title,status,details,**kw):
    return dict(id=id,title=title,status=status,details=details,**kw)

g=load('guided_layout/guided_layout_v1.json')
c=load('reconciliation_geometry_v2.json')
z=load('zodiac_inventory/inventory_v1.json')
zv=load('zodiac_visual/review_v1.json')
raw={}
for version,name in [('ZL','ZL3b-n.txt'),('IT','IT2a-n.txt')]:
    for line in (ROOT/'research/sources'/name).read_text().splitlines():
        if line.startswith('<f67r2.'):
            raw[(version,line.split(',',1)[0][1:])]=line
trans=[]
for t in g['targets']:
    trans.append(row(t['locator'],t['locator'],'unresolved',
        [t['visual_observation'],'已知转写引导定位；两版一致不等于独立释读。'],
        zl=t['raw_versions']['ZL'],it=t['raw_versions']['IT'],
        relation='圆脸内侧的工作邻接关系；尚未认证名称或正文功能。',
        uncertainty=t['ambiguity'],
        original_lines='\n'.join(v+': '+raw[(v,t['locator'])] for v in ['ZL','IT']),
        source_url=GH+'publication/guided-observation.json'))
zd=[]
for p in z['pages']:
    visual=next(v for v in zv['panels'] if v['folio']==p['folio'])
    zd.append(row(p['folio'],p['folio'],'partial',
        [f"两版均有 {p['catalogue_counts']['all']} 处记录：{p['catalogue_counts']['circular']} 处环文、{p['catalogue_counts']['zodiac_labels']} 处短标签。",
         '这是来源类型与目录一致的记录数量，不是独立图像计数。',
         visual['people_star_bands'],
         '已做粗角色观察及一处短串邻接示例；未观察到逐标签独立正文。全部短标签的逐项定位与完整序列仍未完成。'],
        folio=p['physical_leaf'],role='环文 / 短标签；并非同一语义角色',
        eligibility='粗角色可比；完整短标签序列未过门槛',source_url=p['official_canvas']['image_url']))
metadata={
 'window_status':'active',
 'status_note':'首轮圆图测量、固定校准来源及十二黄道图面粗角色观察已有结果；完整文本序列仍未过门槛，继续补查，七小时窗口保持进行中。',
 'findings':[
   '尚未确认任何词义、读音、语种或可靠译文。',
   '两路观察均定位十二个圆脸邻近文字区，可作工作空间对应；它们对分界线、中央分组和外圈覆盖仍有分歧。',
   '全部十二短串与两版原行保留。没有删去分词困难位置，也没有执行真实文本命中或循环评分。',
   '十二黄道图面各版完整提取335个位置，只涉及四个物理叶。全部图面已做粗角色观察，299个目录短标签尚未逐项定位认证。',
   '两部已知语言圆图原图可取得，但缺少独立短标签层及完整分区转写，当前可直接运行的该类校准基准为零。'],
 'stages':[{'stage':1,'title':'完整空间、文字角色与双版原文','status':'partial'},
           {'stage':2,'title':'已知语言校准与跨图角色','status':'running'},
           {'stage':3,'title':'资格通过后的固定预测','status':'awaiting_review'},
           {'stage':4,'title':'综合、限制与七小时终点验收','status':'planned'}],
 'sections':{
  'roles':{'status':'partial','summary':'角色分层已有完整工作清单，但数量相等不保证功能相同。两路观察的分组差异完整保留。','records':[
   row('face-adjacent','十二圆脸内侧文字区','partial',['两路各见十二个圆脸邻近文字区；以圆脸框辅助建立工作对应。','相邻不是名称认证，历史起点和读序尚未确定。']),
   row('sector','十二段扇区文本与分离短行','unresolved',['引导清单包含32条段落行和7条分离短行。图像观察列8个附加粗区，其中污迹附近一处暂定。','分离短行是否并入未来正文须另定政策；三处分界证据存在差异。']),
   row('central-ring','中央环文：八个来源记录 / 七个粗区','unresolved',['图像观察保留7至9个细分段的可能范围；西南粗区可包含两个引导组。','不强迫空间分组等于转写记录数。']),
   row('outer-red','外圈红字：十二个来源记录 / 十三个粗区','unresolved',['O06目前没有与引导阅读框相交，需要核查覆盖。','不能据此断言新发现一个词，也不能删除额外观察区。']),
   row('bottom','底部三行正文','partial',['作为单独版面角色保留，不并入扇区或短标签计数。'])],
   'sources':[source('完整协调记录','reconciliation_report_v1.txt')]},
  'transcriptions':{'status':'partial','summary':'两版各74处源记录完整保存。以下全部十二短串逐项并列；一致单词5处、一致两词组1处、字符差异3处、涉及分词差异3处。','records':trans,
   'sources':[source('双版完整原行清单','publication/transcription-inventory.json')]},
  'spatial':{'status':'unresolved','summary':'画面顺时针相邻关系可作工作对照，尚不认证历史读序或完整扇区边界。下方原图图层保留两路自己的分组。','records':[
   row('cycle','十二处工作空间次序','partial',['两套编号起点不同，换成同一几何对应后顺时针相邻关系相同。','六处文字矩形还有邻框小交集；采用圆脸辅助对应是观察后的几何诊断，不是识字成功率。'],sequence='f67r2.52 → … → f67r2.63 → f67r2.52（画面顺时针；非历史起点）'),
   row('boundaries','三处边界证据分歧','unresolved',['西南两条线：图像观察记弱或不完整，引导观察记连续。','西侧近水平线：一方认为可追踪但受折痕干扰，另一方未能可靠追踪。']),
   row('gate','完整十二项文本检验','not_eligible',['本阶段没有计算真实命中或循环分数。','未定关系记为待核，不能记成无命中零，也不能删掉难例后宣称通过。'])],
   'sources':[source('坐标对照v2与全部候选','reconciliation_geometry_v2.json'),source('协调方法与局限','reconciliation_protocol_v1.txt'),source('独立实现审计与覆盖缺口','publication/geometry-audit.txt')]},
  'calibration':{'status':'complete','summary':'固定两例的资料资格核验已完成，结论是目前不能直接作为短标签—正文基准。完成核验不等于获得可运行基准。','records':[
   row('trinity','Trinity O.7.20 f.1:33r','not_eligible',['原图可取得并已观察；有逐瓶说明、组级说明和中心题名。','未见预定意义下独立逐瓶短标签；完整分区转写和全量连接图复核尚缺。'],source_url='https://cudl.lib.cam.ac.uk/view/MS-TRINITY-COLLEGE-O-00007-00020/71'),
   row('rosenbach','Rosenbach MS1004/29 · 9C','not_eligible',['官方页面明确对应图像5964_0044；有逐瓶说明及一对多组连接。','未见独立逐瓶短标签；不能把说明首词切出来制造标签层。'],source_url='https://bibliophilly.library.upenn.edu/viewer.php?id=MS+1004%2F29')],
   'sources':[source('来源与资格报告','publication/calibration-report.txt')]},
  'zodiac':{'status':'partial','summary':'八幅画布、十二图面已全部做粗角色观察；双版各335个来源记录，36处环文、299处短标签，只涉及四个物理叶。每图一处邻接示例不代表299处全部认证。未见逐标签独立正文，共享环文不能直接分配给单个标签；完整序列仍未过门槛。','records':zd,
   'table':{'headers':['图面','物理叶','环文记录','短标签记录','合计'],
            'rows':[[p['folio'],p['physical_leaf'],p['catalogue_counts']['circular'],p['catalogue_counts']['zodiac_labels'],p['catalogue_counts']['all']] for p in z['pages']]},
   'sources':[source('完整元数据报告','zodiac_inventory/report_v1.txt'),source('335处双版原行与来源','zodiac_inventory/inventory_v1.json'),source('原行及官方映射检查','zodiac_inventory/validation_v1.json'),source('十二图面视觉观察与未完成项','publication/zodiac-visual-report.txt')]}
 }
}
(HERE/'snapshot_v1.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')

# Publication copies alter local path prefixes only. Frozen originals remain unchanged.
selected={
 'spatial_observer/observer_report_v1.json':'image-only-observation.json',
 'guided_layout/guided_layout_v1.json':'guided-observation.json',
 'guided_layout/transcription_inventory_v1.json':'transcription-inventory.json',
 'calibration/qualification_v1.json':'calibration-qualification.json',
 'calibration/资格核验_v1.txt':'calibration-report.txt',
 'calibration/access_records_v1.json':'calibration-access.json',
 'reconciliation_audit/audit_report_v1.txt':'geometry-audit.txt',
 'reconciliation_audit/audit_computation_v1.json':'geometry-audit-computation.json',
 'zodiac_visual/review_v1.json':'zodiac-visual-observation.json',
 'zodiac_visual/review_v1.txt':'zodiac-visual-report.txt',
 'zodiac_visual/manual_count_ledger_v1.json':'zodiac-count-ledger.json',
}
receipt=[]
for src,dst in selected.items():
    path=WINDOW/src
    original=path.read_text()
    # JSON ensure_ascii escaping applies to CJK in some frozen paths.
    def clean(value):
        if isinstance(value,dict): return {k:clean(v) for k,v in value.items()}
        if isinstance(value,list): return [clean(v) for v in value]
        if isinstance(value,str): return value.replace(str(ROOT)+'/', '').replace(str(ROOT.parent)+'/output/', 'private-output/')
        return value
    if path.suffix=='.json':
        content=json.dumps(clean(json.loads(original)),ensure_ascii=False,indent=2)+'\n'
    else: content=clean(original)
    assert '/Users/' not in content and '/home/' not in content,dst
    (HERE/dst).write_text(content)
    receipt.append({'input':src,'input_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                    'output':dst,'output_sha256':hashlib.sha256(content.encode()).hexdigest(),
                    'transform':'Replace local path prefixes with repository-relative or private-output references; JSON reserialized. No scientific fields changed.'})
(HERE/'projection_receipt_v1.json').write_text(json.dumps({'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'files':receipt},ensure_ascii=False,indent=2)+'\n')
print('Snapshot and',len(selected),'explicit publication copies saved; no semantic scores.')
