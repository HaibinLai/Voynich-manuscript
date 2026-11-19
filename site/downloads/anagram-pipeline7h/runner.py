"""Call unchanged author programs. Primary phase never reads truth/ files."""
from pathlib import Path
from collections import Counter
import argparse, datetime, hashlib, json, math, os, re, subprocess, time

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT/'upstream/hk-langid'
ENV = dict(os.environ, PERL_HASH_SEED='0', PERL_PERTURB_KEYS='0')

def save(p, obj):
    assert not p.exists(), f'Refusing to overwrite {p}'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def run_script(data, out, rid, script, args, stdin='', timeout=60):
    logdir = out/'logs'/rid
    assert not logdir.exists()
    logdir.mkdir(parents=True)
    relative_source = os.path.relpath(UPSTREAM, data)
    cmd = ['perl','-I',relative_source,f'{relative_source}/{script}',*args]
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    t = time.monotonic()
    try:
        p = subprocess.run(cmd, input=stdin, text=True, capture_output=True,
                           cwd=data, env=ENV, timeout=timeout)
        stdout, stderr, rc, status = p.stdout, p.stderr, p.returncode, 'COMPLETED'
    except subprocess.TimeoutExpired as e:
        stdout = e.stdout or ''
        stderr = e.stderr or ''
        if isinstance(stdout, bytes): stdout = stdout.decode('utf8',errors='replace')
        if isinstance(stderr, bytes): stderr = stderr.decode('utf8',errors='replace')
        rc, status = None, 'TIMEOUT'
    elapsed = time.monotonic()-t
    (logdir/'stdout.txt').write_text(stdout)
    (logdir/'stderr.txt').write_text(stderr)
    (logdir/'stdin.txt').write_text(stdin)
    receipt = {'id':rid,'script':script,'command':cmd,'cwd':'frozen data directory',
        'start_utc':started,'elapsed_seconds':elapsed,'timeout_seconds':timeout,
        'status':status,'exit_code':rc,'environment':{'PERL_HASH_SEED':'0','PERL_PERTURB_KEYS':'0'},
        'script_sha256':sha(UPSTREAM/script),'stdout_sha256':sha(logdir/'stdout.txt'),
        'stderr_sha256':sha(logdir/'stderr.txt'),'stdin_sha256':sha(logdir/'stdin.txt')}
    save(logdir/'receipt.json',receipt)
    return receipt, stdout, stderr

def language_route(data,out,cid,cipher_file,method,languages):
    receipt, stdout, stderr = run_script(data,out,f'{cid}_lang_{method}',
        'langid_probdist.pl',['-c',cipher_file,'-p','train/*.tra','-d',method,'-v'])
    result = {'run_id':receipt['id'],'method':method,'status':'FAILED','language':None,
              'scores':{},'tie':None,'author_self_report_accuracy_ignored':True}
    if receipt['status']!='COMPLETED' or receipt['exit_code']!=0:
        result['reason']='author_process_failed'; return result
    matches = re.findall(r'^RESULT:\t([^\t]+)\t([^\t]*)\t',stdout,re.M)
    ranks = re.findall(r'^\s*RANK \d+:\t([^\t]+)\t([^\n]+)',stdout,re.M)
    try: scores = {lang:float(score) for lang,score in ranks}
    except ValueError:
        result['reason']='invalid_distance'; return result
    result['scores'] = {k:(v if math.isfinite(v) else None) for k,v in scores.items()}
    if len(matches)!=1 or set(scores)!=set(languages) or not all(math.isfinite(s) for s in scores.values()):
        result['reason']='missing_or_nonfinite_candidate_scores'; return result
    selected = matches[0][1]
    best = min(scores.values())
    ties = [lang for lang in sorted(languages) if scores[lang]==best]
    if selected not in languages or selected != ties[0]:
        result['reason']='unknown_route_or_tie_contract_mismatch'; return result
    result.update(status='PASS',language=selected,tie=len(ties)>1,tied_languages=ties)
    return result

