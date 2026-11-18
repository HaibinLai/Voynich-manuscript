#!/usr/bin/env python3
"""Independent space_bridge implementation, protocol-derived, no scorer imports.
Pre-authorization entry point ONLY verifies preserved raw/slot structure and toys.
No real query matching is performed by --inspect-structure.
"""
from pathlib import Path
import re,json,gzip,hashlib,datetime,argparse
from collections import Counter
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
INPUT=REPO/'research/research_next/label_body/saved_v1/input.json.gz'

def units(s):
 u=re.findall(r"@\d{3};|[a-z']",s)
 return u if u and ''.join(u)==s else None

def parse_raw(raw):
 # Track coordinates in the exact legacy-normalized character stream.
 chars=[];barriers=[];i=0
 while i<len(raw):
  if raw[i]=='<':
   j=raw.find('>',i+1)
   if j<0:raise ValueError('unterminated angle marker')
   tag=raw[i:j+1];barriers.append({'at':len(chars),'tag':tag})
   if tag in ('<->','<~>'):chars.append('.')
   i=j+1;continue
  c=raw[i];i+=1
  if c.isspace() or c in '{}':continue
  chars.append('.' if c==',' else c.lower())
 norm=''.join(chars);out=[]
 for m in re.finditer(r'[^.]+',norm):
  word=m.group();u=units(word);internal=[b for b in barriers if m.start()<b['at']<m.end()]
  out.append({'slot':len(out),'raw':word if u else None,'normalized_raw':word,'start':m.start(),'end':m.end(),'units':u,'comparable':u is not None and not internal,'internal_markers':internal})
 return {'normalized':norm,'tokens':out,'barriers':barriers}

def valid_window(line,i,distance):
 ts=line['tokens'];j=i+distance
 if j>=len(ts) or not all(t['comparable'] for t in ts[i:j+1]):return False
 return not any(ts[i]['end']<=b['at']<=ts[j]['start'] for b in line['barriers'])

def forbidden_seams(query):
 u=units(query)
 if u is None:raise ValueError('invalid query')
 return {k+offset for k in range(len(u)-2) if u[k]=='c' and u[k+1] in 'tkfp' and u[k+2]=='h' for offset in (1,2)}

def joint_opportunity(line,i,distance,query):
 if not valid_window(line,i,distance):return False
 a,b=line['tokens'][i],line['tokens'][i+distance];la,lb=len(a['units']),len(b['units']);bad=forbidden_seams(query)
 return la+lb==len(units(query)) and la not in bad and lb not in bad

def toy_checks():
 checks=[]
 def check(name,ok):
  assert ok,name;checks.append(name)
 p=parse_raw('a.b.c');check('normal_slots', [t['raw'] for t in p['tokens']]==['a','b','c']);check('adjacent',valid_window(p,0,1));check('gap2',valid_window(p,0,2))
 p=parse_raw('a.?.b');check('none_slot_retained',[t['raw'] for t in p['tokens']]==['a',None,'b']);check('gap2_unknown_blocked',not valid_window(p,0,2))
 for tag in ['<->','<~>','<!gap>','<!tear>','<!through plant>','<%>','<$>','<@H=2>']:
  p=parse_raw('a.'+tag+'b.c');check('barrier_'+tag,not valid_window(p,0,1) and not valid_window(p,0,2) and valid_window(p,1,1))
 p=parse_raw('a<!gap>.b');check('trailing_tag',not valid_window(p,0,1))
 p=parse_raw('a.b<!gap>c.d');check('internal_tag',[t['comparable'] for t in p['tokens']]==[True,False,True]);check('internal_tag_does_not_add_slot',len(p['tokens'])==3)
 p=parse_raw('a,b');check('comma_preserves_slots',[t['raw'] for t in p['tokens']]==['a','b'])
 p=parse_raw('@123;.ab');check('extension_atomic',len(p['tokens'][0]['units'])==1)
 p=parse_raw('c.th');check('bench_join_disallowed',not joint_opportunity(p,0,1,'cth'))
 p=parse_raw('c.thx');check('both_order_seams_protected',not joint_opportunity(p,0,1,'cthx'))
 p=parse_raw('ab.cd');check('ordinary_join_opportunity',joint_opportunity(p,0,1,'abcd'))
 p=parse_raw('ab.cd.ef');check('gap_total_excludes_middle',joint_opportunity(p,0,2,'abef'))
 p=parse_raw('a<!funny, glyph>.b');check('comment_comma_not_split',len(p['tokens'])==2)
 return checks

def inspect_structure():
 raw=json.loads(gzip.decompress(INPUT.read_bytes()));versions={}
 for v in ('ZL','IT'):
  counts=Counter();mismatches=[];internal=[]
  for page in raw[v]['pages']:
   for loc in page['body']:
    p=parse_raw(loc['raw']);counts['loci']+=1;counts['slots']+=len(p['tokens']);counts['barriers']+=len(p['barriers'])
    actual=[t['raw'] for t in p['tokens']]
    if actual!=loc['tokens']:mismatches.append({'folio':page['folio'],'locator':loc['locator'],'source_line':loc['source_line'],'expected':loc['tokens'],'rebuilt':actual})
    for t in p['tokens']:
     counts['none_slots']+=t['raw'] is None
     if t['raw'] is not None and not t['comparable']:
      counts['old_exact_retained_now_incomparable']+=1;internal.append({'folio':page['folio'],'locator':loc['locator'],'slot':t['slot'],'markers':t['internal_markers']})
  versions[v]={'counts':dict(counts),'slot_mismatches':mismatches,'internally_marked_retained_tokens':internal}
 out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS' if all(not v['slot_mismatches'] for v in versions.values()) else 'FAIL','scope':'Independent raw/slot/barrier reconstruction only; no real candidate matching or scores','input_sha256':hashlib.sha256(INPUT.read_bytes()).hexdigest(),'audit_py_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'toy_checks':toy_checks(),'versions':versions}
 (HERE/'audit_structure_reconstruction_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':out['status'],'toy_checks':len(out['toy_checks']),'versions':{v:x['counts'] for v,x in versions.items()}},indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inspect-structure',action='store_true');a=p.parse_args()
 if a.inspect_structure:inspect_structure()
 else:print('No real scoring enabled; independent implementation awaits final protocol and explicit authorization.')
