"""Exact named definitions extracted from the recorded author source; no corpus imports."""
from collections import Counter, defaultdict
from functools import lru_cache
import math
EOS="<EOS>"
UNK="<UNK>"
BOS="<BOS>"


class CharLM:
    def __init__(self,words,alphabet,order,alpha):
        self.order=order;self.alpha=alpha;self.vocab=set(alphabet)|{EOS,UNK}
        self.counts=defaultdict(Counter);self.totals=Counter()
        for word in words:
            history=(BOS,)*(order-1)
            for c in word+(EOS,):
                for n in range(order):
                    h=history[-n:] if n else ()
                    self.counts[h][c]+=1;self.totals[h]+=1
                history=(history+(c,))[-(order-1):] if order>1 else ()

    @lru_cache(maxsize=500000)
    def prob(self,h,c):
        lower=self.prob(h[1:],c) if h else 1/len(self.vocab)
        return (self.counts.get(h,{}).get(c,0)+self.alpha*lower)/(self.totals.get(h,0)+self.alpha)

    @lru_cache(maxsize=50000)
    def logp(self,word):
        h=(BOS,)*(self.order-1);s=0.
        for c in word+(EOS,):
            s+=math.log2(self.prob(h,c))
            h=(h+(c,))[-(self.order-1):] if self.order>1 else ()
        return s
