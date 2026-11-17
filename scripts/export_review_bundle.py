"""Build a portable 20-page image/transcription review ZIP from public assets only.

The source JSON and JPEG bytes are preserved. Yale full-resolution originals are
linked, not downloaded. No raw PDF, modern front matter or full-corpus split is
loaded. Transcriptions and unresolved observations are not corrected or guessed.
"""
from pathlib import Path
import argparse
import hashlib
import json
import zipfile

from verify_release import REPO, safe_member, verify_snapshot


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def build_members():
    verify_snapshot()
    site = REPO/'site'
    members = {}
    rows = []
    page_index = []
    plain = [
        '伏尼契手稿：20页原图与双版转写对照',
        '这些EVA字符串是已发表的字形转写，不是发音或译文。',
        '保留原始IVTFF标记、备选读法与未决观察；未做独立盲转写或逐字认证。',
        '每个转写位置不一定是一条物理行；圆环、标签与续行不能混作正文行。',
        '',
    ]
    pages = [json.loads(p.read_text()) for p in sorted((site/'data/folios').glob('*.json'))]
    pages.sort(key=lambda p: (p['pdf_page'], p['folio']))
    if len(pages) != 20 or sum(len(p['rows']) for p in pages) != 332:
        raise ValueError('This exporter is limited to the audited 20 pages / 332 loci.')
    for page in pages:
        folio = page['folio']
        source_json = f'data/folios/{folio}.json'
        members[source_json] = safe_member(site, source_json).read_bytes()
        image = page['image']
        if not image.startswith('assets/images/') or Path(image).suffix != '.jpg':
            raise ValueError('Unexpected review image path')
        members[image] = safe_member(site, image).read_bytes()
        for focus in page['focus_cases']:
            crop = focus['crop']
            if not crop.startswith('assets/crops/') or Path(crop).suffix != '.jpg':
                raise ValueError('Unexpected focused crop path')
            members[crop] = safe_member(site, crop).read_bytes()
        highres = {r['locator']: r for r in page['high_resolution_review']['records']}
        if len(highres) != len(page['rows']):
            raise ValueError('Missing or duplicate high-resolution review locator')
        page_index.append(dict(folio=folio, pdf_page=page['pdf_page'], image=image,
                               page_json=source_json, yale_image=page['yale_image'],
                               locus_count=len(page['rows']), layout_observation=page['layout_observation']))
        plain.extend(['='*56, f"{folio}  |  所供PDF第{page['pdf_page']}页  |  {len(page['rows'])}个转写位置",
                      '版面：' + page['layout_observation'],
                      '耶鲁高清：' + page['yale_image']['source_url'], ''])
        for row in page['rows']:
            review = highres[row['locator']]
            rows.append(dict(folio=folio, pdf_page=page['pdf_page'], **row,
                             high_resolution_review=review))
            plain.extend([f"[{row['locator']}]  IVTFF类型 {row['kind']}",
                          'ZL 原始：' + row['zl_raw'], 'IT 原始：' + row['it_raw'],
                          'ZL 显示：' + row['zl'], 'IT 显示：' + row['it'],
                          '复核状态：' + review['review_status']])
            # The exact complete observation object remains in rows.json and the
            # original per-page JSON, even when the prose schema later expands.
            for key in ('visual_observation', 'observation', 'note'):
                if isinstance(review.get(key), str):
                    plain.append('观察：' + review[key])
            plain.append('')
    members['双版转写对照.txt'] = ('\n'.join(plain) + '\n').encode('utf-8')
    members['rows.json'] = encoded(rows)
    members['pages.json'] = encoded(page_index)
    members['sources/provenance.json'] = (REPO/'research/sources/provenance.json').read_bytes()
    members['打开方式.txt'] = (
        '20页可携带复核工作包\n\n'
        '先打开 双版转写对照.txt，按f2v等folio编号找对应页；assets/images里是20张页面图，'
        'assets/crops里是40处最初重点阅读裁图。高清耶鲁原图保留来源链接，未将整张高清图重复打包。\n'
        'rows.json包含332个位置的原始/显示转写及高清观察；data/folios保留网站逐页JSON的原始字节。'
        'pages.json给出PDF页码、图像路径与版面说明；manifest.json记录包内SHA-256。\n\n'
        '这不是译文，也不是独立OCR。ZL3b/IT2a为公开学术转写；不能为了得到期待的植物或语言名称'
        '删去未知符号。近似阅读框不是逐字分割。原转写文件没有因本次导出被改写。\n'
        '两版来自同一手稿且有历史依赖，不能当作两份独立语言证据。全部332处是位置/版面对照，'
        '并不表示每个字形已经专家终审；未决读法继续保留。\n\n'
        '来源：Yale Beinecke MS408；https://collections.library.yale.edu/manifests/2002046\n'
        '转写来源与版本哈希见sources/provenance.json；发布方CC0说明：https://voynich.nu/roadmap.html\n'
        '图像使用条件以耶鲁馆藏说明为准。转写CC0不扩展到图像或字体；此包不含现代序言、'
        '论文截图、EVA字体、完整PDF或私人文件路径。\n'
        '网站：https://haibinlai.github.io/Voynich-manuscript/\n'
        '代码：https://github.com/HaibinLai/Voynich-manuscript\n'
    ).encode('utf-8')
    manifest = dict(pages=20, loci=332, focused_crops=40, independent_transcription=False,
                    authoritative_glyph_correction=False, decipherment=False,
                    source_json_preserved_byte_for_byte=True,
                    files=[dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                           for name, data in sorted(members.items())])
    members['manifest.json'] = encoded(manifest)
    return members


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() or output == REPO or REPO in output.parents or output.suffix.lower() != '.zip':
        parser.error('Use a new .zip path outside the repository')
    members = build_members()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for name, data in sorted(members.items()):
            info = zipfile.ZipInfo('voynich-review20/' + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            bundle.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
    with zipfile.ZipFile(output) as bundle:
        if bundle.testzip() is not None:
            raise ValueError('ZIP integrity check failed')
        for name, data in members.items():
            if bundle.read('voynich-review20/' + name) != data:
                raise ValueError('Exported bytes differ: ' + name)
    print(json.dumps(dict(pages=20, loci=332, members=len(members), bytes=output.stat().st_size,
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest(), verified=True), indent=2))


if __name__ == '__main__':
    main()
