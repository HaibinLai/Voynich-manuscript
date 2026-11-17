"""Close the authorized window after its deadline and required delivery checks.

This does not schedule work, score data, or publish anything. Run once manually;
--check-only reports readiness without changing the recorded session.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True, help='Local research7h directory')
parser.add_argument('--check-only', action='store_true')
args = parser.parse_args()
root = args.source.resolve()
session_path = root/'session.json'
session = json.loads(session_path.read_text())
now = datetime.datetime.now(datetime.timezone.utc)
deadline = datetime.datetime.fromisoformat(session['deadline_utc'].replace('Z','+00:00'))
start = datetime.datetime.fromisoformat(session['start_utc'].replace('Z','+00:00'))
checks = [
    ('publication_checks/final_public_rebuild.json', 'passed'),
    ('publication_checks/stage7_full_live_manifest.json', 'passed'),
    ('publication_checks/report_pdf_review.json', 'all_pages_visually_inspected'),
    ('concordance/independent_audit/audit_report.json', 'all_passed'),
    ('version_differences/audit_v2/audit_report.json', 'passed'),
]
receipts = []
for name, key in checks:
    data = (root/name).read_bytes()
    record = json.loads(data)
    if record.get(key) is not True:
        raise SystemExit('Required delivery check is not passed: '+name)
    receipts.append(dict(path=name, sha256=hashlib.sha256(data).hexdigest(), required_field=key))
completed = {s['stage'] for s in session['stages'] if s['status']=='complete'}
if not set(range(1,7)).issubset(completed):
    raise SystemExit('An earlier stage remains incomplete.')
if args.check_only:
    print(json.dumps(dict(required_receipts_passed=True, deadline_reached=now>=deadline,
                         seconds_until_deadline=max(0,(deadline-now).total_seconds()),
                         session_unchanged=True), indent=2))
    raise SystemExit(0)
if now < deadline:
    raise SystemExit('Original research window has not ended; no files changed.')
if session['status'] != 'active' or session['stage'] != 7:
    raise SystemExit('Expected active closing stage; refusing duplicate closure.')
receipt = dict(completed_utc=now.isoformat(), start_utc=session['start_utc'],
               original_deadline_utc=session['deadline_utc'], planned_seconds=25200,
               actual_elapsed_seconds=(now-start).total_seconds(),
               all_required_receipts_passed=True, checks=receipts,
               scientific_scoring_during_closing_stage=False, decipherment=False,
               outcome='Research and review deliverables completed; no reliable language identification or continuous plaintext.',
               final_publication_status='Closing metadata prepared; final commit and deployment verified separately.')
(root/'publication_checks/window_closure.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
session['status']='complete'
session['completed_utc']=now.isoformat()
session['updated_utc']=now.isoformat()
session['stage7_running_components']=[]
session['stage7_completed_components']=['full_live_manifest_check','closing_delivery_record','original_window_completion']
session['stages'].append(dict(stage=7,status='complete',completed_utc=now.isoformat(),
                             evidence='Original seven-hour endpoint reached; full live asset and clean rebuild receipts passed. Final metadata deployment tracked separately.'))
session['remaining_plan']='No research tasks remain in this window. Proposed next-round experiments are documented and have not been executed.'
session['next_stage_preparation']='Future plan documented; current window closed.'
session['closure_receipt']='publication_checks/window_closure.json'
session_path.write_text(json.dumps(session,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False,indent=2))
