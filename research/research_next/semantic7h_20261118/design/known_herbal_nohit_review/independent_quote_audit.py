"""Independent source/quote checks, not independent semantic labeling."""
from pathlib import Path
from xml.dom import minidom, Node
from collections import Counter
import datetime
import gzip
import hashlib
import json
import re

D = Path(__file__).resolve().parent
OLD = D.parent/'known_herbal'

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if path.suffix == '.gz' else path.read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def collapse(text):
    return ' '.join(text.split())

def text(node, mode):
    if node.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
        return node.data
    if node.nodeType != Node.ELEMENT_NODE:
        return ''
    tag = node.localName
    if mode == 'scoring' and tag in {'note', 'head', 'gap', 'abbr'}:
        return ' '
    if tag == 'g':
        ref = node.getAttribute('ref')
        if mode == 'sentinel':
            return '[g:ref='+ref+']'
        return '' if ref in {'char:EOLhyphen', 'char:EOLunhyphen'} else ' '
    return ''.join(text(child, mode) for child in node.childNodes)

def main():
    output = D/'independent_quote_audit_v1.json'
    if output.exists():
        raise FileExistsError(output)
    source = gzip.decompress((OLD/'A35365.xml.gz').read_bytes())
    dom = minidom.parseString(source)
    index = {}
    def walk(node, path):
        index[path] = node
        seen = Counter()
        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE:
                seen[child.localName] += 1
                walk(child, path+'/'+child.localName+'['+str(seen[child.localName])+']')
    walk(dom.documentElement, '/TEI[1]')
    review = read(D/'review_v1.json')
    packet = read(D/'source_packet_v1.json.gz')
    queue = read(D/'queue_v1.json')['selected']
    old = {row['id']:row for row in read(OLD/'run_v1/rows.json.gz')}
    expected_ids = {key for key,row in old.items() if not row['own']['binary']}
    assert expected_ids == {r['id'] for r in queue} == {r['id'] for r in review['rows']} == {r['id'] for r in packet['sections']}
    assert len(review['rows']) == len(expected_ids) == 17
    checks = 2
    paragraphs = 0
    quotes = []
    for section in packet['sections']:
        start, end = section['original_xml_byte_range']
        sliced = source[start:end]
        assert sliced == section['original_xml_utf8'].encode('utf-8')
        assert hashlib.sha256(sliced).hexdigest() == section['original_xml_sha256']
        assert index[section['section_path']].getAttribute('type') == 'herb'
        checks += 3
    for row in review['rows']:
        assert row['original_own'] == old[row['id']]['own']
        assert row['label'] == old[row['id']]['label']
        pnodes = index[row['section_xml_path']].getElementsByTagNameNS('*', 'p')
        assert len(pnodes) == row['p_count']
        paragraphs += len(pnodes)
        checks += 3
        for evidence in row['evidence']:
            node = index[evidence['xml_path']]
            assert node.localName == evidence['source_node_tag'] == 'p'
            visible = collapse(text(node, 'sentinel' if evidence['quote_uses_explicit_g_sentinel'] else 'plain'))
            quote = evidence['quote_whitespace_collapsed']
            assert quote in visible, (row['id'], quote)
            scoring_quote = re.sub(r'\[g:ref=char:EOL(?:un)?hyphen\]', '', quote)
            eligible = scoring_quote in collapse(text(node, 'scoring'))
            assert eligible == evidence['quote_present_after_original_exclusions']
            checks += 3
            quotes.append(dict(id=row['id'], path=evidence['xml_path'], literal_quote_verified=True,
                               original_scoring_inclusion_verified=eligible))
    assert paragraphs == 82 and len(quotes) == 29
    checks += 1
    files = [D/'review_v1.json', D/'source_packet_v1.json.gz', D/'queue_v1.json',
             OLD/'A35365.xml.gz', OLD/'run_v1/rows.json.gz', Path(__file__)]
    receipt = dict(passed=True, utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   checks=checks, sections=17, paragraphs=paragraphs, quotes_verified=quotes,
                   inputs={str(p.relative_to(D.parents[1])):sha(p) for p in files},
                   method='Independent minidom path indexing and raw-byte checks; no import or reading of the packet producer or original scorer implementation.',
                   scope='All selected IDs, old own scores, 17 original XML byte slices, 82 paragraph counts, and all 29 quoted passages with inclusion in the old scoring region.',
                   limitations=['Does not verify the observer read every word, independently classify aliases/pronouns, or establish absence of alternate names.',
                                'No facsimile spelling check, new scores, accuracy estimate, or Voynich semantic evidence.'])
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({key:receipt[key] for key in ['passed','checks','sections','paragraphs']}))

if __name__ == '__main__':
    main()
