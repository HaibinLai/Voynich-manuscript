"""Allowed-page design counts only; deliberately no word-match operation."""
from pathlib import Path
from collections import Counter, defaultdict
import json, re, sys, hashlib, statistics, csv

HERE = Path(__file__).resolve().parent
BASE = HERE.parents[1]
sys.path.insert(0, str(BASE/'study20'))
from analyze import tokenize, units

IMAGE = {'La','Lc','Lf','Ln','Lp','Ls','Lt','Lz'}
BODY = {'P0','P1','Pc','Pr','Pt'}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name, value):
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n'
    assert '/Users/' not in text
    (HERE/name).write_text(text)

def counts(rows):
    slots = [s for r in rows for s in r['slots']]
    return dict(loci=len(rows), slots=len(slots), retained=sum(s is not None for s in slots),
        missing=sum(s is None for s in slots),
        complete_loci=sum(bool(r['slots']) and all(s is not None for s in r['slots']) for r in rows),
        incomplete_loci=sum(any(s is None for s in r['slots']) for r in rows),
        empty_loci=sum(not r['slots'] for r in rows),
        multiword_loci=sum(len(r['slots'])>1 for r in rows),
        complete_singleword_loci=sum(len(r['slots'])==1 and r['slots'][0] is not None for r in rows))

def selected_records(name, allowed):
    result, current, seen_pages = [], None, set()
    with (BASE/'sources'/name).open() as stream:
        for line_number,line in enumerate(stream,1):
            if not line.startswith('<'):
                if current in allowed and line.startswith('/'):
                    raise ValueError(('unhandled allowed-page wrapping',name,line_number))
                continue
            head = re.match(r'<([^>]+)>',line)
            if not head:
                raise ValueError(('bad source header',name,line_number))
            tag=head[1]
            if '.' not in tag:
                current=tag
                if current in allowed:seen_pages.add(current)
                continue
            # Payload is deliberately not extracted until the folio allowlist passes.
            if current not in allowed:continue
            locator,kind=tag.split(',',1)
            assert locator.split('.')[0]==current
            payload=line[head.end():].strip()
            if payload.startswith('/') or payload.endswith('/'):
                raise ValueError(('unhandled allowed-locus wrapping',locator))
            token_values=tokenize(payload,spaces='split',alternatives='exclude')
            lengths=[None if word is None else dict(eva=len(units(word,'eva')),
                merged=len(units(word,'merged'))) for word in token_values]
            result.append(dict(folio=current,locator=locator,kind=kind,type=kind[1:],
                source_line=line_number,slots=lengths,
                uncertain_spaces=payload.count(','),
                inline_H=re.findall(r'<@H=([^>]+)>',payload)))
    assert seen_pages==set(allowed)
    assert len({r['locator'] for r in result})==len(result)
    return result

