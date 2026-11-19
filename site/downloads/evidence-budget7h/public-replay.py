#!/usr/bin/env python3
"""Public repo-root replay; output must be a new directory. No private images."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import zlib

W6=Path('research/research_next/evidence_budget7h_20261119')
W5=Path('research/research_next/hierarchical7h_20261119')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',required=True,type=Path);a=p.parse_args()
    if not (W6/'root_information_numeric_approval_v1.json').is_file():
        p.error('Run from the repository root or an exported root preserving repository-relative paths')
    if a.output_dir.exists():p.error('Output directory must be new')
    import numpy
    a.output_dir.mkdir(parents=True)
    log=[]
    def run(args,stdout_file=None):
        cmd=[sys.executable]+[str(x) for x in args]
        proc=subprocess.run(cmd,capture_output=True,text=True)
        safe=[x.replace(str(a.output_dir),'[OUTPUT]') for x in cmd[1:]]
        if proc.returncode:
            raise RuntimeError('Replay command failed: '+repr(safe)+'\n'+proc.stderr.replace(str(a.output_dir),'[OUTPUT]'))
        if stdout_file:(a.output_dir/stdout_file).write_text(proc.stdout)
        log.append({'command':['PYTHON']+safe,'exit_code':proc.returncode})
        return proc.stdout
    run([W6/'root_engine/test_artificial_v1.py','--output-dir',a.output_dir/'root_artificial'])
    run([W6/'independent_engine/artificial_v1.py','--output-dir',a.output_dir/'independent_artificial'])
    run([W6/'root_engine/run_v1.py','--input',W6/'model_input_v1.json',
         '--approval',W6/'root_information_numeric_approval_v1.json','--output-dir',a.output_dir/'root'])
    common=['--input',W6/'independent_engine/prepared_actual_v1/input_v1.json',
            '--observation',W5/'F_observation_v1/observation_v1.json',
            '--approval',W6/'root_information_numeric_approval_v1.json',
            '--artificial-receipt',W6/'independent_engine/artificial_checks_v2/receipt_v1.json']
    run([W6/'independent_engine/grouped_v1.py','run',*common,'--output-dir',a.output_dir/'independent'])
    run([W6/'compare_actual_v1.py','--root-results',a.output_dir/'root',
         '--independent-results',a.output_dir/'independent','--output',a.output_dir/'comparison.json'])
    examples=[('query_unknown_no_information.json','unknown',{}),
              ('query_F06_ideal_signature.json','unknown',{'F06':[0,0,0,0]}),
              ('query_local_certificate.json','unknown',{'F01':[2,0,2,2],'F03':[2,2,0,2],'F04':[2,1,2,2]}),
              ('query_known_g_conflict.json','terminal_region_reading',{'F03':[2,2,0,2]})]
    query_summaries=[]
    for name,regime,observations in examples:
        raw=run([W6/'independent_engine/grouped_v1.py','query',*common,
             '--results-dir',a.output_dir/'independent','--regime',regime,
             '--observations',json.dumps(observations,separators=(',',':'))],name)
        answer=json.loads(raw)
        query_summaries.append({'file':name,'sha256':sha(a.output_dir/name),'regime':regime,
              'hypothetical_observations_not_new_measurements':observations,'class':answer['class'],
              'outcome_specific_minimal_masks':answer['outcome_specific_minimal_masks']})
    comparison=json.loads((a.output_dir/'comparison.json').read_text())
    assert comparison['all_pass'] and comparison['rows_compared']==393600
    assert [x['class'] for x in query_summaries]==['MIXED','MIXED','NONE_JOINT_POSITIVE','CONFLICT']
    assert query_summaries[2]['outcome_specific_minimal_masks']==[13]
    record={'schema':'public_information_replay_run_v1','all_pass':True,
        'python_version':platform.python_version(),'numpy_version':numpy.__version__,
        'zlib_compile_version':zlib.ZLIB_VERSION,'zlib_runtime_version':zlib.ZLIB_RUNTIME_VERSION,
        'replay_script_sha256':sha(Path(__file__)),'commands':log,
        'root_manifest_sha256':sha(a.output_dir/'root/manifest.json'),
        'independent_manifest_sha256':sha(a.output_dir/'independent/manifest_v1.json'),
        'comparison_sha256':sha(a.output_dir/'comparison.json'),'query_examples':query_summaries,
        'private_images_accessed':False,'new_image_measurements':False,
        'scope':'Replay of approved ideal-information model; counts are not probabilities; query values are hypothetical.'}
    (a.output_dir/'public_replay_run_v1.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'all_pass':True,'canonical_tables_per_implementation':96,'rows_compared':393600,
                      'logical_subsets_per_regime':64,'regimes':3,'query_examples':4}))

if __name__=='__main__':main()
