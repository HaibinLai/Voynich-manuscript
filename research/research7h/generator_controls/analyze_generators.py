"""Descriptive fixed-metric comparison; never reads confirm/reserve outcomes."""
from pathlib import Path
from collections import Counter,defaultdict
import datetime,hashlib,json,math,sys
import numpy as np

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent));import corpus
sys.path.insert(0,str(ROOT.parent.parent/'study20'))
from analyze import units,edit_le_one,plain_words
N=8000
METRICS=['h1','h2_within','h2_ratio','length_mean','length_sd','glyph_position_mi',
         'adjacent_exact','adjacent_near_distinct','random_exact','random_near_distinct',
         'exact_excess','near_excess','vocabulary','hapax_type_fraction','top10_share','zipf_slope']

def save(name,obj):
 p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def entropy(c):
 v=np.array(list(c.values()),dtype=float)
 if v.sum()==0:return 0.
 p=v/v.sum();return float(-np.sum(p*np.log2(p)))

def summarize(slots,rep,pair_seed):
 uu=[None if x is None else (x if isinstance(x,tuple) else units(x,rep)) for x in slots]
 words=[x for x in uu if x is not None]
 count=Counter(words);chars=Counter(c for w in words for c in w)
 edges=Counter((a,b) for w in words for a,b in zip(w,w[1:]));prev=Counter();nxt=Counter()
 for (a,b),v in edges.items():prev[a]+=v;nxt[b]+=v
 h2=entropy(edges)-entropy(prev); hn=entropy(nxt)
 pos=Counter();position=Counter();poschar=Counter()
 for w in words:
  for i,c in enumerate(w):
   b='single' if len(w)==1 else ('first' if i==0 else ('last' if i==len(w)-1 else 'interior'))
   pos[(b,c)]+=1;position[b]+=1;poschar[c]+=1
 mi=entropy(position)+entropy(poschar)-entropy(pos)
 lens=Counter(map(len,words));pairs=[]
 for i in range(len(uu)-1):
  if i%12!=11 and uu[i] is not None and uu[i+1] is not None:pairs.append((uu[i],uu[i+1]))
 assert pairs
 exact=sum(a==b for a,b in pairs)/len(pairs)
 near=sum(a!=b and edit_le_one(a,b) for a,b in pairs)/len(pairs)
 rng=np.random.default_rng(pair_seed)
 ij=rng.integers(0,len(words),size=(100000,2))
 rext=sum(words[i]==words[j] for i,j in ij)/len(ij)
 rnear=sum(words[i]!=words[j] and edit_le_one(words[i],words[j]) for i,j in ij)/len(ij)
 ranks=np.arange(1,min(500,len(count))+1);freq=np.array(sorted(count.values(),reverse=True)[:len(ranks)])
 slope=float(np.polyfit(np.log(ranks),np.log(freq),1)[0])
 lengths=np.array([len(w) for w in words],dtype=float)
 return dict(n=len(words),slots=len(slots),missing=sum(x is None for x in uu),adjacent_pairs=len(pairs),
  h1=entropy(chars),h2_within=h2,h2_ratio=h2/hn if hn else 0.,length_mean=float(lengths.mean()),length_sd=float(lengths.std()),
  glyph_position_mi=mi,adjacent_exact=exact,adjacent_near_distinct=near,random_exact=rext,random_near_distinct=rnear,
  exact_excess=exact-rext,near_excess=near-rnear,vocabulary=len(count),hapax_type_fraction=sum(v==1 for v in count.values())/len(count),
  top10_share=sum(v for _,v in count.most_common(10))/len(words),zipf_slope=slope,
  length_histogram={str(k):v for k,v in sorted(lens.items())},
  glyph_position_histogram={b+'|'+c:v for (b,c),v in sorted(pos.items())})

def jsd(a,b):
 keys=sorted(set(a)|set(b));p=np.array([a.get(k,0) for k in keys],float);q=np.array([b.get(k,0) for k in keys],float)
 p/=p.sum();q/=q.sum();m=(p+q)/2
 def kl(x):
  ok=x>0;return float(np.sum(x[ok]*np.log2(x[ok]/m[ok])))
 return (kl(p)+kl(q))/2

def truncate_valid(slots,n):
 out=[];seen=0
 for w in slots:
  out.append(w)
  if w is not None:seen+=1
  if seen==n:break
 assert seen==n,(seen,n)
 return out

def checks():
 s=['ab','ab','ac','bc']*30
 a=summarize(s,'eva',42);b=summarize(list(reversed(s)),'eva',42)
 for k in ['h1','h2_within','length_mean','glyph_position_mi','vocabulary','top10_share']:
  assert abs(a[k]-b[k])<1e-12,(k,a[k],b[k])
 assert jsd({'a':1},{'a':1})==0
 assert abs(jsd({'a':1},{'b':1})-1)<1e-12
 assert edit_le_one(('a','b'),('a','c')) and not edit_le_one(('a','b'),('c','d'))
 return 'Token-order invariance of shape metrics, JSD boundaries, and exact one-edit separation passed.'

