#!/usr/bin/env python3
"""Independent XML/event, slot, opportunity and title-matching reconstruction.
No imports from primary run.py/support.py or any old scorer. Safe explicit output
entry point refuses every pre-existing directory and never modifies frozen data.
"""
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
import xml.etree.ElementTree as ET
import re,gzip,json,hashlib,datetime,argparse,unicodedata,traceback
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'known_herbal';SOURCE=OLD/'A35365.xml.gz'
BARRIER='\ufdd0';SKIP={'head','note','gap','abbr','pb','lb','milestone'};EOL={'char:EOLhyphen','char:EOLunhyphen'};MODELS=('O','B','A','R','G','UA','UR','UG')

def read(p):
 p=Path(p);return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def tag(e):return e.tag.rsplit('}',1)[-1]
def norm(s):return (s or '').replace('ſ','s').casefold()
def pack(x):
 if isinstance(x,Fraction):return {'numerator':x.numerator,'denominator':x.denominator}
 if isinstance(x,dict):return {k:pack(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [pack(v) for v in x]
 return x

def old_text(e,root=False):
 t=tag(e)
 if not root and t in ('note','head','gap','abbr'):return ' '
 if t=='g':return '' if e.get('ref') in EOL else ' '
 if t in ('pb','lb','milestone'):return ' '
 return (e.text or '')+''.join(old_text(c)+(c.tail or '') for c in e)

def paths_for(root):
 result={id(root):'/'+tag(root)+'[1]'}
 def rec(e):
  seen=Counter()
  for c in e:
   seen[tag(c)]+=1;result[id(c)]=result[id(e)]+'/'+tag(c)+'[%d]'%seen[tag(c)];rec(c)
 rec(root);return result

def flow(p,paths=None):
 chunks=[];events=[];offset=0
 def emit(kind,text,e,part=None):
  nonlocal offset
  s=norm(text);events.append({'kind':kind,'tag':tag(e),'path':paths.get(id(e)) if paths else None,'part':part,'attributes':dict(e.attrib),'text':text or '', 'start':offset,'end':offset+len(s)})
  chunks.append(s);offset+=len(s)
 def walk(e,top=False):
  t=tag(e)
  if t in SKIP and not top:emit('barrier',BARRIER,e);return
  if t=='g':
   if e.get('ref') in EOL:emit('eol_removed','',e)
   else:emit('barrier',BARRIER,e)
   return
  if e.text:emit('text',e.text,e,'text')
  for c in e:
   walk(c)
   if c.tail:emit('text',c.tail,c,'tail')
 walk(p,True);return ''.join(chunks),events

def character_class(c):
 if 'a'<=c<='z':return 'word'
 if c==BARRIER:return 'barrier'
 if c.isspace():return 'space'
 if c!='_' and unicodedata.category(c).startswith('P'):return 'punctuation'
 return 'opaque'

def slots_for(stream):
 slots=[];i=0
 while i<len(stream):
  kind=character_class(stream[i]);j=i+1
  if kind in ('space','punctuation'):i=j;continue
  if kind!='barrier':
   while j<len(stream) and character_class(stream[j])==kind:j+=1
  left=character_class(stream[i-1]) if i else None;right=character_class(stream[j]) if j<len(stream) else None
  reasons=[]
  if kind=='word':
   if left in ('barrier','opaque'):reasons.append('left_'+left)
   if right in ('barrier','opaque'):reasons.append('right_'+right)
  slots.append({'slot':len(slots),'kind':kind,'text':stream[i:j],'start':i,'end':j,'comparable':kind=='word' and not reasons,'reasons':reasons})
  i=j
 return slots

def windows_for(stream,slots):
 out={k:[] for k in ('B','A','R','G')}
 def add(m,ss,ee):
  word=''.join(slots[k]['text'] for k in ee);out[m].append({'slots':ss,'endpoints':ee,'word':word,'length':len(word),'start':slots[min(ss)]['start'],'end':slots[max(ss)]['end']})
 for i,t in enumerate(slots):
  if t['comparable']:add('B',[i],[i])
  for length in (2,3):
   ss=list(range(i,i+length))
   if i+length>len(slots) or not all(slots[k]['comparable'] for k in ss):continue
   gaps=[stream[slots[k]['end']:slots[k+1]['start']] for k in ss[:-1]]
   if not all(g and g.isspace() for g in gaps):continue
   if length==2:add('A',ss,ss);add('R',ss,ss[::-1])
   else:add('G',ss,[i,i+2])
 return out

def extract(source,old):
 root=ET.fromstring(source);paths=paths_for(root);herbs=[e for e in root.iter() if e.get('type')=='herb'];assert len(herbs)==len(old)==282
 packet=[];identity=[];changes=[]
 for index,(herb,previous) in enumerate(zip(herbs,old),1):
  head=next(c for c in herb if tag(c)=='head');rawtitle=old_text(head,True);title=re.findall('[a-z]+',norm(rawtitle));unknown=any(tag(c) in ('gap','abbr') for c in head.iter());primary=len(title)==1 and not unknown
  assert (index,rawtitle,title,primary)==(previous['id'],previous['raw_title'],previous['title_tokens'],previous['primary']),('title_identity',index,rawtitle,previous['raw_title'])
  if primary:identity.append({'id':index,'raw_title':rawtitle,'query':title[0]})
  paras=[];old_words=[];ps=[e for e in herb.iter() if tag(e)=='p'];assert len(ps)==len(previous['paragraphs'])
  for pi,e in enumerate(ps):
   stream,events=flow(e,paths);slots=slots_for(stream);windows=windows_for(stream,slots);words=[s['text'] for s in slots if s['kind']=='word']
   assert words==previous['paragraphs'][pi],('old_ascii_runs_changed',index,pi)
   for s in slots:
    if s['kind']=='word':
     rec={'p':pi,'slot':s['slot'],'word':s['text'],'start':s['start'],'end':s['end'],'old_word_index':len(old_words)};old_words.append(rec)
     if not s['comparable']:changes.append(dict(rec,section=index,reasons=s['reasons'],context=stream[max(0,s['start']-60):min(len(stream),s['end']+60)]))
   paras.append({'p':pi,'stream':stream,'events':events,'slots':slots,'windows':windows})
  assert len(old_words)==previous['body_words']
  packet.append({'id':index,'raw_title':rawtitle,'paragraphs':paras,'old_words':old_words})
 assert len(identity)==119
 return packet,identity,changes

def index_packet(packet):
 idx={}
 for sec in packet:
  by={m:defaultdict(list) for m in ('O','B','A','R','G')}
  for w in sec['old_words']:by['O'][len(w['word'])].append(dict(w,model='O'))
  for p in sec['paragraphs']:
   for m,ws in p['windows'].items():
    for wi,w in enumerate(ws):by[m][w['length']].append(dict(w,p=p['p'],window_index=wi,model=m))
  idx[sec['id']]=by
 return idx

def matrices(packet,identity):
 idx=index_packet(packet);result=[]
 for label in identity:
  query=label['query'];L=len(query);cells=[]
  for sec in packet:
   cell={}
   for m in ('O','B','A','R','G'):
    op=idx[sec['id']][m][L];hits=[w for w in op if w['word']==query];cell[m]={'N':len(op),'m':len(hits),'binary':int(bool(hits)),'rate':Fraction(len(hits),len(op)) if op else None,'positions':hits}
   for m,join in [('UA','A'),('UR','R'),('UG','G')]:
    b,a=cell['B'],cell[join];n=b['N']+a['N'];count=b['m']+a['m'];cell[m]={'N':n,'m':count,'binary':max(b['binary'],a['binary']),'rate':Fraction(count,n) if n else None,'positions':b['positions']+a['positions']}
   assert cell['A']['N']==cell['R']['N'];cells.append({'section':sec['id'],'models':cell})
  result.append(dict(label,matrix=cells))
 return result

def summarize(rows):
 result={}
 for m in MODELS:
  vals=[]
  for r in rows:
   own=r['matrix'][r['id']-1]['models'][m]['binary'];other=Fraction(sum(c['models'][m]['binary'] for c in r['matrix'] if c['section']!=r['id']),281);vals.append({'title_id':r['id'],'own':Fraction(own),'other':other,'delta':own-other})
  result[m]={'contributions':vals,**{k:sum((v[k] for v in vals),Fraction())/119 for k in ('own','other','delta')}}
 return result

def toys():
 def p(s):return flow(ET.fromstring('<p>'+s+'</p>'))[0]
 def w(s):
  st=p(s);sl=slots_for(st);return st,sl,windows_for(st,sl)
 tests=[]
 def ck(name,okay):assert okay,name;tests.append(name)
 ck('inline_no_space',p('an<hi>gel</hi>ica')=='angelica');ck('inline_actual_space',p('a <hi>sarabacca</hi>')=='a sarabacca')
 for t in ('gap','abbr','note','pb','lb','milestone','head','g'):
  st,sl,ww=w('fo<'+t+'/>obar');ck('adjacent_barrier_'+t,all(not s['comparable'] for s in sl if s['kind']=='word') and not ww['A'])
 ck('eol_removed',p('an<g ref="char:EOLhyphen"/>gelica')=='angelica')
 st,sl,ww=w('ab cd');ck('forward_reverse',ww['A'][0]['word']=='abcd' and ww['R'][0]['word']=='cdab')
 for punct in (',',"'",'-',';'):
  st,sl,ww=w('ab'+punct+' cd');ck('no_punctuation_join_'+punct,not ww['A'] and len(ww['B'])==2)
 st,sl,ww=w('ab 12 cd');ck('number_slot_blocks_gap2',not ww['G'] and len(sl)==3)
 st,sl,ww=w('ab x cd');ck('gap2_real_middle',ww['G'][0]['word']=='abcd')
 st,sl,ww=w('ab_ cd');ck('opaque_adjacent_fragment',not sl[0]['comparable'])
 st,sl,ww=w('ab <gap/> cd');ck('whitespace_preserves_full_words',len(ww['B'])==2 and not ww['A'])
 st,sl,ww=w('a <hi>sarabacca</hi>');ck('known_case_detector',ww['A'][0]['word']=='asarabacca')
 return tests

def main():
 arg=argparse.ArgumentParser();arg.add_argument('--output',type=Path);args=arg.parse_args();test=toys()
 if args.output is None:print('Synthetic tests only:',len(test));return
 out=args.output.resolve();assert out.parent==HERE.resolve() and out.name.startswith('audit_run_'),'Output must be a new audit_run_* directory here';assert not out.exists(),'Refuse to overwrite any output directory';out.mkdir()
 source=gzip.decompress(SOURCE.read_bytes());oldpath=OLD/'run_v1/sections.json.gz'
 frozen={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_uncompressed_sha256':hashlib.sha256(source).hexdigest(),'independent_scope':'Protocol and schema read; primary run/support and all new result matrices not read before this core freeze. Prior summary/design known, not blind.','files':{str(p):sha(p) for p in [Path(__file__),HERE/'protocol_v1.txt',HERE/'approval_v1.txt',HERE/'SCHEMA.txt',oldpath,SOURCE]},'toy_checks':test}
 (out/'freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
 try:
  assert frozen['source_uncompressed_sha256']=='bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb'
  packet,identity,changes=extract(source,read(oldpath));rows=matrices(packet,identity);summary=summarize(rows)
  for name,x in [('packet',packet),('identity',identity),('changes',changes),('matrix',rows),('summary',summary)]:
   (out/(name+'.json.gz')).write_bytes(gzip.compress(json.dumps(pack(x),ensure_ascii=False,separators=(',',':')).encode()))
  for f,h in frozen['files'].items():assert sha(f)==h
  receipt={'status':'complete','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sections':len(packet),'titles':len(identity),'paragraphs':sum(len(s['paragraphs']) for s in packet),'incomparable_words':len(changes),'affected_sections':len({c['section'] for c in changes}),'files':{p.name:sha(p) for p in out.iterdir()}}
  (out/'complete.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items() if k!='files'},indent=2))
 except Exception as e:
  (out/'failure.json').write_text(json.dumps({'error':str(e),'traceback':traceback.format_exc()},indent=2)+'\n');raise
if __name__=='__main__':main()
