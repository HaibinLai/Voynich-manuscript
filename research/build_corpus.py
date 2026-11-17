"""Preserve published transliterations and associate them with PDF labels."""
from pathlib import Path
from collections import defaultdict
import json
import re

ROOT = Path(__file__).resolve().parent

def parse(name):
    records, pages = [], {}
    current = None
    for source_line, line in enumerate((ROOT / 'sources' / name).read_text().splitlines(), 1):
        if not line.startswith('<'):
            continue
        match = re.fullmatch(r'<([^>]+)>\s*(.*)', line)
        if not match:
            raise ValueError((name, source_line, line))
        tag, content = match.groups()
        if '.' not in tag:
            current = tag
            pages[current] = dict(re.findall(r'\$(\w)=([A-Za-z0-9@])', content))
            continue
        locator, kind = tag.split(',', 1)
        folio = locator.split('.')[0]
        assert folio == current
        # Remove only IVTFF angle-bracket markup. Never resolve alternatives,
        # remove uncertain glyphs, join uncertain spaces, or expand ligatures.
        display = re.sub(r'<[^>]*>', '', re.sub(r'<[-~]>', '.', content)).strip()
        records.append(dict(folio=folio, locator=locator, locus_type=kind,
                            text_ivtff=content, text_display=display,
                            source_file=name, source_line=source_line,
                            page_attributes=pages[folio]))
    return records, pages

def main():
    import fitz
    inventory = json.loads((ROOT / 'pdf_inventory.json').read_text())
    corpora = {name: parse(name) for name in ['ZL3b-n.txt', 'IT2a-n.txt', 'RF1b-e.txt']}
    zl, folios = corpora['ZL3b-n.txt']
    mapping = []
    by_folio = defaultdict(list)
    with fitz.open(inventory['source_path']) as doc:
        for number, page in enumerate(doc, 1):
            lines = page.get_text().splitlines()
            label = lines[0] if lines else None
            image_id = next((x.strip() for x in lines if x.strip().isdigit()), None)
            identifiers = []
            if label and not label.startswith('['):
                cleaned = re.sub(r'\(part of.*?\)', '', label)
                identifiers = re.findall(r'\b(\d+[rv])\b', cleaned)
            candidates = []
            if number == 239:
                candidates = ['fRos']
            else:
                for folio in folios:
                    base = re.sub(r'\d+$', '', folio[1:])
                    if base in identifiers:
                        candidates.append(folio)
            status = 'no_manuscript_transliteration_match'
            if candidates:
                status = ('label_match_not_glyph_verified' if len(candidates) == 1
                          and len(identifiers) == 1 and '(part)' not in label
                          else 'foldout_candidates_need_region_alignment')
            item = dict(pdf_page=number, printed_label=label, image_id=image_id,
                        candidate_folios=candidates, mapping_status=status)
            mapping.append(item)
            for folio in candidates:
                by_folio[folio].append(number)
    (ROOT / 'pdf_folio_mapping.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2))
    for name, (records, pages) in corpora.items():
        destination = ROOT / (name.replace('.txt', '') + '.jsonl')
        for record in records:
            record['pdf_candidate_pages'] = by_folio.get(record['folio'], [])
            record['alignment_note'] = 'PDF label association only; not line or glyph verification'
        destination.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))
    text = ['伏尼契手稿：已发表 EVA 字形转写（Zandbergen–Landini 3b）\n',
            '此文件由公开转写整理；不是本次从 PDF 独立 OCR 的结果，也不是翻译。\n',
            '共 227 个转写分区、5385 个文本位置。一个位置可能是正文行、标签或环形文字。\n',
            'PDF 页码来自页面标签；折页/多图页列出候选页，尚未逐区域校准。\n',
            '文本将插图中断标记 <-> / <~> 转为词间分隔点，移除其他尖括号标记；原文见 sources。\n',
            '点号 . 表示转写中的明确空格；逗号 , 是不确定空格；? 为不可辨字形。\n',
            '[a:b] 保留备选读法，花括号保留连写信息，@数字; 保留扩展字形编码。\n',
            'EVA 拉丁字母只是字形编码，不代表原语言的拼写或发音。\n\n']
    previous = None
    for record in zl:
        if record['folio'] != previous:
            text.append(f"\n===== {record['folio']} | PDF 候选页：{by_folio.get(record['folio'], [])} =====\n")
            previous = record['folio']
        text.append(f"{record['locator']} [{record['locus_type']}]  {record['text_display']}\n")
    (ROOT / '手稿正文_EVA逐行转写.txt').write_text(''.join(text))
    it = {r['locator']: r for r in corpora['IT2a-n.txt'][0]}
    differences = ['ZL 与 IT 同位置转写差异待核对清单\n',
                   '比较的是去除尖括号标记后的编码；编码惯例差异也会触发，不等于识别错误。\n',
                   'RF 来源包含 ZL，不能将其视作第三份独立证据。\n\n']
    count = common = 0
    for record in zl:
        other = it.get(record['locator'])
        if not other:
            continue
        common += 1
        if record['text_display'] != other['text_display']:
            count += 1
            differences.append(f"{record['locator']} | PDF 候选页 {record['pdf_candidate_pages']}\nZL: {record['text_display']}\nIT: {other['text_display']}\n\n")
    (ROOT / '版本差异_待核对.txt').write_text(''.join(differences))
    summary = dict(pdf_pages=inventory['page_count'],
                   corpora={name:dict(folio_sections=len(pages), loci=len(records)) for name,(records,pages) in corpora.items()},
                   pdf_pages_with_candidate_folios=sum(bool(r['candidate_folios']) for r in mapping),
                   foldout_pdf_pages_needing_region_alignment=[r['pdf_page'] for r in mapping if r['mapping_status'].startswith('foldout')],
                   unmapped_zl_sections=[f for f in folios if not by_folio.get(f)],
                   compared_locators=common, unequal_display_strings=count,
                   caution='Published corpus reuse, not independent PDF OCR or decipherment. Differences include notation conventions.')
    (ROOT / 'corpus_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert len(zl) == 5385 and len(folios) == 227
    assert len({r['locator'] for r in zl}) == len(zl)
    assert len(mapping) == 294

if __name__ == '__main__':
    main()
