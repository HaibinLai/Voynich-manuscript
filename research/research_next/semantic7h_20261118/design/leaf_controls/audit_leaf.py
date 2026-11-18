#!/usr/bin/env python3
"""Independent leaf audit. Does not import or execute either research scorer.
Input units are parsed by a new scanner; matched candidates are counted by
explicit position comparison (not the production variant-generation routine).
Joint distributions are streamed as literal Cartesian sums using Python big
integers in NumPy object arrays; no production bisection/moment code is used.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict,Counter
from itertools import permutations,product
from math import lcm,factorial,prod
import gzip,json,re,hashlib,time,ast
import numpy as np
BASE=Path(__file__).resolve().parent
RUN=BASE/'run_v2'
MODELS=['exact','fk','fp','ft','kp','kt','pt']
NAMES=MODELS+['delta_'+m for m in MODELS[1:]]+['max_delta']
checks=Counter(); failures=[]
def ck(ok,kind,detail=''):
 checks[kind]+=1
 if not ok:
  failures.append({'kind':kind,'detail':str(detail)[:1000]})
  if len(failures)<8:print('MISMATCH',kind,detail,flush=True)
def read(p):
 return json.load(gzip.open(p,'rt') if p.suffix=='.gz' else open(p))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def frac(x):return F(int(x['numerator']),int(x['denominator']))
def record(x):return {'numerator':str(x.numerator),'denominator':str(x.denominator),'decimal':float(x)}
def units(s):
 out=[];i=0
 while i<len(s):
  if s[i]=='@':
   j=s.find(';',i);assert j>i and s[i+1:j].isdigit(),s
   out.append(s[i:j+1]);i=j+1
  else:out.append(s[i]);i+=1
 return tuple(out)
def matches(a,b,m):
 if a==b:return True
 if m=='exact' or len(a)!=len(b):return False
 diff=[(x,y) for x,y in zip(a,b) if x!=y]
 return len(diff)==1 and set(diff[0])==set(m)
def check_summary(s,acc,D,label):
 # acc: count,sum,sum of squares,min,max,>=,>,ties,identity integer
 n,sm,sq,lo,hi,ge,gt,eq,obs=map(int,acc)
 mean=F(sm,n*D);var=F(sq,n*D*D)-mean*mean
 vals={'observed':F(obs,D),'mean':mean,'variance':var,'min':F(lo,D),'max':F(hi,D),'excess_over_mean':F(obs,D)-mean,'p_upper':F(ge,n)}
 for k,v in vals.items():
  ck(frac(s[k])==v,'rational_summary',label+'/'+k)
  ck(abs(float(v)-s[k]['decimal'])<=1e-15,'decimal_summary',label+'/'+k)
 for k,v in [('assignments',n),('tail_ge',ge),('tail_gt',gt),('ties',eq),('observed_integer',obs),('score_denominator',D)]:ck(int(s[k])==v,'integer_summary',label+'/'+k)
 ck(ge==gt+eq,'tail_partition',label)
 return {**{k:record(v) for k,v in vals.items()},'assignments':n,'tail_ge':ge,'tail_gt':gt,'ties':eq,'observed_integer':str(obs),'score_denominator':str(D)}
def array_acc(a,obs):
 return [len(a),sum(a),sum(x*x for x in a),min(a),max(a),sum(x>=obs for x in a),sum(x>obs for x in a),sum(x==obs for x in a),obs]

def static_history_audit():
 # This static check was added only after the independent numerical audit passed.
 # Neither source module is imported or executed.
 trees={n:ast.parse((BASE/n).read_text()) for n in ['run.py','run_compact.py']}
 functions={n:{x.name:x for x in t.body if isinstance(x,ast.FunctionDef)} for n,t in trees.items()}
 old=functions['run.py']['analyse'];new=functions['run_compact.py']['analyse']
 class NormalizeOriginal(ast.NodeTransformer):
  def visit_Attribute(self,node):
   node=self.generic_visit(node)
   if isinstance(node.value,ast.Name) and node.value.id=='original':return ast.Name(id=node.attr,ctx=ast.Load())
   return node
 def dump(node):return ast.dump(NormalizeOriginal().visit(ast.parse(ast.unparse(node))),include_attributes=False)
 for i in [0,2,3,4]:ck(dump(old.body[i])==dump(new.body[i]),'static_same_matrix_and_scale',i)
 old_loop=next(x for x in old.body if isinstance(x,ast.For) and ast.unparse(x.target)=='g' and ast.unparse(x.iter)=='groups' and any(isinstance(y,ast.Assign) and any(isinstance(z,ast.Name) and z.id=='perms' for z in y.targets) for y in x.body))
 new_loop=next(x for x in new.body if isinstance(x,ast.For) and ast.unparse(x.target)=='g' and ast.unparse(x.iter)=='groups' and any(isinstance(y,ast.Assign) and any(isinstance(z,ast.Name) and z.id=='perms' for z in y.targets) for y in x.body))
 for i in [0,2,3,4,5,6,7]:ck(dump(old_loop.body[i])==dump(new_loop.body[i]),'static_same_permutation_score_increment',i)
 ck(ast.dump(old_loop.body[1].test)==ast.dump(new_loop.body[1].test),'static_same_group_size_limit')
 compact_refs=sorted({ast.unparse(x) for x in ast.walk(trees['run_compact.py']) if isinstance(x,ast.Attribute) and isinstance(x.value,ast.Name) and x.value.id=='original'})
 for required in ['original.matrix_group','original.build_leaf_bags','original.group_selection']:ck(required in compact_refs,'static_shared_original_component',required)
 for version in ['run_v1','run_v2']:
  for item in read(BASE/version/'freeze.json')['files']:
   path=BASE.parents[2]/item['path'];ck(path.exists() and sha(path)==item['sha256'],'freeze_source_hash',version+'/'+item['path'])
 return {'method':'AST-only comparison after independent implementation; no import/execution of original modules.','same_statistical_kernel':['matrix construction call (compact delegates to frozen original)','leaf-count weighting and LCM denominator','group-size cap, lexicographic permutations, identity','integer score arrays and paired increments'],'original_references_in_compact':compact_refs,'source_hashes':{n:sha(BASE/n) for n in trees}}

def main():
 started=time.time();inp=read(RUN/'input.json.gz');sel=read(RUN/'selection.json');bags={};selection={};reports=[];static_history=static_history_audit();summary_file=read(RUN/'summary.json')
 # Verify source snapshot identity and receipts, without running old code.
 history={}
 for name in ['input.json.gz','selection.json']:
  old=BASE/'run_v1'/name;new=RUN/name
  history[name]={'old_sha256':sha(old),'new_sha256':sha(new),'same_bytes':old.read_bytes()==new.read_bytes()}
  ck(history[name]['same_bytes'],'v1_v2_snapshot_identity',name)
 for item in read(RUN/'complete.json')['files']:
  p=RUN/item['path'];ck(sha(p)==item['sha256'],'completion_hash',item['path']);ck(p.stat().st_size==item['bytes'],'completion_bytes',item['path'])
 for version,data in inp.items():
  b={}
  for page in data['pages']:
   folio=page['folio'];leaf='f85_86' if folio.startswith(('f85','f86','fRos')) else re.match(r'f\d+',folio).group()
   ck(leaf==page['leaf'],'physical_leaf_mapping',version+'/'+folio)
   z=b.setdefault(leaf,{'pages':[],'H':set(),'I':set(),'Q':set(),'labels':defaultdict(list),'body':defaultdict(Counter)})
   z['pages'].append(folio)
   for k in ['H','I','Q']:z[k].add(page[k])
   for lab in page['labels']:
    u=units(lab['word']);ck(list(u)==lab['units'],'label_unit_scanner',lab['locator'])
    z['labels'][len(u)].append((lab['locator'],lab['word'],u))
   for line in page['body']:
    for token in line['tokens']:
     if token is not None:
      u=units(token);z['body'][len(u)][u]+=1
  bags[version]=b;groups=defaultdict(list)
  exclusions=[]
  for leaf,z in sorted(b.items()):
   if any(len(z[k])!=1 or next(iter(z[k])) in [None,'@','?',''] for k in ['H','I']):exclusions.append(leaf);continue
   if not z['labels'] or not z['body']:exclusions.append(leaf);continue
   groups['/'.join(next(iter(z[k])) for k in ['H','I'])].append(leaf)
  mains=[]
  for g,leaves in sorted(groups.items()):
   if len(leaves)<2:continue
   lens=set.intersection(*(set(b[x]['labels']) & set(b[x]['body']) for x in leaves))
   if lens:mains.append({'stratum':g,'leaves':leaves,'lengths':sorted(lens)})
  strict=[]
  for g in mains:
   sub=defaultdict(list)
   for leaf in g['leaves']:
    q=b[leaf]['Q']
    if len(q)==1 and next(iter(q)) not in [None,'@','?','']:sub[next(iter(q))].append(leaf)
   for q,leaves in sorted(sub.items()):
    if len(leaves)<2:continue
    lens=[L for L in g['lengths'] if all(len(b[x]['labels'][L])>=1 and sum(b[x]['body'][L].values())>=5 for x in leaves)]
    if lens:strict.append({'stratum':g['stratum']+'/'+q,'leaves':leaves,'lengths':lens})
  selection[version]={'main_HI':mains,'strict_HIQ5':strict}
 for version in bags:
  other=next(v for v in bags if v!=version);cross=[]
  for g in selection[version]['main_HI']:
   alt=next((x for x in selection[other]['main_HI'] if x['stratum']==g['stratum']),None)
   if alt and alt['leaves']==g['leaves']:
    lens=sorted(set(g['lengths']) & set(alt['lengths']))
    if lens:cross.append({**g,'lengths':lens})
  selection[version]['cross_version_lengths']=cross
 ck(selection==sel['versions'],'complete_support_selection')
 print('Independent support reconstruction complete.',flush=True)
 for version in bags:
  for condition,support in selection[version].items():
   label=version+'/'+condition;print('AUDITING',label,flush=True)
   package=read(RUN/f'{version}_{condition}.json.gz');gg=package['groups'];joint=package['joint'];b=bags[version]
   ck(joint==summary_file[version][condition],'summary_matches_package',label)
   ck(len(gg)==len(support),'group_count',label)
   matrices=[];all_den=[];component_count=0;query_count=0
   for spec,g in zip(support,gg):
    for k in ['stratum','leaves','lengths']:ck(g[k]==spec[k],'group_support',label+'/'+k)
    leaves=spec['leaves'];lengths=spec['lengths'];n=len(leaves);mat={m:[] for m in MODELS}
    for m in MODELS:
     for i,left in enumerate(leaves):
      row=[]
      for j,right in enumerate(leaves):
       rates=[]
       for idx,L in enumerate(lengths):
        labs=b[left]['labels'][L];body=b[right]['body'][L];den=sum(body.values());nums=[]
        comp=g['components'][m][i][j][idx]
        ck(comp['length']==L and comp['query_labels']==len(labs) and comp['body_opportunities']==den,'component_denominators',f'{label}/{m}/{i}/{j}/{L}');component_count+=1
        expected_queries=[]
        for loc,word,u in labs:
         hits=sum(count for v,count in body.items() if matches(u,v,m));nums.append(hits);expected_queries.append({'locator':loc,'word':word,'m':hits});query_count+=1
        ck(expected_queries==comp['queries'],'individual_query_counts',f'{label}/{m}/{i}/{j}/{L}')
        rate=F(sum(nums),len(labs)*den);rates.append(rate)
        ck(frac(comp['rate'])==rate,'component_rate',label)
       score=sum(rates,F(0))/len(lengths);row.append(score);all_den.append(score.denominator)
       ck(frac(g['matrices'][m][i][j])==score,'matrix_entry',f'{label}/{m}/{i}/{j}')
      mat[m].append(row)
    matrices.append(mat)
   scale=lcm(*all_den);ck(int(joint['integer_scale'])==scale,'joint_integer_scale',label)
   N=sum(len(s['leaves']) for s in support);D=scale*N;arrays=[]
   for spec,g,mat in zip(support,gg,matrices):
    n=len(spec['leaves']);perms=list(permutations(range(n)));ck(g['permutations']==[list(x) for x in perms],'permutation_lexicographic_complete',label+'/'+spec['stratum']);ck(tuple(g['permutations'][0])==tuple(range(n)),'identity_first',label)
    ck(int(g['integer_scale'])==scale,'group_integer_scale',label)
    scores={m:[int(sum((mat[m][i][p[i]] for i in range(n)),F(0))*scale) for p in perms] for m in MODELS}
    increments={m:[x-y for x,y in zip(scores[m],scores['exact'])] for m in MODELS[1:]}
    for m in MODELS:
     ck(scores[m]==list(map(int,g['scores'][m])),'complete_group_score_array',label+'/'+m)
     check_summary(g['summaries'][m],array_acc(scores[m],scores[m][0]),scale*n,label+'/group/'+m)
    for m in MODELS[1:]:
     ck(increments[m]==list(map(int,g['increments'][m])),'complete_group_increment_array',label+'/'+m)
     check_summary(g['increment_summaries'][m],array_acc(increments[m],increments[m][0]),scale*n,label+'/group/delta_'+m)
    arrays.append(np.array([scores[m] for m in MODELS]+[increments[m] for m in MODELS[1:]],dtype=object).T)
   labels=sum(len(b[x]['labels'][L]) for g in support for x in g['leaves'] for L in g['lengths']);body=sum(sum(b[x]['body'][L].values()) for g in support for x in g['leaves'] for L in g['lengths'])
   for k,v in [('leaf_count',N),('labels',labels),('body_opportunities',body),('group_count',len(support)),('assignments',prod(factorial(len(s['leaves'])) for s in support))]:ck(joint[k]==v,'joint_support_totals',label+'/'+k)
   # Literal Cartesian enumeration, blocking only to keep memory bounded.
   # The last group has at most 5040 rows. No group score/moment summation formula.
   observed=sum((a[0] for a in arrays),np.zeros(13,dtype=object));observed=np.append(observed,max(observed[7:]))
   counts=np.zeros(14,dtype=object);sums=np.zeros(14,dtype=object);squares=np.zeros(14,dtype=object);ge=np.zeros(14,dtype=object);gt=np.zeros(14,dtype=object);ties=np.zeros(14,dtype=object);mins=None;maxs=None
   for prefix in product(*(range(len(a)) for a in arrays[:-1])):
    offset=sum((arrays[i][idx] for i,idx in enumerate(prefix)),np.zeros(13,dtype=object))
    block=arrays[-1]+offset
    block=np.column_stack((block,np.max(block[:,7:],axis=1)))
    counts+=len(block);sums+=block.sum(axis=0);squares+=(block*block).sum(axis=0)
    ge+=np.sum(block>=observed,axis=0);gt+=np.sum(block>observed,axis=0);ties+=np.sum(block==observed,axis=0)
    lo=block.min(axis=0);hi=block.max(axis=0);mins=lo if mins is None else np.minimum(mins,lo);maxs=hi if maxs is None else np.maximum(maxs,hi)
   out={}
   for c,name in enumerate(NAMES):
    saved=joint['models'][name] if c<7 else joint['increments'][name[6:]] if c<13 else joint['max_increment_global_null']
    out[name]=check_summary(saved,[counts[c],sums[c],squares[c],mins[c],maxs[c],ge[c],gt[c],ties[c],observed[c]],D,label+'/'+name)
   reports.append({'version':version,'condition':condition,'leaves':N,'groups':support,'labels':labels,'body_opportunities':body,'component_checks':component_count,'individual_query_checks':query_count,'integer_scale':str(scale),'joint':out})
   print('DONE',label,'failures',len(failures),'seconds',round(time.time()-started,1),flush=True)
 report={'audit':'leaf_audit_v1','status':'PASS' if not failures else 'FAIL','independence':'Independent script; no import or execution of run.py/run_compact.py. Audit began after frozen geometric review; no longer image-blind. Input parsing accepted the previously frozen token/label fields; their original transcription extraction was not re-audited.','method':'New physical-leaf pooling, unit scanner, positional one-substitution matcher, exact Fraction matrices; complete lexicographic permutations; literal Cartesian streaming of all 13 integer scores and synchronous maximum. Moments are accumulated directly from every joint assignment, not computed by production factorized moment formulas.','arithmetic':'All tails, ties, sums, squared sums, denominators and rational comparisons exact Python integers/Fraction. Saved decimal fields compared at absolute tolerance 1e-15. NumPy dtype=object prevents fixed-width overflow.','checks':dict(checks),'failures':failures,'elapsed_seconds':time.time()-started,'snapshot_history':history,'static_source_history':static_history,'representation_assessment':'run_v1 and run_v2 frozen input and selection are byte-identical. Static AST checks confirm the same matrix construction, weighting, scale, permutations, score arrays and paired increments; both frozen source receipts match. run_v2 matches all independently implemented protocol statistics. Historical statement of approximately 3GB memory and outcome non-exposure is a recorded claim, not independently observable from the surviving files. Complete Cartesian arrays are sufficient for lossless distribution reconstruction; no Monte Carlo used.','coverage':'All 6 packages; all 13 supported leaves per package; all 7 models, 6 increments, global synchronous max; all group summaries and every group permutation; every component denominator, individual query hit and matrix entry.','not_covered':['Historical truth of aborted-run memory use or non-exposure.','Original raw-transcription extraction before frozen input.','Historical meanings, sound values, label/object pairing, exchangeability assumptions.'],'source_hashes':{str(p.relative_to(BASE)):sha(p) for p in [BASE/'protocol.txt',BASE/'representation_change.txt',RUN/'input.json.gz',RUN/'selection.json']},'script_sha256':sha(Path(__file__)),'packages':reports}
 (BASE/'leaf_audit_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 lines=['Independent leaf audit v1',report['status'],report['independence'],report['method'],report['arithmetic'],'',report['coverage'],'',report['representation_assessment'],'','Checks: '+json.dumps(dict(checks)), 'Failures: '+json.dumps(failures),'']
 for r in reports:
  lines.append(f"{r['version']}/{r['condition']}: {r['leaves']} leaves, {r['labels']} labels, {r['body_opportunities']} body opportunities")
  for name,s in r['joint'].items():lines.append(f"  {name}: observed={s['observed']['decimal']:.12g}; excess={s['excess_over_mean']['decimal']:.12g}; ge={s['tail_ge']}; gt={s['tail_gt']}; ties={s['ties']}; N={s['assignments']}; upper={s['p_upper']['decimal']:.12g}")
 lines+=['','Not covered:']+report['not_covered']
 (BASE/'leaf_audit_v1.txt').write_text('\n'.join(lines)+'\n')
 print('AUDIT',report['status'],'elapsed',report['elapsed_seconds'],'checks',sum(checks.values()),flush=True)
if __name__=='__main__':main()
