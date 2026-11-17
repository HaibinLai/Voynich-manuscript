"""Independent scalar replay on saved metadata pages and scored target records."""
from pathlib import Path
from collections import Counter,defaultdict
from functools import lru_cache
import argparse
import datetime
import importlib.util
import math
import re
import numpy as np
from metadata import HERE,ROOT,read,write,sha

spec=importlib.util.spec_from_file_location('independent_scalar',ROOT/'allograph_factor/replay.py')
scalar=importlib.util.module_from_spec(spec);spec.loader.exec_module(scalar)
UNK='<UNK>';BOS='<BOS>';EOS='<EOS>'


def word(token,rep):
    pattern=r'cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z\']' if rep=='merged' else r'@\d{3};|[a-z\']'
    out=tuple(re.findall(pattern,token));assert ''.join(out)==token
    return out


def train_rows(pages,rep):
    out=[]
    for p in pages:
        for li,line in enumerate(p['lines']):
            for j,t in enumerate(line['tokens']):
                if t is not None:out.append(dict(word=word(t,rep),hand=line['effective_hands'][j],
                    position='paragraph_first' if j==0 and line['paragraph_start'] else 'line_first' if j==0 else 'other'))
    return out


def compare(saved,arrays,prefix='inline__'):
    errors={k:float(np.max(np.abs(v-saved[prefix+k]))) for k,v in arrays.items()}
    assert max(errors.values())<1e-10,errors
    return errors


def copy_replay(train,rows,saved,cfg):
    A=set(cfg['alphabet']);M=cfg['escape_size'];classes=tuple(sorted(A|{UNK}))
    models=scalar.groupmodels(train,A,M)
    base=scalar.costs(rows,models,cfg['baseline_weights']);glob=scalar.costs(rows,models,[1,0,0])
    @lru_cache(maxsize=30000)
    def distribution(source,rho):
        n=len(source);p=defaultdict(float);p[source]+=rho
        for i in range(n):p[source[:i]+source[i+1:]]+=(1-rho)/(3*n)
        for i in range(n+1):
            for c in classes:p[source[:i]+(c,)+source[i:]]+=(1-rho)/(3*(n+1)*len(classes))
        for i in range(n):
            for c in classes:
                if c!=source[i]:p[source[:i]+(c,)+source[i+1:]]+=(1-rho)/(3*n*(len(classes)-1))
        p.pop((),None);z=math.fsum(p.values())
        assert abs(z-(1-(1-rho)/3 if n==1 else 1))<1e-12
        return {k:v/z for k,v in p.items()}
    arrays={'base':base,'global':glob}
    for key,cfgrow in cfg['selected'].items():
        result=[]
        for i,row in enumerate(rows):
            source_lists=[];family=cfgrow['family']
            if family in ('H','HV'):source_lists.append(row['H'][-cfgrow['k']:])
            if family in ('V','HV'):source_lists.append(row['V'][str(cfgrow['r'])])
            target=tuple(c if c in A else UNK for c in row['word']);unknown=sum(c not in A for c in row['word'])
            channels=[]
            for sources in source_lists:
                if not sources:continue
                probabilities=[]
                for source in sources:
                    sw=tuple(source['word'])
                    value=float(sw==target) if cfgrow['rho']==1 else distribution(sw,cfgrow['rho']).get(target,0.)
                    probabilities.append(value/(M**unknown if unknown else 1))
                channels.append(math.fsum(probabilities)/len(probabilities))
            bp=2**(-base[i]);cp=math.fsum(channels)/len(channels) if channels else bp
            result.append(-math.log2((1-cfgrow['weight'])*bp+cfgrow['weight']*cp))
        arrays[key]=np.asarray(result)
    return compare(saved,arrays)


def allograph_replay(train,rows,saved,name):
    arrays={}
    for kind in ('FP','KT','both'):
        cfg=read(ROOT/'allograph_factor/configs'/f'{name}_{kind}.json');mp=cfg['map']
        base=scalar.costs(rows,scalar.groupmodels(train,cfg['original_alphabet'],cfg['raw_escape_size']),cfg['raw_weights'])
        qt=[dict(r,word=[mp.get(c,c) for c in r['word']]) for r in train]
        qr=[dict(r,word=[mp.get(c,c) for c in r['word']]) for r in rows]
        q=scalar.costs(qr,scalar.groupmodels(qt,cfg['quotient_alphabet'],cfg['quotient_escape_size']),cfg['quotient_weights'])
        restoration=scalar.restoration(train,rows,mp,cfg['restore_selected'])
        rg=scalar.restoration(train,rows,mp,cfg['restore_global'])
        arrays['base']=base
        arrays.update({kind+'_'+key:value for key,value in dict(quotient=q,restoration=restoration,
            restoration_global=rg,complete=q+restoration,complete_global=q+rg).items()})
    return compare(saved,arrays)


