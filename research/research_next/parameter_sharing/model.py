"""Full-original-word autoregression, convex soft fusion, exact local-curvature DF."""
import collections, math, numpy as np, torch
DTYPE=torch.float64
BOS='<BOS>'; OTHER='<OTHER>'; EOS='<EOS>'

class Corpus:
 def __init__(self, records, common, universe, device='cpu'):
  self.records=records; self.common=list(common); self.universe=list(universe)
  assert set(common)<=set(universe)
  self.labels=[EOS]+self.common+([OTHER] if len(common)<len(universe) else [])
  self.nonref=self.labels[1:]; self.K=len(self.nonref)
  self.hist=self.nonref+[BOS]; self.F=1+3*len(self.hist)+17
  self.other_fee=math.log2(len(universe)-len(common)) if OTHER in self.nonref else 0.
  self.labelid={s:i for i,s in enumerate(self.labels)}; self.histid={s:i for i,s in enumerate(self.hist)}
  self.device=device; grouped=collections.defaultdict(lambda:np.zeros(self.K+1))
  self.word_keys=[]; self.identity_fees=[]
  for rec in records:
   word=rec['word']; assert len(word)>0 and set(word)<=set(universe)
   history=[BOS]*3; keys=[]; fee=0.
   for j,s in enumerate(list(word)+[EOS]):
    mapped=s if s in self.labelid else OTHER
    assert mapped in self.labelid
    key=(min(j,16),*history); grouped[key][self.labelid[mapped]]+=1
    keys.append((key,self.labelid[mapped]))
    if mapped==OTHER: fee+=self.other_fee
    if s!=EOS: history=history[1:]+[mapped]
   self.word_keys.append(keys); self.identity_fees.append(fee)
  self.keys=sorted(grouped); self.keyid={k:i for i,k in enumerate(self.keys)}
  X=np.zeros((len(self.keys),self.F)); C=np.stack([grouped[k] for k in self.keys])
  for i,key in enumerate(self.keys):
   X[i,0]=1.; X[i,1+3*len(self.hist)+key[0]]=1.
   for h,s in enumerate(key[1:]): X[i,1+h*len(self.hist)+self.histid[s]]=1.
  self.X=torch.tensor(X,dtype=DTYPE,device=device); self.C=torch.tensor(C,dtype=DTYPE,device=device)
  self.n=len(records); self.w=self.C.sum(1)/self.n; self.Y=self.C[:,1:]/self.n
  self.first=torch.tensor([k[0]==0 for k in self.keys],device=device)
 def penalty(self,pairs,r=10.):
  Q=torch.eye(self.F,dtype=DTYPE,device=self.device)
  for a,b in pairs:
   assert a in self.common and b in self.common and a!=b
   for h in range(3):
    v=torch.zeros(self.F,dtype=DTYPE,device=self.device)
    v[1+h*len(self.hist)+self.histid[a]]=1/math.sqrt(2)
    v[1+h*len(self.hist)+self.histid[b]]=-1/math.sqrt(2)
    Q+=r*torch.outer(v,v)
  return torch.kron(Q,torch.eye(self.K,dtype=DTYPE,device=self.device))
 def probabilities(self,B):
  Z=self.X@B
  reference=torch.zeros((len(Z),1),dtype=DTYPE,device=self.device)
  reference[self.first]=-torch.inf
  logits=torch.cat((reference,Z),1)
  lp=logits-torch.logsumexp(logits,1,keepdim=True)
  return lp,lp.exp()
 def terms(self,b,P,lam,hessian=False):
  B=b.reshape(self.F,self.K); lp,p=self.probabilities(B)
  # Never multiply a masked -inf reference log probability by zero.
  nll=-(self.Y*lp[:,1:]).sum()-(self.C[~self.first,0]/self.n*lp[~self.first,0]).sum()
  Pb=P@b; obj=nll+.5*lam*(b@Pb)
  grad=(self.X.T@(self.w[:,None]*p[:,1:]-self.Y)).flatten()+lam*Pb
  if not hessian:return obj,grad,nll
  pn=p[:,1:]; XP=(self.X[:,:,None]*pn[:,None,:]).reshape(len(self.keys),-1)
  V=XP*self.w.sqrt()[:,None]; H=-(V.T@V)
  for k in range(self.K):
   rows=torch.arange(k,self.F*self.K,self.K,device=self.device)
   D=self.X.T@((self.w*pn[:,k])[:,None]*self.X)
   H[rows[:,None],rows[None,:]]+=D
  H=(H+H.T)/2
  return obj,grad,nll,H
 def costs(self,b):
  lp,_=self.probabilities(b.reshape(self.F,self.K)); arr=lp.detach().cpu().numpy()
  return np.array([-sum(arr[self.keyid[k],t] for k,t in ks)/math.log(2)+fee
       for ks,fee in zip(self.word_keys,self.identity_fees)])

