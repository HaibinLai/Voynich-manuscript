# -*- coding: utf-8 -*-
"""Toy-only scalar/autograd audit of the parameter-sharing model. No manuscript reads."""
from pathlib import Path
import argparse, datetime, hashlib, importlib.util, json, math, sys, traceback

UNIVERSE = ['a','b','r','s']
COMMON = ['a','b']
WORDS = [['a'],['b','a'],['r','b'],['a','s','b'],['b']*17+['r']]
HISTORY = ['a','b','<OTHER>','<BOS>']
K = 3
F = 1+3*len(HISTORY)+17
D = F*K

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def mapped(symbol): return symbol if symbol in COMMON else '<OTHER>'
def active_features(prefix):
    history = (['<BOS>']*3+[mapped(s) for s in prefix])[-3:]
    return [0]+[1+lag*len(HISTORY)+HISTORY.index(s) for lag,s in enumerate(history)]+[1+3*len(HISTORY)+min(len(prefix),16)]
def log_probabilities(b,prefix):
    logits = [math.fsum(b[f*K+k] for f in active_features(prefix)) for k in range(K)]
    vals = logits if not prefix else [0.0]+logits
    normalizer = max(vals)+math.log(math.fsum(math.exp(z-max(vals)) for z in vals))
    return [(-math.inf if not prefix else -normalizer)]+[v-normalizer for v in logits]
def category(symbol): return 0 if symbol=='<EOS>' else COMMON.index(symbol)+1 if symbol in COMMON else 3

def penalty_matrix():
    matrix = [[float(i==j) for j in range(D)] for i in range(D)]
    for lag in range(3):
        a,b = 1+lag*len(HISTORY), 2+lag*len(HISTORY)
        for out in range(K):
            ia,ib = a*K+out,b*K+out
            matrix[ia][ia]+=5;matrix[ib][ib]+=5
            matrix[ia][ib]-=5;matrix[ib][ia]-=5
    return matrix

def scalar_terms(b,lam,with_hessian=True):
    nll=0.0;g=[0.0]*D;h=[[0.0]*D for _ in range(D)] if with_hessian else None
    for word in WORDS:
        for pos,target in enumerate(word+['<EOS>']):
            prefix=word[:pos];idx=category(target);lp=log_probabilities(b,prefix)
            nll-=lp[idx]/len(WORDS)
            q=[math.exp(v) for v in lp[1:]];features=active_features(prefix)
            for a in features:
                for k in range(K):g[a*K+k]+=(q[k]-float(idx==k+1))/len(WORDS)
            if with_hessian:
                for a in features:
                    for c in features:
                        for k in range(K):
                            for j in range(K):h[a*K+k][c*K+j]+=((q[k] if j==k else 0.0)-q[k]*q[j])/len(WORDS)
    p=penalty_matrix();pb=[math.fsum(a*c for a,c in zip(row,b)) for row in p]
    return nll+0.5*lam*math.fsum(x*y for x,y in zip(b,pb)),[x+lam*y for x,y in zip(g,pb)],nll,h

def scalar_cost(b,word):
    nats=math.fsum(-log_probabilities(b,word[:j])[category(s)] for j,s in enumerate(word+['<EOS>']))
    identity=sum(s not in COMMON for s in word)*math.log2(len(UNIVERSE)-len(COMMON))
    return nats/math.log(2)+identity

def normalization_check(b,max_length=4):
    frontier=[([],1.0)];complete=0.0;remaining=0.0
    for length in range(max_length+1):
        nxt=[]
        for prefix,mass in frontier:
            lp=log_probabilities(b,prefix)
            eos=0 if not prefix else math.exp(lp[0])
            complete+=mass*eos
            if length==max_length:remaining+=mass*(1-eos)
            else:
                for symbol in UNIVERSE:
                    probability=math.exp(lp[category(symbol)])/(2 if symbol not in COMMON else 1)
                    nxt.append((prefix+[symbol],mass*probability))
        frontier=nxt
    return dict(complete_through_length=complete,remaining_longer_mass=remaining,total=complete+remaining)

