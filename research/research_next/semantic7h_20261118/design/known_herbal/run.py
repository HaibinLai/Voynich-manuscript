"""Fixed known-language measurement calibration, using a pinned CC0 TEI edition."""
import argparse, collections, datetime, gzip, hashlib, json, math, re
from pathlib import Path
import xml.etree.ElementTree as ET
from fractions import Fraction

HERE=Path(__file__).resolve().parent
NS='http://www.tei-c.org/ns/1.0'
EXPECTED='bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb'
def local(e):return e.tag.rsplit('}',1)[-1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def flatten(e,counts):
    tag=local(e)
    if tag in {'note','head','gap','abbr'}:
        counts['excluded_'+tag]+=1
        return ' '
    if tag=='g':
        ref=e.get('ref','')
        counts['glyph_'+ref]+=1
        return '' if ref in {'char:EOLhyphen','char:EOLunhyphen'} else ' '
    if tag in {'pb','lb','milestone'}:return ''
    return (e.text or '')+''.join(flatten(c,counts)+(c.tail or '') for c in e)
def heading(e):
    # Direct heading is allowed for the label, but notes/gaps/glyphs are handled identically.
    counts=collections.Counter()
    return (e.text or '')+''.join(flatten(c,counts)+(c.tail or '') for c in e)
def tokens(s):return re.findall('[a-z]+',s.casefold().replace('ſ','s'))
def extract(source):
    r=ET.fromstring(source.read_bytes());sections=[]
    for i,d in enumerate(r.findall('.//{'+NS+'}div[@type="herb"]')):
        h=d.find('{'+NS+'}head');assert h is not None
        title=heading(h);ht=tokens(title)
        head_unknown=any(local(x) in {'gap','abbr'} for x in h.iter())
        ps=[];counts=collections.Counter()
        for p in d.findall('.//{'+NS+'}p'):
            ps.append(tokens(flatten(p,counts)))
        allwords=[w for p in ps for w in p]
        sections.append({'id':i+1,'raw_title':title,'title_tokens':ht,'primary':len(ht)==1 and not head_unknown,
                         'exclusion':'heading_has_gap_or_abbreviation' if head_unknown else ('multiple_or_zero_title_tokens' if len(ht)!=1 else None),
                         'paragraphs':ps,'body_words':len(allwords),'body_counts':dict(collections.Counter(allwords)),
                         'same_length_counts':dict(collections.Counter(map(len,allwords))),'extraction_notes':dict(counts)})
    assert len(sections)==282
    return sections
def avg(v):
    v=list(v);return sum(v,Fraction())/len(v) if v else None
def score(label,section):
    n=section['same_length_counts'].get(len(label),0);m=section['body_counts'].get(label,0)
    return {'section':section['id'],'matches':m,'binary':int(m>0),'same_length_n':n,
            'conditional_rate':Fraction(m,n) if n else None,
            'body_words':section['body_words'],'per_thousand':Fraction(1000*m,section['body_words']) if section['body_words'] else None}
def experiment(sections):
    primary=[s for s in sections if s['primary']];rows=[]
    ids={s['id'] for s in primary}
    for s in primary:
        label=s['title_tokens'][0];matrix=[score(label,t) for t in sections];own=matrix[s['id']-1]
        others=[x for x in matrix if x['section']!=s['id']]
        restricted=[x for x in others if x['section'] in ids]
        b=math.floor(math.log2(max(s['body_words'],1)))
        matched=[x for x in others if math.floor(math.log2(max(x['body_words'],1)))==b]
        row={'id':s['id'],'label':label,'own':own,'matrix':matrix,'controls':{}}
        for name,pool in [('all_other_herbs',others),('other_primary_herbs',restricted),('log2_body_length',matched)]:
            valid=len(pool)>=2
            mu=avg(Fraction(x['binary']) for x in pool) if valid else None
            row['controls'][name]={'count':len(pool),'ids':[x['section'] for x in pool],'binary_mean':mu,
                'delta':Fraction(own['binary'])-mu if valid else None}
        # Deliberate title leakage positive, not natural text.
        artificial=dict(s);artificial['body_counts']=dict(s['body_counts']);artificial['body_counts'][label]=artificial['body_counts'].get(label,0)+1
        artificial['body_words']+=1;artificial['same_length_counts']=dict(s['same_length_counts']);artificial['same_length_counts'][len(label)]=artificial['same_length_counts'].get(len(label),0)+1
        assert score(label,artificial)['binary']==1
        rows.append(row)
    ownmean=avg(Fraction(r['own']['binary']) for r in rows)
    summary={'all_sections':len(sections),'primary_single_word_titles':len(rows),'own_hit_sections':sum(r['own']['binary'] for r in rows),
        'own_binary_mean':ownmean,'own_no_same_length_opportunity':sum(r['own']['same_length_n']==0 for r in rows),
        'controls':{name:{'eligible':sum(r['controls'][name]['delta'] is not None for r in rows),'delta':avg(r['controls'][name]['delta'] for r in rows if r['controls'][name]['delta'] is not None),
        'control_binary_mean':avg(r['controls'][name]['binary_mean'] for r in rows if r['controls'][name]['binary_mean'] is not None)} for name in rows[0]['controls']},
        'title_leakage_positive':{'hits':len(rows),'total':len(rows)},
        'illustrative_first_six_hit':[r['id'] for r in rows if r['own']['binary']][:6],
        'illustrative_first_six_no_hit':[r['id'] for r in rows if not r['own']['binary']][:6]}
    return rows,summary
def toy():
    e=ET.fromstring('<p>A<hi>gri</hi>mony <note>Agrimony</note> root. fo<gap>o</gap>obar. An<g ref="char:EOLhyphen"/>gelica.</p>')
    out=tokens(flatten(e,collections.Counter()))
    assert out==['agrimony','root','fo','obar','angelica'],out
    assert tokens('AGRIMONY ſage')==['agrimony','sage']
    s={'id':1,'body_counts':{'agrimonies':1},'same_length_counts':{10:1},'body_words':1}
    sc=score('agrimony',s);assert sc['binary']==0 and sc['conditional_rate'] is None
    return {'status':'PASS','checks':['nested_inline_join','note_exclusion','gap_boundary','EOL_marker','casefold_long_s','whole_word_not_substring','zero_opportunity_NA','binary_absence']}
def dump(p,x):
    def enc(v):
        if isinstance(v,Fraction):return {'num':v.numerator,'den':v.denominator,'value':float(v)}
        raise TypeError(type(v))
    raw=(json.dumps(x,ensure_ascii=False,indent=2,default=enc,allow_nan=False)+'\n').encode()
    p.write_bytes(gzip.compress(raw,mtime=0) if p.suffix=='.gz' else raw)
def main(a):
    assert sha(a.source)==EXPECTED,'Pinned source mismatch'
    assert not a.output.exists(),'Do not overwrite a run'
    a.output.mkdir(parents=True)
    dump(a.output/'freeze.json',{'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha256':sha(a.source),'protocol_sha256':sha(HERE/'protocol_v1.txt'),'code_sha256':sha(Path(__file__))})
    dump(a.output/'toy.json',toy());sections=extract(a.source);rows,summary=experiment(sections)
    dump(a.output/'sections.json.gz',sections);dump(a.output/'rows.json.gz',rows);dump(a.output/'summary.json',summary)
    dump(a.output/'complete.json',{'status':'complete','files':{p.name:sha(p) for p in sorted(a.output.iterdir()) if p.is_file()}})
    print(json.dumps(summary,default=lambda v:float(v),ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);main(p.parse_args())
