"""Explicit IVTFF H overrides, without changing the frozen corpus parser."""
from pathlib import Path
from collections import Counter
import copy
import gzip
import hashlib
import importlib.util
import json
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('metadata_private_corpus', ROOT/'corpus.py')
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)


def write(path, obj):
    path = Path(path)
    assert not path.exists(), ('No overwrite', path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False)+'\n').encode()
    path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == '.gz' else raw)


def parse_selected(source, allowed):
    """Discard disallowed page bodies before tag, token or metadata parsing."""
    records, pages, tags = [], {}, []
    active = None
    hand = None
    with (ROOT.parent/'sources'/source).open() as stream:
        for source_line, line in enumerate(stream, 1):
            if not line.startswith('<'):
                continue
            header = re.match(r'^<([^>.]+)>\s*(.*)', line)
            if header:
                folio, content = header.groups()
                active = folio if folio in allowed else None
                if active:
                    pages[folio] = dict(re.findall(r'\$(\w)=([A-Za-z0-9@])', content))
                    hand = pages[folio].get('H', '?')
                continue
            if active is None:
                continue
            match = re.fullmatch(r'<([^>]+)>\s*(.*)', line.rstrip('\n'))
            assert match, (source, source_line)
            tag, content = match.groups()
            locator, kind = tag.split(',', 1)
            assert locator.split('.')[0] == active
            values = re.findall(r'<@H=([^>]+)>', content)
            assert len(set(values)) <= 1, ('Conflicting same-locus H', locator)
            if values:
                assert re.fullmatch(r'[A-Za-z0-9@?]', values[0]), values
                hand = values[0]
                tags.append(dict(folio=active, locator=locator, source_line=source_line, value=hand))
            display = re.sub(r'<[^>]*>', '', re.sub(r'<[-~]>', '.', content)).strip()
            records.append(dict(folio=active, locator=locator, locus_type=kind,
                text_ivtff=content, text_display=display, source_file=source,
                source_line=source_line, page_attributes=pages[active], effective_hand=hand))
    assert set(pages) == set(allowed), set(allowed)-set(pages)
    return records, pages, tags


def prepared_pages(source, manifest):
    allowed = {r['folio']:r for r in manifest if r['split'] in ('train', 'legacy', 'dev')}
    records, headers, tags = parse_selected(source, allowed)
    # The private module instance confines this injected input supplier to this
    # preparation process; no frozen file or shared parser object is edited.
    corpus.parse = lambda requested: (records, headers)
    pages, skipped = corpus.all_pages(source)
    loci = {r['locator']:r for r in records}
    changes = []
    for page in pages:
        page['split'] = allowed[page['folio']]['split']
        for li, line in enumerate(page['lines']):
            hands, words = [], []
            for locus in line['loci']:
                rec = loci[locus]
                tokens = corpus.tokenize(rec['text_ivtff'])
                words.extend(tokens)
                hands.extend([rec['effective_hand']]*len(tokens))
            assert words == line['tokens'] and len(hands) == len(words)
            line['effective_hands'] = hands
            for j,(word,h) in enumerate(zip(words,hands)):
                if h != page['metadata'].get('H','?'):
                    changes.append(dict(folio=page['folio'], split=page['split'], line=li,
                        slot=j, old=page['metadata'].get('H','?'), new=h,
                        retained=word is not None))
    return pages, dict(source=source, inline_tags=tags, changes=changes,
        changed_folios=sorted({r['folio'] for r in changes}),
        changed_retained_counts=dict(Counter(r['new'] for r in changes if r['retained'])),
        changed_retained_by_split=dict(Counter(r['split'] for r in changes if r['retained'])),
        joined_lines_with_multiple_hands=[dict(folio=p['folio'],line=i,loci=l['loci'])
            for p in pages for i,l in enumerate(p['lines']) if len(set(l['effective_hands']))>1],
        skipped_loci_by_type=skipped)


def effective_lookup(pages):
    out = {}
    for page in pages:
        for li,line in enumerate(page['lines']):
            hands = line.get('effective_hands')
            assert hands is not None and len(hands) == len(line['tokens']), ('Missing explicit sidecar', page['folio'],li)
            for slot,(word,hand) in enumerate(zip(line['tokens'],hands)):
                out[page['folio'],li,slot] = (hand,word)
    return out


def relabel(rows, pages):
    lookup = effective_lookup(pages)
    out = []
    for row in rows:
        hand, word = lookup[row['folio'],row['line'],row['slot']]
        assert word is not None
        # Boundary records can have UNK-mapped words; equality is checked by
        # each caller against the corresponding complete original row.
        out.append(dict(row,hand=hand))
    return out