def scalar_checks():
    b=[0.04*math.sin(i+1) for i in range(D)];lam=.03
    terms=scalar_terms(b,lam)
    epsilon=1e-5;gradient_error=0.0;hessian_error=0.0
    p=penalty_matrix()
    for i in range(D):
        plus=b.copy();minus=b.copy();plus[i]+=epsilon;minus[i]-=epsilon
        op,gp,_,_=scalar_terms(plus,lam,False);om,gm,_,_=scalar_terms(minus,lam,False)
        gradient_error=max(gradient_error,abs((op-om)/(2*epsilon)-terms[1][i]))
        for j in range(D):hessian_error=max(hessian_error,abs((gp[j]-gm[j])/(2*epsilon)-(terms[3][j][i]+lam*p[j][i])))
    norm=normalization_check(b)
    assert abs(norm['total']-1)<1e-12
    assert log_probabilities(b,[])[0]==-math.inf
    assert abs(scalar_cost(b,['r','a'])-scalar_cost(b,['s','a']))<1e-14
    assert gradient_error<1e-8 and hessian_error<1e-8
    return b,lam,terms,dict(normalization=norm,gradient_central_difference_max_abs=gradient_error,
                           hessian_from_gradient_central_difference_max_abs=hessian_error,
                           first_eos_masked=True,rare_identity_fee_bits_per_occurrence=1,
                           rare_alias_costs_equal=True,long_word_exercises_position_16plus=True)

