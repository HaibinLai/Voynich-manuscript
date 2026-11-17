# -*- coding: utf-8 -*-
"""Build an explicit public allowlist; never change frozen scientific files."""
from pathlib import Path
import datetime,hashlib,json
HERE=Path(__file__).resolve().parent
def main():
    base=['protocol.txt','prepare_skeleton.py','skeleton.json.gz','skeleton_receipt.json',
          'observer.py','run.py','independent_replay.py','verify_toy.py','toy_verification.json',
          'freeze.py','pre_run_review.json','freeze.json','synthetic_gate.json',
          'independent_verification.json','build_report.py','plot_results.py','public_replay.py',
          'REPRODUCTION.txt','研究报告.txt','decomposition.json','website_data.json',
          'public_summary.json','synthetic_transfer.png','synthetic_transfer.svg',
          'PUBLIC_EXPORT.txt','package.py','publication_attempts.json']
    if (HERE/'public_replay_verification.json').exists():base.append('public_replay_verification.json')
    files=base+[str(p.relative_to(HERE)) for folder in ['run_v1','reference_dependencies','independent_cv_audit']
                for p in (HERE/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files=sorted(set(files))
    (HERE/'PUBLIC_EXPORT.txt').write_text('Explicit public allowlist; all paths are relative to this directory.\n'+
        '\n'.join(files)+'\nartifact_manifest.json\n\nExclude __pycache__ and runtime directories. '+
        'reference_dependencies contains exact copies of three frozen external author-code/metadata files. '+
        'public_replay.py restores their original relative layout in a new workspace; freeze is unchanged.\n')
    mapping={'../boundary.py':'reference_dependencies/boundary.py',
             '../line_boundary_design/population.json':'reference_dependencies/population.json',
             '../../study20/analyze.py':'reference_dependencies/analyze.py'}
    manifest=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope='synthetic_only_saved_evidence',
        files=[dict(path=p,sha256=hashlib.sha256((HERE/p).read_bytes()).hexdigest(),bytes=(HERE/p).stat().st_size,publish=True) for p in files],
        frozen_dependencies_portability=dict(original_freeze_unchanged=True,standalone_entry='public_replay.py',external_to_vendored=mapping),
        excluded=['__pycache__','runtime output directories'])
    (HERE/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(files=len(files),bytes=sum(f['bytes'] for f in manifest['files']))))
if __name__=='__main__':main()