def canonical_words(cipher):
    out = []
    for w in cipher.split():
        counts = Counter(w)
        out.append(''.join(c*counts[c] for c in sorted(counts,key=lambda c:(-counts[c],c))))
    return ' '.join(out)

def recover_map(cipher,solution):
    canonical = canonical_words(cipher)
    if len(canonical)!=len(solution): raise ValueError('canonical length mismatch')
    mapping = {}
    for c,d in zip(canonical,solution):
        if c==' ' or d==' ':
            if c!=d: raise ValueError('word boundary mismatch')
            continue
        if not ('a'<=d<='z'): raise ValueError('nonalphabet output')
        if c in mapping and mapping[c]!=d: raise ValueError('inconsistent mapping')
        mapping[c]=d
    if len(set(mapping.values()))!=len(mapping): raise ValueError('noninjective mapping')
    mapped = ''.join(mapping.get(c,c) for c in cipher)
    if [sorted(w) for w in mapped.split()] != [sorted(w) for w in solution.split()]:
        raise ValueError('mapping/solution bag mismatch')
    return mapping,mapped

def decode_words(data,out,rid,language,words):
    # The fixed 20-token blocks are an implementation safeguard, not natural sentences.
    blocks = [words[i:i+20] for i in range(0,len(words),20)]
    stdin = ''.join(' '.join(block)+'\n' for block in blocks)
    receipt,stdout,stderr = run_script(data,out,rid,'alphagram_solver.pl',
        [f'models/shared/{language}/base'],stdin,60)
    decoded = stdout.split()
    lines = stdout.splitlines()
    valid = (receipt['status']=='COMPLETED' and receipt['exit_code']==0
             and len(lines)==len(blocks) and all(len(line.split())==len(block) for line,block in zip(lines,blocks))
             and all(re.fullmatch('[a-z]+',w) for w in decoded))
    return {'run_id':rid,'status':'PASS' if valid else 'FAILED',
            'input_words':words,'output_words':decoded if valid else None,
            'raw_output_word_count':len(decoded),'input_blocks':len(blocks),
            'warnings_observed':bool(stderr.strip()),
            'reason':None if valid else 'process_or_output_shape_failure'}

def core(data,out,cid,variant,language,cipher,label):
    rid = f'{cid}_{label}_{variant}'
    receipt,stdout,stderr = run_script(data,out,rid+'_maspa','maspa_solver.pl',
        ['-c',f'models/{variant}/{language}/model.config','-m','10','-b','10','-p','20'],cipher+'\n',180)
    result = {'id':cid,'variant':variant,'language':language,'label':label,
        'maspa_run_id':receipt['id'],'mapping_status':'FAILED','mapping':None,'mapped_words':None,'decoder':None,
        'warnings_observed':bool(stderr.strip())}
    if receipt['status']!='COMPLETED' or receipt['exit_code']!=0:
        result['reason']='maspa_process_failure'; return result
    lines=stdout.splitlines()
    if len(lines)!=1:
        result['reason']='maspa_output_shape_failure'; return result
    try:
        mapping,mapped = recover_map(cipher,lines[0].strip())
    except ValueError as e:
        result['reason']=str(e); return result
    result.update(mapping_status='PASS',mapping=mapping,mapped_words=mapped.split(),author_solution_words=lines[0].split())
    result['decoder']=decode_words(data,out,rid+'_viterbi',language,lines[0].split())
    return result