def basic_records(pages, rep):
    rows=[]
    for page in pages:
        for li,line in enumerate(page['lines']):
            for slot,word in enumerate(line['tokens']):
                if word is None:
                    continue
                rows.append(dict(folio=page['folio'],leaf=page['leaf'],line=li,slot=slot,
                    word=tuple(corpus.units(word,rep)),hand=page['metadata'].get('H','?'),
                    position='paragraph_first' if slot==0 and line['paragraph_start'] else
                    'line_first' if slot==0 else 'other'))
    return rows


def validate_sidecar(original_pages, supplied):
    """Attach an explicit root-provided locus/slot sidecar; never infer a label."""
    pages=copy.deepcopy(original_pages)
    assert len(pages)==len(supplied)
    for page,side in zip(pages,supplied):
        assert side['page_sha256']==hashlib.sha256(json.dumps(page,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        assert page['folio']==side['folio'] and len(page['lines'])==len(side['lines'])
        for line,sline in zip(page['lines'],side['lines']):
            assert line['loci']==sline['loci']
            hands=sline['effective_hands']
            assert len(hands)==len(line['tokens']) and all(isinstance(h,str) and len(h)==1 for h in hands)
            line['effective_hands']=hands
    return pages


def source_sidecar(source, pages, expected_source_sha256):
    """Only process caller-supplied folios; caller owns permission to expose them."""
    assert pages and len({p['folio'] for p in pages})==len(pages)
    path=ROOT.parent/'sources'/source
    assert sha(path)==expected_source_sha256
    records,headers,tags=parse_selected(source,{p['folio'] for p in pages})
    corpus.parse=lambda requested:(records,headers)
    normalized,_=corpus.all_pages(source)
    normalized={p['folio']:p for p in normalized}
    loci={r['locator']:r for r in records}
    side=[]
    for page in pages:
        old=normalized[page['folio']]
        old['split']=page['split']
        assert old==page,('Source/page normalization mismatch',page['folio'])
        lines=[]
        for line in page['lines']:
            hands=[]
            for loc in line['loci']:
                rec=loci[loc]
                hands.extend([rec['effective_hand']]*len(corpus.tokenize(rec['text_ivtff'])))
            assert len(hands)==len(line['tokens'])
            lines.append(dict(loci=line['loci'],effective_hands=hands))
        side.append(dict(folio=page['folio'],
            page_sha256=hashlib.sha256(json.dumps(page,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),lines=lines))
    assert sha(path)==expected_source_sha256
    return dict(source=source,source_sha256=expected_source_sha256,
        input_folios=[p['folio'] for p in pages],pages=side,inline_tags=tags,
        selected_from_split=False,caller_supplied_pages_only=True)


def main():
    manifest=read(ROOT/'split_manifest.json')
    reports=[]
    for source in ('ZL3b-n.txt','IT2a-n.txt'):
        pages,report=prepared_pages(source,manifest)
        assert report['changed_folios']==['f115r']
        expected={'2':128,'3':328} if source.startswith('ZL') else {'2':120,'3':324}
        assert report['changed_retained_counts']==expected
        assert report['changed_retained_by_split']=={'train':sum(expected.values())}
        assert not report['joined_lines_with_multiple_hands']
        for split in ('train_legacy','dev'):
            selected=[p for p in pages if p['split'] in (('train','legacy') if split=='train_legacy' else ('dev',))]
            path=HERE/'inputs'/f'{source[:-4]}_{split}.json.gz'
            write(path,selected)
        report['train_pages']=sum(p['split'] in ('train','legacy') for p in pages)
        report['dev_pages']=sum(p['split']=='dev' for p in pages)
        reports.append(report)
        for rep,name in [('eva','IT_EVA' if source.startswith('IT') else 'ZL_EVA')]+([] if source.startswith('IT') else [('merged','ZL_merged')]):
            saved=read(ROOT/'allograph_factor/inputs'/f'{name}_train_dev.json.gz')
            for label,old in [('train',saved['train']),('dev',saved['dev'])]:
                pp=[p for p in pages if p['split'] in (('train','legacy') if label=='train' else ('dev',))]
                new=basic_records(pp,rep)
                assert len(new)==len(old)
                for a,b in zip(new,old):
                    assert json.loads(json.dumps(a))==b,(name,label,a['folio'],a['line'],a['slot'])
    write(HERE/'mapping_verification.json',dict(passed=True,confirm_processed=False,reserve_processed=False,
        old_record_fields_match_allograph_saved_train_and_dev=True,sources=reports))
    print('Verified train/dev source alignment; only f115r changes; no confirm/reserve processed.')


if __name__=='__main__':main()
