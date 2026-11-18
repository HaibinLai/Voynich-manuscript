"""Publish the completed catalogue-conditional wind calibration without rerunning research.

Extends frozen snapshot_v4. Existing downloads are explicitly reused from the
published site copies: no comparison experiment, private observer or input
construction is opened or executed. Only the two approved text reports are new.
"""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
GH = 'https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'
EXPECTED = {
    'publication/snapshot_v4.json': '300b2175dc7c671be67e98710f85774242b9ef15ded6824ad30334f02c818dac',
    'publication/build_command_v4.json': 'e76dc4ae11bd6beec2e83685a63b6a0af42d8f4171e5bbd5b81999b3e9993ed6',
    'wind_calibration_run/report_v1.txt': '3a0493977d45089326cf0586a1e8e553ff4aea3965e0a725d97510f466cebbde',
    'wind_calibration_run/numeric_audit/public_package_v1.txt': 'c66b44893782277a4077526571ce72d1167bd8388f8c0b555db8de2e10855991',
}
BASE_FILES = ['session.json', 'plan.txt', 'stage1_protocol_v1.txt', 'stage1_freeze_v1.json', 'image_input_v1.json', 'launch_manifest_v1.json']
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
read = lambda path: json.loads(path.read_text())


def main():
    dependencies = []
    for name, expected in EXPECTED.items():
        path = WINDOW / name
        assert sha(path) == expected, name
        dependencies.append({'path': str(path.relative_to(ROOT)), 'sha256': expected, 'purpose': 'Frozen metadata or approved narrative evidence'})
    meta = read(HERE / 'snapshot_v4.json')
    meta['status_note'] = '已知拉丁文风图的目录条件 C 测量与独立数值复算已完成；两叶结果和未知界分别保留。原图完整认证 I 仍 NOT_READY，伏尼契名称—正文主检验未运行。剩余八幅黄道图的两路观察已分别冻结，尚待统一对照。七小时窗口仍进行中。'
    meta['findings'][0] = '尚未确认伏尼契手稿的任何词义、读音、语种或可靠译文。'
    meta['findings'][2] = '全部十二处伏尼契短串与两版原行保留。没有删去分词困难位置，也没有执行其名称—正文命中或循环主检验。'
    meta['findings'][3] = '十二黄道图面各版完整提取335个位置，只涉及四个物理叶。全部图面已做粗角色观察；剩余八图的两路观察已分别冻结，统一对照与完整字形、词界资格仍待核。'
    meta['findings'] += [
        '目录条件 C 下，W.73 f2r 自身配对的完整名称复现为12/12；主差值保守外界为[2/3,1]。f1v 已知片段未见完整名称复现，但未知项保留，主差值外界为[-1/12,1/12]。',
        'E0与预先固定的S1得到相同矩阵和数值。两叶完整差值点估计均为NA；保守外界不是置信区间，也不宣称各端点可同时实现。原图认证I继续NOT_READY。',
    ]
    spatial = meta['sections']['spatial']
    spatial['summary'] = spatial['summary'].replace('尚未执行真实文本评分。', '尚未执行伏尼契名称—正文主检验。')
    cal = meta['sections']['calibration']
    cal['status'] = 'partial'
    cal['summary'] = '已知拉丁文风图在明确接受目录给定文本与位置对应的条件 C 下，已完成测量和独立数值复算。f2r建立了完整名称复现的条件自身优势；f1v未建立该优势。未知文字未填零，原图完整认证 I 仍 NOT_READY。旧尿诊两例失败及第三风图图源不可用均保留。'
    for row in cal['records']:
        if row['id'] == 'wind-w73-1v':
            row.update(title='W.73 f1v：条件 C 已测，未知界保留', status='complete', source_url='wind-calibration.html')
            row['details'] = [
                'E0与S1相同：144格中，确定出现0格、确定未出现132格、未知12格。已知片段未见完整名称复现，不能据此宣称全页零重复或没有图文关系。',
                '自身出现比例为0至1/12，每个非自身错位比例为0至1/12；主差值保守外界[-1/12,1/12]，完整点估计NA。范围含零，未建立本指标的自身优势。',
                '内层希腊名称目录仅9/12项，未纳入完整十二主检验。S1只采用事先登记的Austro→Austroafricus建议，没有改变矩阵或界。',
                '这是目录条件测量完成；原图逐字完整认证仍未完成。两叶同属一部手稿，不当作独立历史传统。',
            ]
        elif row['id'] == 'wind-w73-2r':
            row.update(title='W.73 f2r：条件 C 的自身复现为12/12', status='complete', source_url='wind-calibration.html')
            row['details'] = [
                'E0与S1相同：144格中，确定出现12格、确定未出现88格、未知44格。自身相位12格均有确定见证，因此12/12是已识别量，不是识字正确率或词义置信度。',
                '每个非自身错位比例的保守范围为0至4/12；主差值外界[2/3,1]，完整点估计NA。其正的条件复现优势不依赖将未知文字填零。',
                '12说明组保留13个独立正文块。图像P07对应目录C10：主块与目录引文的关联是明确条件，额外小块全文仍未知，未删去或跨块拼接。',
                '目录条件C已完成测量与复算；原图完整认证I仍NOT_READY。完整名称重复不排除复制机制，也不能单独确定词义。',
            ]
    cal['records'].append({
        'id': 'wind-scope-and-image-gate', 'title': '完成的是有限复现指标；原图认证仍未就绪', 'status': 'unresolved',
        'details': [
            '主差值=自身出现比例−十一种非自身循环错位的平均比例。辅助差值使用包含自身的十二相位平均；主差值是辅助差值的12/11倍。',
            '辅助差值保守外界：f1v为[-11/144,11/144]，f2r为[11/18,11/12]。这些是未知单元的条件外界，不是概率置信区间，不宣称尖锐；不报告置换p值。',
            '名称必须完整连续出现在一个独立已知片段内；子串、插词、跨unknown或跨块拼接不计确定出现。没有事后增加别名、词干或新阈值。',
            '24个名称的完整笔画范围、24段说明的逐字转写及P07小块尚未全部认证：I=NOT_READY。伏尼契完整名称—正文主检验仍未运行。',
            '18件精确公开依赖的三个入口已在干净目录复算，输出与各冻结基线逐字节一致；这是冻结条件输入的离线复算，不是完整原图或官方目录获取链的重新认证。',
        ], 'source_url': GH + 'wind_calibration_run/report_v1.txt',
    })
    cal['table'] = {'headers': ['叶面（E0与S1相同）', '确定出现 / 确定未出现 / 未知', '自身比例', '各非自身错位比例', '主差值保守外界'], 'rows': [
        ['f1v', '0 / 132 / 12', '0至1/12', '0至1/12', '[-1/12,1/12]；点估计NA'],
        ['f2r', '12 / 88 / 44', '12/12（已识别）', '0至4/12', '[2/3,1]；点估计NA'],
    ]}
    cal['sources'] += [
        {'label': '风图条件校准：逐叶结果、未知界与复算', 'href': 'wind-calibration.html'},
        {'label': '完整条件测量报告', 'href': GH + 'wind_calibration_run/report_v1.txt'},
        {'label': '公开复算的18件精确依赖与范围', 'href': GH + 'wind_calibration_run/numeric_audit/public_package_v1.txt'},
    ]
    zodiac = meta['sections']['zodiac']
    zodiac['summary'] = zodiac['summary'].replace('其他八幅尚未完成本项全量对照。', '剩余八幅的两路观察已分别冻结，尚待统一对照与审核；本页不追加未核对的对照统计或资格结论。')
    remaining = {'f70v2','f72r2','f72r3','f72v3','f72v2','f72v1','f73r','f73v'}
    for row in zodiac['records']:
        if row['id'] in remaining:
            row['details'] = [text for text in row['details'] if not text.startswith('已做粗角色观察及一处短串邻接示例；')]
            row['details'].append('两路观察现已分别冻结，尚待统一对照与审核。此处保留原有来源名册，不增加未核的候选统计或完整词序列资格。')
            row['eligibility'] = '两路已冻结；统一对照待核，完整文本资格未通过'
    (HERE / 'snapshot_v5.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')

    # Reuse the explicit already-published download files, avoiding all experiment directories.
    old = read(HERE / 'build_command_v4.json')['argv']
    argv = old[:]
    argv[argv.index('--approved-metadata') + 1] = str((HERE / 'snapshot_v5.json').relative_to(ROOT))
    reused = []
    for i, arg in enumerate(argv):
        if arg == '--approved-download':
            origin, name = argv[i+1].rsplit('=', 1)
            existing = ROOT / 'site/downloads/astronomical7h' / name
            digest = sha(existing)
            argv[i+1] = str(existing.relative_to(ROOT)) + '=' + name
            reused.append({'original_source_identifier': origin, 'read_path': str(existing.relative_to(ROOT)), 'sha256': digest, 'public_name': name})
            dependencies.append({'path': str(existing.relative_to(ROOT)), 'sha256': digest, 'purpose': 'Byte-preserved published download'})
    for rel, name in [('wind_calibration_run/report_v1.txt','wind-conditional-report.txt'), ('wind_calibration_run/numeric_audit/public_package_v1.txt','wind-public-replay-package.txt')]:
        argv += ['--approved-download', str((WINDOW/rel).relative_to(ROOT)) + '=' + name]
    for path in [Path(__file__).resolve(), ROOT/'site/astronomical7h.html', ROOT/'scripts/build_astronomical7h_page.py', HERE/'geometry_projection_v1.json', *[WINDOW/n for n in BASE_FILES], ROOT/'site/astronomical7h.css', ROOT/'site/astronomical7h.js']:
        dependencies.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path), 'purpose': 'Existing renderer, approved geometry or base window input'})
    (HERE/'build_command_v5.json').write_text(json.dumps({'argv':argv,'purpose':'Completed catalogue-conditional Latin calibration; original-image gate remains NOT_READY; no research execution'},ensure_ascii=False,indent=2)+'\n')
    subprocess.run(argv,cwd=ROOT,check=True)
    for row in reused:
        assert sha(ROOT/row['read_path']) == row['sha256'], row['public_name']
    dependency_manifest = {'schema':'snapshot_v5_public_dependencies','inputs':dependencies,'reused_downloads':reused,'new_metadata':{'path':str((HERE/'snapshot_v5.json').relative_to(ROOT)),'sha256':sha(HERE/'snapshot_v5.json')},'research_computation_executed':False,'new_wind_results_or_inputs_opened':False,'published_download_bytes_reused_without_analysis':True,'required_local_link_targets':['site/wind-calibration.html','site/zodiac-four.html'],'narrative_reports_read':list(EXPECTED)[2:],'comparison_experiment_directories_read':False,'limits':'This page build uses approved frozen narratives and previously published downloads. It does not rerun calibration, input preparation, source certification or comparison experiments.'}
    (HERE/'snapshot_v5_dependencies.json').write_text(json.dumps(dependency_manifest,ensure_ascii=False,indent=2)+'\n')
    print('snapshot_v5 built; prior downloads byte-preserved; no research computation run.')

if __name__ == '__main__':
    main()
