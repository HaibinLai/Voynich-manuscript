#!/usr/bin/env python3
"""Enumerates fixed artificial alphabets; imports no primary proof implementation."""
import argparse,collections,datetime,hashlib,itertools,json
from pathlib import Path
HERE=Path(__file__).resolve().parents[1]
CASES=[['aab','bcc'],['aba'],['ab','ba'],['ab','bc','ca'],['ac','bc'],['aa','bb'],[None,'ab'],[None,'aba'],[None]]
checks=collections.Counter()
def require(test,kind):
    checks[kind]+=1
    if not test:raise AssertionError(kind)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def audit(case,words):
    require(case['words']==words,'fixed_input'); require(case['artificial'] is True and case['semantic_claim'] is False,'nonsemantic_artificial')
    alphabet=sorted({x for w in words if w is not None for x in w}); require(case['nodes']==alphabet,'alphabet')
    unknown=sum(w is None for w in words);require(case['unknown_word_count']==unknown,'unknown_count')
    expected=collections.defaultdict(list)
    for wi,w in enumerate(words):
        if w is None:continue
        for i in range(len(w)):
            for j in range(i+1,len(w)):
                if w[i]!=w[j]:expected[w[i],w[j]].append({'word_index':wi,'positions_zero_based':[i,j]})
    require(case['edges']==[{'from':u,'to':v,'witnesses':expected[u,v]} for u,v in sorted(expected)],'complete_position_edge_multiset')
    valid=[];trials=0
    for sequence in itertools.permutations(alphabet) if alphabet else []:
        trials+=1;rank={x:i for i,x in enumerate(sequence)}
        # Direct word scan is independent of graph construction: adjacent rank monotonicity.
        ok=all(all(rank[x]<=rank[y] for x,y in zip(w,w[1:])) for w in words if w is not None)
        if ok:valid.append(''.join(sequence))
    conflict=bool(alphabet) and not valid
    expected_status=('INCOMPATIBLE_KNOWN_CONSTRAINTS' if conflict else 'UNDETERMINED_MISSING_WORDS' if unknown else 'COMPATIBLE_STRICT_CONDITION' if expected else 'COMPATIBLE_NO_CROSS_SYMBOL_INFORMATION')
    require(case['status']==expected_status,'status')
    full=False if conflict else None if unknown else True
    require(case['full_input_compatibility'] is full,'tristate_full_compatibility')
    require(case['at_most_two_orders_of_known_subset']==valid[:2],'first_two_order_witnesses')
    cycle=case['cycle']; cw=case['cycle_witnesses']
    if conflict:
        require(len(cycle)>=3 and cycle[0]==cycle[-1] and len(set(cycle[:-1]))==len(cycle)-1,'closed_simple_cycle')
        require(len(cw)==len(cycle)-1,'cycle_witness_count')
        for (u,v),witness in zip(zip(cycle,cycle[1:]),cw):
            require(witness['from']==u and witness['to']==v and (u,v) in expected,'cycle_edge')
            wi=witness['word_index'];i,j=witness['positions_zero_based'];w=words[wi]
            require(w is not None and 0<=i<j<len(w) and w[i]==u and w[j]==v and u!=v,'cycle_original_positions')
            require({'word_index':wi,'positions_zero_based':[i,j]} in expected[u,v],'cycle_recorded_provenance')
    else:require(cycle==[] and cw==[],'no_spurious_cycle')
    return {'id':case['id'],'status':'PASS','alphabet':alphabet,'permutations_exhaustively_examined':trials,'all_feasible_orders_known_subset':valid,'distinct_constraint_edges':len(expected),'position_witness_count':sum(map(len,expected.values())),'cycle_certificate_checked':conflict,'unknown_word_count':unknown,'expected_status':expected_status,'all_unknown_policy':'No alphabet or empty-order witness fabricated' if not alphabet else None}
