#!/usr/bin/env python3
"""Schema projection and exhaustive comparison; no primary scorer imports.
Usage: python audit_compare.py --output audit_v1.json
Refuses existing audit report paths and all paths outside this directory.
"""
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction as F
import json,gzip,datetime,hashlib,argparse,xml.etree.ElementTree as ET
import audit_core as core
P=Path(__file__).resolve().parent;RUN=P/'run_v1';OWN=P/'audit_run_v2';counts=Counter();diffs=[]
def ck(path,a,b):
 if isinstance(a,dict) and isinstance(b,dict):
  if set(a)!=set(b):bad(path+'.keys',sorted(a),sorted(b))
  for k in a.keys()&b.keys():ck(path+'.'+k,a[k],b[k])
 elif isinstance(a,list) and isinstance(b,list):
  ck(path+'.length',len(a),len(b))
  for i,(x,y) in enumerate(zip(a,b)):ck(path+'[%d]'%i,x,y)
 else:
  counts['scalar_checks']+=1
  okay=abs(a-b)<=1e-12 if isinstance(a,float) and isinstance(b,(int,float)) else a==b
  if not okay:bad(path,a,b)
def bad(path,a,b):
 counts['differences']+=1
 if len(diffs)<100:diffs.append({'path':path,'independent':str(a)[:300],'primary':str(b)[:300]})
def cv(x):
 if isinstance(x,dict):
  if set(x)=={'numerator','denominator'}:return F(x['numerator'],x['denominator'])
  if set(x)=={'num','den','value'}:
   f=F(x['num'],x['den']);ck('fraction_float_projection',float(f),x['value']);return f
  return {k:cv(v) for k,v in x.items()}
 if isinstance(x,list):return [cv(v) for v in x]
 return x

def old_index(sec,p,slot):return sum(s['kind']=='word' for s in sec['paragraphs'][p]['slots'][:slot])
def position(w,sec):
 m=w['model'];p=w['p'];r={'mechanism':m,'p':p}
 if m=='O':r.update(old_word_index=old_index(sec,p,w['slot']),slots=[w['slot']],endpoints=[w['slot']],start=w['start'],end=w['end'])
 else:r.update(window_index=w['window_index'],**{k:w[k] for k in ('slots','endpoints','length','start','end')})
 return r

def cell(x,sec):return {**{k:x[k] for k in ('m','N','rate','binary')},'positions':[position(w,sec) for w in x['positions']]}
def matrix_rows(own,packet):
 rows=[]
 for r in own:
  rr={'id':r['id'],'label':r['query'],'raw_title':r['raw_title'],'matrix':[],'all_other_281':{}}
  for c in r['matrix']:rr['matrix'].append({'section':c['section'],'mechanisms':{m:cell(c['models'][m],packet[c['section']-1]) for m in core.MODELS}})
  rr['own']=rr['matrix'][r['id']-1]['mechanisms']
  for m in core.MODELS:
   other=F(sum(c['models'][m]['binary'] for c in r['matrix'] if c['section']!=r['id']),281)
   rr['all_other_281'][m]={'count':281,'binary_mean':other,'delta':rr['own'][m]['binary']-other}
  rows.append(rr)
 return rows

def event_path_maps():
 root=ET.fromstring(gzip.decompress(core.SOURCE.read_bytes()));globalpaths=core.paths_for(root);maps=[]
 for herb in (e for e in root.iter() if e.get('type')=='herb'):
  section=[]
  for p in (e for e in herb.iter() if core.tag(e)=='p'):
   mm={}
   def walk(e,rel,top=False):
    t=core.tag(e);g=globalpaths[id(e)]
    if (t in core.SKIP and not top) or t=='g':mm[(g,None)]=rel;return
    n=0
    if e.text:mm[(g,'text')]=rel+'/#text[%d]'%n;n+=1
    for c in e:
     walk(c,rel+'/'+core.tag(c)+'[%d]'%n);n+=1
     if c.tail:mm[(globalpaths[id(c)],'tail')]=rel+'/#text[%d]'%n;n+=1
   walk(p,'p',True);section.append(mm)
  maps.append(section)
 return maps

def projected_events(para,pathmap):
 ev=[]
 for e in para['events']:
  path=pathmap[(e['path'],e['part'])]
  if e['kind']=='text':v={'type':'text','path':path,'raw':e['text'],'normalized':core.norm(e['text']),'start':e['start'],'end':e['end']}
  else:v={'type':'barrier' if e['kind']=='barrier' else 'removed_EOL_control','tag':e['tag'],'path':path,'attributes':e['attributes'],'start':e['start'],'end':e['end']}
  ev.append(v)
 return ev

