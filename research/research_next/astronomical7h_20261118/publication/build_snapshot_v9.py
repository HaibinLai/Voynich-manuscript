"""Publish all central-coverage judgments and preserve an unresolved disagreement."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    source = WINDOW / 'central_annotation_sources'
    subprocess.run(['python3', '-B', 'scripts/build_central_annotations_page_v2.py'], cwd=ROOT, check=True)
    comparison = read(source / 'coverage_comparison_v1.json')
    followup = read(source / 'root_coverage_followup_v1.json')
    previous = read(HERE / 'snapshot_v8.json')
    meta = read(HERE / 'snapshot_v8.json')
    meta['status_note'] += ' 中央十三槽两路覆盖复核及根补查并列：初次四处类别分歧，补查仍保留一处类别分歧及方向级未定。'
    for i, finding in enumerate(meta['findings']):
        if finding.startswith('中央十三个文字槽中'):
            meta['findings'][i] = '中央十三槽仍分十二处普通字母样注记候选与一处不同的伏尼契样短串。框覆盖初次两路有四处类别分歧；根逐槽补查改为5处覆盖、6处截笔、2处未定，另一观察者为5/7/1，f72r3仍保留差别。原记录不覆盖，未新增词义。'
    zodiac = meta['sections']['zodiac']
    zodiac['sources'] += [
        {'label': '中央框覆盖：两路观察、漏看尾笔与未决', 'href': 'downloads/central-annotations/coverage-comparison-report.txt'},
        {'label': '另一观察者先冻结的十三槽原记录', 'href': 'downloads/central-annotations/independent-coverage.json'},
        {'label': '根知情补查：全十三槽、26份实际视图', 'href': 'downloads/central-annotations/root-coverage-followup.json'},
    ]
    grouped = {}
    original = {r['region_uid']: r for r in comparison['rows']}
    label = {'yes': '覆盖', 'no': '截笔', 'uncertain': '未定'}
    for row in followup['records']:
        grouped.setdefault(row['region_uid'].split(':')[0], []).append(row)
    for row in zodiac['records']:
        for new in grouped[row['id']]:
            old = original[new['region_uid']]
            row['details'].append(new['region_uid'] + '覆盖记录（根初次 / 另一观察者 / 根知情补查）：' + ' / '.join(label[v] for v in [old['root_original_coverage'], old['independent_coverage'], new['coverage']]) + '。细小尾笔越界不等于漏一个完整字；补查不算第三位独立观察者。')
    for section in set(previous['sections']) - {'zodiac'}:
        assert meta['sections'][section] == previous['sections'][section]
    assert meta['stages'] == previous['stages']
    (HERE / 'snapshot_v9.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    argv = read(HERE / 'build_command_v8.json')['argv'][:]
    argv[argv.index('--approved-metadata') + 1] = str((HERE / 'snapshot_v9.json').relative_to(ROOT))
    inherited = []
    for i, value in enumerate(argv):
        if value == '--approved-download':
            _, name = argv[i + 1].rsplit('=', 1)
            path = ROOT / 'site/downloads/astronomical7h' / name
            inherited.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
            argv[i + 1] = str(path.relative_to(ROOT)) + '=' + name
    (HERE / 'build_command_v9.json').write_text(json.dumps({'argv': argv, 'purpose': 'Publish disagreements and known-result coverage follow-up; preserve all old observations'}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(argv, cwd=ROOT, check=True)
    assert all(sha(ROOT / item['path']) == item['sha256'] for item in inherited)
    receipt = {'inherited_downloads_unchanged': inherited,
               'central_page_receipt_sha256': sha(source / 'page_build_receipt_v2.json'),
               'comparison_sha256': sha(source / 'coverage_comparison_v1.json'),
               'followup_sha256': sha(source / 'root_coverage_followup_v1.json'),
               'other_scientific_sections_unchanged': True,
               'original_observations_overwritten': False, 'followup_is_blind': False,
               'all_twelve_object_aggregation_published_by_this_release': False}
    (HERE / 'snapshot_v9_build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('v9 built: full three-way coverage record, preserving unresolved f72r3 difference.')


if __name__ == '__main__':
    main()
