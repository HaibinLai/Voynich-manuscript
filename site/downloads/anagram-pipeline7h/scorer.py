"""Truth-based measurement only, run after primary/oracle outputs are frozen."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json

def load(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def count_score(correct, total):
    return {'correct':correct,'total':total,'fraction':correct/total if total else None}
def bag(w): return ''.join(sorted(w))

def evaluate_case(truth,cipher,pipeline,decoder,condition,variant,training):
    target=truth['words']; seen=Counter(''.join(cipher)); mapping=(pipeline or {}).get('mapping')
    vocab=set(training); bags={bag(w) for w in vocab}
    row={'truth_id':truth['id'],'input_id':truth.get('input_id',truth['id']),
         'condition':condition,'variant':variant,'language':truth['language'],
         'selected_language':(pipeline or {}).get('language'),
         'coverage_reference_language':(pipeline or {}).get('language',truth['language']),
         'positive':truth.get('kind')!='nonidentifiable_twin_history',
         'word_count':len(target),'character_count':sum(seen.values()),
         'observed_character_types':len(seen),'mapping_types':None,'mapping_weighted':None,
         'word_bags':None,'exact_words':None,'decoded_words':None,
         'training_word_coverage':count_score(sum(w in vocab for w in target),len(target)),
         'training_bag_coverage':count_score(sum(bag(w) in bags for w in target),len(target)),
         'output_training_word_hit':None,'truth_words':target,
         'mapping_status':(pipeline or {}).get('mapping_status','NOT_APPLICABLE_OR_NOT_EXECUTED'),
         'decoder_status':(decoder or {}).get('status','NOT_EXECUTED'),
         'reused_primary_result':(pipeline or {}).get('reused_primary_result',False)}
    if mapping is not None:
        assert set(mapping)==set(seen)
        assert len(set(mapping.values()))==len(mapping)
        right={c for c in seen if mapping[c]==truth['decryption'][c]}
        row['mapping_types']=count_score(len(right),len(seen))
        row['mapping_weighted']=count_score(sum(seen[c] for c in right),sum(seen.values()))
        mapped=[''.join(mapping[c] for c in w) for w in cipher]
        row['word_bags']=count_score(sum(bag(a)==bag(b) for a,b in zip(mapped,target)),len(target))
    if condition=='oracle_truekey':
        row['mapping_status']='PROVIDED_TRUE_KEY_NOT_RECOVERED'
        row['word_bags']=count_score(len(target),len(target))
    if decoder and decoder['status']=='PASS':
        predicted=decoder['output_words'];assert len(predicted)==len(target)
        row['decoded_words']=predicted
        row['exact_words']=count_score(sum(a==b for a,b in zip(predicted,target)),len(target))
        row['output_training_word_hit']=count_score(sum(w in vocab for w in predicted),len(predicted))
        row['in_vocabulary_exact']=count_score(sum(a==b and b in vocab for a,b in zip(predicted,target)),sum(b in vocab for b in target))
        row['out_of_vocabulary_exact']=count_score(sum(a==b and b not in vocab for a,b in zip(predicted,target)),sum(b not in vocab for b in target))
    return row

def main(data,primary,oracle,out):
    assert not out.exists()
    for row in load(data/'file_hashes.json'):
        assert sha(data/row['path'])==row['sha256']
    for run in (primary,oracle):
        manifest=load(run/'run_manifest.json')
        assert manifest['results_sha256']==sha(run/'results.json')
        assert manifest['data_manifest_sha256']==sha(data/'file_hashes.json')
    p=load(primary/'results.json');o=load(oracle/'results.json')
    assert o['primary_results_sha256']==sha(primary/'results.json')
    inputs=load(data/'execution_inputs.json');rows=[];language_rows=[]
    for case in inputs['cases']:
        cid=case['id'];cipher=(data/case['cipher']).read_text().split()
        pr=next(r for r in p['rows'] if r['id']==cid)
        ore=next(r for r in o['rows'] if r['id']==cid)
        truth_ids=[cid] if cid!='C01' else ['C01A','C01B']
        for tid in truth_ids:
            truth=load(data/'truth'/f'{tid}.json');lang=truth['language']
            training=(data/'train'/f'udhr-{lang}.txt.tra').read_text().split()
            for cond,source in [('primary',pr),('oracle_language',ore)]:
                for variant in inputs['variants']:
                    pipe=next((r for r in source['pipelines'] if r['variant']==variant),None)
                    decoder=(pipe or {}).get('decoder')
                    model_lang=(pipe or {}).get('language',lang)
                    model_training=(data/'train'/f'udhr-{model_lang}.txt.tra').read_text().split()
                    rows.append(evaluate_case(truth,cipher,pipe,decoder,cond,variant,model_training))
            rows.append(evaluate_case(truth,cipher,None,ore['oracle_truekey_decoder'],'oracle_truekey','shared',training))
        for method,r in pr['routes'].items():
            language_rows.append({'id':cid,'positive':cid!='C01','method':method,'true_language':lang,
                'selected_language':r['language'],'status':r['status'],'correct':r['language']==lang if r['status']=='PASS' else None,
                'scores':r['scores'],'tie':r['tie']})
    groups=[]
    for condition,variant in [('primary','readme_lex'),('primary','code_countfirst'),('oracle_language','readme_lex'),('oracle_language','code_countfirst'),('oracle_truekey','shared')]:
        rr=[r for r in rows if r['positive'] and r['condition']==condition and r['variant']==variant]
        g={'condition':condition,'variant':variant,'planned_cases':len(rr),'planned_words':sum(r['word_count'] for r in rr)}
        for metric in ('mapping_types','mapping_weighted','word_bags','exact_words'):
            scored=[r[metric] for r in rr if r[metric] is not None]
            not_applicable=condition=='oracle_truekey' and metric.startswith('mapping_')
            g[metric]={'applicability':'NOT_APPLICABLE_PROVIDED_KEY' if not_applicable else 'APPLICABLE',
                'not_applicable_cases':len(rr) if not_applicable else 0,
                'scored_cases':len(scored),'failed_or_unscored_cases':0 if not_applicable else len(rr)-len(scored),
                **count_score(sum(s['correct'] for s in scored),sum(s['total'] for s in scored))}
        if condition=='oracle_truekey':
            g['word_bags']['basis']='Provided correct key and verified generation history, not recovered key performance'
        g['confirmed_exact_recovery_over_all_planned_words']=count_score(sum((r['exact_words'] or {}).get('correct',0) for r in rr),g['planned_words'])
        groups.append(g)
    result={'schema':'tenth_known_answer_scores_v1','scope':'Original author core with new training adapter; previously exposed same-book held-out-from-training cases; no manuscript or paper-score replication',
        'primary_method':'pattern','primary_variant':'readme_lex','rows':rows,'language_rows':language_rows,'groups':groups,
        'nonidentifiable_control':'C01 has exactly the same ciphertext for two different generating plaintexts; neither unique recovery nor successful semantic decipherment is established by selecting one.',
        'bindings':{'data_sha256':sha(data/'file_hashes.json'),'primary_sha256':sha(primary/'results.json'),'oracle_sha256':sha(oracle/'results.json'),'scorer_sha256':sha(Path(__file__))}}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'groups':groups,'language_rows':language_rows},ensure_ascii=False))

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    for n in ('data','primary','oracle','out'): ap.add_argument('--'+n,required=True,type=Path)
    a=ap.parse_args();main(a.data,a.primary,a.oracle,a.out)