def slot(s):return {k:s[k] for k in ('slot','kind','start','end','text','comparable')}
def project_packet(own,old,maps):
 out=[]
 for sec,prev,sm in zip(own,old,maps):
  rr={k:prev[k] for k in ('id','raw_title','title_tokens','primary')};rr['old_body_words']=len(sec['old_words']);rr['paragraphs']=[]
  for p,pm in zip(sec['paragraphs'],sm):
   rr['paragraphs'].append({'p':p['p'],'stream':p['stream'],'events':projected_events(p,pm),'slots':[slot(s) for s in p['slots']],'windows':{m:[{k:w[k] for k in ('slots','endpoints','length','start','end')} for w in ws] for m,ws in p['windows'].items()}})
   counts['paragraphs']+=1;counts['slots']+=len(p['slots']);counts['events']+=len(p['events']);counts['all_opportunity_windows']+=sum(len(ws) for ws in p['windows'].values())
  out.append(rr)
 return out

def changes(packet):
 removed=[];sc=[];causes_count=Counter()
 for sec in packet:
  nold=nnew=0
  for p in sec['paragraphs']:
   oldi=0;bar={e['start']:e for e in p['events'] if e['type']=='barrier'}
   for s in p['slots']:
    if s['kind']!='word':continue
    oi=oldi;oldi+=1;nold+=1
    if s['comparable']:nnew+=1;continue
    cs=[]
    for side,at in [('left',s['start']-1),('right',s['end'])]:
     if at in bar:cs.append({'side':side,'type':'XML_barrier','event':bar[at]});causes_count[bar[at]['tag']]+=1
     else:
      o=next((x for x in p['slots'] if x['kind']=='opaque' and x['start']<=at<x['end']),None)
      if o:cs.append({'side':side,'type':'opaque','slot':o});causes_count['opaque']+=1
    removed.append({'section':sec['id'],'p':p['p'],'old_word_index':oi,'slot':s,'causes':cs,'normalized_context':p['stream'][max(0,s['start']-60):s['end']+60]})
  sc.append({'section':sec['id'],'old_words':nold,'new_words':nnew,'removed_count':nold-nnew})
 return {'old_total':sum(s['old_words'] for s in sc),'new_total':sum(s['new_words'] for s in sc),'removed_word_count':len(removed),'affected_section_count':sum(s['removed_count']>0 for s in sc),'cause_occurrences':dict(causes_count),'removed_words':removed,'section_counts':sc}

def aggregates(rows):
 result={}
 for m in core.MODELS:
  own=sum(r['own'][m]['binary'] for r in rows);other=sum((r['all_other_281'][m]['binary_mean'] for r in rows),F())/119
  result[m]={'title_count':119,'own_hits':own,'own_binary_mean':F(own,119),'other_binary_mean':other,'delta':F(own,119)-other,'own_N0':sum(r['own'][m]['N']==0 for r in rows),'all_matrix_N0':sum(c['mechanisms'][m]['N']==0 for r in rows for c in r['matrix'])}
 return result

def transitions(rows):
 result={}
 for before,after in [('O','B'),('B','UA'),('B','UR'),('B','UG')]:
  out={'before':before,'after':after,'own_gain_ids':[],'own_loss_ids':[],'other_gain_cells':0,'other_loss_cells':0};contrib=[];changed=[]
  for r in rows:
   own=r['own'][after]['binary']-r['own'][before]['binary'];other=F()
   if own>0:out['own_gain_ids'].append(r['id'])
   if own<0:out['own_loss_ids'].append(r['id'])
   for c in r['matrix']:
    b,a=c['mechanisms'][before],c['mechanisms'][after];d=a['binary']-b['binary']
    if c['section']!=r['id']:other+=F(d,281);out['other_gain_cells']+=d>0;out['other_loss_cells']+=d<0
    if (b['m'],b['N'])!=(a['m'],a['N']):changed.append({'title_id':r['id'],'label':r['label'],'section':c['section'],'before_m':b['m'],'after_m':a['m'],'before_N':b['N'],'after_N':a['N'],'before_binary':b['binary'],'after_binary':a['binary']})
   contrib.append({'title_id':r['id'],'label':r['label'],'own_increment':own,'other_increment_mean':other,'net_increment':own-other})
  out.update(own_increment_mean=sum((F(c['own_increment']) for c in contrib),F())/119,other_increment_mean=sum((c['other_increment_mean'] for c in contrib),F())/119,net_increment=sum((c['net_increment'] for c in contrib),F())/119,title_contributions=contrib,m_or_N_changed_cell_count=len(changed),changed_cells=changed)
  result[before+'_to_'+after]=out
 return result

