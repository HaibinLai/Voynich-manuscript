"""Build the known-language calibration viewer from a reviewed result release."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parent.parent
WINDOW = ROOT / 'research/research_next/astronomical7h_20261118'
RUN = WINDOW / 'wind_calibration_run'
SITE = ROOT / 'site'
GH = 'https://github.com/HaibinLai/Voynich-manuscript/blob/main/research/research_next/astronomical7h_20261118/'

def read(path):
    return json.loads(path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    approval = read(RUN / 'publication_approval_v1.json')
    assert approval['numeric_audit_passed'] is True
    assert approval['scope'] == 'conditional_catalogue_with_measurement_unknowns_only'
    for relative, expected in approval['frozen_sources'].items():
        path = RUN / relative
        assert path.resolve().is_relative_to(RUN.resolve())
        assert sha(path) == expected, relative
    source = read(RUN / 'input_v1.json')
    result = read(RUN / 'results_v1.json')
    assert result['input_sha256'] == sha(RUN / 'input_v1.json')
    cases = []
    for row in result['results']:
        original = next(leaf for regime in source['regimes'] if regime['id'] == row['regime']
                        for leaf in regime['leaves'] if leaf['folio'] == row['folio'])
        labels = [{'id': label['id'], 'given_text': label['given_text'], 'catalogue_id': label['catalogue_id'],
                   'visual_id': label['visual_id'], 'raw_catalogue_field': label['source_field']['raw_catalogue_field']}
                  for label in original['labels']]
        groups = [{'id': group['id'], 'catalogue_id': group['catalogue_id'], 'visual_id': group['visual_id'],
                   'raw_catalogue_field': group['source_field']['raw_catalogue_field'], 'blocks': group['blocks']}
                  for group in original['groups']]
        assert len(labels) == len(groups) == 12 and len(row['cell_evidence']) == 144
        cases.append({'folio': row['folio'], 'regime': row['regime'], 'labels': labels, 'groups': groups,
                      'values': row['engine_output']['matrix']['values'], 'cells': row['cell_evidence'],
                      'statistics': row['engine_output']['statistics'],
                      'note': ('每页完整保留十二名称和十二说明组。f1v有12块，f2r有13块；未知内容仍在矩阵中。'
                               + (' S1只将f1v.C08的Austro按唯一明确建议展开为Austroafricus。' if row['regime'] == 'S1' else ' E0不自动采纳括注改读或拼写修正。'))})
    assert [(c['regime'], c['folio']) for c in cases] == [('E0', 'f1v'), ('E0', 'f2r'), ('S1', 'f1v'), ('S1', 'f2r')]
    downloads = {
        'input_v1.json': 'input.json', 'results_v1.json': 'results.json', 'result_freeze_v1.json': 'result-freeze.json',
        'input_contract_v1.txt': 'input-contract.txt', 'execution_protocol_v1.txt': 'execution-protocol.txt',
        'input_review/review_v1.txt': 'input-review.txt', 'input_review/review_v1.json': 'input-review.json',
        'report_v1.txt': 'report.txt', approval['numeric_audit_report']: 'numeric-audit.txt',
        approval['numeric_audit_json']: 'numeric-audit.json',
    }
    dest = SITE / 'downloads/wind-calibration'
    dest.mkdir(parents=True, exist_ok=True)
    for relative, name in downloads.items():
        raw = (RUN / relative).read_bytes()
        assert b'/Users/' not in raw
        (dest / name).write_bytes(raw)
    (dest / 'source-notice.txt').write_bytes((WINDOW / 'wind_calibration_public/SOURCE_NOTICE.txt').read_bytes())
    payload = {'schema': 'wind_calibration_view_v1', 'snapshot_utc': datetime.now(timezone.utc).isoformat(),
               'input_sha256': sha(RUN / 'input_v1.json'), 'result_sha256': sha(RUN / 'results_v1.json'),
               'findings': approval['public_findings'], 'cases': cases,
               'images': [
                   {'folio': 'f1v', 'url': 'https://ssh.thedigitalwalters.org/Data/WaltersManuscripts/W73/data/W.73/sap/W73_000004_sap.jpg',
                    'item_url': 'https://art.thewalters.org/object/W.73.1V/', 'width': 1031, 'height': 1800,
                    'caption': 'Walters W.73 f.1v，馆方1031×1800预览图；本轮另核完整1959×3420图源。两者是同一摄影的不同采样。'},
                   {'folio': 'f2r', 'url': 'https://ssh.thedigitalwalters.org/Data/WaltersManuscripts/W73/data/W.73/sap/W73_000005_sap.jpg',
                    'item_url': 'https://art.thewalters.org/object/W.73.2R/', 'width': 1006, 'height': 1800,
                    'caption': 'Walters W.73 f.2r，馆方1006×1800预览图；本轮另核完整1911×3418图源。P07小块未获完整读法。'},
               ],
               'links': [{'label': label, 'href': 'downloads/wind-calibration/' + name} for label, name in [
                   ('本轮完整结果与解释', 'report.txt'), ('全部条件输入与原字段', 'input.json'),
                   ('全部576格及来源见证', 'results.json'), ('输入与转换独立审查', 'input-review.txt'),
                   ('另一实现的逐格数值复算', 'numeric-audit.txt'), ('固定输入条件与未知政策', 'input-contract.txt'),
                   ('来源与许可说明', 'source-notice.txt')]]
                   + [{'label': '可复算的研究代码与冻结记录', 'href': GH + 'wind_calibration_run'},
                      {'label': 'Walters官方完整目录', 'href': 'https://ssh.thedigitalwalters.org/Data/WaltersManuscripts/html/W73/description.html'}]}
    content = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    assert '/Users/' not in content
    (SITE / 'data/wind-calibration.json').write_text(content)
    html_path = SITE / 'wind-calibration.html'
    html = html_path.read_text()
    version = hashlib.sha256(content.encode()).hexdigest()[:16]
    html = re.sub(r'(<meta name="wind-snapshot" content=")[^"]*(">)', lambda m: m[1] + version + m[2], html)
    for asset in ['wind-calibration.css', 'wind-calibration.js']:
        html = re.sub(r'(["\'])' + re.escape(asset) + r'(?:\?[^"\']*)?(["\'])',
                      lambda m: m[1] + asset + '?v=' + sha(SITE / asset)[:16] + m[2], html)
    html_path.write_text(html)
    print('Built conditional wind viewer', version, '4 cases, 576 cells; audited sources only.')

if __name__ == '__main__':
    main()
