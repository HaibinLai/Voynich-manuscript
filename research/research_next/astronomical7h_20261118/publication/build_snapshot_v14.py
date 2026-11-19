"""Publish delayed delivery records without claiming the original deadline was met."""
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
W = HERE.parent


def main():
    sources = [
        (W / 'closure/research_delivery_report_v1.txt', 'research-delivery-report.txt'),
        (W / 'closure/root_delivery_review_v1.json', 'root-delivery-review.json'),
        (W / 'requirements_final_audit/requirements_final_audit_v3.txt', 'requirements-final-audit.txt'),
        (W / 'requirements_final_audit/requirements_final_audit_v3.json', 'requirements-final-audit.json'),
        (W / 'requirements_final_audit/public_access_mapping_v3.json', 'evidence-public-access.json'),
        (HERE / 'live_acceptance_v13.json', 'v13-live-acceptance.json'),
        (HERE / 'browser_acceptance_v13.json', 'v13-browser-acceptance.json'),
        (HERE / 'final_prior_site_live_verification_v1.json', 'published-evidence-verification.json'),
    ]
    for path, _ in sources:
        assert path.is_file(), path
        assert b'/Users/' not in path.read_bytes(), path
        assert b'/home/' not in path.read_bytes(), path
    previous = json.loads((HERE / 'snapshot_v13.json').read_text())
    metadata = json.loads((HERE / 'snapshot_v13.json').read_text())
    metadata['window_status'] = 'awaiting_review'
    metadata['status_note'] += ' 已补交研究结果总报告、逐项证据验收与公开来源映射。科学资格不足按原停止分支报告；原时限未满足仍单列，整轮原目标未标为全部完成。'
    metadata['stages'][-1]['status'] = 'awaiting_review'
    metadata['stages'][-1]['title'] = '延期交付与逐项验收；原时限未满足'
    metadata['sections']['zodiac']['sources'][:0] = [
        {'label': '本轮研究交付、限制与下一输入缺口', 'href': 'downloads/astronomical7h/research-delivery-report.txt'},
        {'label': '原37项及后续13项逐项验收', 'href': 'downloads/astronomical7h/requirements-final-audit.txt'},
    ]
    assert metadata['findings'] == previous['findings']
    assert metadata['stages'][:-1] == previous['stages'][:-1]
    for key in set(previous['sections']) - {'zodiac'}:
        assert metadata['sections'][key] == previous['sections'][key]
    snapshot = HERE / 'snapshot_v14.json'
    snapshot.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    argv = json.loads((HERE / 'build_command_v13.json').read_text())['argv']
    argv[argv.index('--approved-metadata') + 1] = str(snapshot.relative_to(ROOT))
    for path, name in sources:
        argv += ['--approved-download', str(path.relative_to(ROOT)) + '=' + name]
    (HERE / 'build_command_v14.json').write_text(json.dumps({'argv': argv, 'scope': 'Delayed delivery evidence; original timing NOT_MET retained; no new scientific observations or scores.'}, ensure_ascii=False, indent=2) + '\n')
    subprocess.run(argv, cwd=ROOT, check=True)
    receipt = {
        'sources': [{'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'download': name} for path, name in sources],
        'scientific_findings_unchanged': True,
        'original_deadline_met': False,
        'whole_goal_complete': False,
    }
    (HERE / 'snapshot_v14_build_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