def adjacent_matches(rows,packet):
 out=[]
 for r in rows:
  for c in r['matrix']:
   for pos in c['mechanisms']['A']['positions']:
    p=packet[c['section']-1]['paragraphs'][pos['p']];out.append({'title_id':r['id'],'label':r['label'],'body_section':c['section'],'own':r['id']==c['section'],'parts':[p['slots'][i]['text'] for i in pos['endpoints']],'baseline_already_hit':bool(c['mechanisms']['B']['binary']),'position':pos,'normalized_context':p['stream'][max(0,pos['start']-65):pos['end']+65]})
 return out

def support_fields(packet,old):
 ss=Counter();ec=Counter();totals=Counter();bylength={m:Counter() for m in ('B','A','R','G')};details=[]
 for sec,prev in zip(packet,old):
  sl=[s for p in sec['paragraphs'] for s in p['slots']];bc={m:Counter(w['length'] for p in sec['paragraphs'] for w in p['windows'][m]) for m in bylength}
  ss['word_slots']+=sum(s['kind']=='word' for s in sl);ss['comparable_slots']+=sum(s['comparable'] for s in sl);ss['incomparable_word_fragments']+=sum(s['kind']=='word' and not s['comparable'] for s in sl);ss['barrier_slots']+=sum(s['kind']=='barrier' for s in sl);ss['opaque_slots']+=sum(s['kind']=='opaque' for s in sl)
  for p in sec['paragraphs']:
   for e in p['events']:
    if e['type']=='barrier':ec['barrier_'+e['tag']]+=1
    elif e['type']=='removed_EOL_control':ec['removed_'+e['attributes']['ref']]+=1
  for m in bylength:bylength[m].update(bc[m]);totals[m]+=sum(bc[m].values())
  details.append({'id':sec['id'],'primary':prev['primary'],'title_length':len(prev['title_tokens'][0]) if prev['primary'] else None,'p_count':len(sec['paragraphs']),'slots':len(sl),'word_slots':sum(s['kind']=='word' for s in sl),'baseline_words':sum(s['comparable'] for s in sl),'old_baseline_words':prev['body_words'],'opportunities_by_length':{m:{str(k):v for k,v in b.items()} for m,b in bc.items()}})
 return {'sections':282,'primary_titles':119,'primary_ids':[s['id'] for s in old if s['primary']],'paragraphs':1317,'structure':dict(ss),'event_counts':dict(ec),'mechanism_total_opportunities':dict(totals),'mechanism_opportunities_by_length':{m:{str(k):v for k,v in c.items()} for m,c in bylength.items()},'old_baseline_word_total':sum(s['body_words'] for s in old),'new_baseline_word_total':ss['comparable_slots'],'sections_with_changed_word_total':sum(d['baseline_words']!=d['old_baseline_words'] for d in details),'sections_detail':details}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',required=True,type=Path);args=ap.parse_args();out=args.output.resolve();assert out.parent==P.resolve() and out.name.startswith('audit_') and out.suffix=='.json' and not out.exists(),'Refuse unsafe/existing output report'
 start=datetime.datetime.now(datetime.timezone.utc).isoformat()
 for folder in [RUN,OWN]:
  receipt=core.read(folder/'complete.json');ck(str(folder)+'.status','complete',receipt['status'])
  for f,h in receipt['files'].items():ck(str(folder)+'.hash.'+f,h,core.sha(folder/f));counts['completion_hashes']+=1
 f=core.read(RUN/'freeze.json')
 for name,h in f['files'].items():ck('primary.freeze.'+name,h,core.sha(P/name));counts['freeze_hashes']+=1
 ck('sourcehash',f['source_sha256'],hashlib.sha256(gzip.decompress(core.SOURCE.read_bytes())).hexdigest())
 ck('oldsectionhash',f['old_sections_sha256'],core.sha(core.OLD/'run_v1/sections.json.gz'));ck('oldrowhash',f['old_rows_sha256'],core.sha(core.OLD/'run_v1/rows.json.gz'))
 for name,h in core.read(OWN/'freeze.json')['files'].items():ck('independent.freeze.'+name,h,core.sha(name))
 old=core.read(core.OLD/'run_v1/sections.json.gz');ownpacket=core.read(OWN/'packet.json.gz');projected=project_packet(ownpacket,old,event_path_maps());ck('packet',projected,core.read(RUN/'packet.json.gz'))
 ident=[{k:s[k] for k in ('id','raw_title','title_tokens','primary')} for s in old if s['primary']];ck('identity',ident,core.read(RUN/'identity.json'))
 supported=support_fields(projected,old);primary_support=core.read(P/'support_v1.json');ck('structural_support',supported,{k:primary_support[k] for k in supported})
 change=changes(projected);ck('input_changes',change,core.read(RUN/'input_changes.json.gz'))
 own=cv(core.read(OWN/'matrix.json.gz'));rows=matrix_rows(own,ownpacket);ck('full_matrix',rows,cv(core.read(RUN/'matrix.json.gz')));counts['matrix_cells']=119*282*8
 oldrows=cv(core.read(core.OLD/'run_v1/rows.json.gz'))
 for r,oldr in zip(rows,oldrows):
  ck('old.id',r['id'],oldr['id']);ck('old.label',r['label'],oldr['label'])
  for c,oc in zip(r['matrix'],oldr['matrix']):
   v=c['mechanisms']['O'];ck('old.cell',{'section':c['section'],'matches':v['m'],'binary':v['binary'],'same_length_n':v['N'],'conditional_rate':v['rate'],'body_words':old[c['section']-1]['body_words'],'per_thousand':F(v['m']*1000,old[c['section']-1]['body_words']) if old[c['section']-1]['body_words'] else None},oc)
 ag=aggregates(rows);tr=transitions(rows);ck('transitions',tr,cv(core.read(RUN/'transitions.json.gz')))
 summary=cv(core.read(RUN/'summary.json'));ck('aggregates',ag,summary['aggregates']);compact={k:{f:v for f,v in t.items() if f not in ('title_contributions','changed_cells')} for k,t in tr.items()};ck('summary.transitions',compact,summary['transitions']);ck('summary.input_change',{'removed_words':change['removed_word_count'],'sections':change['affected_section_count'],'cause_occurrences':change['cause_occurrences']},summary['input_change']);ck('summary.exposed',[{'id':r['id'],'label':r['label'],'own':r['own']} for r in rows if r['id']==12],summary['exposed_case'])
 for k,v in {'sections':282,'titles':119,'paragraphs':1317,'matrix_cells_per_mechanism':33558,'core_mechanisms':['B','A','R','G'],'unions':['UA','UR','UG'],'old_comparison':'O'}.items():ck('summary.'+k,v,summary[k])
 adjacent=adjacent_matches(rows,projected);ck('all_adjacent_matches',adjacent,core.read(P/'all_adjacent_matches.json'))
 report={'status':'PASS' if not counts['differences'] else 'FAIL','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'started':start,'scope':'Independent source XML reconstruction, full packet/events/slots/window positions, all 119x282x8 matrix entries, exact rational controls, all transitions/support changes and matched locations; no primary source imports.','counts':dict(counts),'differences':diffs,'aggregates':ag,'transitions':compact,'all_adjacent_matches':adjacent,'input_changes':{k:v for k,v in change.items() if k not in ('removed_words','section_counts')},'source_sha256':f['source_sha256'],'primary_complete_sha256':core.sha(RUN/'complete.json'),'primary_matrix_sha256':core.sha(RUN/'matrix.json.gz'),'independent_complete_sha256':core.sha(OWN/'complete.json'),'exposure':'Known prior Asarabacca example, 476/182 support counts, and later a collaborator summary of five matches including or+pine were known. Not blind. Core frozen before reading primary packet/matrix.','limitations':['Approved conservative comparability can exclude otherwise complete words touching editorial annotations; this is not a semantic classification.','Asarabacca is an exposed detectability case, not a new independent discovery.','English rates and controls do not transfer to Voynich meaning or language.','Union m/N counts tagged windows, not natural word frequency.'],'independent_failed_runs':['audit_run_v1/failure.json: old body_words integer was initially mistaken for a token list; assertion failed before matching. Frozen attempt source retained.'],'files':{n:core.sha(P/n) for n in ['audit_core.py','audit_core_attempt_01.py','audit_compare.py']}}
 out.write_text(json.dumps(core.pack(report),ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':report['status'],'counts':dict(counts),'differences':diffs[:8]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
