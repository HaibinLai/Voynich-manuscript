"""Publish frozen wind qualification and a selected rectangle-corner diagnostic."""
from pathlib import Path
import hashlib
import json
import subprocess

HERE = Path(__file__).resolve().parent
WINDOW = HERE.parent
ROOT = WINDOW.parents[2]
GH = 'https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'

def read(path):
    return json.loads(path.read_text())

def main():
    exports = {
        'wind_calibration_text': ('report_freeze_v1.json', ['catalog_text_v1.json', 'qualification_v1.json', 'qualification_report_v1.txt']),
        'wind_calibration_visual': ('observer_output_freeze_v1.json', ['observer_report_v1.json', 'visual_summary_v1.txt']),
        'wind_calibration_resolution': ('output_freeze_v1.json', ['resolution_report_v1.json', 'resolution_report_v1.txt']),
        'wind_calibration_alignment': ('report_freeze_v1.json', ['alignment_v1.json', 'alignment_report_v1.txt']),
    }
    public = WINDOW / 'wind_calibration_public'
    public.mkdir(exist_ok=True)
    projection = []
    cached_receipt = public / 'projection_receipt_v1.json'
    cached = {r['source']: r for r in read(cached_receipt)['files']} if cached_receipt.exists() else {}
    private_prefix = str(ROOT.parent / 'output') + '/'
    for directory, (freeze, names) in exports.items():
        freeze_path = WINDOW / directory / freeze
        hashes = {r['path']: r['sha256'] for r in read(freeze_path)['files']} if freeze_path.exists() else {}
        for name in names:
            source = WINDOW / directory / name
            if not source.exists() or not freeze_path.exists():
                # A public checkout rebuilds from the reviewed projection. It does
                # not pretend to reverify unavailable private original bytes.
                row = cached[directory + '/' + name]
                assert hashlib.sha256((public / row['output']).read_bytes()).hexdigest() == row['output_sha256']
                projection.append(row)
                continue
            raw = source.read_bytes()
            assert hashlib.sha256(raw).hexdigest() == hashes[name], (directory, name)
            text = raw.decode().replace(private_prefix, 'private-output/')
            assert '/Users/' not in text
            dest = directory.removeprefix('wind_calibration_') + '_' + name
            (public / dest).write_text(text)
            projection.append({'source': directory + '/' + name, 'source_sha256': hashes[name], 'output': dest,
                               'output_sha256': hashlib.sha256(text.encode()).hexdigest(),
                               'change': 'Only a local private-output path prefix is replaced; scientific fields unchanged.' if text.encode() != raw else 'Byte-identical copy.'})
    (public / 'projection_receipt_v1.json').write_text(json.dumps({'files': projection}, ensure_ascii=False, indent=2) + '\n')

    # The corner reports are frozen independently; do not alter the old comparison.
    corner = WINDOW / 'f72_corner_review'
    for freeze in ['root_freeze_v1.json', 'peer_freeze_v1.json']:
        manifest = read(corner / freeze)
        for r in manifest['files']:
            assert hashlib.sha256((corner / r['path']).read_bytes()).hexdigest() == r['sha256']
    image_dir = ROOT / 'site/assets/f72-corner'
    image_dir.mkdir(parents=True, exist_ok=True)
    for name in ['context_native.png', 'corner_context_native.png', 'intersection_native.png']:
        (image_dir / name).write_bytes((corner / name).read_bytes())

    meta = read(HERE / 'snapshot_v3.json')
    meta['findings'] = [
        '原先固定的两部尿诊圆图可取得原图，但不具备本检验要求的独立短标签层及完整分区转写；该失败记录保留，后续风图另列资格。'
        if text.startswith('两部已知语言圆图原图可取得') else text
        for text in meta['findings']
    ]
    meta['status_note'] = '风图两叶的24个名称位置已对回原图，24段说明仍未逐字认证；P07额外小块覆盖未定。四图一处矩形角落已补查，原候选全部保留。真实伏尼契文本评分继续停止，七小时研究仍进行中。'
    meta['findings'] += [
        'Walters W.73 两叶均有分开的名称与说明区域，24个名称已有图像位置依据；目录完整列表不能直接当作24段完整原图转写。',
        'f72r1一处1200平方像素矩形交集可见星形图案轮廓，不是已辨认的标签文字。此为选定案例补查，不删旧候选、不提升完整词序列资格。',
    ]
    calibration = meta['sections']['calibration']
    calibration['summary'] = '两叶风图已完成目录提取、完整区域名册、官方较清晰图源核验与24个名称的位置对应。完整说明转写尚未认证，f2r P07还包含目录覆盖未定的小块。正在准备明确区分目录条件与原图认证的有限校准；尚未执行真实文字匹配。旧尿诊两例失败及第三风图图源不可用均保留。'
    for row in calibration['records']:
        if row['id'] == 'wind-w73-1v':
            row['title'] = 'Walters W.73 f.1v：名称已定位，说明逐字待核'
            row['details'] = ['12个外层Latin名称和12个辐条说明区域均已定位；使用完整1959×3420官方图源补查。名称身份的区域定位不等于每字每笔认证。',
                              '内层目录只提供9个名字，第5、6、8槽仍缺项；不补齐、不纳入完整十二主检验。',
                              '保留原名Austro及编辑不确定性；与f.2r同属一部手稿，不当作独立历史传统。']
            row['source_url'] = GH + 'wind_calibration_public/alignment_alignment_report_v1.txt'
        elif row['id'] == 'wind-w73-2r':
            row['title'] = 'Walters W.73 f.2r：十二说明区含十三文字块'
            row['details'] = ['12个彩环名称及其说明区已有实际图像位置依据，官方较清晰图源为1911×3418。',
                              'P07同时保留主块和内侧小块。小块的完整转写、性质及目录引文覆盖关系尚未确认；不能把目录12段直接称为原图全部文字。',
                              '原目录未明说读向的字段继续为空。图像实际位置表另存，不把观察推断写回目录。']
            row['source_url'] = GH + 'wind_calibration_public/alignment_alignment_report_v1.txt'
    calibration['sources'] += [
        {'label': '两路角色与目录资格报告', 'href': GH + 'wind_calibration_public/text_qualification_report_v1.txt'},
        {'label': '24项位置对应和未决文字覆盖', 'href': GH + 'wind_calibration_public/alignment_alignment_report_v1.txt'},
        {'label': '官方高分辨率来源及失败记录', 'href': GH + 'wind_calibration_public/resolution_resolution_report_v1.txt'},
        {'label': 'Walters官方完整目录', 'href': 'https://ssh.thedigitalwalters.org/Data/WaltersManuscripts/html/W73/description.html'},
    ]
    meta['sections']['zodiac']['sources'].append({'label': '矩形角落为何不等于文字重叠：原图案例', 'href': 'zodiac-four.html#z4-corner-case'})
    (HERE / 'snapshot_v4.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2) + '\n')
    argv = read(HERE / 'build_command_v3.json')['argv'][:]
    argv[argv.index('--approved-metadata') + 1] = str((HERE / 'snapshot_v4.json').relative_to(ROOT))
    additions = {str((public / r['output']).relative_to(ROOT)): 'wind-' + r['output'] for r in projection}
    additions[str((public / 'projection_receipt_v1.json').relative_to(ROOT))] = 'wind-projection-receipt.json'
    additions[str((public / 'SOURCE_NOTICE.txt').relative_to(ROOT))] = 'wind-source-notice.txt'
    for name in ['protocol_v1.txt', 'root_observation_v1.txt', 'peer_observation_v1.txt', 'crop_receipts_v1.json']:
        additions[str((corner / name).relative_to(ROOT))] = 'f72-corner-' + name
    for src, dst in additions.items():
        argv += ['--approved-download', src + '=' + dst]
    (HERE / 'build_command_v4.json').write_text(json.dumps({'argv': argv, 'purpose': 'Frozen wind qualification and selected corner diagnostic; no text scores'}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(argv, cwd=ROOT, check=True)

if __name__ == '__main__':
    main()
