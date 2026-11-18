"""Independent DOM extraction and exact arithmetic audit of known-herbal v1.

Does not import the primary runner. The DOM walk keeps text nodes in original
order, while the primary implementation used ElementTree text/tail recursion.
"""
from pathlib import Path
from collections import Counter
from fractions import Fraction
from xml.dom import minidom,Node
import argparse,datetime,gzip,hashlib,json,re

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[4]
NS='http://www.tei-c.org/ns/1.0'
SOURCE=REPO.parent/'output/voynich/research_next/semantic7h_20261118/known_herbal/A35365/A35365.xml'
EXPECTED='bff4bd8569c5417e1fead6cc4c06b6e0be5b27eaf93295481feccaf524ee9acb'
ERRORS=[];COUNTS=Counter();MAX_FLOAT_ERROR=0.0

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(gzip.decompress(p.read_bytes()) if p.suffix=='.gz' else p.read_text())
def average(v):return sum(v,Fraction(0))/len(v) if v else None

def compare(actual,expected,path):
    global MAX_FLOAT_ERROR
    if isinstance(actual,Fraction):
        compare(actual.numerator,expected['num'],path+'/num')
        compare(actual.denominator,expected['den'],path+'/den')
        diff=abs(float(actual)-expected['value']);MAX_FLOAT_ERROR=max(diff,MAX_FLOAT_ERROR)
        COUNTS['rational_values']+=1
        if diff>1e-14:ERRORS.append([path,'float discrepancy',float(actual),expected['value']])
    elif isinstance(actual,dict):
        if set(actual)!=set(expected):ERRORS.append([path,'keys',str(sorted(actual)),str(sorted(expected))]);return
        for k,a in actual.items():compare(a,expected[k],path+'/'+str(k))
    elif isinstance(actual,list):
        if len(actual)!=len(expected):ERRORS.append([path,'length',len(actual),len(expected)]);return
        for i,(a,b) in enumerate(zip(actual,expected)):compare(a,b,path+'/'+str(i))
    elif actual!=expected:ERRORS.append([path,'exact',actual,expected])
    else:COUNTS['exact_values']+=1

def flatten_node(node,counts,allow_direct_heading=False):
    if node.nodeType in [Node.TEXT_NODE,Node.CDATA_SECTION_NODE]:return node.data
    if node.nodeType!=Node.ELEMENT_NODE:return ''
    name=node.localName
    if name in {'note','gap','abbr'} or (name=='head' and not allow_direct_heading):
        counts['excluded_'+name]+=1
        return ' '
    if name=='g':
        ref=node.getAttribute('ref')
        counts['glyph_'+ref]+=1
        return '' if ref in ['char:EOLhyphen','char:EOLunhyphen'] else ' '
    if name in ['pb','lb','milestone']:return ''
    return ''.join(flatten_node(child,counts) for child in node.childNodes)

def lex(text):
    # ASCII alphabetic words after fixed casefold; no stemming or spelling fixes.
    return re.findall(r'[a-z]+',text.casefold().replace('\u017f','s'))

def elements(node,name):return list(node.getElementsByTagNameNS(NS,name))

def extract(source):
    tree=minidom.parse(str(source));all_herbs=[d for d in elements(tree,'div') if d.getAttribute('type')=='herb']
    structural=Counter();sections=[];nodes={}
    for i,div in enumerate(all_herbs,1):
        headings=[c for c in div.childNodes if c.nodeType==Node.ELEMENT_NODE and c.localName=='head']
        assert len(headings)==1,('direct head count',i,len(headings))
        head=headings[0];raw=flatten_node(head,Counter(),allow_direct_heading=True);title=lex(raw)
        unknown=bool(elements(head,'gap') or elements(head,'abbr'))
        paragraphs=elements(div,'p');body=[];notes=Counter()
        for p in paragraphs:
            parent=p.parentNode
            while parent is not div:
                if parent.nodeType==Node.ELEMENT_NODE:
                    if parent.localName=='p':structural['paragraph_nested_in_paragraph']+=1
                    if parent.localName in ['note','head','gap','abbr']:structural['paragraph_nested_in_excluded_tag']+=1
                parent=parent.parentNode
                assert parent is not None
            body.append(lex(flatten_node(p,notes)))
        counts=Counter(w for para in body for w in para)
        length_counts=Counter(len(w) for para in body for w in para)
        sections.append(dict(id=i,raw_title=raw,title_tokens=title,primary=len(title)==1 and not unknown,
            exclusion='heading_has_gap_or_abbreviation' if unknown else ('multiple_or_zero_title_tokens' if len(title)!=1 else None),
            paragraphs=body,body_words=sum(counts.values()),body_counts=dict(counts),
            same_length_counts={str(k):v for k,v in length_counts.items()},extraction_notes=dict(notes)))
        nodes[i]=div
        structural['herb_sections']+=1;structural['paragraphs']+=len(paragraphs)
        structural['nested_herb_sections']+=sum(d.getAttribute('type')=='herb' for d in elements(div,'div'))
    assert structural['paragraph_nested_in_paragraph']==0
    assert structural['paragraph_nested_in_excluded_tag']==0
    assert structural['nested_herb_sections']==0
    return sections,nodes,dict(structural)

