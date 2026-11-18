"""Replay the frozen independent scorer into a fresh directory, without overwriting audits."""
from pathlib import Path
import argparse, importlib.util, json
HERE=Path(__file__).resolve().parent
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise SystemExit('Output must not exist')
    spec=importlib.util.spec_from_file_location('crossplant_independent_replay',HERE/'audit.py')
    audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    raw,labels=audit.read(audit.INPUT),audit.read(audit.LABELS)
    rebuilt=audit.rebuild(raw,labels)
    result=audit.audit(HERE/'run_v2',rebuilt,raw,labels)
    def encode(x):
        if isinstance(x,set):return sorted(x)
        if isinstance(x,audit.F):return audit.pack(x)
        raise TypeError(type(x).__name__)
    args.output.mkdir(parents=True)
    (args.output/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=encode)+'\n')
    print(result['status'],result['failure_count'],'failures;',sum(result['checks_by_category'].values()),'checks')
    if result['failure_count']:raise SystemExit(1)
if __name__=='__main__':main()
