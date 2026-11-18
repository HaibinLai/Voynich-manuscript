"""Design-stage opportunity inventory. NO label/body string comparisons or match scores."""
import collections, datetime, gzip, hashlib, itertools, json, re
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE.parents[1]
REPO=HERE.parents[4]
INPUT=RUN.parent/'label_body/saved_v1/input.json.gz'
LABELS=RUN/'literature/label_support.json'
PAIRS=RUN/'literature/plant_pairs.json'
MANIFEST=REPO/'research/research7h/visual_audit/yale_manifest.json'
SIX=[''.join(p) for p in itertools.combinations('fkpt',2)]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def units(w): return re.findall(r"@\d{3};|[a-z']",w)
def protected_positions(w):
    return {i for m in re.finditer(r'c[tfkp]h',w) for i in range(m.start(),m.end())}
def bare_counts(w):
    protected=protected_positions(w)
    return dict(collections.Counter(c for i,c in enumerate(w) if c in 'fkpt' and i not in protected))
def expansion_length(w):
    bc=bare_counts(w)
    return len(units(w))+bc.get('f',0)+bc.get('p',0)
def clean_label(raw):
    return re.sub(r'<[^>]*>','',raw).split('.')
def histogram(page,strict,expanded):
    # Only word LENGTH enters the output; no target identity is examined.
    count=collections.Counter()
    for row in page['body']:
        if strict and row['uncertain_space']:continue
        for word in row['tokens']:
            if word is None:continue
            count[expansion_length(word) if expanded else len(units(word))]+=1
    return count
def meta(p):return {k:p[k] for k in ['folio','leaf','H','I','Q']}

