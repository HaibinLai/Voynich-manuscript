"""Replay the independent boundary audit without replacing historical receipts."""
from pathlib import Path
import argparse
import importlib.util
import json

HERE = Path(__file__).resolve().parent

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit('Output must not exist')
    spec = importlib.util.spec_from_file_location('boundary_independent_replay', HERE/'audit.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    raw, labels = audit.read(audit.INPUT), audit.read(audit.LABELS)
    rebuilt = audit.rebuild(raw, labels)
    result = audit.audit(rebuilt, raw, labels, HERE/'run_v1')
    args.output.mkdir(parents=True)
    (args.output/'audit.json').write_text(json.dumps(result, ensure_ascii=False,
        indent=2, default=audit.serial)+'\n')
    print(result['status'], result['failure_count'], 'failures;',
          sum(result['checks_by_category'].values()), 'scalar/schema checks')
    if result['failure_count']:
        raise SystemExit(1)

if __name__ == '__main__':
    main()