def main():
 verification=checks()
 gen_checks=json.loads((ROOT/'generation_checks.json').read_text());assert [x['seed'] for x in gen_checks]==list(range(19,39))
 manifest=json.loads((ROOT.parent/'split_manifest.json').read_text()); allowed={'train','legacy','dev'}
 baselines={};panels={};selection={}
 for source in ['ZL3b-n.txt','IT2a-n.txt']:
  pages=corpus.load(source=source,splits=sorted(allowed));assert all(p['split'] in allowed for p in pages)
  for pool,splits in [('train_legacy',{'train','legacy'}),('dev',{'dev'})]:
   pp=[p for p in pages if p['split'] in splits]
   slots=[w for p in pp for line in p['lines'] for w in line['tokens']]
   available=sum(w is not None for w in slots);n=min(N,available)
   key=source.split('-')[0]+'_'+pool
   cut=truncate_valid(slots,n);panels[key]=n
   contributing=[];taken=0
   for p in pp:
    count=sum(w is not None for line in p['lines'] for w in line['tokens'])
    if count:contributing.append(p['folio']);taken+=count
    if taken>=n:break
   selection[key]=dict(folios=contributing,eligible_folios=[p['folio'] for p in pp],allowed_splits=sorted(splits),available_valid_tokens=available,scored_valid_tokens=n,first_n_in_original_order=True)
   for rep in ['eva','merged']:baselines[key+'_'+rep]=summarize(cut,rep,2026111704)
 save('manuscript_baselines.json',dict(selection=selection,metrics=baselines,excluded_splits=['confirm','reserve']))
 ns=sorted(set(panels.values()));records=[]
 latin_words=plain_words('latin_caesar.xml')[:N]
 natural={str(n):summarize(latin_words[:n],'eva',2026111704) for n in ns}
 for seed in range(19,39):
  d=ROOT/f'data/seed_{seed}'
  series={name:(d/(name+'.txt')).read_text().split() for name in ['naibbe','naibbe_space_removed','naibbe_strict_unique','timm']}
  assert all(len(s)>=N for s in series.values())
  for rep in ['eva','merged']:
   for n in ns:
    for name,values in series.items():
     words=values[:n]
     metrics=summarize(words,rep,2026111704+seed)
     row=dict(seed=seed,generator=name,representation=rep,n=n,metrics=metrics)
     row['divergences']={k:dict(length_jsd=jsd(metrics['length_histogram'],b['length_histogram']),
       glyph_position_jsd=jsd(metrics['glyph_position_histogram'],b['glyph_position_histogram']))
       for k,b in baselines.items() if k.endswith('_'+rep) and b['n']==n}
     records.append(row)
     if name=='naibbe':
      rng=np.random.default_rng(2026111705+seed)
      shuffled=list(words);rng.shuffle(shuffled)
      st=summarize(shuffled,rep,2026111704+seed)
      for k in ['h1','h2_within','length_mean','glyph_position_mi','vocabulary']:
       assert abs(st[k]-metrics[k])<1e-10,(seed,k)
      records.append(dict(seed=seed,generator='naibbe_token_shuffle',representation=rep,n=n,metrics=st))
      glyphs=[]
      for w in words:
       u=list(units(w,rep));rng.shuffle(u);glyphs.append(tuple(u))
      sg=summarize(glyphs,rep,2026111704+seed)
      assert abs(sg['h1']-metrics['h1'])<1e-10 and sg['length_histogram']==metrics['length_histogram']
      records.append(dict(seed=seed,generator='naibbe_glyph_shuffle',representation=rep,n=n,metrics=sg))
  print(json.dumps(dict(seed=seed,metric_rows=len(records))),flush=True)
 save('results.json',dict(records=records,latin_word_baseline=natural,manuscript=baselines,selection=selection))
 groups=defaultdict(list)
 for r in records:groups[(r['generator'],r['representation'],r['n'])].append(r)
 summaries=[]
 for (g,rep,n),rows in sorted(groups.items()):
  sm={k:dict(median=float(np.median([r['metrics'][k] for r in rows])),simulation_95=np.quantile([r['metrics'][k] for r in rows],[.025,.975]).tolist()) for k in METRICS}
  div={}
  for panel in rows[0].get('divergences',{}):
   div[panel]={k:dict(median=float(np.median([r['divergences'][panel][k] for r in rows])),simulation_95=np.quantile([r['divergences'][panel][k] for r in rows],[.025,.975]).tolist()) for k in ['length_jsd','glyph_position_jsd']}
  summaries.append(dict(generator=g,representation=rep,n=n,seeds=len(rows),metrics=sm,divergences=div))
 save('summary.json',dict(generators=summaries,manuscript=baselines,latin_word_baseline=natural,selection=selection,
  limitations=['External manuscript-derived fixed tables/rules; not independent validation','One Latin passage only','Artificial common reflow; no native paragraph claim','No tuning or scoring on confirm/reserve','Simulation ranges are not equivalence tests or historical confidence intervals'],
  protocol_sha256=hashlib.sha256((ROOT/'protocol.txt').read_bytes()).hexdigest(),amendment_sha256=hashlib.sha256((ROOT/'amendment_01.txt').read_bytes()).hexdigest(),
  finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),verification=verification))
 save('verification.json',dict(passed=True,checks=verification,seed_count=20,strict_unique_roundtrip_all=all(x['strict_unique']['normalized_plaintext_exact'] for x in gen_checks),
  official_truth_in_candidates_all=all(x['truth_in_candidates_rate']==1 for x in gen_checks),
  excluded_split_folios=[x['folio'] for x in manifest if x['split'] not in allowed],scored_splits=sorted(allowed)))

if __name__=='__main__':main()
