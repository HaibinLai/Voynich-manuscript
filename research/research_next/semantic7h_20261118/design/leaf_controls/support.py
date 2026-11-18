"""Length/metadata support only. Never compares a label with a body word."""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, datetime, gzip, hashlib, json, re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
INPUT=ROOT.parent/'label_body/saved_v1/input.json.gz'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def lengths(word):return len(re.findall(r"@\d{3};|[a-z']",word))

def support(data,mode):
    physical=defaultdict(list)
    for p in data['pages']:physical[p['leaf']].append(p)
    leaves=[];excluded=[]
    for leaf,pp in sorted(physical.items()):
        hi={(p['H'],p['I']) for p in pp}
        qq={p['Q'] for p in pp}
        labels=Counter(len(r['units']) for p in pp for r in p['labels'])
        body=Counter(lengths(w) for p in pp for r in p['body'] for w in r['tokens'] if w is not None)
        reason=None
        if len(hi)!=1:reason='mixed_HI_physical_leaf'
        elif not all(h in set('12345') and i in set('ABCHPSTZ') for h,i in hi):reason='unknown_HI'
        elif mode=='strict_HIQ5' and (len(qq)!=1 or None in qq):reason='mixed_or_unknown_Q'
        elif not labels:reason='no_complete_singleword_image_label'
        elif not body:reason='no_retained_prose_word'
        if reason:
            excluded.append(dict(leaf=leaf,reason=reason,pages=[p['folio'] for p in pp],labels=sum(labels.values()),body=sum(body.values())))
            continue
        h,i=next(iter(hi));q=next(iter(qq)) if len(qq)==1 else None
        leaves.append(dict(leaf=leaf,H=h,I=i,Q=q,pages=[p['folio'] for p in pp],
            label_counts=dict(sorted(labels.items())),body_counts=dict(sorted(body.items())),
            label_types=dict(Counter(r['type'] for p in pp for r in p['labels'])),
            body_loci=sum(len(p['body']) for p in pp),label_loci=sum(len(p['labels']) for p in pp)))
    strata=defaultdict(list)
    for l in leaves:
        key=(l['H'],l['I'],l['Q']) if mode=='strict_HIQ5' else (l['H'],l['I'])
        strata['/'.join(key)].append(l)
    out=[]
    for key,ll in sorted(strata.items()):
        minimum=5 if mode=='strict_HIQ5' else 1
        sets=[{L for L,n in l['label_counts'].items() if n>=1 and l['body_counts'].get(L,0)>=minimum} for l in ll]
        common=sorted(set.intersection(*sets))
        valid=len(ll)>=2 and bool(common)
        details=[]
        for l in ll:
            details.append(dict(**l,retained_labels=sum(l['label_counts'].get(L,0) for L in common),
                                retained_body=sum(l['body_counts'].get(L,0) for L in common)))
        out.append(dict(stratum=key,eligible=valid,reason=None if valid else ('one_leaf' if len(ll)<2 else 'no_shared_label_and_body_length'),
            common_lengths=common,leaf_count=len(ll),leaves=details,
            retained_labels=sum(l['retained_labels'] for l in details) if valid else 0,
            retained_body=sum(l['retained_body'] for l in details) if valid else 0,
            query_length_weight='Equal across common lengths, then equal labels within each length and each physical source leaf.',
            body_length_opportunity_minimum=minimum))
    return dict(mode=mode,strata=out,excluded_leaves=excluded,
        eligible_groups=sum(g['eligible'] for g in out),
        eligible_leaves=sum(g['leaf_count'] for g in out if g['eligible']),
        eligible_labels=sum(g['retained_labels'] for g in out),
        eligible_body_words=sum(g['retained_body'] for g in out),
        no_lexical_matches_computed=True)

def main(output):
    assert not output.exists(),output
    data=json.loads(gzip.decompress(INPUT.read_bytes()))
    result=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_packet_sha256=sha(INPUT),script_sha256=sha(Path(__file__)),
        scope='Only metadata, label types, lengths and body opportunity counts. No label/body identity or new matrix score is computed.',
        versions={v:{mode:support(d,mode) for mode in ['main_HI1','strict_HIQ5']} for v,d in data.items()})
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for version,rr in result['versions'].items():
        for mode,r in rr.items():
            print(version,mode,'leaves',r['eligible_leaves'],'labels',r['eligible_labels'],'body',r['eligible_body_words'])
            for g in r['strata']:
                print(' ',g['stratum'],g['eligible'],g['leaf_count'],g['common_lengths'],g['retained_labels'],[l['leaf'] for l in g['leaves']])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'support_v1.json');a=p.parse_args();main(a.output)