def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'artificial_demo_audit_v1.json');a=p.parse_args()
    require(not a.output.exists() and not a.output.with_suffix('.txt').exists(),'new_output')
    data=json.loads((HERE/'artificial_demo_v1.json').read_text());freeze=json.loads((HERE/'artificial_code_freeze_v1.json').read_text())
    require(data['freeze_sha256']==sha(HERE/'artificial_code_freeze_v1.json'),'freeze_binding')
    for ref in freeze['files']:require(sha(HERE/ref['path'])==ref['sha256'],'frozen_file')
    require(data['manuscript_input'] is False and len(data['cases'])==9,'fixed_scope')
    rows=[]
    for i,(case,words) in enumerate(zip(data['cases'],CASES),1):
        require(case['id']=='T%02d'%i,'case_id');rows.append(audit(case,words))
    free=data['free_reordering_witness'];require(free['id']=='F01' and free['artificial'] is True and free['source_word']=='aab' and free['observed_words']==['aab','aba','baa'],'free_fixture')
    require(len(free['permutations_output_positions_from_input_zero_based'])==3,'free_permutation_count')
    for perm,word in zip(free['permutations_output_positions_from_input_zero_based'],free['observed_words']):
        require(all(type(i) is int for i in perm) and sorted(perm)==list(range(3)),'position_bijection')
        require(''.join(free['source_word'][i] for i in perm)==word,'position_permutation_replay')
        require(collections.Counter(word)==collections.Counter(free['source_word']),'same_multiset')
    require(free['same_multiset'] is True,'multiset_label');rows.append(audit(free['strict_joint'],free['observed_words']))
    bound=['artificial_protocol_v1.txt','artificial_code_freeze_v1.json','code/artificial_order_demo.py','artificial_demo_v1.json','code/independent_artificial_audit_v1.py','independent_preflight/artificial_order_check_v1.py','independent_preflight/artificial_order_receipt_v1.json']
    result={'schema':'ninth_independent_artificial_demo_audit_v1','status':'PASS','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'Exhaustive alphabet permutations with direct adjacent-rank scans; independently reconstruct every unequal original-position edge; verify cycle original positions. No primary module import.','manuscript_input':False,'sources':[{'path':x,'sha256':sha(HERE/x)} for x in bound],'cases':rows,'scope':{'protocol_cases':9,'free_reordering_cases':1,'explicit_free_position_permutations':3,'exhaustive_total_orders_examined':sum(r['permutations_exhaustively_examined'] for r in rows),'original_position_edge_witnesses':sum(r['position_witness_count'] for r in rows),'unknown_cases':['T07','T08','T09'],'earlier_seven_cases_preserved_separately':True},'checks':dict(checks),'failures':[],'limits':['Only these fixed artificial strings and atomic a/b/c symbols.','No manuscript scores, new glyph judgments, key or language inference.','Feasible orders with missing words apply to the known subset only; all unknown yields no order witness.','Cycle validity verified; no claim that returned cycle is shortest or reproduces primary DFS traversal.','Informed AI implementation audit, not independent historical evidence.']}
    with a.output.open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    a.output.with_suffix('.txt').write_text('纯人工9例独立审核：PASS。\n独立枚举全部小字母表排列，直接按各词相邻字符秩检验非降序；另从原词全部i<j位置重建边与全部原像。9例及F01联合输入均一致，循环每边与原始位置有效，已报最多2个字母序优先的可行序一致。\n共核'+str(result['scope']['exhaustive_total_orders_examined'])+'个全序、'+str(result['scope']['original_position_edge_witnesses'])+'个位置见证，以及F01三份显式位置双射。None+ab保持未定，None+aba保留已知冲突，只有None不编造字母表或空序通过。\n不导入主证明器，不要求循环最短，也不声称模拟相同DFS。此前7例保留；没有新手稿输入、评分或图像判断。这是同知情AI的实现独立复核，不是历史编码认证。\n')
    print(json.dumps({'status':'PASS','scope':result['scope'],'json_sha256':sha(a.output),'text_sha256':sha(a.output.with_suffix('.txt'))},ensure_ascii=False))
if __name__=='__main__':main()