def main():
    assert not (HERE/'support_v1.json').exists(),'Do not overwrite a design snapshot'
    data=json.loads(gzip.decompress(INPUT.read_bytes()))
    lab=json.loads(LABELS.read_text());pair={r['pair_id']:r for r in json.loads(PAIRS.read_text())['records']}
    selected=[r for r in lab['records'] if r['status']=='source_numbered_locator']
    result={'scope':'Metadata, source labels, lengths and opportunity counts ONLY. No lexical matches computed.',
      'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'protocol_status':'proposal_not_frozen',
      'inputs':{str(p.relative_to(REPO)):sha(p) for p in [INPUT,LABELS,PAIRS,MANIFEST,Path(__file__)]},
      'excluded_23':[{'pair_id':r['pair_id'],'reason':r['status'],'target_object':pair[r['pair_id']]['herbal_object']} for r in lab['records'] if r not in selected],
      'records':[]}
    for r in selected:
        pr=pair[r['pair_id']]
        rec={k:r[k] for k in ['pair_id','pharma_folio','fragment_id','herbal_folio','source_grade','candidate_locators','illustration_source_url']}
        rec.update(target_object=pr['herbal_object'],source_row=pr['row_top_to_bottom'],source_column=pr['column_in_source_number_table'],visual_rechecked=False,versions={})
        for v,d in data.items():
            pages={p['folio']:p for p in d['pages']};target=pages[r['herbal_folio']];source=pages[r['pharma_folio']]
            texts=[clean_label(l['raw']) for l in r['label_records'][v]]
            flat=sum(texts,[]);single=len(flat)==1 and len(texts)==1
            wholeleaf=collections.defaultdict(set)
            for p in d['pages']:wholeleaf[p['leaf']].add((p['H'],p['I']))
            controls=[p for p in d['pages'] if p['H']==target['H'] and p['I']==target['I'] and p['leaf'] not in {source['leaf'],target['leaf']}]
            info={'source':meta(source),'target':meta(target),'locus_word_groups':texts,'main_single_word':single,
                'word_lengths':[len(units(w)) for w in flat],
                'bare_gallows':[bare_counts(w) for w in flat],
                'protected_benches':[re.findall(r'c[tfkp]h',w) for w in flat],
                'six_pair_changeable_positions':{s:sum(sum(bare_counts(w).get(c,0) for c in s) for w in flat) for s in SIX},
                'expanded_lengths':[expansion_length(w) for w in flat],
                'target_unknown_hand':target['H'] not in set('12345'),
                'target_leaf_mixed_HI':len(wholeleaf[target['leaf']])>1,
                'control_pages':[meta(p) for p in controls],
                'control_leaf_count':len({p['leaf'] for p in controls}),
                'whole_leaf_HI_control_leaves':sorted({p['leaf'] for p in controls if len(wholeleaf[p['leaf']])==1}),
                'opportunities':{}}
            for strict in [False,True]:
                for expanded in [False,True]:
                    name=('strict_space' if strict else 'packet_tokens')+('_expanded_length' if expanded else '_raw_length')
                    Ls=info['expanded_lengths'] if expanded else info['word_lengths']
                    th=histogram(target,strict,expanded)
                    leafcounts=collections.defaultdict(lambda:collections.Counter())
                    pagecounts={}
                    for p in controls:
                        hh=histogram(p,strict,expanded);leafcounts[p['leaf']].update(hh)
                        pagecounts[p['folio']]={L:hh[L] for L in sorted(set(Ls))}
                    info['opportunities'][name]={'target_counts':{L:th[L] for L in sorted(set(Ls))},
                      'control_page_counts':pagecounts,
                      'control_leaf_counts':{leaf:{L:hh[L] for L in sorted(set(Ls))} for leaf,hh in sorted(leafcounts.items())},
                      'support_by_length':{L:{'control_leaves_min1':sum(hh[L]>=1 for hh in leafcounts.values()),'control_leaves_min5':sum(hh[L]>=5 for hh in leafcounts.values()),'target_min1':th[L]>=1,'target_min5':th[L]>=5} for L in sorted(set(Ls))}}
            rec['versions'][v]=info
        result['records'].append(rec)
    (HERE/'support_v1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for r in result['records']:
        print(r['pair_id'])
        for v,d in r['versions'].items():
            ss=d['opportunities']['strict_space_raw_length']
            print(' ',v,d['locus_word_groups'],'L',d['word_lengths'],'H',d['target']['H'],'controls',d['control_leaf_count'],'strictleaf',len(d['whole_leaf_HI_control_leaves']),'support',ss['target_counts'],ss['support_by_length'])
    # Map SOURCE-established folio references to official manifest canvas metadata.
    # f90v2 is deliberately unresolved because the source link and catalog label conflict.
    oid={'f13v':1006099,'f18v':1006109,'f19r':1006110,'f23r':1006118,'f34v':1006141,'f36r':1006144,'f44r':1006160,'f48r':1006168,'f51r':1006174,'f96v':1006245,'f89v2':1006234,'f99r':1006246,'f99v':1006247,'f100r':1006248,'f100v':1006249,'f102r2':1006251,'f102v2':1006252,'f102v1':1006253,'f90v2':1006236}
    mf=json.loads(MANIFEST.read_text());cm={int(c['id'].rsplit('/',1)[1]):c for c in mf['items']}
    canvases={}
    for folio,n in oid.items():
        c=cm[n];im=c['items'][0]['items'][0]['body']
        canvases[folio]={'folio':folio,'oid':n,'manifest_label':c['label'],'canvas_id':c['id'],'image_id':im['id'],'width':im['width'],'height':im['height'],
            'mapping_status':'unresolved_source_link_catalog_label_conflict' if folio=='f90v2' else 'source_link_metadata_only_not_visually_confirmed'}
    queue=[]
    for r in result['records']:
        queue.append({k:r[k] for k in ['pair_id','fragment_id','pharma_folio','herbal_folio','source_row','source_column','source_grade','candidate_locators','target_object','illustration_source_url']})
        queue[-1].update(source_canvas=canvases[r['pharma_folio']]['canvas_id'],target_canvas_candidate=canvases[r['herbal_folio']]['canvas_id'],
            source_label_groups={v:r['versions'][v]['locus_word_groups'] for v in ['ZL','IT']},review_status='pending',crop_coordinates=None,
            checks=['Identify panel before numbering object; do not search for a lexical hit.', 'Verify source object row/column from full drawing, then label spatial attachment and all locus boundaries.', 'Record absent/ambiguous attachment or glyph without substituting neighboring labels.', 'Compare fixed plant pair morphology while blinded to herbal text; preserve similarity/uncertainty and mismatches.', 'Do not infer species or established semantics; do not add pairs based on text.'])
    audit={'scope':'Metadata only. No new image inspection or download. Fixed 12-pair review queue.',
      'official_manifest_id':mf['id'],'saved_manifest_sha256':sha(MANIFEST),'canvases':canvases,'queue':queue,
      'f90v2_conflict':{'source_folio':'f90v2','source_page':'https://www.voynich.nu/q15/index.html','linked_catalog_url':'https://collections.library.yale.edu/catalog/2002046?child_oid=1006236','official_label':'90r','alternative_not_auto_selected':{'oid':1006237,'manifest_label':cm[1006237]['label']},'resolution':'Check image and foldout geometry before admitting pair136; no substitution based on words.'}}
    (HERE/'visual_queue_v1.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
