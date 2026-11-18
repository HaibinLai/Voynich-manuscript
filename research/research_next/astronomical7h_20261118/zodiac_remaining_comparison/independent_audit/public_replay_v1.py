#!/usr/bin/env python3
"""Recompute saved geometry and audit it; write only to a new output directory."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,json,hashlib,subprocess,sys
HERE=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    if args.output.exists():raise RuntimeError('Output already exists; no source or old result is overwritten.')
    out=args.output.resolve();out.mkdir(parents=True)
    started=datetime.now(timezone.utc).isoformat();steps=[]
    commands=[('rebuild',[sys.executable,'-B',str(HERE/'rebuild_v1.py'),'--output',str(out/'calculation')]),
              ('compare',[sys.executable,'-B',str(HERE/'compare_saved_v2.py'),'--calculation',str(out/'calculation/independent_expected_v1.json.gz'),'--output',str(out/'audit_report.json')])]
    for label,command in commands:
        r=subprocess.run(command,cwd=HERE,capture_output=True,text=True)
        (out/(label+'_stdout.txt')).write_text(r.stdout);(out/(label+'_stderr.txt')).write_text(r.stderr)
        steps.append({'step':label,'exit_code':r.returncode})
        if r.returncode:
            (out/'incomplete.json').write_text(json.dumps({'started_utc':started,'steps':steps,'status':'failed; outputs retained'},indent=2)+'\n')
            raise SystemExit(r.returncode)
    audited=json.loads((out/'audit_report.json').read_text())
    receipt={'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
             'all_passed':audited['all_passed'],'exact_checks':audited['exact_checks'],'differences':len(audited['differences']),
             'steps':steps,'no_primary_code_executed':True,'no_source_files_written':True,
             'original_private_source_reports_reopened':False,'new_images_or_transcription_or_semantics_measured':False,
             'files':{n:sha(out/n) for n in ['calculation/independent_expected_v1.json.gz','calculation/calculation_receipt_v1.json','audit_report.json']}}
    (out/'execution_receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'all_passed':receipt['all_passed'],'exact_checks':receipt['exact_checks'],'differences':receipt['differences']},ensure_ascii=False))

if __name__=='__main__':main()
