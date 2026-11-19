#!/usr/bin/env python3
"""Artificial finite controls only: accepts no manuscript input."""
import itertools,json

def edges(words):
    return sorted({(u,v) for word in words for i,u in enumerate(word) for v in word[i+1:] if u!=v})
def feasible(words):
    alphabet=sorted(set(''.join(words))); ee=edges(words); orders=[]
    for order in itertools.permutations(alphabet):
        rank={u:i for i,u in enumerate(order)}
        if all(rank[u]<rank[v] for u,v in ee):orders.append(''.join(order))
    return ee,orders

def main():
    tests=[('repeated_sandwich',['aba'],False),('sorted_repetition',['aab','abbc','cc'],True),('across_word_opposition',['ab','ba'],False),('three_cycle',['ab','bc','ca'],False),('single_symbol',['aaa'],True),('independent_units',['a','b'],True),('descending_global',['ccb','bba'],True)]
    rows=[]
    for name,words,expected in tests:
        ee,orders=feasible(words);assert bool(orders)==expected
        rows.append({'id':name,'words':words,'edges':[{'from':u,'to':v,'witnesses':[{'word_index':wi,'positions_zero_based':[i,j]} for wi,w in enumerate(words) for i in range(len(w)) for j in range(i+1,len(w)) if w[i]==u and w[j]==v]} for u,v in ee],'feasible_orders':orders,'expected_feasible':expected,'PASS':True})
    assert sorted('aba')==list('aab')
    print(json.dumps({'schema':'independent_artificial_common_order_v1','status':'PASS','manuscript_input':False,'tests':rows,'normalization_counterexample':{'observed':'aba','external_normalization':'aab','meaning':'Internal sorting can remove a conflict without proving that observed text was historically sorted.'}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
