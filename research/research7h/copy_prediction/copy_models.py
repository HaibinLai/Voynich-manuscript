"""Normalized past-context word prediction, with finite-universe escape."""
from collections import defaultdict
from functools import lru_cache
import itertools,math
import numpy as np
from reference_models import BodyLM,universe,UNK

RHOS=(.25,.5,.75)
LAMBDAS=(0,.025,.05,.1,.2,.4)
CONTEXTS=[('H',k,0) for k in (1,4,8)]+[('V',0,r) for r in (1,3)]+[('HV',k,r) for k in (1,4,8) for r in (1,3)]

@lru_cache(maxsize=300000)
def path_masses(source,target,alphabet_size):
    L=len(source);T=len(target)
    identity=float(source==target);delete=insert=substitute=0.
    if T==L-1:
        delete=sum(source[:i]+source[i+1:]==target for i in range(L))/L
    elif T==L+1:
        insert=sum(target[:i]+target[i+1:]==source for i in range(T))/((L+1)*alphabet_size)
    elif T==L and sum(a!=c for a,c in zip(source,target))==1:
        substitute=1/(L*(alphabet_size-1))
    return identity,(delete+insert+substitute)/3

def kernel(source,target,size,rho):
    if not target:return 0.
    identity,edit=path_masses(tuple(source),tuple(target),size)
    z=1-(1-rho)/3 if len(source)==1 else 1.
    return (rho*identity+(1-rho)*edit)/z

def exact(source,target):return float(source==target)

