"""Add frozen disagreements and known-result follow-up, preserving original observations."""
import hashlib
import html
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'research/research_next/astronomical7h_20261118/central_annotation_sources'
SITE = ROOT / 'site'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
esc = lambda s: html.escape(str(s), quote=True)
LABEL = {'yes': '可见笔画在框内', 'no': '可见笔画被截', 'uncertain': '边界未定'}


def main():
    for dirname, filename in [('', 'coverage_comparison_output_freeze_v1.json'),
                              ('independent_coverage_review', 'output_freeze_v1.json')]:
        folder = SOURCE / dirname
        for entry in read(folder / filename)['files']:
            assert sha(folder / entry['path']) == entry['sha256']
    run = subprocess.run(['python3', '-B', str(SOURCE / 'compare_coverage_v1.py')], cwd=ROOT, capture_output=True, check=True)
    assert run.stdout == (SOURCE / 'coverage_comparison_v1.json').read_bytes()
    subprocess.run(['python3', '-B', 'scripts/build_central_annotations_page.py'], cwd=ROOT, check=True)
    comparison = read(SOURCE / 'coverage_comparison_v1.json')
    followup = read(SOURCE / 'root_coverage_followup_v1.json')
    first = read(SOURCE / 'crosswalk_observations_v1.json')
    rows = {r['region_uid']: r for r in comparison['rows']}
    later = {r['region_uid']: r for r in followup['records']}
    old = {r['region_uid']: r for r in first['observations']}
    assert rows.keys() == later.keys() == old.keys() and len(rows) == 13
    page = (SITE / 'central-annotations.html').read_text()
    articles = re.findall(r'<article class="ca-card".*?</article>', page, flags=re.S)
    assert len(articles) == 13
    for article, r in zip(articles, comparison['rows']):
        uid = r['region_uid']
        assert esc(uid.split(':', 1)[1]) in article and esc(r['panel']) in article
        f = later[uid]
        clipped = 'no' in (r['root_original_coverage'], r['independent_coverage'], f['coverage'])
        uncertain = f['coverage'] == 'uncertain'
        updated = re.sub(r'data-clipped="(?:true|false)"', f'data-clipped="{str(clipped).lower()}" data-uncertain="{str(uncertain).lower()}"', article)
        table = '<div class="ca-comparison"><table><caption>可见笔画覆盖：三份记录按时间并列</caption><thead><tr><th>根初次</th><th>另一观察者</th><th>根知情补查</th></tr></thead><tbody><tr>'
        table += ''.join('<td>' + LABEL[v] + '</td>' for v in [r['root_original_coverage'], r['independent_coverage'], f['coverage']])
        table += '</tr></tbody></table><p class="ca-muted">补查已知对方判断，不是第三位独立观察者。原框与两份旧记录均保留。</p></div>'
        updated, n = re.subn(r'<p class="(?:ca-cut|ca-muted)">[^<]*</p>', table, updated, count=1)
        assert n == 1
        updated = updated.replace('<p>' + esc(old[uid]['observed_fact']) + '</p>', '<p><strong>根初次记录（原样保留）：</strong>' + esc(old[uid]['observed_fact']) + '</p>')
        extra = '<p><strong>另一观察者：</strong>' + esc(r['independent_stroke_evidence']) + '</p><p><strong>根知情补查：</strong>' + esc(f['observed_fact']) + '</p>'
        updated = updated.replace('</details></article>', extra + '</details></article>')
        page = page.replace(article, updated, 1)
    page = page.replace('以及四处被旧工作框截到的笔画。', '以及两路观察对框边界的分歧和后续补查。')
    page = page.replace('<div><strong>4</strong>旧框截到笔画的位置</div><div><strong>0</strong>新增的伏尼契词义</div>', '<div><strong>4</strong>初次覆盖判断有分歧</div><div><strong>1</strong>补查后仍有类别分歧</div>')
    notice = '<p class="ca-boundary"><strong>覆盖复核更新：</strong>根初次记 9 处在框内、4 处截笔；另一观察者记 5 处在框内、7 处截笔、1 处未定。根逐槽补查后改为 5 / 6 / 2，f72r3 仍保留“截笔 / 未定”分歧。先前的四处截笔不是穷尽清单。没有新增伏尼契词义。</p>'
    page = page.replace('<div class="ca-controls">', notice + '<div class="ca-controls">', 1)
    page = page.replace('<option value="clipped">旧框截到笔画</option>', '<option value="clipped">任一观察记为截笔</option><option value="uncertain">根补查仍未定</option>')
    page = page.replace("filter.value==='other'&&c.dataset.located==='false'", "filter.value==='other'&&c.dataset.located==='false'||filter.value==='uncertain'&&c.dataset.uncertain==='true'")
    page = page.replace('四处截断说明工作框能定位邻域，但不一定给出完整字串。', '两路覆盖判断不同，说明工作框能定位邻域，但不能仅凭文字主体的位置认证完整字串。补查同样保留细小笔画与图形线条难以区分的情形。')
    page = page.replace('<div class="ca-links">', '<div class="ca-links"><a href="downloads/central-annotations/coverage-comparison-report.txt">两路比较、改判与未决</a><a href="downloads/central-annotations/independent-coverage.json">另一观察者原始冻结记录</a><a href="downloads/central-annotations/root-coverage-followup.json">根知情补查：26份视图</a>', 1)
    page = page.replace('记录快照：' + sha(SOURCE / 'crosswalk_observations_v1.json')[:16], '初次定位快照：' + sha(SOURCE / 'crosswalk_observations_v1.json')[:16] + '；覆盖补查快照：' + sha(SOURCE / 'root_coverage_followup_v1.json')[:16])
    page = page.replace('</style>', '.ca-comparison{overflow-x:auto}.ca-comparison table{width:100%;border-collapse:collapse;max-width:760px;margin:18px 0}.ca-comparison th,.ca-comparison td{text-align:left;padding:10px;border-bottom:1px solid #d2c8b2}.ca-comparison caption{text-align:left;font-weight:600;padding:8px 0}</style>')
    (SITE / 'central-annotations.html').write_text(page)
    downloads = {'coverage-comparison.json': 'coverage_comparison_v1.json',
                 'coverage-comparison-report.txt': 'coverage_comparison_report_v1.txt',
                 'coverage-comparison-input-freeze.json': 'coverage_comparison_input_freeze_v1.json',
                 'coverage-comparison-output-freeze.json': 'coverage_comparison_output_freeze_v1.json',
                 'independent-coverage.json': 'independent_coverage_review/observer_report_v1.json',
                 'independent-coverage-freeze.json': 'independent_coverage_review/output_freeze_v1.json',
                 'root-coverage-followup.json': 'root_coverage_followup_v1.json',
                 'root-coverage-followup-protocol.txt': 'root_coverage_followup_protocol_v1.txt'}
    for public, source in downloads.items():
        (SITE / 'downloads/central-annotations' / public).write_bytes((SOURCE / source).read_bytes())
    receipt = {'page_sha256': sha(SITE / 'central-annotations.html'), 'cards': len(articles),
               'source_comparison_sha256': sha(SOURCE / 'coverage_comparison_v1.json'),
               'source_followup_sha256': sha(SOURCE / 'root_coverage_followup_v1.json'),
               'original_rows_replaced': False, 'text_meanings_added': False,
               'added_downloads': [{'public': k, 'source': v, 'sha256': sha(SOURCE / v)} for k, v in downloads.items()]}
    (SOURCE / 'page_build_receipt_v2.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
    print('Built central v2: 13 three-way rows, initial4 disagreements and residual1 category disagreement.')


if __name__ == '__main__':
    main()
