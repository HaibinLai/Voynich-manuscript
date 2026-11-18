# -*- coding: utf-8 -*-
"""Fixed, approved four-mechanism known-English measurement calibration.

Uses only the frozen local structural parser; imports no Voynich/old scoring code.
"""
import collections,datetime,gzip,hashlib,json
from pathlib import Path
from fractions import Fraction
import support

HERE=Path(__file__).resolve().parent
OUT=HERE/'run_v1'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
read=lambda p:json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def dump(path,obj):
 def encode(v):
  if isinstance(v,Fraction):return dict(num=v.numerator,den=v.denominator,value=float(v))
  raise TypeError(type(v))
 raw=(json.dumps(obj,ensure_ascii=False,separators=(',',':'),default=encode,allow_nan=False)+'\n').encode()
 path.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw)
def avg(values):
 values=list(values);return sum(values,Fraction())/len(values) if values else None
def cell(positions,N):
 m=len(positions)
 return dict(m=m,N=N,rate=Fraction(m,N) if N else None,binary=int(m>0),positions=positions)
KEYS=['O','B','A','R','G','UA','UR','UG']
def index_section(s,old):
 ix={k:collections.defaultdict(list) for k in ['O','B','A','R','G']}
 ns={k:collections.Counter() for k in ix};removed=[]
 assert len(s['paragraphs'])==len(old['paragraphs'])
 for p,oldwords in zip(s['paragraphs'],old['paragraphs']):
  wordslots=[t for t in p['slots'] if t['kind']=='word']
  assert [t['text'] for t in wordslots]==oldwords,('raw ASCII run identity changed',s['id'],p['p'])
  for oldidx,t in enumerate(wordslots):
   pos=dict(mechanism='O',p=p['p'],old_word_index=oldidx,slots=[t['slot']],endpoints=[t['slot']],start=t['start'],end=t['end'])
   ix['O'][t['text']].append(pos);ns['O'][len(t['text'])]+=1
   if t['comparable']:continue
   causes=[]
   for side,offset in [('left',t['start']-1),('right',t['end'])]:
    if offset<0 or offset>=len(p['stream']):continue
    c=p['stream'][offset]
    if support.separator(c) or support.wordchar(c):continue
    e=next((e for e in p['events'] if e['type']=='barrier' and e['start']==offset),None)
    if e is not None:causes.append(dict(side=side,type='XML_barrier',event=e))
    else:
     opaque=next(u for u in p['slots'] if u['kind']=='opaque' and u['start']<=offset<u['end'])
     causes.append(dict(side=side,type='opaque',slot=opaque))
   assert causes
   removed.append(dict(section=s['id'],p=p['p'],old_word_index=oldidx,slot=t,causes=causes,normalized_context=p['stream'][max(0,t['start']-55):t['end']+55]))
  for key in ['B','A','R','G']:
   for wi,w in enumerate(p['windows'][key]):
    candidate=''.join(p['slots'][i]['text'] for i in w['endpoints'])
    assert len(candidate)==w['length']
    ix[key][candidate].append(dict(mechanism=key,p=p['p'],window_index=wi,**w));ns[key][w['length']]+=1
 return ix,ns,removed
def aggregate(rows):
 return {key:dict(title_count=len(rows),own_hits=sum(r['own'][key]['binary'] for r in rows),own_binary_mean=avg(Fraction(r['own'][key]['binary']) for r in rows),other_binary_mean=avg(r['all_other_281'][key]['binary_mean'] for r in rows),delta=avg(r['all_other_281'][key]['delta'] for r in rows),own_N0=sum(r['own'][key]['N']==0 for r in rows),all_matrix_N0=sum(c['mechanisms'][key]['N']==0 for r in rows for c in r['matrix'])) for key in KEYS}
def transition(rows,before,after):
 ownplus=[];ownminus=[];otherplus=otherminus=0;details=[];changes=[]
 for r in rows:
  a=r['own'][before]['binary'];b=r['own'][after]['binary']
  if b>a:ownplus.append(r['id'])
  if b<a:ownminus.append(r['id'])
  inc=[]
  for c in r['matrix']:
   old=c['mechanisms'][before];new=c['mechanisms'][after]
   if (old['m'],old['N'])!=(new['m'],new['N']):changes.append(dict(title_id=r['id'],label=r['label'],section=c['section'],before_m=old['m'],after_m=new['m'],before_N=old['N'],after_N=new['N'],before_binary=old['binary'],after_binary=new['binary']))
   if c['section']==r['id']:continue
   d=new['binary']-old['binary'];inc.append(d);otherplus+=d>0;otherminus+=d<0
  details.append(dict(title_id=r['id'],label=r['label'],own_increment=b-a,other_increment_mean=avg(Fraction(x) for x in inc),net_increment=Fraction(b-a)-avg(Fraction(x) for x in inc)))
 return dict(before=before,after=after,own_gain_ids=ownplus,own_loss_ids=ownminus,other_gain_cells=otherplus,other_loss_cells=otherminus,own_increment_mean=avg(Fraction(d['own_increment']) for d in details),other_increment_mean=avg(d['other_increment_mean'] for d in details),net_increment=avg(d['net_increment'] for d in details),title_contributions=details,m_or_N_changed_cell_count=len(changes),changed_cells=changes)
