import random,time,json,torch,numpy as np
from model import Corpus,fit
if __name__=='__main__':
 torch.set_num_threads(2);torch.set_default_dtype(torch.float64)
 rng=random.Random(9); common=list('abcdefgh')
 rows=[{'word':[rng.choice(common) for _ in range(rng.randrange(3,8))]} for i in range(2000)]
 c=Corpus(rows,common,common,'cuda:0');P=c.penalty([('a','b')]);t=time.perf_counter()
 b,info=fit(c,P,.01);torch.cuda.synchronize()
 print(json.dumps({'torch':torch.__version__,'numpy':np.__version__,'gpu':torch.cuda.get_device_name(),'d':c.F*c.K,'contexts':len(c.keys),'seconds':time.perf_counter()-t,'fit':info},indent=2))
