"""Add separately frozen comparator audit and explicit appearance normalization caveat."""
from pathlib import Path
import json,hashlib,subprocess
ROOT=Path(__file__).resolve().parents[1];S=ROOT/'research/research_next/astronomical7h_20261118/central_annotation_sources';C=S/'independent_coverage_review/comparison';SITE=ROOT/'site'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 for name in ['output_freeze_v1.json','root_comparator_audit_freeze_v1.json']:
  for x in json.loads((C/name).read_text())['files']:assert sha(C/x['path'])==x['sha256']
 subprocess.run(['python3','-B','scripts/build_central_annotations_page_v2.py'],cwd=ROOT,check=True)
 p=SITE/'central-annotations.html';s=p.read_text()
 extra='<p class="ca-boundary"><strong>记录比较已另行核验：</strong>另一代理先冻结原两份观察的比较，再核根比较程序，175项检查无差异。这验证记录转换，不证明像素判断正确。外观“13处相容”依赖已声明的文字描述归一化，其中f72r2初稿依据上下文归类；并非13个原始枚举字段完全相同。</p>'
 s=s.replace('<div class="ca-controls">',extra+'<div class="ca-controls">',1)
 s=s.replace('<div class="ca-links">','<div class="ca-links"><a href="zodiac-relations.html">全12图文字与图形关系</a><a href="downloads/central-annotations/independent-comparator-audit.txt">175项记录比较核验与限制</a><a href="downloads/central-annotations/independent-original-comparison.txt">另一代理先冻结的比较</a>',1)
 p.write_text(s)
 mapping={'independent-comparator-audit.json':'root_comparator_audit_v1.json','independent-comparator-audit.txt':'root_comparator_audit_v1.txt','independent-original-comparison.json':'comparison_v1.json','independent-original-comparison.txt':'comparison_v1.txt'}
 for out,src in mapping.items():(SITE/'downloads/central-annotations'/out).write_bytes((C/src).read_bytes())
 receipt={'page_sha256':sha(p),'sources':[{'path':str((C/v).relative_to(ROOT)),'sha256':sha(C/v),'download':k} for k,v in mapping.items()],'observations_changed':False,'audit_is_pixel_validation':False,'appearance_prose_normalization_explicit':True}
 (S/'page_build_receipt_v3.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print('Central annotations v3: comparator audit and normalization limits added.')
if __name__=='__main__':main()
