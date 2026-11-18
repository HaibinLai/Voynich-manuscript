"""Build a static semantic-research window snapshot, never a job monitor.

Run again after session.json and approved records change. Optional research
publication.json may provide reviewed public `findings` (list of strings) and
`modules` overrides keyed images/literature/leaf_controls/abbreviations, with
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
publication = read('publication.json', {})
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
    ('原图几何观察','geometry-review.txt'),('外部植物配对候选','plant-pairs.json'),
    ('整叶对照协议','leaf-controls-protocol.txt'),('共同支持盘点','support.json'),
]
downloads = [link for label,name in download_names
             if (link:=approved_link({'label':label,'href':f'downloads/semantic7h/{name}'}))]
downloads += [link for r in publication.get('downloads',[]) if (link:=approved_link(r))]
payload = {
    'schema_version':1,
    'snapshot_utc':snapshot.isoformat(),
    'snapshot_elapsed_seconds':elapsed,
    'window':{k:session[k] for k in ['start_utc','deadline_utc','duration_hours','local_timezone','local_window','status','stage']},
    'stages':[{'stage':s['stage'],'title':stage_titles.get(s['stage'],s['title']),'status':s['status']} for s in session['stages']],
    'modules':modules,
    'findings':publication.get('findings',[
        '当前进展是把对象归属、外部图像假说和统计对照拆成可逐项复核的证据；尚未产生可靠译文。',
        '几何邻接不等于对象名称；文献配对不等于本轮确认；计算完成也不等于通过复核。',
    ]),
    'plan':plan,
    'downloads':downloads,
    'sources':seen,
    'scope':'Static saved evidence snapshot. No live monitoring, countdown, implied completion percentage, or semantic decoding claim.',
}
text = json.dumps(payload,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
assert '/Users/' not in text
(SITE/'data/semantic7h.json').write_text(text)
print('site/data/semantic7h.json:',len(text.encode()),'bytes; snapshot',payload['snapshot_utc'])