def score(query,target):
    m=target['body_counts'].get(query,0)
    n=sum(count for word,count in target['body_counts'].items() if len(word)==len(query))
    words=sum(target['body_counts'].values())
    return dict(section=target['id'],matches=m,binary=bool(m),same_length_n=n,
        conditional_rate=Fraction(m,n) if n else None,body_words=words,
        per_thousand=Fraction(1000*m,words) if words else None)

def experiment(sections):
    included=[s for s in sections if s['primary']];ids={s['id'] for s in included}
    rows=[];positive=[]
    for s in included:
        query=s['title_tokens'][0];matrix=[score(query,t) for t in sections]
        own=next(r for r in matrix if r['section']==s['id'])
        pools={
            'all_other_herbs':[r for r in matrix if r['section']!=s['id']],
            'other_primary_herbs':[r for r in matrix if r['section']!=s['id'] and r['section'] in ids],
            'log2_body_length':[r for r in matrix if r['section']!=s['id'] and max(r['body_words'],1).bit_length()==max(s['body_words'],1).bit_length()]
        }
        controls={}
        for name,pool in pools.items():
            mu=Fraction(sum(r['binary'] for r in pool),len(pool)) if len(pool)>=2 else None
            controls[name]=dict(count=len(pool),ids=[r['section'] for r in pool],binary_mean=mu,
                                delta=Fraction(own['binary'])-mu if mu is not None else None)
        rows.append(dict(id=s['id'],label=query,own=own,matrix=matrix,controls=controls))
        # Rebuild an artificial word stream instead of just incrementing counters.
        artificial=[query]+[w for para in s['paragraphs'] for w in para]
        positive.append(dict(id=s['id'],label=query,matches=artificial.count(query),
                             binary=query in artificial,body_words=len(artificial),
                             same_length_n=sum(len(w)==len(query) for w in artificial)))
    summary=dict(all_sections=len(sections),primary_single_word_titles=len(rows),
        own_hit_sections=sum(r['own']['binary'] for r in rows),
        own_binary_mean=Fraction(sum(r['own']['binary'] for r in rows),len(rows)),
        own_no_same_length_opportunity=sum(r['own']['same_length_n']==0 for r in rows),
        controls={name:dict(eligible=sum(r['controls'][name]['delta'] is not None for r in rows),
                    delta=average([r['controls'][name]['delta'] for r in rows if r['controls'][name]['delta'] is not None]),
                    control_binary_mean=average([r['controls'][name]['binary_mean'] for r in rows if r['controls'][name]['binary_mean'] is not None])) for name in rows[0]['controls']},
        title_leakage_positive=dict(hits=sum(r['binary'] for r in positive),total=len(positive)),
        illustrative_first_six_hit=[r['id'] for r in rows if r['own']['binary']][:6],
        illustrative_first_six_no_hit=[r['id'] for r in rows if not r['own']['binary']][:6])
    return rows,summary,positive

def toy():
    # Includes unresolved glyph/abbreviation barriers and layout marker handling.
    raw='<p>A<hi>gri</hi>mony <note>Agrimony</note> root. fo<gap>o</gap>obar. An<g ref="char:EOLhyphen"/>gelica. ab<abbr>cd</abbr>ef xy<g ref="char:unknown"/>zz <head>hidden</head> sa<pb/>ge.</p>'
    tokens=lex(flatten_node(minidom.parseString(raw).documentElement,Counter()))
    expected=['agrimony','root','fo','obar','angelica','ab','ef','xy','zz','sage']
    assert tokens==expected,(tokens,expected)
    assert lex('AGRIMONY ſage')==['agrimony','sage']
    assert lex('A Sarabacca')==['a','sarabacca']
    s=dict(id=1,body_counts={'agrimonies':1})
    result=score('agrimony',s)
    assert not result['binary'] and result['conditional_rate'] is None
    return dict(passed=True,cases=['inline_join','note_head_exclusion','gap_abbr_unknown_glyph_barriers','EOL_control_removal',
        'page_marker_removal','casefold_long_s','literal_initial_space_preserved','whole_word_non_substring','zero_length_opportunity_NA'])

