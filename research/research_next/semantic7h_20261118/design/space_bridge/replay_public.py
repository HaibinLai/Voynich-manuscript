#!/usr/bin/env python3
"""Safe public replay: fresh independent reconstruction, frozen adapter, new output only.

No historical script main() is invoked. Their importable frozen computational
functions are used without modifying the original published or frozen records.
"""
import argparse,datetime,gzip,hashlib,json
from pathlib import Path
import audit_numeric as numerical
import audit_compare as comparison

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
PUBLIC=HERE/'public_repro'
HISTORY=HERE/'run_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return numerical.read(p)
def dump(p,x):
    raw=(json.dumps(numerical.pack(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    p.write_bytes(gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw)
def validate_inputs():
    allow=read(PUBLIC/'allowlist_v1.json')
    for row in allow['files']:
        f=(REPO/row['path']).resolve()
        if not f.is_relative_to(REPO):raise ValueError('Allowlist entry escapes repository')
        if sha(f)!=row['sha256']:raise ValueError('Allowlist hash mismatch: '+row['path'])
    projected=read(PUBLIC/'audit_numeric_freeze.public.json')
    for relative,h in projected['files'].items():
        f=(REPO/relative).resolve()
        if not f.is_relative_to(REPO) or sha(f)!=h:raise ValueError('Projected independent freeze mismatch: '+relative)
    complete=read(HISTORY/'complete.json')
    for name,h in complete['files'].items():
        if sha(HISTORY/name)!=h:raise ValueError('Historical result hash mismatch: '+name)
    freeze=read(HISTORY/'freeze.json')
    for name,h in freeze['inputs'].items():
        if sha(REPO/name)!=h:raise ValueError('Historical input hash mismatch: '+name)
    image_base=HERE.parents[1]/'visual/crossplant'
    for name,h in freeze['image_gate']['files'].items():
        if sha(image_base/name)!=h:raise ValueError('Image review metadata hash mismatch: '+name)
    return allow,complete
def compare_main(own,raw,labels):
    """I/O orchestration only; all numerical/schema calculations use frozen adapter."""
    check=comparison.check;canon=comparison.canon;summary=[];labelmap={r['pair_id']:r for r in labels['records']}
    for version in ('ZL','IT'):
        for boundary in ('strict_space','packet_tokens'):
            key=version+'_'+boundary
            main=canon(read(HISTORY/(version+'__'+boundary+'.json.gz')));rows=own[key]['rows']
            check(key+'.ids',[r['pair_id'] for r in rows],[r['pair_id'] for r in main['candidates']])
            check(key+'.condition',boundary+'/page_HI',main['condition']);check(key+'.version',version,main['version'])
            for r,c in zip(rows,main['candidates']):
                for field in ('pair_id','fragment_id','query','source_leaf','source_folio','target_leaf','target_folio'):check(key+'.'+field,r[field],c[field])
                locs=[]
                for loc in labelmap[r['pair_id']]['label_records'][version]:
                    import re
                    locs.append({'locator':loc['locator'],'raw':loc['raw'],'words':[w for w in re.split('[.,]',re.sub('<[^>]*>','',loc['raw'])) if w]})
                check(key+'.label_loci',locs,c['label_loci'])
                donor_folios=[f for fs in r['donors'].values() for f in fs]
                check(key+'.donor_set',sorted(donor_folios),sorted(d['folio'] for d in c['donor_pages']))
                for d in c['donor_pages']:check(key+'.donor_leaf',next(l for l,fs in r['donors'].items() if d['folio'] in fs),d['leaf'])
                scores={r['target_folio']:c['target'],**{d['folio']:d['models'] for d in c['donor_pages']}}
                for folio,model_scores in scores.items():
                    for model in numerical.METHODS:
                        expected=comparison.expected_page(r,folio,model)
                        check(key+'.'+r['pair_id']+'.'+folio+'.'+model,expected,model_scores[model])
                        comparison.counts['page_model_blocks']+=1
                        comparison.counts['opportunity_windows']+=expected['n']
                        comparison.counts['hit_windows']+=expected['m']
                for model in numerical.METHODS:check(key+'.contrast.'+model,comparison.contrast(r,model),c['contrasts'][model])
            for model in numerical.METHODS:
                expected=comparison.summarize(rows,model)
                check(key+'.summary.'+model,expected,main['models'][model])
                summary.append({'version':version,'boundary':boundary,'model':model,'summary':expected})
            import re
            excluded=[]
            for r in labels['records']:
                if r['status']=='source_numbered_locator' and r['fragment_id']==110:
                    excluded.append({'pair_id':r['pair_id'],'reason':'two_locus_three_word_group_not_executed','loci':[{'locator':l['locator'],'raw':l['raw'],'words':[w for w in re.split('[.,]',re.sub('<[^>]*>','',l['raw'])) if w]} for l in r['label_records'][version]]})
            check(key+'.excluded_group',excluded,main['excluded_group'])
            comparison.inspect_inventory(read(HISTORY/('inventory__'+version+'__'+boundary+'.json.gz')),version,boundary,raw)
    check('summary_16',summary,canon(read(HISTORY/'summary_16.json')))
    check('summary_partial',summary,canon(read(HISTORY/'summary_partial.json')))
    return summary
def main(output):
    output=output.resolve()
    if output.exists():raise SystemExit('Choose a new output directory; existing output is never overwritten.')
    if output.is_relative_to(REPO):raise SystemExit('Choose an output directory outside the repository to protect historical records.')
    output.mkdir(parents=True)
    started=datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        allow,complete=validate_inputs()
        tests=numerical.numerical_toys()
        raw=read(numerical.INPUT);labels=read(numerical.LABELS)
        rebuilt=numerical.rebuild(raw,labels)
        dump(output/'reconstructed.json.gz',rebuilt)
        own=comparison.canon(numerical.pack(rebuilt))
        archived=comparison.canon(read(HERE/'audit_rebuilt_v1.json.gz'))
        comparison.check('fresh_rebuild_vs_frozen_independent_archive',own,archived)
        summary=compare_main(own,raw,labels)
        status='PASS' if not comparison.counts['differences'] else 'FAIL'
        dump(output/'summary_16.json',summary)
        receipt=dict(status=status,started_utc=started,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            scope='Fresh independent reconstruction compared with frozen independent archive and every primary opportunity, hit, rate, NA, union, contribution, inventory and summary.',
            reused_functions='Frozen independent numerical/structural core and frozen schema comparison functions; no primary scorer imported.',
            original_records_modified=False,privacy_projection='Only metadata path keys are repository-relative in the public freeze; numerical records and frozen code retain original bytes.',
            difference_count=comparison.counts['differences'],counts=dict(comparison.counts),differences=comparison.diff,
            numerical_toys=tests,allowlist_sha256=sha(PUBLIC/'allowlist_v1.json'),historical_complete_sha256=sha(HISTORY/'complete.json'),
            public_freeze_sha256=sha(PUBLIC/'audit_numeric_freeze.public.json'),replay_script_sha256=sha(Path(__file__)),
            output_files={p.name:sha(p) for p in output.iterdir() if p.is_file()})
        dump(output/'replay_receipt.json',receipt)
        print(json.dumps({'status':status,'differences':receipt['difference_count'],'page_model_blocks':comparison.counts['page_model_blocks'],'opportunity_windows':comparison.counts['opportunity_windows']},indent=2))
        if status!='PASS':raise SystemExit(1)
    except Exception as exc:
        # No machine path/traceback is written into portable evidence. Preserve type.
        dump(output/'failure.json',{'status':'failed_preserved','exception_type':type(exc).__name__,'note':'Failure details remain in the local invocation output; no historical record overwritten.'})
        raise
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
