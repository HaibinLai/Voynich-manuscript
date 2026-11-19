"""Fixed-dose W8 copy calibration; no tuning, new support search or image work."""
from pathlib import Path
from fractions import Fraction
from copy import deepcopy
import argparse, datetime, json, platform
from exact_reference import MODELS, fraction, q
from matrix_support import (W,ROOT,OLD,INPUT,MODES,read,dump,sha,verify_inputs,verify_code_freeze,
                            packet,score_groups,old_functions,accept_counts,apply_word_change)
from copy_generator import prepare, PREFIXES, SEED_START, SEED_COUNT

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def effect_bin(effect):
    pp=effect*100
    if pp<=0:return '<=0'
    for bound,label in [(Fraction(1,100),'(0,0.01]'),(Fraction(5,100),'(0.01,0.05]'),
                        (Fraction(1,10),'(0.05,0.10]'),(Fraction(1,5),'(0.10,0.20]')]:
        if pp<=bound:return label
    return '>0.20'

def validate_zero(summary, old):
    for family in ('models','increments'):
        for m,actual in summary[family].items():
            expected=old[family][m]
            for k in ('observed','mean','excess_over_mean','min','max','p_upper'):
                assert fraction(actual[k])==fraction(expected[k]),(family,m,k)
            for k in ('assignments','tail_ge','tail_gt','ties'):
                assert actual[k]==expected[k],(family,m,k)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--version',choices=['ZL','IT'],required=True)
    ap.add_argument('--code-freeze',type=Path,required=True);a=ap.parse_args();v=a.version
    assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-11-19T21:09:19+00:00')
    input_hash=verify_inputs();code_hash=verify_code_freeze(a.code_freeze)
    assert read(W/'runs/toy.json')['pass'] and read(W/'runs/null/complete.json')['pass']
    assert read(W/'audit_A_v1.json')['status']=='PASS'
    out=W/'runs/copy'/v;out.mkdir(parents=True,exist_ok=False)
    dump(out/'started.json',{'started_utc':utc(),'version':v,'input_freeze_sha256':input_hash,
                           'code_freeze_sha256':code_hash,'python':platform.python_version(),
                           'zero_dose_is_fixed_real_background_not_the_artificial_null':True})
    data=read(INPUT)[v];selection=read(OLD/'run_v2/selection.json')['versions'][v]
    gen=prepare(v,data,selection);tokens=gen.tokens
    registry={'metadata':gen.metadata,'candidates':gen.candidates,
              'original_raw_source_reference':str(INPUT.relative_to(ROOT)),
              'original_raw_source_sha256':sha(INPUT),
              'token_index_reconstruction':'copy_generator prepare() deterministic sort retains original null slots; tokens reference immutable input, not newly transcribed text.'}
    dump(out/'candidate_registry.json.gz',registry)
    if gen.status=='INFEASIBLE':
        dump(out/'complete.json',{'status':'INFEASIBLE','completed_utc':utc(),'expected_seed_tasks':SEED_COUNT,
                                'completed_seed_tasks':0,'reason':'NO_INITIAL_FEASIBLE_CANDIDATE','detection_rate':None,
                                'CP_interval':None,'registry_sha256':sha(out/'candidate_registry.json.gz')})
        print(v,'INFEASIBLE',flush=True);return
    old=old_functions();bags,_=old.build_leaf_bags(data);counts=accept_counts(bags)
    templates={mode:packet(v,mode) for mode in MODES};baseline={}
    for mode,p in templates.items():
        summary,_=score_groups(p['groups'],p['matrix_scale']);validate_zero(summary,p['old_joint'])
        baseline[mode]={'summary':summary,'old_path':p['old_path'],'old_sha256':p['old_sha256'],
                        'matrix_scale':p['matrix_scale'],'groups':p['groups'],
                        'scope':'Zero-dose reconstruction equality check and reference reuse, not a new primary finding.'}
    dump(out/'zero_dose_reference.json.gz',baseline)
    complete=[]
    for ordinal in range(SEED_COUNT):
        # Each seed is a checkpoint. Never start another after the reserved final-review cutoff.
        assert datetime.datetime.now(datetime.timezone.utc)<datetime.datetime.fromisoformat('2026-11-19T21:09:19+00:00')
        seed=SEED_START[v]+ordinal;generated=gen.generate(seed);assert generated['status']=='COMPLETE'
        assert len(generated['events'])==64 and [x['K'] for x in generated['prefixes']]==list(PREFIXES)
        current={mode:deepcopy(p) for mode,p in templates.items()};event_offset=0;results=[]
        for prefix in generated['prefixes']:
            K=prefix['K']
            assert all(prefix['invariants'].values())
            for event in generated['events'][event_offset:K]:
                if event['status']=='NO_LEGAL_SWAP':continue
                assert event['status']=='SWAP'
                for role in ('target','donor'):
                    token=tokens[event[role+'_index']]
                    before=event['before'][role+'_word'];after=event['after'][role+'_word']
                    L=len(event['before'][role+'_units']);assert L==len(event['after'][role+'_units'])
                    for mode,p in current.items():apply_word_change(p,counts,token['leaf'],L,before,after)
            event_offset=K
            modes={}
            for mode,p in current.items():
                if K==0:
                    modes[mode]={'summary_reference':'zero_dose_reference.json.gz#/'+mode,
                                 'exact_effect_pp':q(0),'exact_effect_bin':'<=0'}
                    continue
                summary,_=score_groups(p['groups'],p['matrix_scale'])
                effects={fam:{m:q(fraction(row['excess_over_mean'])-fraction(baseline[mode]['summary'][fam][m]['excess_over_mean']))
                              for m,row in summary[fam].items()} for fam in ('models','increments')}
                effect=fraction(effects['models']['exact'])
                modes[mode]={'summary':summary,'matrix_scale':p['matrix_scale'],'groups':deepcopy(p['groups']),
                             'effects_relative_to_zero_rate_units':effects,'exact_effect_pp':q(effect*100),
                             'exact_effect_bin':effect_bin(effect)}
            results.append({'K':K,'successful_swaps':prefix['successful_swaps'],
                            'no_legal_swap_attempts':prefix['no_legal_swap_attempts'],'modes':modes})
        result={'schema':'eighth_copy_seed_result_v1','status':'COMPLETE','completed_utc':utc(),
                'version':v,'seed':seed,'ordinal':ordinal,'input_freeze_sha256':input_hash,'code_freeze_sha256':code_hash,
                'registry_sha256':sha(out/'candidate_registry.json.gz'),
                'zero_dose_reference_sha256':sha(out/'zero_dose_reference.json.gz'),
                'generator':generated,'results':results,
                'interpretation':'Simulated copying on a fixed real-text background. Does not certify object names; the nonsemantic-copy world shares precisely these observations.'}
        path=out/f'seed_{ordinal:03}.json.gz';dump(path,result)
        entry={'ordinal':ordinal,'seed':seed,'path':str(path.relative_to(ROOT)),'sha256':sha(path),'bytes':path.stat().st_size}
        complete.append(entry)
        with (out/'progress.jsonl').open('a') as f:f.write(json.dumps({'completed_utc':utc(),**entry})+'\n');f.flush()
        if ordinal%8==0 or ordinal==127:print(v,'completed',ordinal+1,'/128',flush=True)
    dump(out/'complete.json',{'status':'COMPLETE','completed_utc':utc(),'version':v,'expected_seed_tasks':SEED_COUNT,
                            'completed_seed_tasks':len(complete),'registry_sha256':sha(out/'candidate_registry.json.gz'),
                            'zero_dose_reference_sha256':sha(out/'zero_dose_reference.json.gz'),'seeds':complete,
                            'all_doses':list(PREFIXES),'conditions':list(MODES),'same_generator_for_all_models':True})
    print(v,'COMPLETE',flush=True)
if __name__=='__main__':main()
