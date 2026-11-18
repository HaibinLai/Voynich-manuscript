"""Publish paired spacing follow-up and audited four-panel geometry."""
from pathlib import Path
import json
import subprocess

HERE=Path(__file__).resolve().parent
WINDOW=HERE.parent
ROOT=WINDOW.parents[2]
GH='https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'

def read(path):return json.loads(path.read_text())

def main():
    meta=read(HERE/'snapshot_v2.json')
    spacing=read(WINDOW/'f67_spacing_comparison/comparison_v1.json')
    four=read(WINDOW/'four_panel_comparison/comparison_v1.json')
    audit=read(WINDOW/'four_panel_comparison/audit_v1.json')
    assert audit['errors']==[] and spacing['summary']['fixed_targets']==12
    meta['status_note']='四图的两路完整名册及坐标复算已完成；十二短串词界补查仍未裁决。真实文本评分继续停止，另查已知语言风向圆图的校准资格；七小时窗口保持进行中。'
    meta['findings'] += [
        '四幅固定黄道图保留全部60条Lz、11条Cc与双版142原行；前三图两环的粗区域次序一致，第四图仍有跨环附带矩形交集。矩形对应不是词义或对象归属。',
        '十二短串的两路词界补查保留5个引导核查区与9个图像空隙窗口；空隙可见不等于词界得到认证，没有选择ZL或IT作为真值。']
    for row in meta['sections']['transcriptions']['records']:
        r=next(r for r in spacing['records'] if r['locator']==row['id'])
        row['details'] += ['后续词界补查：'+r['guided_assessment'], '只看图像的一路：'+r['image_assessment']]
    meta['sections']['spatial']['records'].append({
        'id':'spacing-followup','title':'全部十二处词界补查：间隔可见，语言边界未定','status':'unresolved',
        'details':['两路分别冻结后比较，保留24条原行；JPEG/TIFF来自同一摄影，不是独立历史证据。',
                   '5个引导候选与9个图像候选不构成票数。相应目标内7组候选矩形对有5组正交集，但候选框不是空白掩膜或精确词界。',
                   '没有候选也不能认证为一个词；.58两处切口的逐字符对齐仍未定。全部十二主检验继续停止。'],
        'source_url':GH+'f67_spacing_comparison/report_v1.txt'})
    z=meta['sections']['zodiac']
    z['summary']='十二图面粗角色盘点保持完整。四幅选定图进一步完成全量名册，保留60条Lz、11条Cc及全部细分、损伤；2956组矩形对已另行复算。前三图两环粗区域次序一致，但没有一图两环都获得完整的细分双向唯一对应；不能直接开启真实文本预测。其他八幅尚未完成本项全量对照。'
    for row in z['records']:
        p=next((p for p in four['panels'] if p['folio']==row['id']),None)
        if p:
            s=p['summary']
            row['details'][-1]='后续已完成两路全量名册：来源短标签15条、图像粗区15个；细分备选为'+str(s['image_fine_alternative_units'])+'个空间单元，均不是单词数。'
            row['details'].append('粗框正交集'+str(s['positive_coarse_pairs'])+'组、双向单候选'+str(s['mutual_single_coarse_candidates'])+'组；全部候选保留，不选最大交集。')
            row['eligibility']='粗空间对照已核；完整细分词序列、对象归属及逐标签正文仍未认证'
    z['sources'] += [{'label':'交互查看四图原图、框与完整原行','href':'zodiac-four.html'},
                     {'label':'四图完整坐标协调报告','href':GH+'four_panel_comparison/report_v1.txt'},
                     {'label':'独立实现审核与细分限制','href':GH+'four_panel_comparison/audit_v1.txt'}]
    c=meta['sections']['calibration']
    c['status']='running'
    c['summary']='原固定两例的资格核验已完成，均不能直接用作短标签—正文基准。另按版面条件补查三项风向圆图候选；这是新登记的有界调查，旧失败记录保留，尚未取得可运行的新基准。'
    c['records'] += [
        {'id':'wind-w73-2r','title':'补充候选：Walters W.73 f.2r','status':'running','details':['官方目录描述有独立环带风名和对应扇区说明；正在逐项核查完整十二项图像及转写。','目录角色描述尚不能替代实际图像资格；未执行词匹配。'],'source_url':'https://art.thewalters.org/object/W.73.2R/'},
        {'id':'wind-w73-1v','title':'补充候选：Walters W.73 f.1v','status':'running','details':['官方目录描述外层拉丁风名、内层希腊风名与辐条说明；两种标签层分开核查。','与f.2r属于同一手稿，不能当成两个独立传统。'],'source_url':'https://art.thewalters.org/object/W.73.1V/'},
        {'id':'wind-harley3035','title':'补充候选：Harley MS 3035 f.58v','status':'not_eligible','details':['官方目录明确该叶有风向圆图，但当前标注数字图像不可用；本轮保留图源不可得状态。','不因无法观察而从候选清单删除，也不改找另一个更容易通过的图。'],'source_url':'https://searcharchives.bl.uk/catalog/040-002024116'}]
    (HERE/'snapshot_v3.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    argv=read(HERE/'build_command_v2.json')['argv'][:]
    argv[argv.index('--approved-metadata')+1]=str((HERE/'snapshot_v3.json').relative_to(ROOT))
    for src,dst in {
        'f67_spacing_comparison/report_v1.txt':'spacing-comparison-report.txt',
        'f67_spacing_comparison/comparison_v1.json':'spacing-comparison.json',
        'f67_spacing_comparison/guided_observation_v1.json':'spacing-guided-observation.json',
        'f67_spacing_comparison/image_observation_v1.json':'spacing-image-observation.json',
        'f67_spacing_comparison_plan_v1.txt':'spacing-comparison-plan.txt',
        'wind_calibration_search/candidates_v1.json':'wind-calibration-candidates.json',
        'wind_calibration_search/search_plan_v1.txt':'wind-calibration-search-plan.txt',
        'publication/SUPPLEMENT_README_v3.txt':'four-panel-spacing-readme.txt',
    }.items():argv+=['--approved-download',str((WINDOW/src).relative_to(ROOT))+'='+dst]
    (HERE/'build_command_v3.json').write_text(json.dumps({'argv':argv,'purpose':'Reviewed spacing follow-up, audited four-panel geometry, registered supplementary calibration search'},ensure_ascii=False,indent=2)+'\n')
    subprocess.run(argv,cwd=ROOT,check=True)

if __name__=='__main__':main()