def main():
    manifest=json.loads((HERE.parent/'split_manifest.json').read_text())
    allowed={r['folio']:r for r in manifest if r['split'] in {'train','legacy','dev'}}
    assert all(r['split'] not in {'confirm','reserve'} for r in allowed.values())
    save('allowed_pages.json',list(allowed.values()))
    summary={}; per_page=[]; all_rows={}; support=[]; label_slots=[]
    for source in ['ZL3b-n.txt','IT2a-n.txt']:
        rows=selected_records(source,allowed);all_rows[source]=rows
        bypage=defaultdict(list)
        for r in rows:bypage[r['folio']].append(r)
        for folio,m in allowed.items():
            rr=bypage[folio]
            image=[r for r in rr if r['type'] in IMAGE and r['kind'][0]!='!']
            body=[r for r in rr if r['type'] in BODY and r['kind'][0]!='!']
            rec={**m,'source':source,'pool':'dev' if m['split']=='dev' else 'train_legacy',
                'image_labels':counts(image),'body':counts(body),
                'Pb_separate':counts([r for r in rr if r['type']=='Pb']),
                'L0_separate':counts([r for r in rr if r['type']=='L0']),
                'Lx_separate':counts([r for r in rr if r['type']=='Lx']),
                'image_by_type':{t:counts([r for r in image if r['type']==t]) for t in sorted({r['type'] for r in image})}}
            rec['pairable']=rec['image_labels']['retained']>0 and rec['body']['retained']>0
            per_page.append(rec)
            if not rec['pairable']:continue
            for r in image:
                for slot,ln in enumerate(r['slots']):
                    if ln is None:continue
                    label_slots.append(dict(source=source,folio=folio,leaf=m['leaf'],split=m['split'],pool=rec['pool'],
                        H=m['metadata'].get('H','?'),I=m['metadata'].get('I','?'),Q=m['metadata'].get('Q','?'),
                        locator=r['locator'],slot=slot,type=r['type'],kind=r['kind'],**ln,
                        single_complete=len(r['slots'])==1,
                        at_single_complete=len(r['slots'])==1 and r['kind'][0]=='@'))
        ss=[]
        for pool in ['train_legacy','dev','all_allowed']:
            pp=[p for p in per_page if p['source']==source and (pool=='all_allowed' or p['pool']==pool)]
            paired=[p for p in pp if p['pairable']]
            pp_rows=[r for r in rows if any(p['folio']==r['folio'] for p in pp)]
            ss.append(dict(pool=pool,allowed_pages=len(pp),allowed_leaves=len({p['leaf'] for p in pp}),
                image_loci=counts([r for r in pp_rows if r['type'] in IMAGE and r['kind'][0]!='!']),
                paired_pages=len(paired),paired_leaves=len({p['leaf'] for p in paired}),
                paired_folios=[p['folio'] for p in paired],
                paired_body={k:sum(p['body'][k] for p in paired) for k in ['loci','slots','retained','missing']},
                paired_labels={k:sum(p['image_labels'][k] for p in paired) for k in ['loci','slots','retained','missing','complete_loci','multiword_loci','complete_singleword_loci']}))
        summary[source]=dict(pools=ss,locus_types=dict(Counter(r['kind'] for r in rows)))
    support_details=[]
    for source in all_rows:
        for pool in ['train_legacy','dev']:
            for mode in ['all_image_slots','single_complete','at_single_complete']:
                pop=[s for s in label_slots if s['source']==source and s['pool']==pool and (mode=='all_image_slots' or s[mode])]
                for representation in ['eva','merged']:
                    for conditioning in ['HI_length','HI_type_length','HIQ_length']:
                        details=[]
                        for s in pop:
                            fields=['H','I',representation]
                            if conditioning=='HI_type_length':fields+=['type']
                            if conditioning=='HIQ_length':fields+=['Q']
                            donors=[t for t in pop if s['H'] in {'1','2','3','4','5'} and t['leaf']!=s['leaf'] and all(t[k]==s[k] for k in fields)]
                            d=dict(source=source,pool=pool,mode=mode,representation=representation,conditioning=conditioning,
                                locator=s['locator'],slot=s['slot'],folio=s['folio'],leaf=s['leaf'],
                                donor_pages=sorted({t['folio'] for t in donors}),donor_leaves=sorted({t['leaf'] for t in donors}),
                                donor_slots=len(donors))
                            details.append(d)
                        support_details+=details
                        eligible=[d for d in details if d['donor_leaves']]
                        support.append(dict(source=source,pool=pool,mode=mode,representation=representation,conditioning=conditioning,
                            retained_slots=len(pop),eligible_slots=len(eligible),
                            all_pages=len({s['folio'] for s in pop}),all_leaves=len({s['leaf'] for s in pop}),
                            eligible_pages=len({s['folio'] for s in eligible}),eligible_leaves=len({s['leaf'] for s in eligible}),
                            eligible_min_donor_leaves=min((len(d['donor_leaves']) for d in eligible),default=0),
                            eligible_median_donor_leaves=statistics.median([len(d['donor_leaves']) for d in eligible]) if eligible else None))
    zl={r['locator']:r for r in all_rows['ZL3b-n.txt'] if r['type'] in IMAGE and r['kind'][0]!='!'}
    it={r['locator']:r for r in all_rows['IT2a-n.txt'] if r['type'] in IMAGE and r['kind'][0]!='!'}
    common=sorted(zl.keys()&it.keys())
    dual=dict(zl_image_loci=len(zl),it_image_loci=len(it),common_image_loci=len(common),
        zl_only=sorted(zl.keys()-it.keys()),it_only=sorted(it.keys()-zl.keys()),
        common_types_equal=all(zl[k]['type']==it[k]['type'] for k in common),
        common_slot_counts_equal=sum(len(zl[k]['slots'])==len(it[k]['slots']) for k in common),
        both_all_slots_retained=sum(bool(zl[k]['slots']) and bool(it[k]['slots']) and None not in zl[k]['slots'] and None not in it[k]['slots'] for k in common),
        both_single_complete=sum(len(zl[k]['slots'])==len(it[k]['slots'])==1 and zl[k]['slots'][0] is not None and it[k]['slots'][0] is not None for k in common),
        paired_page_intersection=sorted({p['folio'] for p in per_page if p['source']=='ZL3b-n.txt' and p['pairable']} & {p['folio'] for p in per_page if p['source']=='IT2a-n.txt' and p['pairable']}),
        caution='Presence/slot readability only; no label/body lexical hit or inter-version word identity compared.')
    save('inventory.json',dict(schema_version=1,scope='Design support only; no lexical outcome computed',
        sources={n:sha(BASE/'sources'/n) for n in all_rows},manifest_sha256=sha(HERE.parent/'split_manifest.json'),
        protocol_sha256=sha(HERE/'inventory_protocol.txt'),script_sha256=sha(Path(__file__)),
        allowed_pages=len(allowed),allowed_leaves=len({m['leaf'] for m in allowed.values()}),
        image_types=sorted(IMAGE),body_types=sorted(BODY),summaries=summary,dual_version=dual,
        confirm_or_reserve_payload_parsed=False,lexical_hits_computed=False,new_images_read=False,
        count_unit_caution='locus/word-slot counts are not independently identified drawing labels'))
    save('page_counts.json',per_page);save('locus_lengths.json',all_rows)
    save('control_support.json',support);save('control_support_details.json',support_details)
    with (HERE/'page_counts.csv').open('w') as stream:
        cols=['source','folio','leaf','split','H','I','Q','pairable','label_loci','label_slots','label_retained','label_missing','body_retained','body_missing']
        writer=csv.DictWriter(stream,fieldnames=cols);writer.writeheader()
        for p in per_page:
            writer.writerow({**{k:p[k] for k in ['source','folio','leaf','split','pairable']},
                **{k:p['metadata'].get(k,'?') for k in ['H','I','Q']},
                **{'label_'+k:p['image_labels'][k] for k in ['loci','slots','retained','missing']},
                **{'body_'+k:p['body'][k] for k in ['retained','missing']}})
    print(json.dumps(dict(summary={n:v['pools'] for n,v in summary.items()},dual=dual),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
