#!/usr/bin/env python3
"""Publish an explicit, reviewable astronomical-window snapshot.

Reads ONLY BASE_FILES by default, never walks a research directory. Optional:
  --approved-metadata path/to/publication.json
  --approved-geometry path/to/approved-geometry-projection.json
  --approved-download path/to/approved-file.txt=public-name.txt (repeatable)

Metadata is a publication projection supplied after review, not raw observer data.
Top-level fields: findings [str], status_note str, stages [{stage,title,status}],
window_status str, sections {roles|transcriptions|spatial|calibration|zodiac: {...}}.
Each section: status, summary, records, sources [{label,href}]. Records may have
id,title,status,details [str],source_url,zl,it,relation,uncertainty,role,sequence,
folio,eligibility,original_lines. Values are plain text; null means not available.
Optional table {headers:[str],rows:[[scalar]]} supports approved specialist data.
No scores, images, links or sections are discovered from neighboring files.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / 'research/research_next/astronomical7h_20261118'
SITE = ROOT / 'site'
BASE_FILES = {
    'session.json': '窗口登记',
    'plan.txt': '完整研究计划',
    'stage1_protocol_v1.txt': '空间测量协议',
    'stage1_freeze_v1.json': '测量协议冻结记录',
    'image_input_v1.json': '官方原图来源记录',
    'launch_manifest_v1.json': '启动文件核验清单',
}
SECTION_KEYS = ('roles', 'transcriptions', 'spatial', 'calibration', 'zodiac')
STATE_KEYS = {'active', 'running', 'planned', 'awaiting_review', 'partial', 'complete', 'completed', 'blocked', 'paused', 'not_eligible', 'unresolved'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def public_link(href):
    if not isinstance(href, str):
        return False
    parsed = urlsplit(href)
    if parsed.scheme == 'https' and parsed.netloc:
        return True
    if parsed.scheme or parsed.netloc or '\\' in href:
        return False
    local = Path(parsed.path)
    return not local.is_absolute() and '..' not in local.parts and bool(parsed.path) and (SITE / local).is_file()


def explicit_path(value):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    path.relative_to(ROOT)
    if {'spatial_observer', 'guided_layout'} & set(path.parts):
        raise ValueError('Isolated observer inputs are not publication inputs; supply an approved projection.')
    if not path.is_file():
        raise ValueError(f'Explicit input does not exist: {path.name}')
    return path


def validate_public(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'href', 'source_url'} and item and not public_link(item):
                raise ValueError(f'Invalid or absent publication link: {item}')
            validate_public(item)
    elif isinstance(value, list):
        for item in value:
            validate_public(item)
    elif isinstance(value, str) and ('/Users/' in value or '/home/' in value or 'file://' in value):
        raise ValueError('Local private paths must not be published.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-metadata', type=str)
    parser.add_argument('--approved-geometry', type=str)
    parser.add_argument('--approved-download', action='append', default=[], metavar='SOURCE=PUBLIC_NAME')
    args = parser.parse_args()
    raw = {name: (SOURCE / name).read_bytes() for name in BASE_FILES}
    loaded = {name: json.loads(data) if name.endswith('.json') else data.decode('utf-8') for name, data in raw.items()}
    manifest = loaded['launch_manifest_v1.json']
    for entry in manifest['files']:
        name = entry['path']
        if name not in raw or sha(raw[name]) != entry['sha256']:
            raise ValueError('Launch manifest mismatch: ' + name)
    session = loaded['session.json']
    image = loaded['image_input_v1.json']
    if not image['official_url'].startswith('https://collections.library.yale.edu/iiif/2/'):
        raise ValueError('Expected an official Yale image URL')
    loci = loaded['stage1_freeze_v1.json']['fixed_loci']
    if loci != [f'f67r2.{n}' for n in range(52, 64)]:
        raise ValueError('All twelve fixed locations must be retained')
    downloads = []
    target = SITE / 'downloads/astronomical7h'
    target.mkdir(parents=True, exist_ok=True)
    for name, label in BASE_FILES.items():
        (target / name).write_bytes(raw[name])
        downloads.append({'label': label, 'href': f'downloads/astronomical7h/{name}'})
    public_names = set(BASE_FILES)
    for spec in args.approved_download:
        source_arg, sep, name = spec.rpartition('=')
        if not sep or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*\.(json|txt|csv|md|pdf)', name) or name in public_names:
            raise ValueError('Downloads need a unique safe PUBLIC_NAME and explicit SOURCE=PUBLIC_NAME')
        path = explicit_path(source_arg)
        content = path.read_bytes()
        if path.suffix.lower() != '.pdf':
            validate_public(content.decode('utf-8'))
        (target / name).write_bytes(content)
        public_names.add(name)
        downloads.append({'label': name, 'href': f'downloads/astronomical7h/{name}'})
    sections = {
        'roles': {'status': 'running', 'summary': '先分清文字出现的位置和形式，再讨论功能。以下四类是测量协议规定的观察范围，尚不是经过复核的角色判定。', 'records': [
            {'id': 'face-adjacent', 'title': '十二圆脸内侧短串', 'status': 'awaiting_review', 'details': ['保留 f67r2.52–.63 全部十二处。文字与圆脸邻近，不自动证明它们是名称。']},
            {'id': 'sector', 'title': '扇区文本', 'status': 'awaiting_review', 'details': ['核对各段边界、相邻图形与可能的跨区文字。']},
            {'id': 'central-ring', 'title': '中央环文', 'status': 'awaiting_review', 'details': ['与外围短串、扇区文本分开登记；完整次序待核。']},
            {'id': 'bottom-prose', 'title': '底部正文', 'status': 'awaiting_review', 'details': ['保留整图上下文，不把底部正文并入扇区计数。']}]},
        'transcriptions': {'status': 'awaiting_review', 'summary': '十二处固定位置全部保留。ZL 与 IT 的完整原行、空格和读字分歧，经复核后在这里并列展示；缺失值不会填成空串或零。', 'records': [{'id': locus, 'title': locus, 'status': 'awaiting_review', 'zl': None, 'it': None, 'uncertainty': '双版原行和转写资格待核。'} for locus in loci]},
        'spatial': {'status': 'running', 'summary': '需要核对完整闭环、方向和每处文字的归属。目前不发布未经协调复核的坐标、框或次序，也不默认正上方是第一项。', 'records': []},
        'calibration': {'status': 'running', 'summary': '先核查真实已知语言圆图能否提供可读短标签、对象说明、连线与完整转写。候选不可用也会保留资格结果。', 'records': [
            {'id': 'trinity', 'title': 'Trinity O.7.20 f.1:33r', 'status': 'awaiting_review', 'details': ['已登记的馆藏候选；可取得的文字角色与转写范围待核。']},
            {'id': 'rosenbach', 'title': 'Rosenbach MS1004/29', 'status': 'awaiting_review', 'details': ['已登记的馆藏候选；尚不作为语言或语义金标。']}]},
        'zodiac': {'status': 'planned', 'summary': '计划完整盘点十二个黄道图面，再核查至少两个图是否存在可比的同角色序列。图面清单尚待冻结；不按中央动物图预先认定外围文字的含义。', 'records': []},
    }
    metadata = {}
    sources = [{'path': name, 'sha256': sha(data)} for name, data in raw.items()]
    if args.approved_metadata:
        metadata_path = explicit_path(args.approved_metadata)
        metadata_raw = metadata_path.read_bytes()
        metadata = json.loads(metadata_raw)
        validate_public(metadata)
        for key, value in metadata.get('sections', {}).items():
            if key not in SECTION_KEYS or not isinstance(value, dict):
                raise ValueError('Unknown or malformed publication section: ' + key)
            sections[key].update(value)
        sources.append({'path': str(metadata_path.relative_to(ROOT)), 'sha256': sha(metadata_raw)})
    for key, section in sections.items():
        if section['status'] not in STATE_KEYS or not isinstance(section.get('records'), list):
            raise ValueError('Invalid section state or records: ' + key)
        if key == 'transcriptions' and {r['id'] for r in section['records']} != set(loci):
            raise ValueError('Transcription publication must retain all twelve fixed loci')
        for row in section['records']:
            if row.get('status', 'awaiting_review') not in STATE_KEYS:
                raise ValueError('Invalid record state')
    titles = ['完整空间、文字角色与双版原文', '已知语言校准与跨图角色', '资格通过后的固定预测', '综合、限制与七小时终点验收']
    stages = metadata.get('stages', [{'stage': s['stage'], 'title': titles[s['stage'] - 1], 'status': s['status']} for s in session['stages']])
    payload = {
        'schema_version': 1,
        'snapshot_utc': datetime.now(timezone.utc).isoformat(),
        'window': {key: session[key] for key in ('start_utc', 'deadline_utc', 'duration_hours', 'local_window', 'status', 'stage')},
        'status_note': metadata.get('status_note', '本次发布记录：第三窗口进行中；空间测量与校准资格核查已启动，研究结果仍待复核。'),
        'findings': metadata.get('findings', ['尚未确认词义、语言或可靠译文。', '测量协议已经冻结；真实文本匹配评分尚未获本阶段协议授权。', '完整转写与部分图像此前已接触，本轮不称新的盲样本。']),
        'stages': stages,
        'sections': sections,
        'image': {'official_url': image['official_url'], 'sha256': image['sha256'], 'description': '耶鲁官方完整画布；底图保持原样。可选阅读框是观察记录，不是字形或词义认证。'},
        'plan': loaded['plan.txt'],
        'protocol': loaded['stage1_protocol_v1.txt'],
        'downloads': downloads,
        'sources': sources,
    }
    if args.approved_geometry:
        geometry_path = explicit_path(args.approved_geometry)
        geometry_raw = geometry_path.read_bytes()
        geometry = json.loads(geometry_raw)
        validate_public(geometry)
        if geometry.get('status') != 'approved_for_display_as_observations_not_certification':
            raise ValueError('Geometry requires explicit observation-only display approval')
        canvas = geometry['canvas']
        if canvas['url'] != image['official_url']:
            raise ValueError('Geometry and original image must use the same official canvas')
        if any(type(canvas[k]) is not int or canvas[k] <= 0 for k in ('width', 'height')):
            raise ValueError('Geometry needs positive original-pixel canvas dimensions')
        layers = geometry['layers']
        layer_ids = [layer['id'] for layer in layers]
        if len(layer_ids) != len(set(layer_ids)) or not layer_ids:
            raise ValueError('Geometry layers must be unique and nonempty')
        identities = set()
        for box in geometry['boxes']:
            identity = (box['layer'], box['id'])
            if box['layer'] not in layer_ids or identity in identities:
                raise ValueError('Geometry record has unknown layer or duplicate ID')
            identities.add(identity)
            bbox = box['bbox']
            if len(bbox) != 4 or any(type(n) is not int for n in bbox):
                raise ValueError('Geometry boxes require integer x1,y1,x2,y2')
            x1, y1, x2, y2 = bbox
            if not (0 <= x1 < x2 <= canvas['width'] and 0 <= y1 < y2 <= canvas['height']):
                raise ValueError('Geometry box lies outside the original canvas')
        # Embed the approved projection only. Input hashes are provenance, never file reads.
        payload['geometry'] = {key: geometry[key] for key in ('utc', 'status', 'canvas', 'limits', 'layers', 'boxes', 'inputs')}
        sources.append({'path': str(geometry_path.relative_to(ROOT)), 'sha256': sha(geometry_raw)})
        geometry_name = 'geometry-projection.json'
        if geometry_name in public_names:
            raise ValueError('geometry-projection.json is reserved for --approved-geometry')
        (target / geometry_name).write_bytes(geometry_raw)
        downloads.append({'label': '原图阅读框与观察来源', 'href': f'downloads/astronomical7h/{geometry_name}'})
    if 'window_status' in metadata:
        if metadata['window_status'] not in STATE_KEYS:
            raise ValueError('Unknown window status')
        payload['window']['status'] = metadata['window_status']
    validate_public(payload)
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (SITE / 'data').mkdir(exist_ok=True)
    (SITE / 'data/astronomical7h.json').write_text(content, encoding='utf-8')
    html_path = SITE / 'astronomical7h.html'
    html = html_path.read_text(encoding='utf-8')
    version = sha(content.encode())[:16]
    html = re.sub(r'(<meta name="astronomical7h-snapshot" content=")[^"]*(">)', lambda m: m[1] + version + m[2], html)
    for asset in ('astronomical7h.css', 'astronomical7h.js'):
        digest = sha((SITE / asset).read_bytes())[:16]
        html = re.sub(r'(["\'])' + re.escape(asset) + r'(?:\?[^"\']*)?(["\'])', lambda m: m[1] + asset + '?v=' + digest + m[2], html)
    html_path.write_text(html, encoding='utf-8')
    print(f'Built astronomical7h snapshot {version}; {len(downloads)} explicitly selected downloads.')


if __name__ == '__main__':
    main()
