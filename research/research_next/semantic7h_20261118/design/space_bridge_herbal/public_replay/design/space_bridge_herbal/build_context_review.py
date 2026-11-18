"""Read all five fixed join hits in the public-domain source's XML context.

Post-result interpretive annotation, not an independent semantic benchmark.
Does not alter frozen scoring, numerators, denominators, or eligibility.
"""
from pathlib import Path
from datetime import datetime, timezone
import gzip, hashlib, json, re
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
SOURCE=HERE.parent/'known_herbal/A35365.xml.gz'
NS={'t':'http://www.tei-c.org/ns/1.0'}
CASES={
 12:('A Sarabacca hath many Heads','name_reference',
     '正文开头把名称分成 A 与 Sarabacca；拼接恢复与本节标题一致的字串。这是实验前已知的例子，不是新发现。'),
 135:('each part resembling a Hors Tail (from whence it was so called)', 'naming_metaphor',
      '这里说各部分像马尾，并解释名称由来。它与名称有语义联系，但这一处直接指的是比喻中的马尾，不能仅凭拼接称为植物名称的再次出现。'),
 147:('in some convenient Liquor is', 'incidental_word_boundary_collision',
      'Liquor 是液体一词，is 是后面的系动词。合并成 liquoris 与查询字串相等，并不表示此处提到了该植物。'),
 180:('somwhat like Night shade but larger', 'cross_entry_name_reference',
      '另一植物条目以 Night shade 作叶片形态比较。此处可以在语境中理解为名称指称；出现在别的条目并不自动是假阳性。'),
 185:('or Pine Kernels', 'incidental_word_boundary_collision',
      'or 是连接词，Pine 修饰 Kernels。拼成 orpine 只产生字面相等，并非此处在说查询植物。'),
}

def sha(raw): return hashlib.sha256(raw).hexdigest()
def main():
    assert not (HERE/'context_review_v1.json').exists(), 'Do not overwrite frozen annotations'
    source=SOURCE.read_bytes();xml=gzip.decompress(source)
    herbs=ET.fromstring(xml).findall('.//t:div[@type="herb"]',NS)
    assert len(herbs)==282
    hits=json.loads((HERE/'all_adjacent_matches.json').read_text())
    assert {x['title_id'] for x in hits}==set(CASES) and len(hits)==5
    rows=[]
    for hit in hits:
        snippet,category,reason=CASES[hit['title_id']]
        node=herbs[hit['body_section']-1]
        # Independent raw XML flattening only verifies these short literal passages.
        # It is deliberately not reused as the experiment's boundary parser.
        text=re.sub(r'\s+',' ',''.join(node.itertext()))
        assert snippet in text,(hit['title_id'],snippet)
        head=node.find('t:head',NS)
        rows.append({'title_id':hit['title_id'],'query':hit['label'],
          'body_section':hit['body_section'],'body_heading':''.join(head.itertext()).strip(),
          'parts':hit['parts'],'literal_passage':snippet,'category':category,'explanation_zh':reason,
          'interpretation_scope':'Single observer reading a known English text after results; not a certified historical-botanical label or an estimate of error rate.'})
    payload={'utc':datetime.now(timezone.utc).isoformat(),
      'scope':'All five forward-join hits interpreted after numerical results; no cases selected or removed. Illustrative context review only.',
      'source_url':'https://github.com/textcreationpartnership/A35365/blob/2b09f3e54d85c5faf0738f823648edf6f070cef8/A35365.xml',
      'source_rights':'1652 public-domain text; TCP XML released CC0.',
      'source_xml_sha256':sha(xml),'source_gzip_sha256':sha(source),
      'matches_sha256':sha((HERE/'all_adjacent_matches.json').read_bytes()),
      'original_scores_modified':False,'rows':rows,
      'implication_zh':'字面命中、自身条目命中和语境中的名称指称是三个不同问题。相邻拼接既能恢复名称，也能合并无关词边界；他节出现也可能是真正的名称引用。伏尼契仍缺可检验这种差别的独立读法，不能拿字串命中直接当破译。'}
    (HERE/'context_review_v1.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    lines=['五个英文拼接命中的上下文：命中不等于词义','',payload['implication_zh'],'',
      '这是全部五个既有命中的结果后说明，不改原统计，不构造新的准确率或独立语义金标。','']
    for row in rows: lines += [row['query']+' | '+row['body_heading'],row['literal_passage'],row['explanation_zh'],'']
    (HERE/'context_review_v1.txt').write_text('\n'.join(lines)+'\n')
    (HERE/'context_review_receipt_v1.json').write_text(json.dumps({'files':{n:sha((HERE/n).read_bytes()) for n in ['build_context_review.py','context_review_v1.json','context_review_v1.txt']},'all_five_literal_passages_found_in_pinned_xml':True,'scores_modified':False},indent=2)+'\n')
    print('All five source passages verified; annotations saved.')

if __name__=='__main__':main()