def fit(corpus,P,lam,start=None,maxiter=50,gtol=1e-8):
 b=torch.zeros(corpus.F*corpus.K,dtype=DTYPE,device=corpus.device) if start is None else start.clone()
 trace=[]; status='max_iterations'
 for it in range(maxiter+1):
  obj,g,nll,H=corpus.terms(b,P,lam,True); grad=float(g.abs().max())
  gap_bound=float(g@g)/(2*lam)
  trace.append({'iteration':it,'objective':float(obj),'gradient_inf':grad,'objective_gap_upper_bound':gap_bound})
  if grad<=gtol and gap_bound<=1e-8:status='converged';break
  if it==maxiter:break
  A=H+lam*P
  try:
   L=torch.linalg.cholesky(A); step=torch.cholesky_solve(g[:,None],L)[:,0]
  except RuntimeError:
   status='cholesky_failure'; break
  decrement=float(g@step); accepted=False
  for bt in range(30):
   scale=2.**(-bt); candidate=b-scale*step
   f2,_,_=corpus.terms(candidate,P,lam)
   if float(f2)<=float(obj)-1e-4*scale*decrement:
    b=candidate;accepted=True;break
  if not accepted:status='line_search_failure';break
 out={'lambda':lam,'status':status,'iterations':it,'objective':float(obj),'gradient_inf':grad,'objective_gap_upper_bound':gap_bound,'trace':trace}
 if status=='converged':
  try:
   L=torch.linalg.cholesky(H+lam*P)
   out['df']=float(torch.trace(torch.cholesky_solve(H,L)))
   if not math.isfinite(out['df']) or not -.000001<=out['df']<=len(b)+.000001:out['status']='invalid_df'
   out['train_nll_bits_per_word_excluding_identity']=float(nll)/math.log(2)
  except RuntimeError:out['status']='df_cholesky_failure'
 return b,out

def match_df(corpus,pairs,targets=(50.,150.),r=10.):
 P=corpus.penalty(pairs,r); fits=[]; states={}; previous=None
 for power in range(1,-9,-1):
  lam=10.**power; b,info=fit(corpus,P,lam,previous); fits.append(info)
  if info['status']=='converged':states[lam]=b;previous=b
 good=[x for x in fits if x['status']=='converged']
 solutions={}; audit=[]
 for target in targets:
  tol=max(.1,.002*target)
  close=[x for x in good if abs(x['df']-target)<=tol]
  bracket=None
  for a,z in zip(fits,fits[1:]):
   if a['status']=='converged' and z['status']=='converged' and (a['df']-target)*(z['df']-target)<=0:
    bracket=(a,z);break
  chosen=max(close,key=lambda x:x['lambda']) if close else None
  steps=[]
  if chosen is None and bracket:
   a,z=bracket
   for _ in range(12):
    lam=math.sqrt(a['lambda']*z['lambda']); b,info=fit(corpus,P,lam,states[a['lambda']]); steps.append(info)
    if info['status']!='converged':break
    states[lam]=b
    if abs(info['df']-target)<=tol:chosen=info;break
    if (a['df']-target)*(info['df']-target)<=0:z=info
    else:a=info
  audit.append({'target':target,'tolerance':tol,'refinements':steps,'matched':chosen is not None,
   'selected':chosen,'initial_bracket':None if bracket is None else [x['lambda'] for x in bracket]})
  if chosen:solutions[target]=(states[chosen['lambda']],chosen)
 return solutions,{'pairs':pairs,'r':r,'grid':fits,'targets':audit,
  'grid_nonmonotone':any(b['df']<a['df']-1e-7 for a,b in zip(good,good[1:]))}

def common_units(records,minimum=20):
 c=collections.Counter(s for x in records for s in x['word']);return sorted(s for s,n in c.items() if n>=minimum)
