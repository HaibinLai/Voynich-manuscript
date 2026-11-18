"""Read-only extraction of the frozen 17 sections; no new match scoring."""
from pathlib import Path
import gzip, hashlib, json, re, xml.etree.ElementTree as ET
from xml.parsers import expat
HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'known_herbal/A35365.xml.gz'
local=lambda e:e.tag.rsplit('}',1)[-1]
sha=lambda b:hashlib.sha256(b).hexdigest()
q=json.loads((HERE/'queue_v1.json').read_text())['selected']
raw=gzip.decompress(SOURCE.read_bytes())
parser=expat.ParserCreate(); starts=[]; ranges=[]; stack=[]
def start(tag,attrs):
    stack.append(tag)
    if tag=='div' and attrs.get('type')=='herb':starts.append((len(stack),parser.CurrentByteIndex))
def end(tag):
    if starts and starts[-1][0]==len(stack):
        _,a=starts.pop();b=raw.index(b'>',parser.CurrentByteIndex)+1;ranges.append((a,b))
    stack.pop()
parser.StartElementHandler=start;parser.EndElementHandler=end;parser.Parse(raw,True)
assert len(ranges)==282
root=ET.fromstring(raw);paths={}
def walk(e,path):
    paths[id(e)]=path;counts={}
    for c in e:
        t=local(c);counts[t]=counts.get(t,0)+1;walk(c,path+'/'+t+'['+str(counts[t])+']')
walk(root,'/'+local(root)+'[1]')
divs=[e for e in root.iter() if local(e)=='div' and e.get('type')=='herb']
def visible(e):
    # Preserve all textual content; special empty source tags are explicit.
    if local(e) in {'g','gap','lb','pb'}:return '['+local(e)+':'+','.join(k+'='+v for k,v in e.attrib.items())+']'
    return (e.text or '')+''.join(visible(c)+(c.tail or '') for c in e)
bundle=[];lines=[]
for row in q:
    i=row['id'];d=divs[i-1];a,b=ranges[i-1]; exact=raw[a:b]
    assert ET.fromstring(exact).attrib==d.attrib
    nodes=[]
    for n in d.iter():
        if local(n) in {'head','p','note','abbr','gap'}:
            nodes.append({'path':paths[id(n)],'tag':local(n),'attributes':n.attrib,'full_visible_text':visible(n),'xml_serialization':ET.tostring(n,encoding='unicode')})
    bundle.append({'id':i,'label':row['label'],'original_own':row['own'],'section_path':paths[id(d)],'original_xml_utf8':exact.decode(),'original_xml_byte_range':[a,b],'original_xml_sha256':sha(exact),'nodes':nodes})
    lines.append('\nSECTION '+str(i)+' '+row['label']+' '+paths[id(d)])
    lines.extend(n['tag']+' '+n['path']+'\n'+n['full_visible_text'] for n in nodes)
out={'source_gzip_sha256':sha(SOURCE.read_bytes()),'source_xml_sha256':sha(raw),'queue_sha256':sha((HERE/'queue_v1.json').read_bytes()),'selection_count':len(bundle),'sections':bundle,'raw_xml_note':'Exact UTF-8 byte slices from decompressed original; no namespace or whitespace rewriting. Node serialization is separately marked.'}
(HERE/'source_packet_v1.json.gz').write_bytes(gzip.compress((json.dumps(out,ensure_ascii=False,indent=2)+'\n').encode(),mtime=0))
(HERE/'reading_packet_v1.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({'sections':len(bundle),'paragraphs':sum(n['tag']=='p' for b in bundle for n in b['nodes']),'source_sha256':out['source_gzip_sha256'],'packet_sha256':sha((HERE/'source_packet_v1.json.gz').read_bytes())}))
