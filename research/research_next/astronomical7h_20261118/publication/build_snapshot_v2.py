"""Append reviewed source sensitivity and artificial method checks to snapshot v1.

Never reads either unfinished four-panel observer directory.
"""
from pathlib import Path
import json
import subprocess
import shutil

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
GH = 'https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'

def read(path):
    return json.loads(path.read_text())

def record(identity, title, status, details):
    return dict(id=identity, title=title, status=status, details=details)

def main():
    # Keep the first published scientific snapshot and its receipt unchanged.
    meta = read(HERE / 'snapshot_v1.json')
    source = read(WINDOW / 'source_sensitivity/report_v1.json')
    assert source, 'Reviewed source report must be present'
    meta['status_note'] = '已补查官方TIFF与用户PDF：未解决三处分界线疑问。人工方法核对单独展示，不是手稿得分。四幅黄道图的两路完整名册正在分别核查；七小时窗口继续。'
    meta['findings'].append('官方TIFF与JPEG为同一摄影、同为4972×3738；PDF对应嵌图为2000×1504。三处分界完整连续性仍未定，红字O06阅读框覆盖缺口已确认。')
    spatial = meta['sections']['spatial']
    spatial['summary'] = '十二处可作工作空间对应，但完整扇区边界仍未确认。共同起点或共同方向未知本身不阻碍单图循环对照；两侧相对归属及文本范围不明才是实质缺口。尚未执行真实文本评分。'
    spatial['records'].extend([
        record('source-sensitivity', '三种数字图源补测：没有新增空间分辨率', 'complete', [
            '官方JPEG与原始TIFF均为4972×3738，取景与细部位置一致；解码像素并非完全相同，不能称字节或像素一致。它们不是两次独立摄影。',
            '用户PDF第202页已核为ImageID1006194，嵌图2000×1504。没有用放大插值或图像增强补出字迹。',
            '三来源、四个预定局部共12个裁区均已查看。B07/B08/B09的完整墨线连续性仍未定；完成补测不等于边界通过。',
            'O06内有真实红字，旧引导框仍未覆盖。此结论只针对阅读框，不新增词数、行数或来源位置。']),
        record('coordinate-freedom', '方法澄清：共同起点不等于相对对应', 'complete', [
            '标签与正文同时换起点，原位匹配及全部错位得分不变；同时反向只重排错位的编号。一般结论来自求和换元证明。',
            '只转动正文侧会改变谁对应谁，不能看过得分后挑最有利的对齐。跨图缺少相对锚点仍不能据最佳对齐确认读序。',
            '这项方法核对不读取手稿词串，不解决当前边界、角色及分词问题，也不开放真实文本检验。'])])
    spatial['sources'].extend([
        {'label':'TIFF / JPEG / PDF补测报告', 'href':GH+'source_sensitivity/报告_v1.txt'},
        {'label':'共同起点与方向的完整证明', 'href':GH+'method_preflight/invariance_report_v1.txt'}])
    meta['sections']['roles']['records'][3]['details'][0] = '后续三图源补测确认O06内有红色笔迹，且未与旧引导阅读框相交；对应来源位置仍未知。'
    meta['sections']['zodiac']['summary'] += ' 下一阶段固定核查f70v1、f71r、f71v、f72r1的全量名册，两路各自保存后再比较，不强迫图像区数等于来源记录数。'
    (HERE/'snapshot_v2.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    argv = read(HERE/'build_command_v1.json')['argv'][:]
    argv[argv.index('--approved-metadata')+1] = str((HERE/'snapshot_v2.json').relative_to(ROOT))
    extra = {
        'source_sensitivity/报告_v1.txt':'source-sensitivity-report.txt',
        'source_sensitivity/report_v1.json':'source-sensitivity-report.json',
        'four_panel_comparison_protocol_v1.txt':'four-panel-comparison-plan.txt',
        'method_preflight/report_v1.txt':'artificial-method-report.txt',
        'method_preflight/invariance_report_v1.txt':'coordinate-invariance-proof.txt',
        'method_preflight/results_v1.json':'artificial-method-results.json',
        'method_preflight/invariance_results_v1.json':'coordinate-invariance-results.json',
        'method_preflight/audit_v1.txt':'artificial-method-audit.txt',
        'publication/SUPPLEMENT_README_v2.txt':'supplement-readme.txt',
    }
    for src, dst in extra.items():
        argv += ['--approved-download', str((WINDOW/src).relative_to(ROOT))+'='+dst]
    figures = ROOT/'site/assets/astronomical7h'
    figures.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(WINDOW/'method_preflight/artificial_phase_patterns_v1.svg',figures/'artificial-phase-patterns-v1.svg')
    (HERE/'build_command_v2.json').write_text(json.dumps({'argv':argv,'purpose':'Reviewed source supplement and separately labeled artificial method checks'},ensure_ascii=False,indent=2)+'\n')
    subprocess.run(argv,cwd=ROOT,check=True)

if __name__ == '__main__':
    main()
