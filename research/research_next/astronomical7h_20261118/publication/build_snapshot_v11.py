"""Publish fixed f73r contact diagnostics and the wider spatial-role measurement plan."""
from pathlib import Path
import json,hashlib,subprocess
HERE=Path(__file__).resolve().parent;W=HERE.parent;ROOT=W.parents[2];P=W/'zodiac_object_relations';F=P/'f73r_contact_followup'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 subprocess.run(['python3','-B','scripts/build_f73r_contacts_page.py','--release-approval',str((F/'publication_approval_v1.json').relative_to(ROOT))],cwd=ROOT,check=True)
 prev=read(HERE/'snapshot_v10.json');m=read(HERE/'snapshot_v10.json')
 m['status_note']+=' f73r全部5处P来源及4个固定同带N对照已完成两路知情补查，没有确认完整文字引线；细节未决保留。另已制定全322固定窗口的宽空间角色合同，首轮编码已收齐、科学交叉复核进行中，尚未发布最终角色判定。'
 m['findings']+=['f73r固定9区、每路27原生视图的诊断补查已完成。5个预定P目标仍保留接触/叠压未定，4个N控制未见明确连接；中央没有同带控制。知情诊断不计算成功率，也不等于无语义指代。','粗接触类别相容不等于逐笔一致：ZO03淡弯笔身份、ZE02细缝范围及若干原框完整度没有得到同等精度确认；原记录与两路补查并列公开。','新的全322窗口空间角色合同允许比较共享图场，无需先读词义或指定唯一对象。完整采样框不等于完整铭文；人物带、环文、中央、页边和未定项全部保留。首轮编码尚在交叉复核，不提前宣布同质性或完整序列资格通过。']
 z=m['sections']['zodiac'];z['sources'][:0]=[{'label':'f73r固定接触补查：三种原图视野、三份记录','href':'f73r-contacts.html'},{'label':'9区诊断结果与细节未决','href':'downloads/f73r-contacts/report.txt'},{'label':'宽空间角色与独有对象不同：方法复核','href':'downloads/astronomical7h/block-role-method-review.txt'},{'label':'全322固定窗口角色登记执行协议','href':'downloads/astronomical7h/block-role-execution-protocol.txt'}]
 for row in z['records']:
  if row['id']=='f73r':row['details'].append('另完成全5个P来源与4个同带N控制的两路知情诊断；没有确认完整文字独立引线。原24候选边保留，根只作区域级及预定P目标诊断，不能称两人独立重评全部边；细笔与截框范围未决另列。')
 for k in set(prev['sections'])-{'zodiac'}:assert m['sections'][k]==prev['sections'][k]
 (HERE/'snapshot_v11.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 argv=read(HERE/'build_command_v10.json')['argv'][:];argv[argv.index('--approved-metadata')+1]=str((HERE/'snapshot_v11.json').relative_to(ROOT));inherited=[]
 for i,v in enumerate(argv):
  if v=='--approved-download':
   _,n=argv[i+1].rsplit('=',1);p=ROOT/'site/downloads/astronomical7h'/n;inherited.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p)});argv[i+1]=str(p.relative_to(ROOT))+'='+n
 for src,name in [('role_contract_review/review_v1.txt','block-role-method-review.txt'),('block_role_ledger/execution_protocol_v1.txt','block-role-execution-protocol.txt')]:argv+=['--approved-download',str((P/src).relative_to(ROOT))+'='+name]
 (HERE/'build_command_v11.json').write_text(json.dumps({'argv':argv,'purpose':'Publish bounded f73r informed diagnostic; wider role coding under review, full seven-hour goal active'},ensure_ascii=False,indent=2)+'\n');subprocess.run(argv,cwd=ROOT,check=True)
 assert all(sha(ROOT/x['path'])==x['sha256'] for x in inherited)
 receipt={'f73r_approval_sha256':sha(F/'publication_approval_v1.json'),'f73r_comparison_sha256':sha(F/'comparison_v1.json'),'inherited_downloads_unchanged':inherited,'other_scientific_sections_unchanged':True,'full322_role_ledger_final_results_published':False,'whole_window_complete':False}
 (HERE/'snapshot_v11_build_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print('v11 built: informed contact diagnostics and wider spatial-role plan.')
if __name__=='__main__':main()
