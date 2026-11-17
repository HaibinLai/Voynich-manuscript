"""Create review inventory without changing either published transliteration."""
from pathlib import Path
from collections import Counter
import difflib,hashlib,json,re,sys
ROOT=Path(__file__).resolve().parent
BASE=ROOT.parent.parent
sys.path.insert(0,str(BASE))
from build_corpus import parse

def normalized(text):
    text=re.sub(r'<[-~]>','.',text)
    text=re.sub(r'<[^>]*>','',text)
    return re.sub(r'\s','',text.replace('{','').replace('}','')).lower()

def main():
    selection=json.loads((BASE/'study20/selection.json').read_text());chosen={s['folio'] for s in selection}
    a,_=parse('ZL3b-n.txt');b,_=parse('IT2a-n.txt');other={r['locator']:r for r in b}
    rows=[]
    for r in a:
        if r['folio'] not in chosen:continue
        t=other.get(r['locator']);z=normalized(r['text_ivtff']);i=normalized(t['text_ivtff']) if t else None
        category='missing_correspondence' if i is None else ('normalized_agreement' if z==i else ('spacing_only' if z.replace('.','').replace(',','')==i.replace('.','').replace(',','') else 'glyph_or_annotation_difference'))
        differences=[]
        if i is not None:
            for op,a0,a1,b0,b1 in difflib.SequenceMatcher(None,z,i,autojunk=False).get_opcodes():
                if op!='equal':differences.append(dict(operation=op,zl_span=[a0,a1],it_span=[b0,b1],zl=z[a0:a1],it=i[b0:b1]))
        rows.append(dict(folio=r['folio'],locator=r['locator'],locus_type=r['locus_type'],zl=r['text_ivtff'],it=t['text_ivtff'] if t else None,
                         normalized_zl=z,normalized_it=i,category=category,differences=differences,
                         source_lines=dict(zl=r['source_line'],it=t['source_line'] if t else None),
                         visual_status='not_reviewed_at_high_resolution'))
    (ROOT/'locus_inventory.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
    summary=dict(loci=len(rows),categories=dict(Counter(r['category'] for r in rows)),
                 source_hashes={s:hashlib.sha256((BASE/'sources'/s).read_bytes()).hexdigest() for s in ['ZL3b-n.txt','IT2a-n.txt']},
                 scope='Mechanical disagreement inventory only; not evidence either version is wrong.')
    (ROOT/'inventory_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    for f in chosen:
        text=f+' — 高分辨率逐位置复核工作单\n原版不改写，图像有歧义时保留两版。\n\n'
        for r in rows:
            if r['folio']==f:
                text+=f'{r["locator"]} [{r["locus_type"]}] {r["category"]}\nZL: {r["zl"]}\nIT: {r["it"]}\n\n'
        (ROOT/'worksheets').mkdir(exist_ok=True);(ROOT/'worksheets'/f'{f}.txt').write_text(text)
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
