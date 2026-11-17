"""Independent scalar replay from saved records; no manuscript parser imported."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,datetime,hashlib,json,math
import numpy as np
P=Path(__file__).resolve().parent
BOS='<BOS>';EOS='<EOS>';UNK='<UNK>'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
class Scalar:
 def __init__(self,rows,alphabet,M):
  self.A=set(alphabet);self.M=M;self.V=self.A|{EOS}|({UNK} if M else set());self.C=defaultdict(Counter);self.N=Counter();self.memo={}
  for row in rows:
   h=(BOS,)*3
   for c in tuple(row['word'])+(EOS,):
    for n in range(4):k=h[-n:] if n else ();self.C[k][c]+=1;self.N[k]+=1
    h=(h+(c,))[-3:]
 def p(self,h,c):
  if (h,c) not in self.memo:
   parent=self.p(h[1:],c) if h else 1/len(self.V);self.memo[h,c]=(self.C[h][c]+100*parent)/(self.N[h]+100)
  return self.memo[h,c]
 def full(self,w):
  h=(BOS,)*3;terms=[-math.log2(1-self.p(h,EOS))]
  for c in w:
   m=c if c in self.A else UNK;terms.append(math.log2(self.p(h,m)))
   if m==UNK:terms.append(-math.log2(self.M))
   h=(h+(m,))[-3:]
  terms.append(math.log2(self.p(h,EOS)));return 2**math.fsum(terms)

def groupmodels(rows,A,M):
 g=Scalar(rows,A,M);hands={h:Scalar([r for r in rows if r['hand']==h],A,M) for h in {r['hand'] for r in rows}};pos={s:Scalar([r for r in rows if r['position']==s],A,M) for s in {r['position'] for r in rows}};return g,hands,pos

def costs(rows,models,weights):
 g,h,p=models;return np.asarray([-math.log2(math.fsum(w*m.full(r['word']) for w,m in zip(weights,[g,h.get(r['hand'],g),p.get(r['position'],g)]))) for r in rows])

def events(row,mp):
 y=[mp.get(c,c) for c in row['word']];rev={v:k for k,v in mp.items()};n=len(y)
 for i,(x,c) in enumerate(zip(row['word'],y)):
  if c not in rev:continue
  role='single' if n==1 else 'first' if i==0 else 'last' if i==n-1 else 'middle'
  k0=(c,);k1=(c,row['hand'],row['position'],role);k2=k1+(y[i-1] if i else BOS,y[i+1] if i+1<n else EOS)
  yield int(x==rev[c]),[k0,k1,k2]

def restoration(train,test,mp,choice):
 tables=[defaultdict(lambda:[0,0]) for _ in range(3)]
 for r in train:
  for branch,keys in events(r,mp):
   for d,key in enumerate(keys):tables[d][key][branch]+=1
 alpha=choice['alpha'];depth=choice['depth'];out=[]
 for r in test:
  terms=[]
  for branch,keys in events(r,mp):
   q=.5
   for d in range(depth+1):n0,n1=tables[d][keys[d]];q=(n1+alpha*q)/(n0+n1+alpha)
   terms.append(-math.log2(q if branch else 1-q))
  out.append(math.fsum(terms))
 return np.asarray(out)

def main(kind='all'):
 findings=[]
 for path in sorted((P/'runs').glob('*.json')):
  if kind=='synthetic' and not path.name.startswith('toy_'):continue
  if kind=='manuscript' and path.name.startswith('toy_'):continue
  result=json.loads(path.read_text());cp=P/result['config_path'];assert sha(cp)==result['config_sha256'];cfg=json.loads(cp.read_text());inp=P/cfg['input_path'];assert sha(inp)==cfg['input_sha256'];train=json.loads(inp.read_text())['train'];tp=P/result['target_path'];assert sha(tp)==result['target_sha256'];test=json.loads(tp.read_text());sp=P/result['score_path'];assert sha(sp)==result['score_sha256'];saved=np.load(sp);mp=cfg['map']
  raw=costs(test,groupmodels(train,cfg['original_alphabet'],cfg['raw_escape_size']),cfg['raw_weights']);qtrain=[dict(r,word=[mp.get(c,c) for c in r['word']]) for r in train];qtest=[dict(r,word=[mp.get(c,c) for c in r['word']]) for r in test]
  q=costs(qtest,groupmodels(qtrain,cfg['quotient_alphabet'],cfg['quotient_escape_size']),cfg['quotient_weights']);rr=restoration(train,test,mp,cfg['restore_selected']);rg=restoration(train,test,mp,cfg['restore_global']);arrays=dict(base=raw,quotient=q,restoration=rr,restoration_global=rg,complete=q+rr,complete_global=q+rg)
  errs={k:float(np.max(np.abs(a-saved[k]))) for k,a in arrays.items()};assert max(errs.values())<1e-11,(path.name,errs)
  pp=defaultdict(list);ll={}
  for i,r in enumerate(test):pp[r['folio']].append(raw[i]-q[i]-rr[i]);ll[r['folio']]=r['leaf']
  leaf=defaultdict(list)
  for f,v in pp.items():leaf[ll[f]].append(math.fsum(v)/len(v))
  gain=math.fsum(math.fsum(v)/len(v) for v in leaf.values())/len(leaf);assert abs(gain-result['selected_gain']['mean_leaf_bits_saved'])<1e-11
  finding=dict(name=result['name'],merge=result['merge'],max_cost_error=max(errs.values()),tokens=len(test),gain_replayed=gain)
  if path.name.startswith('toy_'):
   # Exact selected-pair realized truth, rather than half of all-pair truth.
   exact=[]
   for r in test:
    ev=list(events(r,mp));prob=r['alias_probability']
    if result['name'].startswith('toy_correlated_'):
     seen=set();ev=[(b,keys) for b,keys in ev if not (keys[0][0] in seen or seen.add(keys[0][0]))]
    exact.append(-math.fsum(math.log2(prob if branch else 1-prob) for branch,keys in ev))
   finding['known_realized_selected_pair_bits']=float(np.mean(exact));finding['restoration_minus_exact_truth']=float(rr.mean()-np.mean(exact))
  findings.append(finding)
 out=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),scope=kind,runs=findings,all_passed=True,confirm_reloaded=False,reserve_requested=False,
  method='Independent scalar hierarchical counts, arithmetic mixture with math.fsum, separately rebuilt Bernoulli hierarchy, saved train/target records only. Raw run toy truth for one pair is half full-word truth; this replay additionally computes exact selected-pair realized truth.')
 (P/('replay_'+kind+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'scope':kind,'runs':len(findings),'max_error':max(x['max_cost_error'] for x in findings)}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scope',choices=['all','synthetic','manuscript'],default='all');args=p.parse_args();main(args.scope)