def full_checks(model_path,device,b,lam,expected):
    import numpy as np
    import torch
    torch.set_num_threads(1)
    spec=importlib.util.spec_from_file_location('audited_production_model',model_path)
    model=importlib.util.module_from_spec(spec);spec.loader.exec_module(model)
    records=[dict(word=w,folio='toy',leaf='toy') for w in WORDS]
    corpus=model.Corpus(records,COMMON,UNIVERSE,device=device)
    assert corpus.F==F and corpus.K==K
    tensor=torch.tensor(b,dtype=torch.float64,device=device)
    independent_p=torch.tensor(penalty_matrix(),dtype=torch.float64,device=device)
    p=corpus.penalty([('a','b')],10.)
    result=corpus.terms(tensor,p,lam,True)
    diffs={'penalty':float((p-independent_p).abs().max()),
           'objective':abs(float(result[0])-expected[0]),
           'gradient':float((result[1]-torch.tensor(expected[1],dtype=torch.float64,device=device)).abs().max()),
           'unpenalized_nll':abs(float(result[2])-expected[2]),
           'hessian':float((result[3]-torch.tensor(expected[3],dtype=torch.float64,device=device)).abs().max()),
           'word_costs_bits':float(np.max(np.abs(corpus.costs(tensor)-np.array([scalar_cost(b,w) for w in WORDS]))))}
    # An independent ungrouped objective; no Corpus design matrix, gradient or terms calls.
    def autograd_objective(beta):
        total=torch.zeros((),dtype=torch.float64,device=device)
        for word in WORDS:
            for pos,symbol in enumerate(word+['<EOS>']):
                logits=beta.reshape(F,K)[active_features(word[:pos])].sum(0)
                if pos==0: loss=-torch.log_softmax(logits,0)[category(symbol)-1]
                else:
                    full=torch.cat([torch.zeros(1,dtype=torch.float64,device=device),logits])
                    loss=-torch.log_softmax(full,0)[category(symbol)]
                total=total+loss/len(WORDS)
        return total+.5*lam*(beta@(independent_p@beta))
    beta=tensor.clone().requires_grad_(True)
    autodiff_g=torch.autograd.functional.jacobian(autograd_objective,beta)
    autodiff_h=torch.autograd.functional.hessian(autograd_objective,beta)
    diffs['autograd_gradient']=float((result[1]-autodiff_g).abs().max())
    diffs['autograd_hessian_penalized']=float((result[3]+lam*p-autodiff_h).abs().max())
    assert max(diffs.values())<1e-9,diffs
    h=result[3];a=h+lam*p
    df_solve=float(torch.trace(torch.linalg.solve(a,h)))
    l=torch.linalg.cholesky(a)
    whiten=torch.linalg.solve_triangular(l,h,upper=False)
    whiten=torch.linalg.solve_triangular(l,whiten.T,upper=False).T
    df_eigen=float(torch.linalg.eigvalsh((whiten+whiten.T)/2).sum())
    assert abs(df_solve-df_eigen)<1e-10
    fitted,fit_info=model.fit(corpus,p,lam)
    assert fit_info['status']=='converged',fit_info
    fitted_scalar=scalar_terms(fitted.detach().cpu().tolist(),lam)
    assert max(map(abs,fitted_scalar[1]))<=1.01e-8
    independent_df=float(torch.trace(torch.linalg.solve(torch.tensor(fitted_scalar[3],dtype=torch.float64,device=device)+lam*p,torch.tensor(fitted_scalar[3],dtype=torch.float64,device=device))))
    assert abs(independent_df-fit_info['df'])<1e-9
    _,no_steps=model.fit(corpus,p,lam,maxiter=0)
    assert no_steps['status']=='max_iterations' and 'df' not in no_steps
    solutions,path=model.match_df(corpus,[('a','b')],targets=(2.,5.,1e6))
    assert len(path['grid'])==10
    assert [f['lambda'] for f in path['grid']]==[10.**i for i in range(1,-9,-1)]
    assert 1e6 not in solutions
    for receipt in path['targets']:
        assert len(receipt['refinements'])<=12
        if receipt['matched']:
            value,selected=solutions[receipt['target']]
            assert abs(selected['df']-receipt['target'])<=receipt['tolerance']
            _,_,_,h_scalar=scalar_terms(value.detach().cpu().tolist(),selected['lambda'])
            hs=torch.tensor(h_scalar,dtype=torch.float64,device=device)
            exact_df=float(torch.trace(torch.linalg.solve(hs+selected['lambda']*p,hs)))
            assert abs(exact_df-selected['df'])<1e-8
    return dict(device=device,torch_version=torch.__version__,numpy_version=np.__version__,
                formula_max_absolute_differences=diffs,df_solve=df_solve,df_whitened_eigen_sum=df_eigen,
                df_formula_difference=abs(df_solve-df_eigen),fit=fit_info,
                selected_fit_independent_df=independent_df,zero_iteration_failure_preserved=True,
                match_df_path=path,synthetic_target_solutions=sorted(solutions),
                impossible_df_target_unmatched=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',type=Path,default=Path(__file__).with_name('model.py'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--device',default='cpu')
    parser.add_argument('--scalar-only',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('Use a fresh output directory; preserve failures.')
    args.output.mkdir(parents=True)
    report=dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),passed=False,
                checker_sha256=sha(Path(__file__)),model_sha256=sha(args.model),scalar_only=args.scalar_only,
                scope='Only fixed artificial words over a,b,r,s. No manuscript train/dev/evaluation data loaded. Full mode imports production code solely as the black-box subject of independent formula checks.',
                python_version=sys.version,exceptions=[])
    try:
        b,lam,expected,checks=scalar_checks();report['scalar_checks']=checks
        if not args.scalar_only:report['full_model_checks']=full_checks(args.model,args.device,b,lam,expected)
        report['passed']=True
    except Exception as exc:
        report['exceptions'].append(dict(type=type(exc).__name__,message=str(exc),traceback=traceback.format_exc()))
    report['completed_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (args.output/'audit_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'scalar_only':args.scalar_only,'output':str(args.output),'exceptions':report['exceptions']},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
