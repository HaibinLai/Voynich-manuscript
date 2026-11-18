# -*- coding: utf-8 -*-
"""Structural support only. Never tests real headings against body/candidate strings."""
import collections, datetime, gzip, hashlib, json, re, unicodedata
from pathlib import Path
from xml.dom import minidom, Node

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
SOURCE=HERE.parent/'known_herbal/A35365.xml'
OLD=HERE.parent/'known_herbal/run_v1/sections.json.gz'
EXPECTED='bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb'
NS='http://www.tei-c.org/ns/1.0';MARK='\ufdd0'
EXCLUDE={'note','head','gap','abbr'};LAYOUT={'pb','lb','milestone'}
EOL={'char:EOLhyphen','char:EOLunhyphen'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
norm=lambda s:s.casefold().replace('ſ','s')
dump=lambda p,o:p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def lname(n):return n.localName or n.nodeName
def elements(n,name):return list(n.getElementsByTagNameNS(NS,name))
def old_heading(n,direct=False):
 if n.nodeType in [Node.TEXT_NODE,Node.CDATA_SECTION_NODE]:return n.data
 if n.nodeType!=Node.ELEMENT_NODE:return ''
 tag=lname(n)
 if tag in EXCLUDE and not (direct and tag=='head'):return ' '
 if tag=='g':return '' if n.getAttribute('ref') in EOL else ' '
 if tag in LAYOUT:return ''
 return ''.join(old_heading(c) for c in n.childNodes)
def events(p):
 out=[]
 def walk(n,path):
  if n.nodeType in [Node.TEXT_NODE,Node.CDATA_SECTION_NODE]:
   assert MARK not in n.data
   out.append(dict(type='text',path=path,raw=n.data,normalized=norm(n.data)));return
  if n.nodeType!=Node.ELEMENT_NODE:return
  tag=lname(n);attrs={n.attributes.item(i).name:n.attributes.item(i).value for i in range(n.attributes.length)}
  if tag=='g' and n.getAttribute('ref') in EOL:
   out.append(dict(type='removed_EOL_control',tag=tag,path=path,attributes=attrs));return
  if tag in EXCLUDE|LAYOUT or tag=='g':
   out.append(dict(type='barrier',tag=tag,path=path,attributes=attrs));return
  for i,c in enumerate(n.childNodes):walk(c,path+'/'+lname(c)+'['+str(i)+']')
 walk(p,'p')
 stream=''
 for event in out:
  event['start']=len(stream)
  stream+=event.get('normalized','') if event['type']=='text' else MARK if event['type']=='barrier' else ''
  event['end']=len(stream)
 return stream,out
def wordchar(c):return 'a'<=c<='z'
def separator(c):return c.isspace() or (unicodedata.category(c).startswith('P') and c!='_')
def slots(stream):
 out=[];i=0
 while i<len(stream):
  start=i;c=stream[i]
  if wordchar(c):
   i+=1
   while i<len(stream) and wordchar(stream[i]):i+=1
   complete=not ((start>0 and not separator(stream[start-1]) and not wordchar(stream[start-1])) or (i<len(stream) and not separator(stream[i]) and not wordchar(stream[i])))
   kind='word'
  elif c==MARK:i+=1;kind='barrier';complete=False
  elif separator(c):i+=1;continue
  else:
   i+=1
   while i<len(stream) and stream[i]!=MARK and not wordchar(stream[i]) and not separator(stream[i]):i+=1
   kind='opaque';complete=False
  out.append(dict(slot=len(out),kind=kind,start=start,end=i,text=stream[start:i],comparable=complete))
 return out
def windows(stream,ss):
 out={k:[] for k in ['B','A','R','G']}
 for i,t in enumerate(ss):
  if t['comparable']:out['B'].append(dict(slots=[i],endpoints=[i],length=len(t['text']),start=t['start'],end=t['end']))
 for width,keys in [(2,['A','R']),(3,['G'])]:
  for i in range(len(ss)-width+1):
   ts=ss[i:i+width]
   if not all(t['comparable'] for t in ts):continue
   seams=[stream[a['end']:b['start']] for a,b in zip(ts,ts[1:])]
   if not all(s and s.isspace() for s in seams):continue
   for key in keys:
    ends=[i+width-1,i] if key=='R' else [i,i+width-1]
    out[key].append(dict(slots=list(range(i,i+width)),endpoints=ends,length=len(ts[0]['text'])+len(ts[-1]['text']),start=ts[0]['start'],end=ts[-1]['end']))
 return out
def paragraph(p):
 stream,ee=events(p);ss=slots(stream);return dict(stream=stream,events=ee,slots=ss,windows=windows(stream,ss))
def toy():
 tested=[]
 def parse(s):return paragraph(minidom.parseString(s).documentElement)
 def candidates(p,key):return [''.join(p['slots'][i]['text'] for i in w['endpoints']) for w in p['windows'][key]]
 def ck(name,test):assert test,name;tested.append(name)
 p=parse('<p>A <hi>Sarabacca</hi></p>');ck('known exposed split toy, no spelling change',candidates(p,'B')==['a','sarabacca'] and candidates(p,'A')==['asarabacca'] and candidates(p,'R')==['sarabaccaa'])
 p=parse('<p>A<hi>gri</hi>mony An<g ref="char:EOLhyphen"/>gelica.</p>');ck('style continuity and old EOL removal',candidates(p,'B')==['agrimony','angelica'])
 p=parse('<p>A<g ref="char:EOLunhyphen"/>corn</p>');ck('EOLunhyphen removal',candidates(p,'B')==['acorn'])
 p=parse('<p>red sage blue</p>');ck('adjacent reverse and gap2',candidates(p,'A')==['redsage','sageblue'] and candidates(p,'R')==['sagered','bluesage'] and candidates(p,'G')==['redblue'])
 for tag in ['note','head','gap','abbr','pb','lb','milestone']:
  p=parse('<p>red <'+tag+'>hidden</'+tag+'> blue</p>');ck(tag+' preserves hard slot, no crossing',not candidates(p,'A') and not candidates(p,'G') and len(p['slots'])==3)
 p=parse('<p>red <g ref="char:unknown"/> blue</p>');ck('unknown g barrier',not candidates(p,'A') and not candidates(p,'G'))
 p=parse('<p>fo<gap/>obar An<lb/>gelica</p>');ck('touching XML fragment runs excluded',not candidates(p,'B'))
 for s in ['red, blue','red; blue','red-blue','red / blue']:
  p=parse('<p>'+s+'</p>');ck('punctuation seam '+s,not candidates(p,'A'))
 p=parse('<p>red 123 blue</p>');ck('gap2 opaque numeric middle never skipped',not candidates(p,'G') and len(p['slots'])==3)
 p=parse('<p>red ♄ blue</p>');ck('gap2 opaque symbol middle',not candidates(p,'G'))
 p=parse('<p>red a1b blue</p>');ck('touching opaque fragments cannot be middle',not candidates(p,'G') and [t['comparable'] for t in p['slots']]==[True,False,False,False,True])
 p=parse('<p>red x, blue</p>');ck('gap2 checks both seams',not candidates(p,'G'))
 pp=[parse('<p>red</p>'),parse('<p>blue</p>')];ck('never forms paragraph-crossing windows',not any(candidates(p,'A') for p in pp))
 p=parse('<p>ſAGE. Saint\'s</p>');ck('old ASCII normalization and baseline punctuation runs',candidates(p,'B')==['sage','saint','s'])
 return dict(status='PASS',checks=tested,count=len(tested),real_heading_body_matches_computed=False)
def extract():
 tree=minidom.parse(str(SOURCE));old=json.loads(gzip.decompress(OLD.read_bytes()));sections=[];struct=collections.Counter();notes=collections.Counter()
 divs=[d for d in elements(tree,'div') if d.getAttribute('type')=='herb']
 for i,d in enumerate(divs,1):
  heads=[c for c in d.childNodes if c.nodeType==Node.ELEMENT_NODE and lname(c)=='head'];assert len(heads)==1
  h=heads[0];raw=old_heading(h,True);title=re.findall('[a-z]+',norm(raw));primary=len(title)==1 and not(elements(h,'gap') or elements(h,'abbr'))
  assert old[i-1]['id']==i and old[i-1]['raw_title']==raw and old[i-1]['title_tokens']==title and old[i-1]['primary']==primary
  ps=[]
  for pno,p in enumerate(elements(d,'p')):
   parent=p.parentNode
   while parent is not d:
    assert parent is not None
    if parent.nodeType==Node.ELEMENT_NODE:assert lname(parent) not in EXCLUDE|{'p'}
    parent=parent.parentNode
   packet=paragraph(p);packet['p']=pno;ps.append(packet)
   for e in packet['events']:
    if e['type']=='barrier':notes['barrier_'+e['tag']]+=1
    elif e['type']=='removed_EOL_control':notes['removed_'+e['attributes']['ref']]+=1
   for s in packet['slots']:struct[s['kind']+'_slots']+=1;struct['comparable_slots']+=s['comparable'];struct['incomparable_word_fragments']+=s['kind']=='word' and not s['comparable']
  sections.append(dict(id=i,raw_title=raw,title_tokens=title,primary=primary,paragraphs=ps,old_body_words=old[i-1]['body_words']))
 assert len(sections)==282 and sum(s['primary'] for s in sections)==119
 return sections,dict(struct),dict(notes)
def main():
 assert sha(SOURCE)==EXPECTED
 assert not (HERE/'support_v1.json').exists(),'No overwrite'
 dump(HERE/'support_freeze_v1.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),stage='Before structure/toy only; not permission to score real labels',source_sha256=sha(SOURCE),old_sections_sha256=sha(OLD),files={p.name:sha(p) for p in [HERE/'protocol_v1.txt',Path(__file__)]}))
 toys=toy();sections,structure,notes=extract();details=[];totals={k:collections.Counter() for k in ['B','A','R','G']}
 for s in sections:
  lengths={k:collections.Counter(w['length'] for p in s['paragraphs'] for w in p['windows'][k]) for k in totals}
  for k in totals:totals[k].update(lengths[k])
  details.append(dict(id=s['id'],primary=s['primary'],title_length=len(s['title_tokens'][0]) if s['primary'] else None,p_count=len(s['paragraphs']),slots=sum(len(p['slots']) for p in s['paragraphs']),word_slots=sum(t['kind']=='word' for p in s['paragraphs'] for t in p['slots']),baseline_words=sum(lengths['B'].values()),old_baseline_words=s['old_body_words'],opportunities_by_length={k:dict(sorted(c.items())) for k,c in lengths.items()}))
 out=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sections=282,primary_titles=119,primary_ids=[s['id'] for s in sections if s['primary']],paragraphs=sum(len(s['paragraphs']) for s in sections),structure=structure,event_counts=notes,mechanism_total_opportunities={k:sum(c.values()) for k,c in totals.items()},mechanism_opportunities_by_length={k:dict(sorted(c.items())) for k,c in totals.items()},old_baseline_word_total=sum(s['old_body_words'] for s in sections),new_baseline_word_total=sum(totals['B'].values()),sections_with_changed_word_total=sum(x['baseline_words']!=x['old_baseline_words'] for x in details),sections_detail=details,toy=toys,heading_body_equality_computed=False,matching_matrices_computed=False,next_step='Wait for root approval before any real title matching or result selection.')
 dump(HERE/'support_v1.json',out);dump(HERE/'toy_v1.json',toys)
 print(json.dumps({k:v for k,v in out.items() if k not in ['sections_detail','primary_ids','mechanism_opportunities_by_length','toy']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
