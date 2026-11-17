"""Independent scalar replay from saved contexts; does not reopen confirm/reserve."""
from pathlib import Path
from collections import Counter,defaultdict
from functools import lru_cache
import datetime,hashlib,json,math,sys
import numpy as np
P=Path(__file__).resolve().parent;sys.path.insert(0,str(P.parent));import corpus
BOS='<BOS>';EOS='<EOS>';UNK='<UNK>'

class ScalarLM:
 def __init__(self,words,alphabet,M):
  self.alphabet=set(alphabet);self.M=M;self.vocab=self.alphabet|{EOS}|({UNK} if M else set());self.count=defaultdict(Counter);self.total=Counter();self.memo={}
  for word in words:
   h=(BOS,)*3
   for c in tuple(word)+(EOS,):
    for n in range(4):
     key=h[-n:] if n else ();self.count[key][c]+=1;self.total[key]+=1
    h=(h+(c,))[-3:]
 def prob(self,h,c):
  key=(h,c)
  if key not in self.memo:
   lower=self.prob(h[1:],c) if h else 1/len(self.vocab)
   self.memo[key]=(self.count[h][c]+100*lower)/(self.total[h]+100)
  return self.memo[key]
 def full(self,word):
  h=(BOS,)*3;lp=-math.log2(1-self.prob(h,EOS))
  for c in word:
   mapped=c if c in self.alphabet else UNK
   lp+=math.log2(self.prob(h,mapped))
   if mapped==UNK:lp-=math.log2(self.M)
   h=(h+(mapped,))[-3:]
  lp+=math.log2(self.prob(h,EOS));return 2**lp


def main():
 findings=[]
 for name in ('ZL_EVA','ZL_merged','IT_EVA'):
  result=json.loads((P/'runs'/f'{name}.json').read_text());config=json.loads((P/result['config_path']).read_text());rep=result['representation']
  raw=corpus.load(result['task']['source'],splits=['train','legacy'])
  assert all(p['split'] in ('train','legacy') for p in raw)
  train=[]
  for page in raw:
   for line in page['lines']:
    for j,t in enumerate(line['tokens']):
     if t:train.append(dict(word=tuple(corpus.units(t,rep)),hand=page['metadata'].get('H','?'),position='paragraph_first' if j==0 and line['paragraph_start'] else 'line_first' if j==0 else 'other'))
  A=set(config['alphabet']);M=config['escape_size'];classes=tuple(sorted(A|({UNK} if M else set())))
  glob=ScalarLM([r['word'] for r in train],A,M)
  hands={h:ScalarLM([r['word'] for r in train if r['hand']==h],A,M) for h in {r['hand'] for r in train}}
  positions={s:ScalarLM([r['word'] for r in train if r['position']==s],A,M) for s in {r['position'] for r in train}}
  @lru_cache(maxsize=50000)
  def distribution(source,rho):
   paths=defaultdict(float);L=len(source);paths[source]+=rho
   for i in range(L):paths[source[:i]+source[i+1:]]+=(1-rho)/(3*L)
   for i in range(L+1):
    for c in classes:paths[source[:i]+(c,)+source[i:]]+=(1-rho)/(3*(L+1)*len(classes))
   for i in range(L):
    for c in classes:
     if c!=source[i]:paths[source[:i]+(c,)+source[i+1:]]+=(1-rho)/(3*L*(len(classes)-1))
   paths.pop((),None);Z=math.fsum(paths.values())
   assert abs(Z-(1-(1-rho)/3 if L==1 else 1))<1e-12
   for w in paths:paths[w]/=Z
   assert abs(math.fsum(paths.values())-1)<1e-12
   return dict(paths)
  rows=json.loads((P/result['targets_path']).read_text());stored=np.load(P/result['scores_path']);lookup={(r['folio'],r['line'],r['slot']):tuple(r['word']) for r in rows}
  worst=0.;sources=0;unknown=0;replayed={k:[] for k in stored.files}
  for i,row in enumerate(rows):
   word=tuple(row['word']);target=tuple(c if c in A else UNK for c in word);u=sum(c not in A for c in word);unknown+=u
   B=math.fsum(w*model.full(word) for w,model in zip(config['baseline_weights'],[glob,hands.get(row['hand'],glob),positions.get(row['position'],glob)]))
   replayed['base'].append(math.log2(B))
   for s in row['H']+[s for vv in row['V'].values() for s in vv]:
    coord=tuple(s['coord']);assert coord[0]==row['folio'] and coord[1:]<(row['line'],row['slot'])
    assert lookup[coord]==tuple(s['word']) and set(s['word'])<=A;sources+=1
   for model,cfg in config['selected'].items():
    family,k,r,rho,lam=(cfg[x] for x in ('family','k','r','rho','weight'))
    channels=[]
    candidates=[]
    if family in ('H','HV'):candidates.append(row['H'][-k:])
    if family in ('V','HV'):candidates.append(row['V'][str(r)])
    for ss in candidates:
     if ss:
      probs=[]
      for s in ss:
       source=tuple(s['word']);q=float(source==target) if rho==1 else distribution(source,rho).get(target,0.)
       probs.append(q/(M**u if u else 1))
      channels.append(math.fsum(probs)/len(probs))
    C=math.fsum(channels)/len(channels) if channels else B
    replayed[model].append(math.log2((1-lam)*B+lam*C))
  for model,values in replayed.items():
   diff=float(np.max(np.abs(np.asarray(values)-stored[model])));worst=max(worst,diff);assert diff<1e-11,(name,model,diff)
  assert unknown==result['unknown_units']
  findings.append(dict(name=name,targets=len(rows),checked_source_references=sources,max_absolute_log2_error=worst,escape_units=unknown,
   direct_scalar_replay=True,explicit_edit_paths_summed=True,confirm_reloaded=False,reserve_requested=False))
  distribution.cache_clear()
 output=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),runs=findings,all_passed=True,
   method='Rebuild only training counts; read frozen target/context artifacts; independently enumerate edit outputs and scalar probability sums. No development search or new confirm load.')
 (P/'replay_verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(output,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