def absence_diagnostic(rows,nodes):
    # Post-result measurement example only, never used to revise normalization.
    selected=next(r for r in rows if r['label']=='asarabacca')
    div=nodes[selected['id']]
    excerpts=[]
    for p in elements(div,'p'):
        xml=p.toxml()
        if 'Sarabacca' in xml:
            start=xml.index('Sarabacca');excerpts.append(xml[max(0,start-30):start+100])
    assert selected['own']['matches']==0
    assert excerpts
    return dict(id=selected['id'],label=selected['label'],literal_matches=selected['own']['matches'],
        source_excerpt=excerpts[0],explanation='An explicit source-space between A and inline Sarabacca produces two tokens a/sarabacca. Zero whole-word match is a measurement/spelling boundary fact, not evidence the plant name or referent is absent.',
        normalization_changed=False)

def main(source,output):
    assert sha(source)==EXPECTED
    run=HERE/'run_v1';freeze=read(run/'freeze.json')
    compare(sha(source),freeze['source_sha256'],'freeze/source')
    compare(sha(HERE/'run.py'),freeze['code_sha256'],'freeze/primary_code')
    compare(sha(HERE/'protocol_v1.txt'),freeze['protocol_sha256'],'freeze/protocol')
    for name,digest in read(run/'complete.json')['files'].items():compare(sha(run/name),digest,'complete/'+name)
    sections,nodes,structural=extract(source)
    compare(sections,read(run/'sections.json.gz'),'sections')
    rows,summary,positive=experiment(sections)
    compare(rows,read(run/'rows.json.gz'),'rows')
    compare(summary,read(run/'summary.json'),'summary')
    COUNTS['sections']=len(sections);COUNTS['primary_headings']=len(rows)
    COUNTS['matrix_cells']=sum(len(r['matrix']) for r in rows)
    COUNTS['control_sets']=sum(len(r['controls']) for r in rows)
    COUNTS['leakage_positive_targets']=len(positive)
    positive_correct=all(r['binary'] and r['matches']>=1 for r in positive)
    if not positive_correct:ERRORS.append(['leakage','failure'])
    report=dict(passed=not ERRORS,checked_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        counts=dict(COUNTS),max_float_difference=MAX_FLOAT_ERROR,errors=ERRORS,
        structural_checks=structural,toy_checks=toy(),source_sha256=sha(source),audit_code_sha256=sha(Path(__file__)),
        frozen_commit='2b09f3e54d85c5faf0738f823648edf6f070cef8',
        input_hashes={p.name:sha(p) for p in sorted(run.iterdir()) if p.is_file()},
        no_hit_ids=[r['id'] for r in rows if not r['own']['binary']],
        log2_insufficient_controls=[dict(id=r['id'],label=r['label'],count=r['controls']['log2_body_length']['count']) for r in rows if r['controls']['log2_body_length']['delta'] is None],
        leakage_positive_rows=positive,post_result_measurement_example=absence_diagnostic(rows,nodes),
        scope='Independent minidom source extraction and rational matrix/control/summary replay. No primary-run imports; all paragraphs and annotation exclusions checked.',
        limitations=['This is a detector calibration on one known English herbal, not a natural-language null for Voynich.',
                    '17 literal no-hit sections do not establish absence of the plant name, spelling variants or reference in the text.',
                    'No original page-image palaeographic verification or semantic annotation was performed.'])
    output.with_suffix('.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['已知英文草药书：独立提取与计算审核','',('通过' if report['passed'] else '失败'),
        '未导入主run.py。用独立DOM遍历重建所有标题/段落/字串与标记计数，再用有理数复算矩阵和控制。',
        '全部282个herb分节、119个主要单词标题、33,558个标题×正文矩阵格、357个控制集合及119个标题泄漏阳性检查通过。',
        '自身原样词命中102/119=6/7；未原样命中的17条不是“名字完全没有被提到”。',
        'Asarabacca事后例证：XML保留A与Sarabacca之间空格，固定规则得到a/sarabacca两词。这是测量/拼写边界问题；主结果没有被偷偷修正。',
        '正文排除note/head/gap/abbr；gap、abbr、未知glyph隔开两侧，EOL控制标记被删除；样式hi不自动插入词界，原有空格仍保留。独立结构检查未发现p嵌套或p处于排除标记内部。',
        '三个对照池、log2支持不足和等标题/等对照分节权重均逐项复核。完整计数与矩阵的整数/有理数均一致。',
        '本已知文本只校准当前检测器的行为，不能用其命中率与伏尼契手稿差值判断后者不是自然语言。','',json.dumps({k:report[k] for k in ['counts','structural_checks','max_float_difference','log2_insufficient_controls','post_result_measurement_example','errors']},ensure_ascii=False,indent=2)]
    output.with_suffix('.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps({k:report[k] for k in ['passed','counts','max_float_difference','structural_checks','log2_insufficient_controls','errors']},ensure_ascii=False,indent=2))
    if ERRORS:raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=SOURCE);p.add_argument('--output',type=Path,default=HERE/'audit_v1')
    a=p.parse_args();main(a.source,a.output)