def make_records(pages,units,representation,alphabet):
    rows=[];omega=universe(representation)
    for p in pages:
        line_words=[]
        for line in p['lines']:
            ww=[]
            for token in line['tokens']:
                word=tuple(units(token,representation)) if token else None
                assert word is None or set(word)<=omega
                ww.append(word)
            line_words.append(ww)
        for li,(line,words) in enumerate(zip(p['lines'],line_words)):
            history=[]
            vertical_ok=False
            if li:
                previous=p['lines'][li-1]
                vertical_ok=(line.get('paragraph_known',False) and previous.get('paragraph_known',False)
                    and line.get('block')==previous.get('block')
                    and line.get('paragraph')==previous.get('paragraph')
                    and not line['paragraph_start'] and not previous.get('paragraph_end',False))
            for j,word in enumerate(words):
                if word is None:
                    history=[];continue
                mapped=tuple(c if c in alphabet else UNK for c in word)
                row=dict(folio=p['folio'],leaf=p['leaf'],line=li,slot=j,word=word,mapped=mapped,
                    unknown=sum(c not in alphabet for c in word),hand=p['metadata'].get('H','?'),
                    position='paragraph_first' if j==0 and line['paragraph_start'] else 'line_first' if j==0 else 'other',
                    H=list(history[-8:]),V={1:[],3:[]},line_slots=len(words),vertical_layout_eligible=bool(vertical_ok))
                if vertical_ok:
                    prevwords=line_words[li-1]
                    if prevwords:
                        x=j/(len(words)-1) if len(words)>1 else 0.
                        center=math.floor(x*(len(prevwords)-1)+.5)
                        for r in (1,3):
                            for slot in range(center-r//2,center+r//2+1):
                                if 0<=slot<len(prevwords):
                                    source=prevwords[slot]
                                    if source is not None and set(source)<=alphabet:
                                        row['V'][r].append(dict(word=source,coord=(p['folio'],li-1,slot)))
                for source in row['H']+[s for ss in row['V'].values() for s in ss]:
                    f,l,slot=source['coord'];assert f==p['folio'] and (l<li or (l==li and slot<j))
                rows.append(row)
                if row['unknown']:history=[]
                else:history.append(dict(word=word,coord=(p['folio'],li,j)))
    return rows

class Baseline:
    def __init__(self,train,alphabet,representation):
        self.alphabet=frozenset(alphabet);self.omega=universe(representation);self.escape_size=len(self.omega-self.alphabet)
        words=[r['word'] for r in train]
        self.global_lm=BodyLM(words,alphabet,self.omega,4,100)
        self.hands={hand:BodyLM([r['word'] for r in train if r['hand']==hand],alphabet,self.omega,4,100) for hand in sorted({r['hand'] for r in train})}
        self.positions={pos:BodyLM([r['word'] for r in train if r['position']==pos],alphabet,self.omega,4,100) for pos in sorted({r['position'] for r in train})}
        self.weights=None
    def components(self,rows):
        return np.asarray([[self.global_lm.logp_full(r['word']),self.hands.get(r['hand'],self.global_lm).logp_full(r['word']),self.positions.get(r['position'],self.global_lm).logp_full(r['word'])] for r in rows])
    def tune(self,dev):
        components=self.components(dev);options=[]
        for gi in range(5):
            for hi in range(5-gi):
                pi=4-gi-hi;weights=(gi/4,hi/4,pi/4)
                lp=self.combine(components,weights)
                options.append(dict(loss=float(-lp.mean()),weights=list(weights)))
        best=min(options,key=lambda x:(x['loss'],-x['weights'][0],x['weights'][1]))
        self.weights=tuple(best['weights']);self.tuning=options
        return self.combine(components,self.weights)
    @staticmethod
    def combine(components,weights):
        result=np.full(len(components),-np.inf)
        for i,w in enumerate(weights):
            if w:result=np.logaddexp2(result,math.log2(w)+components[:,i])
        return result
    def scores(self,rows):return self.combine(self.components(rows),self.weights)


def source_sets(row,context):
    family,k,r=context
    H=row['H'][-k:] if k else []
    V=row['V'][r] if r else []
    return H,V

def channel_prob(source_list,row,size,rho):
    if not source_list:return None
    if rho==1:return sum(exact(s['word'],row['mapped']) for s in source_list)/len(source_list)
    return sum(kernel(s['word'],row['mapped'],size,rho) for s in source_list)/len(source_list)


def copy_arrays(rows,baseline,base_scores):
    size=len(baseline.alphabet)+(baseline.escape_size>0)
    assert size>=2
    result={};available={};hits={}
    # Compute each H/V channel once; compose HV without changing candidates.
    primitives={}
    for family,k,r in CONTEXTS:
        if family=='HV':continue
        avail=np.zeros(len(rows),dtype=bool)
        for rho in (*RHOS,1):
            probs=np.zeros(len(rows));hit=np.zeros(len(rows),dtype=bool)
            for i,row in enumerate(rows):
                H,V=source_sets(row,(family,k,r));sources=H if family=='H' else V
                value=channel_prob(sources,row,size,rho)
                if value is not None:
                    avail[i]=True;probs[i]=value;hit[i]=value>0
            primitives[(family,k,r,rho)]=probs
            hits[(family,k,r,rho)]=hit
        available[(family,k,r)]=avail
    for family,k,r in CONTEXTS:
        key=(family,k,r)
        if family=='HV':
            ha=available[('H',k,0)];va=available[('V',0,r)];avail=ha|va;available[key]=avail
        else:avail=available[key]
        for rho in (*RHOS,1):
            if family=='HV':
                hp=primitives[('H',k,0,rho)];vp=primitives[('V',0,r,rho)]
                probs=(hp+vp)/np.maximum(ha.astype(int)+va.astype(int),1)
                hits[(family,k,r,rho)]=probs>0
            else:probs=primitives[(family,k,r,rho)]
            lp=np.full(len(rows),-np.inf);positive=probs>0
            lp[positive]=np.log2(probs[positive])
            if baseline.escape_size:
                lp-=np.asarray([row['unknown'] for row in rows])*math.log2(baseline.escape_size)
            lp[~avail]=base_scores[~avail]
            result[(family,k,r,rho)]=lp
    return result,available,hits


def mix_scores(base,copy,weight):
    if weight==0:return base.copy()
    return np.logaddexp2(math.log2(1-weight)+base,math.log2(weight)+copy)

def tune_copy(base,arrays):
    grid=[]
    for family,k,r in CONTEXTS:
        for rho in (*RHOS,1):
            for weight in LAMBDAS:
                loss=float(-mix_scores(base,arrays[(family,k,r,rho)],weight).mean())
                grid.append(dict(family=family,k=k,r=r,rho=rho,weight=weight,dev_bits=loss,kernel='exact' if rho==1 else 'edit'))
    def best(family,kind,k=None,r=None):
        candidates=[v for v in grid if v['family']==family and v['kernel']==kind and (k is None or v['k']==k) and (r is None or v['r']==r)]
        return dict(min(candidates,key=lambda v:(v['dev_bits'],v['weight'],-v['rho'],v['k'],v['r'])))
    hv=best('HV','edit');k,r=hv['k'],hv['r']
    selected={'edit_HV':hv,'exact_HV_matched':best('HV','exact',k,r),'edit_H_matched':best('H','edit',k,0),
        'edit_V_matched':best('V','edit',0,r),'exact_H_matched':best('H','exact',k,0),'exact_V_matched':best('V','exact',0,r),
        'edit_H_independent':best('H','edit'),'exact_HV_independent':best('HV','exact')}
    return selected,grid


def score_selected(base,arrays,selected):
    result={'base':base}
    for name,c in selected.items():
        result[name]=mix_scores(base,arrays[(c['family'],c['k'],c['r'],c['rho'])],c['weight'])
    return result


def verify_kernel():
    alphabet=('a','b',UNK);worst=0.;collisions=[]
    for L in range(1,4):
        for source in itertools.product(alphabet,repeat=L):
            for rho in RHOS:
                outputs=defaultdict(float);outputs[source]+=rho
                for i in range(L):outputs[source[:i]+source[i+1:]]+=(1-rho)/(3*L)
                for i in range(L+1):
                    for c in alphabet:outputs[source[:i]+(c,)+source[i:]]+=(1-rho)/(3*(L+1)*len(alphabet))
                for i in range(L):
                    for c in alphabet:
                        if c!=source[i]:outputs[source[:i]+(c,)+source[i+1:]]+=(1-rho)/(3*L*(len(alphabet)-1))
                outputs.pop((),None);mass=sum(outputs.values())
                total=0.
                for word,value in outputs.items():
                    direct=kernel(source,word,len(alphabet),rho);worst=max(worst,abs(direct-value/mass));total+=direct
                assert abs(total-1)<1e-12
    assert abs(kernel(tuple('aaa'),tuple('aa'),3,.25)-.25)<1e-12
    assert abs(kernel(tuple('a'),tuple('a'),3,.25)-1/3)<1e-12
    assert worst<1e-12
    # Expand UNK to two distinct legal identities; total mass remains exactly one.
    source=('a',);mapped_alphabet=('a',UNK);expanded_alphabet=('a','x','y')
    expanded=0.
    for L in (1,2):
        for word in itertools.product(expanded_alphabet,repeat=L):
            mapped=tuple(c if c=='a' else UNK for c in word)
            expanded+=kernel(source,mapped,len(mapped_alphabet),.5)/2**sum(c!='a' for c in word)
    assert abs(expanded-1)<1e-12
    return dict(kernel_mass_one=True,all_edit_paths_summed=True,single_unit_empty_deletion_conditioned=True,max_path_probability_error=worst,escape_expanded_kernel_mass=expanded)
