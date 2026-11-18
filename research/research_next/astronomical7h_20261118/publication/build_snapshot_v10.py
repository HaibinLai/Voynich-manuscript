"""Publish full12 object inventory and explicit sequence insufficiency, retaining old evidence."""
from pathlib import Path
import json,hashlib,subprocess
HERE=Path(__file__).resolve().parent;W=HERE.parent;ROOT=W.parents[2];P=W/'zodiac_object_relations'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 approval=read(P/'publication_approval_v1.json');assert approval['release_approved']
 subprocess.run(['python3','-B','scripts/build_zodiac_relations_page.py','--release-approval',str((P/'publication_approval_v1.json').relative_to(ROOT))],cwd=ROOT,check=True)
 subprocess.run(['python3','-B','scripts/build_central_annotations_page_v3.py'],cwd=ROOT,check=True)
 prev=read(HERE/'snapshot_v9.json');m=read(HERE/'snapshot_v9.json')
 m['status_note']='全12幅黄道图的固定对象关系名册已完成并独立复算，322个文字/疑似文字区与606个原图形部件全部保留。9个单一布局候选均属于普通字母样中央注记位置；完整同角色目标文字序列证据仍不足，未运行外围文字预测。f67r2三表与已知拉丁文风图目录条件C结果继续保留，原图认证I仍NOT_READY。本七小时窗口仍进行中。'
 m['findings'] += ['全12图关系记录完整：322文字或疑似文字区域、606原部件、358细分备选；追加40部件复核和5别名另列。797查看记录含773原生细节和24导航，跨8画布4物理叶，不是797个独立样本。','9个单一布局候选全部落在源知情定位的中央普通字母样注记集合；没有外围短串。目标粒度不同，这不是9次语义成功，也不证明集合外没有历史指代。','文字—对象候选边有6处部分接触、没有确认的明确文字引线；人物连星线不自动属于文字。没有引线本身也不否定文字可能指代对象。','完整跨图预测尚不具备条件：具体缺口是文字分组、竞争对象、连续环文混入及开放弧/跨带过渡。粗几何环序与中央注记空间角色的正面支持保留；词义未知及历史起点未知本身不是失败理由。','独立汇编核查196532次字段/容器比较无差异；事后ID关联113项无差异。二者均是记录与实现核验，不是盲专家认证或破译置信度。']
 m['stages'][1]={'stage':2,'title':'校准与全12图核查已记录；完整序列资格不足','status':'partial'}
 m['stages'][2]={'stage':3,'title':'固定预测：当前测量证据不足，未运行','status':'not_eligible'}
 z=m['sections']['zodiac'];z['summary']='全12幅图的固定文字/图形关系名册已完成，原区域、细分、部件、NA和竞争对象均保留，独立汇编复算一致。9个单一布局候选全是普通字母样中央注记候选。粗空间层仍可比较，但尚无至少两图完整同角色目标文字序列，未启动外围文字预测。下方335处表是原转写来源位置名册；322处是图像侧固定区域名册，两者口径不同，不是删掉13个难例。'
 z['sources'].append({'label':'本窗口公开证据覆盖核查与路径投影限制','href':'downloads/astronomical7h/public-evidence-coverage-review.txt'})
 z['sources'][:0]=[{'label':'全12图：原图、文字框与竞争对象交互查看','href':'zodiac-relations.html'},{'label':'全12图结果、计数口径与限制','href':'downloads/zodiac-relations/report.txt'},{'label':'逐图完整序列资格：具体证据与正面支持','href':'downloads/zodiac-relations/sequence-qualification.txt'},{'label':'独立汇编复算报告','href':'downloads/zodiac-relations/independent-audit.txt'},{'label':'公开源文件与哈希清单','href':'downloads/zodiac-relations/public-manifest.json'}]
 agg=read(P/'aggregation_v1.json');q=read(P/'sequence_qualification/qualification_ledger_v1.json')
 panels={x['panel']:x for x in agg['panels']};quals={x['panel']:x for x in q['panels']}
 for row in z['records']:
  p=panels[row['id']];r=p['full_frozen_report'];row['details'].append(f"本图全部{len(r['text_records'])}个固定文字/疑似文字区的对象关系记录已完成；原种子ID与NA保留，报告交付完整不等于完整序列资格通过。")
  row['details']+=['当前具体缺口：'+v for v in quals[row['id']]['Q1']['concrete_gaps_or_limits']]
  row['eligibility']='观察名册与复算完整；完整同角色目标文字序列证据不足。'
 for k in set(prev['sections'])-{'zodiac'}:assert m['sections'][k]==prev['sections'][k]
 (HERE/'snapshot_v10.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 argv=read(HERE/'build_command_v9.json')['argv'][:];argv[argv.index('--approved-metadata')+1]=str((HERE/'snapshot_v10.json').relative_to(ROOT))
 inherited=[]
 for i,v in enumerate(argv):
  if v=='--approved-download':
   _,n=argv[i+1].rsplit('=',1);p=ROOT/'site/downloads/astronomical7h'/n;inherited.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)});argv[i+1]=str(p.relative_to(ROOT))+'='+n
 for src,name in [('evidence_coverage_review/evidence_coverage_review_v1.txt','public-evidence-coverage-review.txt'),('evidence_coverage_review/new_projection_field_fidelity_receipt_v1.json','public-freeze-projection-fidelity.json')]:
  argv+=['--approved-download',str((HERE/src).relative_to(ROOT))+'='+name]
 (HERE/'build_command_v10.json').write_text(json.dumps({'argv':argv,'purpose':'Full12 fixed inventory and bounded scientific qualification; seven-hour goal remains active'},ensure_ascii=False,indent=2)+'\n')
 subprocess.run(argv,cwd=ROOT,check=True)
 assert all(sha(ROOT/x['path'])==x['sha256'] for x in inherited)
 receipt={'full12_approval_sha256':sha(P/'publication_approval_v1.json'),'public_manifest_sha256':sha(P/'public_manifest_v1.json'),'inherited_downloads_unchanged':inherited,'other_scientific_sections_unchanged':True,'whole_window_complete':False,'no_semantic_prediction_performed':True}
 (HERE/'snapshot_v10_build_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print('v10 built: full12 inventory and explicit complete-sequence insufficiency.')
if __name__=='__main__':main()
