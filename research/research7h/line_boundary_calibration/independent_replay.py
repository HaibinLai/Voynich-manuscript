"""Independent scalar replay of synthetic records; never import the observer."""
from collections import defaultdict
from pathlib import Path
import argparse,datetime,gzip,hashlib,json,math
import numpy as np

HERE=Path(__file__).resolve().parent


def keys(row, conditioned, x):
    h=row['hand'];s=row['section'];n=min(10,row['previous_length'])
    rest=[('hs',h,s),('tl',h,s,0),('pl',h,s,0,n),('position',h,s,0,n,row['position_bin'],row['paragraph_line'])]
    return [()]+([('context',x)]+[k+(x,) for k in rest] if conditioned else rest)


class Scalar:
    def __init__(self,geometry,x,y,alpha,conditioned):
        self.a=alpha;self.conditioned=conditioned;self.tables={}
        for row,xx,yy in zip(geometry,x,y):
            for k in keys(row,conditioned,int(xx)):
                if k not in self.tables:self.tables[k]=[0,0,0,0,0]
                self.tables[k][int(yy)]+=1;self.tables[k][4]+=1

    def probability(self,row,x,y):
        q=.25
        for k in keys(row,self.conditioned,x):
            if k in self.tables:
                v=self.tables[k];q=(v[y]+self.a*q)/(v[4]+self.a)
        return q


def joint_oracle(rho,permutation):
    p=[.55,.25,.15,.05];joint=[[0.]*4 for _ in range(4)]
    for x in range(4):
        for raw_y in range(4):
            joint[x][permutation[raw_y]]=p[x]*((1-rho)*p[raw_y]+rho*(x==raw_y))
    py=[math.fsum(row[y] for row in joint) for y in range(4)]
    mi=math.fsum(joint[x][y]*math.log2(joint[x][y]/(p[x]*py[y])) for x in range(4) for y in range(4))
    h0=-math.fsum(q*math.log2(q) for q in py)
    h1=-math.fsum(joint[x][y]*math.log2(joint[x][y]/p[x]) for x in range(4) for y in range(4))
    assert abs(math.fsum(map(math.fsum,joint))-1)<1e-14 and abs(h0-h1-mi)<1e-14
    return joint,py,mi,h0,h1


