"""Check source lines, all source-selected loci, explicit page links and counts."""
from pathlib import Path
from collections import Counter
import datetime as dt
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
PRIVATE=ROOT.parent/'output/voynich/research_next/astronomical7h_20261118/zodiac_inventory'
d=json.loads((HERE/'inventory_v1.json').read_text())
checks=[]
for version,data in d['versions'].items():
    lines=(ROOT/data['file']).read_text().splitlines()
    for f,page in data['folios'].items():
        selected={i:s for i,s in enumerate(lines,1) if s.startswith('<'+f+'.')}
        saved={r['line']:r['raw'] for r in page['records']}
        assert selected==saved,(version,f,'source completeness')
        codes=Counter(s.split('>',1)[0].rsplit(',',1)[1][1:] for s in selected.values())
        assert dict(codes)==page['type_counts'],(version,f,'code counts')
        checks.append({'version':version,'folio':f,'raw_lines_exact_and_complete':True,
                       'loci':len(saved),'types':dict(codes)})
joins=[]
for page in d['pages']:
    q=page['source_page'].split('/')[-2]
    html=(PRIVATE/(q+'.html')).read_text()
    match=re.search(r'ID="'+page['folio']+r'"',html,re.I)
    assert match,page['folio']
    following=re.search(r'<TH\s+CLASS="Ph"',html[match.end():],re.I)
    end=match.end()+following.start() if following else len(html)
    section=html[match.start():end]
    count=int(re.search(r'This page has\s+(\d+)\s+text items',section).group(1))
    circular=int(re.search(r'(\d+)\s+items of circular writing',section).group(1))
    labels=int(re.search(r'(\d+)\s+zodiac labels',section).group(1))
    ids=re.findall(r'collections.library.yale.edu/catalog/2002046\?child_oid=(\d+)',section)
    expected=page['official_canvas']['id'].split('/')[-1]
    assert expected in ids,(page['folio'],ids,expected)
    assert page['catalogue_counts']=={'all':count,'circular':circular,'zodiac_labels':labels}
    for v in page['versions'].values():
        assert all(x==0 for x in v['catalogue_count_differences'].values())
    joins.append({'folio':page['folio'],'source_page':page['source_page'],
                  'source_html_character_range':[match.start(),end],
                  'linked_official_ids':ids,'joined_canvas':expected,'all_counts_match':True})
out={'utc':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'PASS_METADATA_ONLY',
     'inventory_sha256':hashlib.sha256((HERE/'inventory_v1.json').read_bytes()).hexdigest(),
     'source_line_checks':checks,'catalogue_joins':joins,
     'total_loci_each_version':{v:x['selected_line_count'] for v,x in d['versions'].items()},
     'scope_limits':['Verifies complete extraction and explicit primary-source metadata joins.',
                     'Does not verify visual object references, word readings, historical sequence or semantics.']}
(HERE/'validation_v1.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
print(out['status'],out['total_loci_each_version'],len(joins),'explicit catalogue joins')