def boundary_replay(pages,rep,train,rows,saved,name):
    suffix={'ZL_EVA':'','ZL_merged':'_merged','IT_EVA':'_IT'}[name]
    cfg=read(ROOT/'results'/f'boundary_word_confirm{suffix}_frozen_config.json')
    A=set(cfg['alphabet']);select=cfg['selected'];M=(1033 if rep=='merged' else 1027)-len(A)
    assert select['char_order']==4 and select['char_alpha']==100
    lm=scalar.Scalar(train,A,M)
    pairs=[]
    for page in pages:
        for li,line in enumerate(page['lines']):
            ts=line['tokens']
            for j in range(2,len(ts)-1,2):
                if ts[j-1] is None or ts[j] is None:continue
                a=tuple(c if c in A else UNK for c in word(ts[j-1],rep));b=tuple(c if c in A else UNK for c in word(ts[j],rep))
                pairs.append(dict(hand=line['effective_hands'][j],section=page['metadata'].get('I','?'),
                    previous_length=len(a),length=0,position_bin=min(2,3*j//(len(ts)-1)),
                    paragraph_line=int(line['paragraph_start']),last=a[-1],target=b[0]))
    def keys(r,feature):
        h,s=r['hand'],r['section'];prev=min(10,r['previous_length'])
        rest=[('hs',h,s),('tl',h,s,0),('pl',h,s,0,prev),('position',h,s,0,prev,r['position_bin'],r['paragraph_line'])]
        return [(),('context',r['last'])]+[k+(r['last'],) for k in rest] if feature else [()]+rest
    tables={}
    for feature in (False,True):
        counts=defaultdict(Counter)
        for r in pairs:
            for key in keys(r,feature):counts[key][r['target']]+=1
        tables[feature]=counts
    def prob(r,feature,alpha):
        q=1/(len(A)+1)
        for key in keys(r,feature):
            counts=tables[feature][key]
            q=(counts[r['target']]+alpha*q)/(sum(counts.values())+alpha)
        return q
    arrays={'base':[],'last':[],'target_escape':[]};setting=select['features']['last']
    for r in rows:
        target=tuple(c if c in A else UNK for c in r['word']);h=(BOS,BOS,target[0]);tail=[]
        for c in target[1:]+(EOS,):tail.append(-math.log2(lm.p(h,c)));h=(h+(c,))[-3:]
        escape=sum(c not in A for c in r['word'])*math.log2(M)
        bp=prob(r,False,select['base_alpha']);mp=(1-setting['weight'])*bp+setting['weight']*prob(r,True,setting['alpha'])
        arrays['base'].append(-math.log2(bp)+math.fsum(tail)+escape)
        arrays['last'].append(-math.log2(mp)+math.fsum(tail)+escape)
        arrays['target_escape'].append(escape)
    return compare(saved,{k:np.asarray(v) for k,v in arrays.items()})


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();assert not args.out.exists();findings=[]
    for name in ('ZL_EVA','ZL_merged','IT_EVA'):
        rep='merged' if name=='ZL_merged' else 'eva';source='IT2a-n' if name=='IT_EVA' else 'ZL3b-n'
        pages=read(HERE/'inputs'/f'{source}_train_legacy.json.gz');train=train_rows(pages,rep)
        for family in ('copy','allograph','boundary'):
            prefix=family+'_'+name;rr=read(args.run/(prefix+'_rows.json.gz'));rows=[dict(r,hand=r['inline_hand']) for r in rr]
            path=args.run/(prefix+'.npz');saved=np.load(path);receipt=read(args.run/(prefix+'.json'))
            assert sha(path)==receipt['scores_sha256']
            if family=='copy':errors=copy_replay(train,rows,saved,read(ROOT/'copy_prediction/configs'/f'{name}.json'))
            elif family=='allograph':errors=allograph_replay(train,rows,saved,name)
            else:errors=boundary_replay(pages,rep,train,rows,saved,name)
            findings.append(dict(name=name,family=family,targets=len(rows),errors=errors,max_error=max(errors.values())))
            print(prefix+' independent replay passed',flush=True)
    write(args.out,dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        all_passed=True,findings=findings,source_replay_sha256=sha(Path(__file__)),
        scalar_reference_sha256=sha(ROOT/'allograph_factor/replay.py'),
        raw_corpus_loaded=False,new_target_pages_loaded=False,reserve_loaded=False,
        method='Independent scalar hierarchical counts, arithmetic mixtures, explicit edit paths, Bernoulli restoration and scalar first-unit contexts. Saved train/target records only.'))


if __name__=='__main__':main()
