"""Nine fixed artificial examples. No corpus inputs or linguistic interpretation."""
import argparse,datetime,hashlib,json
from pathlib import Path
CASES=[('T01',['aab','bcc']),('T02',['aba']),('T03',['ab','ba']),('T04',['ab','bc','ca']),('T05',['ac','bc']),('T06',['aa','bb']),('T07',[None,'ab']),('T08',[None,'aba']),('T09',[None])]
def analyse(case_id,words):
 nodes=sorted({x for w in words if w is not None for x in w});edges={}
 for wi,w in enumerate(words):
  if w is None:continue
  for i,u in enumerate(w):
   for j in range(i+1,len(w)):
    v=w[j]
    if u!=v:edges.setdefault((u,v),[]).append({'word_index':wi,'positions_zero_based':[i,j]})
 adjacency={u:sorted(v for a,v in edges if a==u) for u in nodes};state={};stack=[];cycle=[]
 def visit(u):
  nonlocal cycle
  state[u]=1;stack.append(u)
  for v in adjacency[u]:
   if state.get(v)==1:cycle=stack[stack.index(v):]+[v];return True
   if not state.get(v) and visit(v):return True
  stack.pop();state[u]=2;return False
 for u in nodes:
  if not state.get(u) and visit(u):break
 orders=[]
 def extend(prefix,left):
  if len(orders)>=2:return
  if not left:orders.append(''.join(prefix));return
  for u in sorted(left):
   if not any(a in left and b==u for a,b in edges):extend(prefix+[u],left-{u})
 if nodes and not cycle:extend([],set(nodes))
 unknown=sum(w is None for w in words)
 status=('INCOMPATIBLE_KNOWN_CONSTRAINTS' if cycle else 'UNDETERMINED_MISSING_WORDS' if unknown else 'COMPATIBLE_STRICT_CONDITION' if edges else 'COMPATIBLE_NO_CROSS_SYMBOL_INFORMATION')
 return {'id':case_id,'artificial':True,'words':words,'nodes':nodes,'unknown_word_count':unknown,'edges':[{'from':u,'to':v,'witnesses':edges[u,v]} for u,v in sorted(edges)],'cycle':cycle,'cycle_witnesses':[{'from':u,'to':v,**edges[u,v][0]} for u,v in zip(cycle,cycle[1:])],'at_most_two_orders_of_known_subset':orders,'status':status,'full_input_compatibility':False if cycle else None if unknown else True,'semantic_claim':False}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);a=ap.parse_args();out=Path(a.output);assert not out.exists()
 w=Path(__file__).resolve().parents[1];freeze=json.loads((w/'artificial_code_freeze_v1.json').read_text())
 for r in freeze['files']:assert hashlib.sha256((w/r['path']).read_bytes()).hexdigest()==r['sha256']
 rows=[analyse(i,words) for i,words in CASES]
 free={'id':'F01','artificial':True,'source_word':'aab','observed_words':['aab','aba','baa'],'permutations_output_positions_from_input_zero_based':[[0,1,2],[0,2,1],[2,0,1]],'same_multiset':True,'strict_joint':analyse('F01-strict',['aab','aba','baa']),'claim':'Free per-word reordering permits this artificial observation; a common strict order does not. No manuscript or author mechanism is thereby proved.'}
 result={'schema':'ninth_artificial_order_demo_v1','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'COMPLETED_PENDING_INDEPENDENT_AUDIT','freeze_sha256':hashlib.sha256((w/'artificial_code_freeze_v1.json').read_bytes()).hexdigest(),'manuscript_input':False,'cases':rows,'free_reordering_witness':free,'independent_audit_pending':True,'limits':['All strings are artificial','Unknown words are not filled or counted as a pass','At most two orders are exhibited; not claimed to enumerate all','Strict incompatibility does not refute arbitrary anagrams or noise-tolerant historical hypotheses']}
 out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'cases':len(rows),'statuses':{x['id']:x['status'] for x in rows}}))
if __name__=='__main__':main()
