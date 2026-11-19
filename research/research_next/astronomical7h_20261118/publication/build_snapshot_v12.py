"""Publish all fixed-window role judgments without replacing sequence eligibility."""
from pathlib import Path
import json,hashlib,subprocess
HERE=Path(__file__).resolve().parent;W=HERE.parent;ROOT=W.parents[2];B=W/'zodiac_object_relations/block_role_ledger'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 approval=B/'publication_approval_v1.json';a=read(approval);assert a['release_approved'] and a['approved_by']=='root'
 prev=read(HERE/'snapshot_v11.json');m=read(HERE/'snapshot_v11.json')
 old='另已制定全322固定窗口的宽空间角色合同，首轮编码已收齐、科学交叉复核进行中，尚未发布最终角色判定。'
 new='全322固定窗口的空间角色台账已完成原编码、交叉复核及根逐项审阅，原判断、更正与裁定并列公开。两处连续环文反例仍保留；宽空间角色支持不等于独有对象、完整铭文或完整跨图序列。'
 assert old in m['status_note'];m['status_note']=m['status_note'].replace(old,new)
 m['findings'][-1]='全322固定窗口的空间角色台账现逐项公开原判断、交叉复核与根裁定，全部原框、358细分备选及未定项保留。完整窗口不等于完整铭文，多个文字簇或对象也不是自动NA。'
 m['findings']+=['f72v2:ZO13、ZO14的原框采到连续环文，而非孤立短标签。两个反例原样保留，不删框或移动窗口来获得外围同质性。','细笔与手臂接触、背景损伤和空间场边界分别处理：每个范围修正都有原事实及理由；未定来源措辞与复核分歧仍可见。这批同AI知情记录审查没有读出词义，也没有改变原完整序列的资格门槛。']
 z=m['sections']['zodiac'];z['sources'][:0]=[{'label':'全部322固定窗口：原图、原判断、交叉复核与根裁定','href':'block-roles.html'},{'label':'固定窗口空间角色审阅报告与限制','href':'downloads/block-roles/root_adjudication-report_v1.txt'}]
 z['summary']+=' 新增全322窗口空间角色台账，逐项保留来源、表示更正、交叉意见与根裁定；它只支持声明范围内的空间比较，不替代完整词序列认证。'
 for k in set(prev['sections'])-{'zodiac'}:assert m['sections'][k]==prev['sections'][k]
 snapshot=HERE/'snapshot_v12.json';snapshot.write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 argv=read(HERE/'build_command_v11.json')['argv'][:];argv[argv.index('--approved-metadata')+1]=str(snapshot.relative_to(ROOT));inherited=[]
 for i,v in enumerate(argv):
  if v=='--approved-download':
   _,name=argv[i+1].rsplit('=',1);p=ROOT/'site/downloads/astronomical7h'/name;inherited.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)});argv[i+1]=str(p.relative_to(ROOT))+'='+name
 (HERE/'build_command_v12.json').write_text(json.dumps({'argv':argv,'purpose':'Publish full322 spatial role ledger; original sequence gate remains unpassed and seven-hour goal active.'},ensure_ascii=False,indent=2)+'\n')
 subprocess.run(argv,cwd=ROOT,check=True);assert all(sha(ROOT/x['path'])==x['sha256'] for x in inherited)
 receipt={'approval_sha256':sha(approval),'root_report_sha256':a['root_report_sha256'],'inherited_downloads_unchanged':inherited,'other_scientific_sections_unchanged':True,'full322_role_ledger_published_in_build':True,'full_sequence_gate_unchanged':True,'whole_window_complete':False}
 (HERE/'snapshot_v12_build_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print('v12 built with approved role ledger; full goal remains active.')
if __name__=='__main__':main()
