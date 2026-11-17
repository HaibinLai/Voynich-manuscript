"""Normalized quotient-word probability times fully paid binary restoration."""
from collections import Counter,defaultdict
from functools import lru_cache
import itertools,math
import numpy as np
from reference_models import BodyLM,universe,BOS,EOS
ALPHAS=(1,5,20,100);MERGES=('FP','KT','both')

def mapping(kind,representation):
 assert kind in ('raw',)+MERGES
 d={}
 if kind in ('FP','both'):
  d['p']='f'
  if representation=='merged':d['cph']='cfh'
 if kind in ('KT','both'):
  d['t']='k'
  if representation=='merged':d['cth']='ckh'
 return d

def quotient(omega,mp):return frozenset(mp.get(c,c) for c in omega)
def transform(rows,mp):return [dict(r,word=tuple(mp.get(c,c) for c in r['word'])) for r in rows]
def role(j,n):return 'single' if n==1 else 'first' if j==0 else 'last' if j==n-1 else 'middle'

class StyleLM:
 def __init__(self,rows,omega):
  self.omega=frozenset(omega);self.alphabet=frozenset(c for r in rows for c in r['word']);assert self.alphabet<=self.omega
  self.escape_size=len(self.omega-self.alphabet)
  self.global_lm=BodyLM([tuple(r['word']) for r in rows],self.alphabet,self.omega,4,100)
  self.hands={h:BodyLM([tuple(r['word']) for r in rows if r['hand']==h],self.alphabet,self.omega,4,100) for h in sorted({r['hand'] for r in rows})}
  self.positions={s:BodyLM([tuple(r['word']) for r in rows if r['position']==s],self.alphabet,self.omega,4,100) for s in sorted({r['position'] for r in rows})}
  self.weights=None
 def components(self,rows):
  return np.asarray([[m.logp_full(tuple(r['word'])) for m in (self.global_lm,self.hands.get(r['hand'],self.global_lm),self.positions.get(r['position'],self.global_lm))] for r in rows])
 @staticmethod
 def combine(comp,weights):
  v=np.full(len(comp),-np.inf)
  for j,w in enumerate(weights):
   if w:v=np.logaddexp2(v,math.log2(w)+comp[:,j])
  return v
 def tune(self,rows):
  c=self.components(rows);grid=[]
  for g in range(5):
   for h in range(5-g):
    w=[g/4,h/4,(4-g-h)/4];grid.append(dict(weights=w,dev_bits=float(-self.combine(c,w).mean())))
  best=min(grid,key=lambda r:(r['dev_bits'],-r['weights'][0],r['weights'][1]));self.weights=tuple(best['weights']);self.grid=grid
  return best
 def scores(self,rows):return self.combine(self.components(rows),self.weights)
 def escape(self,rows):
  n=np.asarray([sum(c not in self.alphabet for c in r['word']) for r in rows]);return n,n*math.log2(self.escape_size) if self.escape_size else n.astype(float)

class Restore:
 def __init__(self,rows,mp):
  self.mp=mp;self.other={v:k for k,v in mp.items()};assert len(self.other)==len(mp)
  self.counts=[defaultdict(Counter) for _ in range(3)];self.totals=[Counter() for _ in range(3)];self.cache={}
  for r in rows:
   for label,keys in self.events(r):
    for d,key in enumerate(keys):self.counts[d][key][label]+=1;self.totals[d][key]+=1
 def events(self,r):
  w=tuple(r['word']);y=tuple(self.mp.get(c,c) for c in w)
  for j,c in enumerate(w):
   canon=y[j]
   if canon not in self.other:continue
   assert c in (canon,self.other[canon]);label=int(c!=canon)
   k0=(canon,);k1=(canon,r['hand'],r['position'],role(j,len(w)));k2=k1+(y[j-1] if j else BOS,y[j+1] if j+1<len(y) else EOS)
   yield label,(k0,k1,k2)
 def prob(self,keys,depth,alpha):
  key=(keys,depth,alpha)
  if key not in self.cache:
   p=.5
   for d in range(depth+1):p=(self.counts[d].get(keys[d],{}).get(1,0)+alpha*p)/(self.totals[d].get(keys[d],0)+alpha)
   assert 0<p<1;self.cache[key]=p
  return self.cache[key]
 def scores(self,rows,depth,alpha):
  return np.asarray([math.fsum(math.log2(p if label else 1-p) for label,keys in self.events(r) for p in [self.prob(keys,depth,alpha)]) for r in rows])
 def tune(self,rows):
  grid=[]
  for d in range(3):
   for a in ALPHAS:grid.append(dict(depth=d,alpha=a,dev_bits=float(-self.scores(rows,d,a).mean())))
  best=min(grid,key=lambda v:(v['dev_bits'],v['depth'],v['alpha']));glob=min([v for v in grid if v['depth']==0],key=lambda v:(v['dev_bits'],v['alpha']))
  self.selected=best;self.global_selected=glob;self.grid=grid;return best,glob
 def encode(self,word):
  y=tuple(self.mp.get(c,c) for c in word);labels=tuple(int(c!=z) for c,z in zip(word,y) if z in self.other);return y,labels
 def decode(self,y,labels):
  labels=iter(labels);out=[]
  for c in y:out.append(self.other[c] if next(labels) else c) if c in self.other else out.append(c)
  assert next(labels,None) is None;return tuple(out)

def verify():
 reports=[]
 for representation in ('eva','merged'):
  for kind in MERGES:
   mp=mapping(kind,representation);O=universe(representation);Y=quotient(O,mp)
   expected=(1025 if kind=='both' else 1026) if representation=='eva' else (1029 if kind=='both' else 1031)
   assert len(Y)==expected
   small={'a',*mp.keys(),*mp.values()};smallq=quotient(small,mp)
   rows=[dict(word=(next(iter(mp.values())),'a'),hand='H0',position='other')]*5
   restore=Restore(rows,mp)
   for n in range(1,4):
    for y in itertools.product(sorted(smallq),repeat=n):
     opts=[(c,restore.other[c]) if c in restore.other else (c,) for c in y];mass=0.
     for x in itertools.product(*opts):
      r=dict(word=x,hand='unseen',position='paragraph_first');enc,labels=restore.encode(x);assert enc==y and restore.decode(y,labels)==x
      mass+=2**restore.scores([r],2,5)[0]
     assert abs(mass-1)<1e-12
   # Smaller exact alphabet exercises all original preimages and one unseen unit.
   if representation=='eva' and kind=='FP':
    original={'a','f','p','x'};q=quotient(original,mp);lm=StyleLM(rows,q);lm.weights=(.25,.5,.25)
    full=0.
    for n in range(1,5):
     for x in itertools.product(sorted(original),repeat=n):
      r=dict(word=x,hand='H0',position='other');yr=transform([r],mp);full+=2**(lm.scores(yr)[0]+restore.scores([r],2,5)[0])
    body=lm.global_lm;tail=0.
    for prefix in itertools.product(sorted(q),repeat=4):
     h=body.initial_history;prob=1/body.nonempty_mass
     for c in prefix:prob*=body.actual_prob(h,c);h=body.advance(h,body.mapped(c))
     tail+=prob*(1-body.prob(h,EOS))
    assert abs(full+tail-1)<1e-10
    reports.append(dict(kind='joint_original_word_normalization',prefix_length=4,finite_word_mass=full,remaining_mass=tail,total=full+tail,unknown_original_unit='x'))
   reports.append(dict(representation=representation,merge=kind,original_omega=len(O),quotient_omega=len(Y),all_short_preimages_normalized=True,roundtrip=True))
 return reports
