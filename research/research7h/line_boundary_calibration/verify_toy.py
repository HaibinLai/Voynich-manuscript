"""Small normalization/oracle/implementation contracts, not formal calibration."""
from pathlib import Path
import datetime,hashlib,json,math
import numpy as np
from observer import Conditional,contexts,truth,select
from independent_replay import Scalar,joint_oracle

HERE=Path(__file__).resolve().parent
def main():
    rows=[dict(folio='toy'+str(i%6),leaf='toy'+str(i%6),hand=str(i%2),section='toy',
               previous_length=1+i%5,length=0,position_bin=0,paragraph_line=0,x=i%4,y=(i//4)%4) for i in range(96)]
    worst=0.
    for alpha in (1,5,20,100,500):
        for feature in (False,True):
            v=Conditional(rows,alpha,feature);s=Scalar(rows,[r['x'] for r in rows],[r['y'] for r in rows],alpha,feature)
            for row in rows[:12]+[dict(rows[0],hand='unseen',section='unseen')]:
                for x in range(4):
                    q=v.distribution(contexts(row,feature,x))
                    assert abs(float(q.sum())-1)<1e-12
                    for y in range(4):worst=max(worst,abs(float(q[y])-s.probability(row,x,y)))
    oracles=[]
    for rho in (0.,.15,.5):
        mis=[]
        for pi in ((0,1,2,3),(2,3,0,1)):
            j,p,mi=truth(rho,pi);jj,pp,mii,h0,h1=joint_oracle(rho,pi)
            assert np.max(np.abs(j-np.array(jj)))<1e-14 and abs(mi-mii)<1e-14
            assert abs((h0-h1)-mi)<1e-14
            mis.append(mi)
        assert abs(mis[0]-mis[1])<1e-14
        oracles.append(dict(rho=rho,mutual_information_bits=mis))
    cfg,_,_=select(rows,{'toy'+str(i):i%3 for i in range(6)})
    assert cfg['candidates_base']==5 and cfg['candidates_feature']==25
    assert worst<1e-13
    fixtures=[]
    for rho,expected in [(0.,0.),(.15,-.0853698818156758),(.5,-.748244498841970)]:
        source,_,_=truth(rho,(0,1,2,3))
        moved,_,_=truth(rho,(1,2,3,0))
        p=[.55,.25,.15,.05]
        gain=math.fsum(float(moved[x,y])*math.log2(float(source[x,y])/(p[x]*p[y]))
                       for x in range(4) for y in range(4))
        assert abs(gain-expected)<1e-12
        fixtures.append(dict(rho=rho,permutation=[1,2,3,0],expected_oracle_source_gain=expected,
                             independently_checked=gain,not_a_formal_candidate=True))
    out=HERE/'toy_verification.json';assert not out.exists()
    out.write_text(json.dumps(dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        passed=True,max_scalar_probability_error=worst,oracles=oracles,external_oracle_fixtures=fixtures,synthetic_rows=96,
        selection_contract_only=True,formal_twenty_seed_calibration_run=False,
        code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
    print('Toy contracts pass; no formal calibration budget executed.')
if __name__=='__main__':main()