def main(data,out,phase,primary=None):
    assert not out.exists(), 'Runs are immutable; never overwrite a run'
    inputs=json.loads((data/'execution_inputs.json').read_text())
    for row in json.loads((data/'file_hashes.json').read_text()):
        if row['path'].startswith('truth/'):
            continue  # Never open answer bytes before the oracle's primary-result guard.
        assert sha(data/row['path'])==row['sha256'],row['path']
    out.mkdir(parents=True)
    if phase=='primary':
        # Intentionally no truth metadata is opened anywhere in this branch.
        rows=[]
        for case in inputs['cases']:
            cid=case['id']; cipher=(data/case['cipher']).read_text().strip()
            routes={m:language_route(data,out,cid,case['cipher'],m,inputs['languages']) for m in ('pattern','unigram')}
            row={'id':cid,'kind':case['kind'],'routes':routes,'pipelines':[]}
            route=routes['pattern']
            if route['status']=='PASS':
                for variant in inputs['variants']:
                    row['pipelines'].append(core(data,out,cid,variant,route['language'],cipher,'primary'))
            else:
                row['downstream_status']='NOT_EXECUTED_ROUTE_FAILED'
            rows.append(row)
            print(json.dumps({'phase':phase,'case':cid,'route':route['language'],'mapping':[p['mapping_status'] for p in row['pipelines']]}),flush=True)
            save(out/f'{cid}.json',row)
        result={'phase':phase,'rows':rows,'primary_method':'pattern','author_core_modified':False,
            'source_hashes':json.loads((ROOT/'upstream/acquisition_v1.json').read_text()),'truth_used_for_solver':False}
    else:
        assert primary is not None and (primary/'results.json').is_file()
        primary_manifest=json.loads((primary/'run_manifest.json').read_text())
        assert primary_manifest['phase']=='primary'
        assert primary_manifest['results_sha256']==sha(primary/'results.json')
        assert primary_manifest['data_manifest_sha256']==sha(data/'file_hashes.json')
        prior=json.loads((primary/'results.json').read_text())
        assert prior['phase']=='primary'
        assert [r['id'] for r in prior['rows']]==[r['id'] for r in inputs['cases']]
        for row in json.loads((data/'file_hashes.json').read_text()):
            if row['path'].startswith('truth/'):
                assert sha(data/row['path'])==row['sha256'],row['path']
        rows=[]
        for case in inputs['cases']:
            cid=case['id']; cipher=(data/case['cipher']).read_text().strip()
            # Oracle deliberately opens truth only after primary results exist and are hash-bound.
            truth_name=cid if cid!='C01' else 'C01A'
            truth=json.loads((data/'truth'/f'{truth_name}.json').read_text())
            language=truth['language']
            pr=next(r for r in prior['rows'] if r['id']==cid)
            pipelines=[]
            for variant in inputs['variants']:
                old=next((r for r in pr['pipelines'] if r['variant']==variant and r['language']==language),None)
                if old is not None:
                    pipelines.append({'reused_primary_result':True,'original_primary_case':cid,**old,'label':'oracle_language'})
                else:
                    pipelines.append(core(data,out,cid,variant,language,cipher,'oracle_language'))
            mapped=''.join(truth['decryption'].get(c,c) for c in cipher).split()
            truekey=decode_words(data,out,cid+'_oracle_truekey_viterbi',language,mapped)
            row={'id':cid,'oracle_language':language,'pipelines':pipelines,'oracle_truekey_decoder':truekey}
            rows.append(row); save(out/f'{cid}.json',row)
            print(json.dumps({'phase':phase,'case':cid,'truekey_decoder':truekey['status']}),flush=True)
        result={'phase':phase,'rows':rows,'primary_results_sha256':sha(primary/'results.json'),'oracle_diagnostics_not_primary_results':True}
    save(out/'results.json',result)
    save(out/'run_manifest.json',{'phase':phase,'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'data_manifest_sha256':sha(data/'file_hashes.json'),'runner_sha256':sha(Path(__file__)),
        'results_sha256':sha(out/'results.json'),'files':[{'path':str(p.relative_to(out)),'sha256':sha(p)} for p in sorted(out.rglob('*')) if p.is_file()]})

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--data',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--phase',required=True,choices=['primary','oracle'])
    ap.add_argument('--primary',type=Path)
    a=ap.parse_args()
    main(a.data.resolve(),a.out.resolve(),a.phase,a.primary.resolve() if a.primary else None)
