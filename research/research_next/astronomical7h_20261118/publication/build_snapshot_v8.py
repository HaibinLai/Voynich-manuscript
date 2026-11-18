"""Publish attributed central annotations and an exposed, frozen image crosswalk."""
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
    subprocess.run(['python3', '-B', 'scripts/build_central_annotations_page.py'], cwd=ROOT, check=True)
    crosswalk = read(source / 'crosswalk_observations_v1.json')
    assert crosswalk['summary']['located_annotation_candidates'] == 12
    assert len(crosswalk['summary']['original_boxes_with_observed_truncation']) == 4
    previous = read(HERE / 'snapshot_v7.json')
    meta = read(HERE / 'snapshot_v7.json')
    meta['status_note'] = meta['status_note'].replace('其余图面对象关系复核仍在进行。', '十二图对象关系汇编另行更新。')
    meta['status_note'] += ' 中央注记来源与十三个中央文字槽的原图对应已公开；未建立伏尼契词义。'
    meta['findings'].append('中央十三个文字槽中，十二处可定位为外部文献报告的普通字母注记候选，f70v2另有一处不同的伏尼契样短串。四个旧框截到注记笔画；保留原框和外扩细节。此项已知读法后观察，不是独立转写或新破译。')
    zodiac = meta['sections']['zodiac']
    zodiac['sources'] += [
        {'label': '中央注记：原框、外扩细节与来源读法并排', 'href': 'central-annotations.html'},
        {'label': '普通字母月份注记的外部来源与限制', 'href': 'downloads/central-annotations/source-report.txt'},
        {'label': '十三处中央文字槽的完整图像对应报告', 'href': 'downloads/central-annotations/crosswalk-report.txt'},
        {'label': '原坐标、29份实际视图与候选', 'href': 'downloads/central-annotations/crosswalk.json'},
    ]
    by_panel = {}
    for row in crosswalk['observations']:
        by_panel.setdefault(row['panel'], []).append(row)
    for row in zodiac['records']:
        observations = by_panel[row['id']]
        annotation = next(x for x in observations if x['match_status'] == 'located_candidate')
        text = '中央普通字母注记已按外部报告定位到 ' + annotation['region_uid'] + '；已知读法后看图，不认证附近伏尼契文字的词义。'
        if annotation['original_box_covers_candidate'] is False:
            text += ' 原工作框截到笔画，原框与外扩细节并列保留。'
        if len(observations) > 1:
            text += ' 另有中央ZC02伏尼契样短串，不与该注记混作同角色。'
        row['details'].append(text)
    for section in set(previous['sections']) - {'zodiac'}:
        assert meta['sections'][section] == previous['sections'][section]
    assert meta['stages'] == previous['stages']
    (HERE / 'snapshot_v8.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    argv = read(HERE / 'build_command_v7.json')['argv'][:]
    argv[argv.index('--approved-metadata') + 1] = str((HERE / 'snapshot_v8.json').relative_to(ROOT))
    inherited = []
    for i, value in enumerate(argv):
        if value == '--approved-download':
            _, name = argv[i + 1].rsplit('=', 1)
            path = ROOT / 'site/downloads/astronomical7h' / name
            inherited.append({'path': str(path.relative_to(ROOT)), 'sha256': sha(path)})
            argv[i + 1] = str(path.relative_to(ROOT)) + '=' + name
    (HERE / 'build_command_v8.json').write_text(json.dumps({'argv': argv, 'purpose': 'Add source-attributed central-note crosswalk without semantic scores or changed frozen observations'}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(argv, cwd=ROOT, check=True)
    assert all(sha(ROOT / x['path']) == x['sha256'] for x in inherited)
    receipt = {'inherited_downloads_unchanged': inherited,
               'central_page_receipt_sha256': sha(source / 'page_build_receipt_v1.json'),
               'crosswalk_sha256': sha(source / 'crosswalk_observations_v1.json'),
               'source_review_sha256': sha(source / 'source_review_v1.json'),
               'all_twelve_object_aggregation_published_by_this_release': False,
               'central_crosswalk_is_blind': False, 'new_voynich_word_meanings': 0,
               'other_scientific_sections_unchanged': True}
    (HERE / 'snapshot_v8_build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('v8 built: central note provenance, original/padded images and four crop limits.')


if __name__ == '__main__':
    main()
