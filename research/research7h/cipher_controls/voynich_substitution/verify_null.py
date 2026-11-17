"""Independent checks on training-only nulls; does not load any held-out data."""
from collections import Counter,defaultdict
from experiment import ROOT,REPS,read,save,null_pages,role

def signature(pages):
    hist=Counter();mask=[]
    for p in pages:
        for li,l in enumerate(p['lines']):
            mask.append((p['folio'],li,tuple(w is None for w in l['tokens']),tuple(len(w) if w else None for w in l['tokens'])))
            for ti,w in enumerate(l['tokens']):
                if not w:continue
                key=(p['folio'],len(w),role(l,ti))
                for pos in range(0,len(w),2):hist[key+(pos,w[pos:pos+2])]+=1
    return hist,mask
out=[]
for rep in REPS:
    pages=read(ROOT/'data'/f'train_{rep}.json');before=signature(pages)
    for replicate in [0,1,198]:
        null,stats=null_pages(pages,rep,replicate);assert before==signature(null)
        again,stats2=null_pages(pages,rep,replicate);assert null==again and stats==stats2
        byrole=defaultdict(Counter)
        for p,q in zip(pages,null):
            for l,m in zip(p['lines'],q['lines']):
                for i,(w,v) in enumerate(zip(l['tokens'],m['tokens'])):
                    if w:
                        r=role(l,i);byrole[r]['tokens']+=1;byrole[r]['changed']+=int(w!=v)
        byrole={r:{**dict(c),'changed_fraction':c['changed']/c['tokens']} for r,c in byrole.items()}
        out.append({'representation':rep,'replicate':replicate,'grouped_block_frequency_exact':True,'missing_and_length_masks_exact':True,'fixed_seed_replay_exact':True,'stats':stats,'by_role':byrole})
save(ROOT/'null_verification.json',{'scope':'training only; no dev/confirm/reserve reads','results':out})
print(out[0]['stats']);print(out[0]['by_role'])
