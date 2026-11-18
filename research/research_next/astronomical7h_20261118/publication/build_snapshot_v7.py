"""Publish three-table consolidation and a complete first-panel repeat, with disagreements."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
read = lambda p: json.loads(p.read_text())


def main():
    tables = WINDOW / 'f67_measurement_tables'
    repeat = WINDOW / 'zodiac_object_relations/root_repeat_f70v1'
    observer = WINDOW / 'zodiac_object_relations/circle_spatial_observer/f70v1'
    # Replay deterministic record projections, without new image or text scoring.
    for script, output in [(tables / 'build_v1.py', tables / 'tables_v1.json'),
                           (repeat / 'compare_v1.py', repeat / 'comparison_v1.json')]:
        run = subprocess.run(['python3', '-B', str(script)], cwd=ROOT,
                             capture_output=True, check=True)
        assert run.stdout == output.read_bytes() and not run.stderr
    comparison = read(repeat / 'comparison_v1.json')
    assert comparison['body_grade_disagreements'] == ['O04', 'I04']
    assert len(comparison['body_comparison']) == 15
    assert len(comparison['text_layout_category_comparison']) == 17
    meta = read(HERE / 'snapshot_v6.json')
    before = read(HERE / 'snapshot_v6.json')
    meta['status_note'] += ' f67r2完整三表已汇编；首个黄道图面的完整重复观察保留两处连接等级分歧。其余图面对象关系复核仍在进行。'
    meta['findings'].append('f67r2十二行角色、双版转写资格与顺序三表已经汇编，148条原始上下文行保留。完整十二主检验仍因角色、词界和部分分界未定而未执行，不把不可评分写成零命中。')
    meta['findings'].append('首图f70v1重复观察的两份记录都计11处明确身体—星形连接，但O04与I04逐项不一致；保留分歧。身体连线不认证文字归属，且这次复核事先知道汇总信息，不是盲读。')
    common = [
        {'label': 'f67r2完整十二行三表与未决处', 'href': 'downloads/astronomical7h/f67-three-tables-report.txt'},
        {'label': '三表完整来源、原行和候选', 'href': 'downloads/astronomical7h/f67-three-tables.json'},
    ]
    for section in ['roles', 'transcriptions', 'spatial']:
        meta['sections'][section]['sources'] += common
    zodiac = meta['sections']['zodiac']
    zodiac['sources'] += [
        {'label': 'f70v1完整重复观察：总数相同、逐项有分歧', 'href': 'downloads/astronomical7h/f70v1-repeat-report.txt'},
        {'label': '两份冻结判断逐项对照', 'href': 'downloads/astronomical7h/f70v1-repeat-comparison.json'},
        {'label': '比较前冻结的根代理观察', 'href': 'downloads/astronomical7h/f70v1-root-observations.json'},
        {'label': '首位观察者原始关系记录', 'href': 'downloads/astronomical7h/f70v1-first-observer.json'},
    ]
    for row in zodiac['records']:
        if row['id'] == 'f70v1':
            row['details'] += [
                '对象关系完整重复观察已完成：17处文字邻域、15组身体—尖形邻域；根代理实际显示40份固定图和4份补充旋转图。',
                '两份记录都是11E/3P/1N，但O04为P/E、I04为E/P（首位观察者/根代理）。总数一致不能替代逐项一致；两份原记录并列保留。',
                '17处布局类别一致不认证目标粒度一致，也未独立复现全部46条组件级文字候选边。没有确认文字引线、名称或词义。',
            ]
    assert meta['sections']['calibration'] == before['sections']['calibration']
    assert meta['stages'] == before['stages']
    (HERE / 'snapshot_v7.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    argv = read(HERE / 'build_command_v6.json')['argv'][:]
    argv[argv.index('--approved-metadata') + 1] = str((HERE / 'snapshot_v7.json').relative_to(ROOT))
    inherited = []
    for i, value in enumerate(argv):
        if value == '--approved-download':
            _, name = argv[i + 1].rsplit('=', 1)
            file = ROOT / 'site/downloads/astronomical7h' / name
            inherited.append({'path': str(file.relative_to(ROOT)), 'sha256': sha(file)})
            argv[i + 1] = str(file.relative_to(ROOT)) + '=' + name
    exports = [
        (tables / 'tables_v1.json', 'f67-three-tables.json'),
        (tables / 'report_v1.txt', 'f67-three-tables-report.txt'),
        (tables / 'input_freeze_v1.json', 'f67-three-tables-input-freeze.json'),
        (tables / 'output_freeze_v1.json', 'f67-three-tables-output-freeze.json'),
        (tables / 'source_integrity_check_v1.json', 'f67-three-tables-source-check.json'),
        (repeat / 'root_observations_v1.json', 'f70v1-root-observations.json'),
        (repeat / 'report_v1.txt', 'f70v1-repeat-report.txt'),
        (repeat / 'comparison_v1.json', 'f70v1-repeat-comparison.json'),
        (repeat / 'own_output_freeze_v1.json', 'f70v1-root-own-freeze.json'),
        (repeat / 'comparison_freeze_v1.json', 'f70v1-repeat-comparison-freeze.json'),
        (observer / 'observer_report_v1.json', 'f70v1-first-observer.json'),
        (observer / 'output_freeze_v1.json', 'f70v1-first-observer-freeze.json'),
    ]
    for path, name in exports:
        argv += ['--approved-download', str(path.relative_to(ROOT)) + '=' + name]
    (HERE / 'build_command_v7.json').write_text(json.dumps({'argv': argv,
        'purpose': 'Publish complete three-table consolidation and one-panel repeat; retain disagreements and unopened semantic gates'}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(argv, cwd=ROOT, check=True)
    for row in inherited:
        assert sha(ROOT / row['path']) == row['sha256']
    for path, name in exports:
        assert sha(path) == sha(ROOT / 'site/downloads/astronomical7h' / name)
    receipt = {
        'inherited_downloads_unchanged': inherited,
        'new_exports': [{'source': str(path.relative_to(ROOT)), 'public_name': name,
                         'sha256': sha(path)} for path, name in exports],
        'projections_replayed_byte_identically': ['f67_three_tables', 'f70v1_record_comparison'],
        'new_image_observation_in_builder': False,
        'new_text_score_in_builder': False,
        'root_repeat_is_blind': False,
        'all_twelve_object_relation_reviews_complete': False,
    }
    (HERE / 'snapshot_v7_build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('v7 built: three tables and first-panel repeat, including two disagreements.')


if __name__ == '__main__':
    main()
