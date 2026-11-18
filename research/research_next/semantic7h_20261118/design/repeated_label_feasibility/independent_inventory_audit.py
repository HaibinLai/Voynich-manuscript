"""Independently rebuild label support from raw IVTFF, then compare the inventory.

No import of inventory.py, no manuscript images, no body-match scores.
Does not independently certify object boxes, canvas assignment, or semantics.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json, re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def word(raw):
    # Strip comments only at the two outer boundaries. An internal comment is
    # not used to merge fragments; the complete certain word must remain intact.
    x=raw.strip()
    while re.match(r'^<![^>]*>',x): x=re.sub(r'^<![^>]*>','',x,count=1).strip()
    while re.search(r'<![^>]*>$',x): x=re.sub(r'<![^>]*>$','',x,count=1).strip()
    return x if re.fullmatch(r'(?:[a-z]|@[0-9]{3};)+',x) else None

def parse(p):
    records={}
    for i,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
        m=re.match(r'^<([^,>]+),([^>]+)>\s*(.*)$',line)
        if not m:continue
        loc,layout,raw=m.groups()
        if len(layout)<3 or layout[1]!='L':continue
        assert loc not in records,loc
        records[loc]={'layout':layout,'subtype':layout[1:3],
          'raw':raw.strip(),'line_number':i,'word':word(raw),
          'physical_leaf':re.match(r'^f\d+',loc).group() if re.match(r'^f\d+',loc) else None}
    return records

def main():
    out=HERE/'independent_audit_v1.json'
    assert not out.exists(), 'Never overwrite a completed audit'
    toys={'<!95b>otoldy':'otoldy','otoldy<!note>':'otoldy',
          'ot<!internal>oldy':None,'o.toldy':None,'o,toldy':None,
          'ot[al:ol]dy':None,'otoldy<$>':None,'@123;ol':'@123;ol',
          'o{ta}l':None,"o'tal":None,'o*tal':None,'':None}
    for raw,expected in toys.items():assert word(raw)==expected,(raw,word(raw),expected)
    paths={'ZL':ROOT/'research/sources/ZL3b-n.txt','IT':ROOT/'research/sources/IT2a-n.txt'}
    versions={v:parse(p) for v,p in paths.items()}
    common={};clusters=defaultdict(list)
    for loc in sorted(set(versions['ZL'])|set(versions['IT'])):
        z=versions['ZL'].get(loc);i=versions['IT'].get(loc)
        valid=bool(z and i and z['subtype']==i['subtype'] and z['word'] is not None and z['word']==i['word'])
        common[loc]={'valid':valid,'agreed_word':z['word'] if valid else None,
                     'subtype':z['subtype'] if z else i['subtype']}
        if valid and z['subtype'] in ['Lp','Lf']:clusters[(z['subtype'],z['word'])].append(loc)
    selected={k:locs for k,locs in clusters.items() if len({re.match(r'^f\d+',loc).group() for loc in locs if re.match(r'^f\d+',loc)})>=2}
    # Freeze the rebuilt support before reading the primary inventory records.
    rebuilt={'utc':datetime.now(timezone.utc).isoformat(),'implementation_sha256':digest(Path(__file__)),
      'inputs':{str(p.relative_to(ROOT)):digest(p) for p in paths.values()},
      'source_counts':{v:dict(Counter(r['subtype'] for r in rows.values())) for v,rows in versions.items()},
      'union_count':len(common),'agreed_by_subtype':dict(Counter(r['subtype'] for r in common.values() if r['valid'])),
      'selected_clusters':{k[0]+':'+k[1]:v for k,v in selected.items()}}
    rebuilt_path=HERE/'independent_rebuilt_support_v1.json'
    assert not rebuilt_path.exists()
    rebuilt_path.write_text(json.dumps(rebuilt,indent=2)+'\n')
    primary=json.loads((HERE/'inventory_v1.json').read_text())
    diffs=[];checks=0
    def check(label,a,b):
        nonlocal checks
        checks+=1
        if a!=b:diffs.append({'check':label,'independent':a,'primary':b})
    check('source_counts',rebuilt['source_counts'],primary['source_label_counts'])
    check('all_loci',sorted(common),sorted(r['locator'] for r in primary['records']))
    for row in primary['records']:
        loc=row['locator'];r=common[loc]
        check(loc+'/eligibility',r['valid'],row['strict_reading_eligible'])
        check(loc+'/agreed_word',r['agreed_word'],row['agreed_word'])
        for version in ['ZL','IT']:
            original=versions[version].get(loc);saved=row['versions'].get(version)
            check(loc+'/'+version+'/exists',original is not None,saved is not None)
            if original and saved:
                for key in ['raw','layout','subtype','line_number','word']:
                    check(loc+'/'+version+'/'+key,original[key],saved[key])
    declared=json.loads((HERE/'clusters_v1.json').read_text())
    check('all_plant_cross_leaf_clusters',rebuilt['selected_clusters'],
          {r['subtype']+':'+r['agreed_word']:r['locators'] for r in declared})
    for typ,s in primary['summary_by_subtype'].items():
        check('eligible/'+typ,rebuilt['agreed_by_subtype'].get(typ,0),s['strict_agreed_single_word_loci'])
    audit={'utc':datetime.now(timezone.utc).isoformat(),'status':'PASS' if not diffs else 'FAIL',
      'scope':'Raw IVTFF label extraction, complete certain word eligibility, per-version source fields, cross-leaf clusters and all agreed counts. Not an independent box or image review.',
      'checks':checks,'toy_cases':len(toys),'differences':diffs,
      'implementation_sha256':digest(Path(__file__)),'rebuilt_support_sha256':digest(rebuilt_path),
      'primary_files':{n:digest(HERE/n) for n in ['inventory_v1.json','clusters_v1.json','protocol_v1.txt']},
      'known_exposure':'Published support counts, roster and sample schema were known before implementation; primary inventory.py was not read or imported.'}
    out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':audit['status'],'checks':checks,'diff_count':len(diffs),'first_differences':diffs[:12]},ensure_ascii=False))
    if diffs:raise SystemExit(1)

if __name__=='__main__':main()