def aggregate(rows,values):
    pp=defaultdict(list);leafmap={}
    for r,v in zip(rows,values):pp[r['folio']].append(float(v));leafmap[r['folio']]=r['leaf']
    ll=defaultdict(list)
    for page,v in pp.items():ll[leafmap[page]].append(math.fsum(v)/len(v))
    return math.fsum(math.fsum(v)/len(v) for v in ll.values())/len(ll)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--run',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();assert not args.output.exists()
    run=args.run;complete=json.loads((run/'complete.json').read_text());assert complete['all_passed'] and len(complete['cases'])==60
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    receipt=json.loads((run/'execution_receipt.json').read_text())
    freeze=json.loads((HERE/'freeze.json').read_text())
    assert receipt['mode']=='synthetic_only' and receipt['freeze_sha256']==digest(HERE/'freeze.json')
    for item in freeze['files']:
        assert digest(HERE/item['path'])==item['sha256'],item['path']
    skeleton=json.loads(gzip.decompress((HERE/'skeleton.json.gz').read_bytes()))
    train=skeleton['train_legacy']['rows'];targets=skeleton['dev']['rows'];findings=[]
    for entry in complete['cases']:
        casepath=run/entry['path'];assert digest(casepath)==entry['sha256'];case=json.loads(casepath.read_text())
        assert digest(run/case['synthetic_path'])==case['synthetic_sha256']
        assert digest(run/case['score_path'])==case['scores_sha256']
        data=np.load(run/case['synthetic_path']);saved=np.load(run/case['score_path']);models={}
        for name,cfg in case['configs'].items():
            domain='A' if name=='source' else 'B';pi=[2,3,0,1] if name=='target_shift' else [0,1,2,3]
            ys=np.array(pi)[data[domain+'_y']]
            models[name]=(Scalar(train,data[domain+'_x'],ys,cfg['base_alpha'],False),
                          Scalar(train,data[domain+'_x'],ys,cfg['alpha'],True),cfg['weight'])
            bg=min(cfg['base_grid'],key=lambda p:(p[0],-p[1]));assert bg[1]==cfg['base_alpha']
            fg=min(cfg['feature_grid'],key=lambda p:(p['loss'],p['weight'],-p['alpha']))
            assert (fg['alpha'],fg['weight'])==(cfg['alpha'],cfg['weight'])
        errors={};identities=[]
        for row_result in case['results']:
            shift=row_result['shift'];mode=row_result['mode'];pi=[0,1,2,3] if shift=='identity' else [2,3,0,1]
            fit='source' if mode=='source_transport' else 'target_'+shift;base,child,w=models[fit]
            joint,py,mi,h0,h1=joint_oracle(case['rho'],pi)
            assert abs(mi-row_result['oracle_mutual_information_bits'])<1e-13
            vals={k:[] for k in ('base_bits','model_bits','expected_base_bits','expected_model_bits')}
            for r,x,yy in zip(targets,data['T_x'],data['T_y']):
                x=int(x);y=pi[int(yy)];b=[base.probability(r,x,z) for z in range(4)]
                q=[[(1-w)*b[z]+w*child.probability(r,t,z) for z in range(4)] for t in range(4)]
                assert abs(math.fsum(b)-1)<1e-12 and all(abs(math.fsum(v)-1)<1e-12 for v in q)
                eb=-math.fsum(py[z]*math.log2(b[z]) for z in range(4))
                em=-math.fsum(joint[t][z]*math.log2(q[t][z]) for t in range(4) for z in range(4))
                kl0=math.fsum(py[z]*math.log2(py[z]/b[z]) for z in range(4))
                kl1=math.fsum(joint[t][z]*math.log2(joint[t][z]/([.55,.25,.15,.05][t]*q[t][z])) for t in range(4) for z in range(4))
                identities.append(abs((eb-em)-(mi+kl0-kl1)))
                vals['base_bits'].append(-math.log2(b[y]));vals['model_bits'].append(-math.log2(q[x][y]))
                vals['expected_base_bits'].append(eb);vals['expected_model_bits'].append(em)
            prefix=shift+'__'+mode
            for name,v in vals.items():errors[prefix+'__'+name]=float(np.max(np.abs(np.asarray(v)-saved[prefix+'__'+name])))
            for suffix,after,before in [('mean_leaf_gain','model_bits','base_bits'),('mean_leaf_expected_gain','expected_model_bits','expected_base_bits')]:
                gain=[a-b for a,b in zip(vals[before],vals[after])]
                assert abs(aggregate(targets,gain)-row_result[suffix])<1e-11
        assert max(errors.values())<1e-10 and max(identities)<1e-12
        findings.append(dict(seed=case['seed'],rho=case['rho'],max_error=max(errors.values()),
                             exact_MI_KL_identity_max_error=max(identities),conditions=4))
    result=dict(passed=True,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        cases=len(findings),conditions=sum(x['conditions'] for x in findings),findings=findings,
        independent_scalar_counts=True,oracle_enumerated_exactly=True,selection_grid_minima_checked=True,
        inner_fold_grid_probabilities_not_independently_recomputed=True,
        source_summary_sha256=digest(run/'summary.json'),source_complete_sha256=digest(run/'complete.json'),
        synthetic_geometry_sha256=digest(HERE/'skeleton.json.gz'),replay_code_sha256=digest(Path(__file__)),
        real_endpoint_glyphs_used=False,manuscript_target_scoring=False,reserve_loaded=False)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    print(json.dumps(dict(passed=True,cases=len(findings),max_error=max(x['max_error'] for x in findings))))


if __name__=='__main__':main()
