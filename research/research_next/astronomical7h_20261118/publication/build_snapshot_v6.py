"""Publish approved remaining-eight arithmetic status, retaining v5 science and failure history."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE=Path(__file__).resolve().parent
WINDOW=HERE.parent
ROOT=WINDOW.parents[2]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(p.read_text())
EXPECTED={'snapshot_v5.json':'dfafcbbe0c796b86515db2c72bc34fa5303daf7a61c568310c8d0b7578f5ea40','build_command_v5.json':'5e9115ce2b26fcb66de7f90a2a73ab359ae936317dc5ae3943b57db63320e191'}
BASE_FILES=['session.json','plan.txt','stage1_protocol_v1.txt','stage1_freeze_v1.json','image_input_v1.json','launch_manifest_v1.json']
REMAINING={'f70v2','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v'}
APPROVAL=WINDOW/'zodiac_remaining_comparison/publication_approval_v1.json'

def main():
    dependencies=[]
    def dep(p,purpose):
        dependencies.append({'path':str(p.relative_to(ROOT)),'sha256':sha(p),'purpose':purpose})
    for name,expected in EXPECTED.items():
        assert sha(HERE/name)==expected
        dep(HERE/name,'Frozen prior snapshot / explicit previous build command')
    approval=read(APPROVAL)
    assert approval['schema']=='zodiac_eight_release_approval_v1' and approval['approved_by']=='root'
    assert approval['release_approved'] is True and approval['independent_arithmetic_audit']=='COMPLETE'
    assert approval['audit_report_path']=='research/research_next/astronomical7h_20261118/zodiac_remaining_comparison/independent_audit/audit_report_v1.json'
    assert approval['audit_text_path']=='research/research_next/astronomical7h_20261118/zodiac_remaining_comparison/independent_audit/audit_report_v1.txt'
    audit_path=ROOT/approval['audit_report_path'];text_path=ROOT/approval['audit_text_path']
    assert sha(audit_path)==approval['audit_report_sha256'] and sha(text_path)==approval['audit_text_sha256']
    audit=read(audit_path)
    assert audit['schema']=='independent_v2_geometry_audit_v1' and audit['all_passed'] is True and audit['differences']==[]
    assert audit['dependencies']['comparison_v2.json']==approval['comparison_sha256']
    assert audit['dependencies']['output_freeze_v1.json']==approval['output_freeze_sha256']
    assert len(audit['tables_checked'])==48 and sum(t['cartesian_pairs'] for t in audit['tables_checked'])==16472
    page=read(ROOT/'site/data/zodiac-eight.json')
    assert page['preview'] is False and page['release_approval']==approval
    assert page['release_approval_sha256']==sha(APPROVAL)
    assert page['independent_audit']==audit
    for p in [APPROVAL,audit_path,text_path,ROOT/'site/data/zodiac-eight.json']:
        dep(p,'Root-approved eight-panel publication evidence; no research computation')
    meta=read(HERE/'snapshot_v5.json')
    meta['status_note']=meta['status_note'].replace('剩余八幅黄道图的两路观察已分别冻结，尚待统一对照。','剩余八幅黄道图已完成两路坐标对照并通过独立算术复核；对象归属、词界、词义与完整文本序列仍未认证。')
    meta['findings'][3]='十二黄道图面各版完整提取335个位置，只涉及四个物理叶。剩余八图的两路坐标对照已完成并经独立算术复核；8个未定位来源框与额外候选保留，完整字形、词界及对象资格仍未认证。'
    meta['findings'].append('剩余八图的48张表、16,472个矩形配对已由另一实现复核，120,518项精确检查零差异。这是算术实现独立，不是盲图像复读；v2没有独立来源侧环序，因此所有环序对照未计算。')
    zodiac=meta['sections']['zodiac']
    zodiac['summary']=zodiac['summary'].replace('剩余八幅的两路观察已分别冻结，尚待统一对照与审核；本页不追加未核对的对照统计或资格结论。','剩余八幅的两路坐标对照已完成，48张表和16,472个矩形配对已通过另一实现复核。8个NA主框及额外候选完整保留；v2环序均未计算。算术一致不认证词义、对象归属或完整文本序列。')
    for row in zodiac['records']:
        if row['id'] in REMAINING:
            row['details']=[t for t in row['details'] if not t.startswith('两路观察现已分别冻结，尚待统一对照与审核。')]
            row['details'].append('两路坐标对照已完成并通过独立算术复核。NA不填零，额外候选不替代主框；已定位框中的双向唯一候选仍不证明共同墨迹、对象归属或词身份。')
            row['details'].append('v2缺少来源侧独立登记的几何环序，环序对照未计算。完整文本序列与逐标签专属正文资格仍未开放。')
            row['eligibility']='坐标对照与独立算术复核完成；完整文本、对象归属及词义未认证'
    zodiac['sources'] += [
      {'label':'剩余八图：原图、NA、候选与完整双版原行','href':'zodiac-eight.html'},
      {'label':'八图独立算术审计：范围、零差异与限制','href':'downloads/astronomical7h/zodiac-eight-independent-audit.txt'},
      {'label':'八图审计完整数据','href':'downloads/astronomical7h/zodiac-eight-independent-audit.json'},
      {'label':'八图发布批准及精确审计哈希','href':'downloads/astronomical7h/zodiac-eight-publication-approval.json'},
    ]
    # Calibration, previous failures, transcription, geometry and old four-panel records stay exact.
    previous=read(HERE/'snapshot_v5.json')
    for section in set(previous['sections'])-{'zodiac'}:
        assert meta['sections'][section]==previous['sections'][section]
    assert zodiac['table']==previous['sections']['zodiac']['table']
    for row,old in zip(zodiac['records'],previous['sections']['zodiac']['records']):
        if row['id'] not in REMAINING:assert row==old
    (HERE/'snapshot_v6.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    argv=read(HERE/'build_command_v5.json')['argv'][:]
    argv[argv.index('--approved-metadata')+1]=str((HERE/'snapshot_v6.json').relative_to(ROOT))
    reused=[]
    for i,arg in enumerate(argv):
        if arg=='--approved-download':
            origin,name=argv[i+1].rsplit('=',1)
            p=ROOT/'site/downloads/astronomical7h'/name
            reused.append({'original_source_identifier':origin,'read_path':str(p.relative_to(ROOT)),'sha256':sha(p),'public_name':name})
            argv[i+1]=str(p.relative_to(ROOT))+'='+name;dep(p,'Byte-preserved published download')
    for p,name in [(audit_path,'zodiac-eight-independent-audit.json'),(text_path,'zodiac-eight-independent-audit.txt'),(APPROVAL,'zodiac-eight-publication-approval.json')]:
        argv+=['--approved-download',str(p.relative_to(ROOT))+'='+name]
    for p in [Path(__file__).resolve(),ROOT/'scripts/build_astronomical7h_page.py',ROOT/'site/astronomical7h.html',ROOT/'site/astronomical7h.css',ROOT/'site/astronomical7h.js',HERE/'geometry_projection_v1.json',*[WINDOW/n for n in BASE_FILES]]:dep(p,'Explicit renderer / approved geometry / base input')
    (HERE/'build_command_v6.json').write_text(json.dumps({'argv':argv,'purpose':'Publish completed eight-panel geometry comparison and independent arithmetic audit; preserve all scientific gates'},ensure_ascii=False,indent=2)+'\n')
    subprocess.run(argv,cwd=ROOT,check=True)
    for row in reused:assert sha(ROOT/row['read_path'])==row['sha256']
    manifest={'schema':'snapshot_v6_public_dependencies','inputs':dependencies,'reused_downloads':reused,'new_metadata':{'path':str((HERE/'snapshot_v6.json').relative_to(ROOT)),'sha256':sha(HERE/'snapshot_v6.json')},'research_computation_executed':False,'private_observations_read':False,'comparison_results_recomputed':False,'required_local_link_targets':['site/zodiac-eight.html','site/zodiac-four.html','site/wind-calibration.html'],'limits':'Arithmetic implementation independence does not certify blind visual review, glyphs, objects, historical order or semantics. v1 scope error remains archived; v2 cycles uncomputed.'}
    (HERE/'snapshot_v6_dependencies.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('snapshot_v6 built; inherited downloads and prior scientific sections preserved.')
if __name__=='__main__':main()
