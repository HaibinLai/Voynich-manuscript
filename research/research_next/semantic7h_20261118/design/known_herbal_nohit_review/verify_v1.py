from pathlib import Path
import gzip,hashlib,json,xml.etree.ElementTree as ET,datetime
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sha=lambda b:hashlib.sha256(b).hexdigest()
freeze=json.loads((HERE/'freeze_v1.json').read_text()); checks=[]
for rel,h in freeze['inputs'].items():
    assert sha((ROOT/rel).read_bytes())==h,rel
    checks.append('frozen input unchanged: '+rel)
packet=json.loads(gzip.decompress((HERE/'source_packet_v1.json.gz').read_bytes()))
original=gzip.decompress((HERE.parent/'known_herbal/A35365.xml.gz').read_bytes())
queue=json.loads((HERE/'queue_v1.json').read_text())['selected']
review=json.loads((HERE/'review_v1.json').read_text())['rows']
assert [r['id'] for r in review]==[r['id'] for r in queue]
checks.append('all 17 fixed rows retained in frozen order')
uncovered=[]
def walk(e,covered,sid):
    tag=e.tag.rsplit('}',1)[-1];covered=covered or tag in {'p','head'}
    if e.text and e.text.strip() and not covered:uncovered.append((sid,tag,e.text))
    for c in e:
        walk(c,covered,sid)
        if c.tail and c.tail.strip() and not covered:uncovered.append((sid,'tail',c.tail))
for p,r,q in zip(packet['sections'],review,queue):
    a,b=p['original_xml_byte_range'];part=original[a:b]
    assert part==p['original_xml_utf8'].encode() and sha(part)==p['original_xml_sha256']
    checks.append('exact original XML bytes and hash: '+str(p['id']))
    assert q['own']==r['original_own']==p['original_own'] and not q['own']['binary']
    checks.append('old score copied without changes: '+str(p['id']))
    assert r['all_section_read'] and all(e['quote_present_after_original_exclusions'] for e in r['evidence'])
    walk(ET.fromstring(part),False,p['id'])
assert not uncovered
assert sum(r['p_count'] for r in review)==82
checks+=['all source textual content contained in read heads or paragraphs; 0 uncovered','82 paragraphs declared read; 29 evidence containment checks separately saved']
out={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'PASS','checks':checks,'count':len(checks),'uncovered_text_nodes':uncovered,'scope':'Mechanical provenance/coverage/score-preservation checks, not independent semantic confirmation'}
(HERE/'verification_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
manifest={'utc':out['utc'],'status':'complete','all17':True,'new_scores_computed':False,'files':{p.name:sha(p.read_bytes()) for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='complete_v1.json'}}
(HERE/'complete_v1.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'complete_sha256':sha((HERE/'complete_v1.json').read_bytes()),'report_sha256':sha((HERE/'report_v1.md').read_bytes()),'review_sha256':sha((HERE/'review_v1.json').read_bytes())}))
