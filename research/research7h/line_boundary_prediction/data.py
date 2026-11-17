"""Only four allowlisted saved train/dev inputs; no raw/confirm/reserve loader."""
from collections import Counter
from pathlib import Path
import gzip,hashlib,json,re

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
SOURCES={
 ('ZL3b-n','train_legacy'):'139f2ce735689086e4a64f1786271f5f18b3ab288cf7ef84d6abcd994d06cc8c',
 ('ZL3b-n','dev'):'0f95c04fae55357398983aca0f0b89e3f3b9a3f8a034f73b13716f1053cd5e73',
 ('IT2a-n','train_legacy'):'d8001be26b06c64063e640f3ed7c1241c6f52cf75bd4c6b8cd6bfe6b0d5e211b',
 ('IT2a-n','dev'):'5dc88bb9adac08184aaacae7b24e814ff8ffff3564846ca9495328f8b9f4ac82',
}
REPRESENTATIONS={'ZL_EVA':('ZL3b-n','eva'),'ZL_merged':('ZL3b-n','merged'),'IT_EVA':('IT2a-n','eva')}


def load(source,split):
    expected=SOURCES[source,split]
    path=ROOT/'metadata_sensitivity/inputs'/f'{source}_{split}.json.gz'
    payload=path.read_bytes();assert hashlib.sha256(payload).hexdigest()==expected
    pages=json.loads(gzip.decompress(payload));allowed={'train','legacy'} if split=='train_legacy' else {'dev'}
    assert pages and {p['split'] for p in pages}<=allowed
    for p in pages:
        for line in p['lines']:assert len(line['tokens'])==len(line['effective_hands'])
    return pages


def units(token,representation):
    pattern=r"cth|ckh|cph|cfh|ch|sh|@\d{3};|[a-z']" if representation=='merged' else r"@\d{3};|[a-z']"
    values=tuple(re.findall(pattern,token));assert values and ''.join(values)==token
    return values


def universe(representation):
    values=set("abcdefghijklmnopqrstuvwxyz'")|{'@%03d;'%i for i in range(1000)}
    if representation=='merged':values|={'ch','sh','cth','ckh','cph','cfh'}
    return frozenset(values)


def all_words(pages,representation):
    return [units(t,representation) for p in pages for line in p['lines'] for t in line['tokens'] if t is not None]


def pairs(pages,representation):
    rows=[];counts=Counter()
    for p in pages:
        for li,(a,b) in enumerate(zip(p['lines'],p['lines'][1:]),1):
            counts['candidate_adjacent_parsed_rows']+=1
            if not a['paragraph_known'] or not b['paragraph_known']:
                counts['unknown_paragraph']+=1;continue
            if a['paragraph_end'] or b['paragraph_start'] or a['block']!=b['block'] or a['paragraph']!=b['paragraph']:
                counts['paragraph_or_block_boundary']+=1;continue
            if a['aligned_to_excluded_locus'] or b['aligned_to_excluded_locus']:
                counts['aligned_to_excluded_locus']+=1;continue
            if not a['tokens'] or not b['tokens'] or a['tokens'][-1] is None or b['tokens'][0] is None:
                counts['missing_endpoint']+=1;continue
            previous=units(a['tokens'][-1],representation);word=units(b['tokens'][0],representation)
            row=dict(folio=p['folio'],leaf=p['leaf'],line=li,slot=0,previous_line=li-1,previous_slot=len(a['tokens'])-1,
                word=word,previous_word=previous,previous_length=len(previous),length=0,
                hand=b['effective_hands'][0],previous_hand=a['effective_hands'][-1],section=p['metadata'].get('I','?'),
                position_bin=0,paragraph_line=0,source_file_adjacent=max(a['source_lines'])+1==min(b['source_lines']))
            rows.append(row);counts['eligible_same_paragraph_cross_row']+=1
    counts['cross_hand_pairs']=sum(r['hand']!=r['previous_hand'] for r in rows)
    counts['unresolved_target_H_at']=sum(r['hand']=='@' for r in rows)
    counts['source_file_adjacent_only']=sum(r['source_file_adjacent'] for r in rows)
    return rows,dict(counts)


def mapped(rows,alphabet):
    result=[]
    for row in rows:
        r=dict(row);r['original_word']=tuple(row['word'])
        r['word']=tuple(c if c in alphabet else '<UNK>' for c in row['word'])
        r['last']=row['previous_word'][-1] if row['previous_word'][-1] in alphabet else '<UNK>'
        r['target']=r['word'][0]
        r['target_unknown_units']=sum(c not in alphabet for c in row['word'])
        r['source_unknown_units']=sum(c not in alphabet for c in row['previous_word'])
        result.append(r)
    return result