def main():
 assert not OUT.exists(),'No overwrite of frozen run'
 sf=read(HERE/'support_freeze_v1.json')
 for name,h in sf['files'].items():assert sha(HERE/name)==h,('Frozen parser/protocol changed',name)
 assert sha(support.SOURCE)==support.EXPECTED
 old=read(support.OLD);primary=[dict(id=s['id'],raw_title=s['raw_title'],title_tokens=s['title_tokens'],primary=s['primary']) for s in old if s['primary']]
 assert len(primary)==119
 OUT.mkdir();dump(OUT/'identity.json',primary)
 frozen=[HERE/'protocol_v1.txt',HERE/'approval_v1.txt',HERE/'support.py',Path(__file__),HERE/'support_freeze_v1.json',HERE/'support_v1.json',HERE/'toy_v1.json',OUT/'identity.json']
 dump(OUT/'freeze.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),before_real_title_matching=True,source_sha256=sha(support.SOURCE),old_sections_sha256=sha(support.OLD),old_rows_sha256=sha(HERE.parent/'known_herbal/run_v1/rows.json.gz'),files={str(p.relative_to(HERE)):sha(p) for p in frozen},parser_policy='Approved conservative common comparability, unchanged from support freeze.'))
 toy=support.toy();assert toy==read(HERE/'toy_v1.json');dump(OUT/'toy.json',toy)
 sections,struct,notes=support.extract();dump(OUT/'packet.json.gz',sections)
 indices=[];denoms=[];removed=[]
 for s,o in zip(sections,old):
  ix,ns,rr=index_section(s,o);indices.append(ix);denoms.append(ns);removed+=rr
 assert len(removed)==476 and len({r['section'] for r in removed})==182
 causes=collections.Counter(c['event']['tag'] if c['type']=='XML_barrier' else 'opaque' for r in removed for c in r['causes'])
 dump(OUT/'input_changes.json.gz',dict(old_total=sum(s['body_words'] for s in old),new_total=sum(sum(n['B'].values()) for n in denoms),removed_word_count=len(removed),affected_section_count=len({r['section'] for r in removed}),cause_occurrences=dict(causes),removed_words=removed,section_counts=[dict(section=s['id'],old_words=o['body_words'],new_words=sum(n['B'].values()),removed_count=sum(r['section']==s['id'] for r in removed)) for s,o,n in zip(sections,old,denoms)]))
 oldrows={r['id']:r for r in read(HERE.parent/'known_herbal/run_v1/rows.json.gz')};rows=[]
 for s in sections:
  if not s['primary']:continue
  label=s['title_tokens'][0];L=len(label);matrix=[]
  for t,ix,ns in zip(sections,indices,denoms):
   metrics={k:cell(ix[k].get(label,[]),ns[k].get(L,0)) for k in ['O','B','A','R','G']}
   assert metrics['A']['N']==metrics['R']['N']
   previous=oldrows[s['id']]['matrix'][t['id']-1]
   assert previous['section']==t['id'] and previous['matches']==metrics['O']['m'] and previous['same_length_n']==metrics['O']['N'] and previous['binary']==metrics['O']['binary']
   for key in ['A','R','G']:
    metrics['U'+key]=cell(metrics['B']['positions']+metrics[key]['positions'],metrics['B']['N']+metrics[key]['N'])
    assert metrics['U'+key]['binary']>=metrics['B']['binary']
   matrix.append(dict(section=t['id'],mechanisms=metrics))
  own=matrix[s['id']-1]['mechanisms'];other=[c for c in matrix if c['section']!=s['id']];assert len(other)==281
  controls={k:dict(count=281,binary_mean=avg(Fraction(c['mechanisms'][k]['binary']) for c in other),delta=Fraction(own[k]['binary'])-avg(Fraction(c['mechanisms'][k]['binary']) for c in other)) for k in KEYS}
  rows.append(dict(id=s['id'],label=label,raw_title=s['raw_title'],own=own,matrix=matrix,all_other_281=controls))
 assert len(rows)==119
 dump(OUT/'matrix.json.gz',rows)
 transitions={f'{a}_to_{b}':transition(rows,a,b) for a,b in [('O','B'),('B','UA'),('B','UR'),('B','UG')]}
 dump(OUT/'transitions.json.gz',transitions)
 summary=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source='Pinned CC0 TCP 1652 Culpeper; exposed Asarabacca case',sections=282,titles=119,paragraphs=sum(len(s['paragraphs']) for s in sections),matrix_cells_per_mechanism=119*282,core_mechanisms=['B','A','R','G'],unions=['UA','UR','UG'],old_comparison='O',aggregates=aggregate(rows),transitions={k:{a:b for a,b in v.items() if a not in ['changed_cells','title_contributions']} for k,v in transitions.items()},input_change=dict(removed_words=len(removed),sections=len({r['section'] for r in removed}),cause_occurrences=dict(causes)),exposed_case=[dict(id=r['id'],label=r['label'],own=r['own']) for r in rows if r['label']=='asarabacca'],limitations=['Conservative input eligibility can exclude complete words touching annotations; O→B must be separate from B→union.','No semantic/linguistic significance test or transfer of English proportions to Voynich.','Asarabacca was known before this test, not an independent discovery.','Union rate denominators count tagged windows, not natural word frequency.'])
 dump(OUT/'summary.json',summary)
 dump(OUT/'complete.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='complete',files={p.name:sha(p) for p in sorted(OUT.iterdir()) if p.is_file()}))
 print(json.dumps({k:{'own_hits':v['own_hits'],'other_mean':float(v['other_binary_mean']),'delta':float(v['delta'])} for k,v in summary['aggregates'].items()},ensure_ascii=False,indent=2))
 print('Transitions',json.dumps({k:{a:b for a,b in v.items() if a in ['own_gain_ids','own_loss_ids','other_gain_cells','other_loss_cells']} for k,v in transitions.items()},ensure_ascii=False))
if __name__=='__main__':main()
