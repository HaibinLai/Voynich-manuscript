"""Enumerate design support only; no image reading or similarity scoring."""
from pathlib import Path
from collections import Counter, defaultdict
from itertools import combinations, permutations, product
import hashlib
import json
import math
import datetime

D = Path(__file__).resolve().parent
BASE = D.parents[1]
ROSTER = BASE / 'design/repeated_label_feasibility/fixed_nine_roster_v1.json'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def save(name, value):
    p = D / name
    if p.exists():
        raise FileExistsError(p)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def main():
    records = json.loads(ROSTER.read_text())['records']
    nodes = [{k: r[k] for k in ('locator', 'cluster_word', 'physical_leaf')} for r in records]
    assert len({n['locator'] for n in nodes}) == len(nodes)
    indices = defaultdict(list)
    for i, n in enumerate(nodes):
        indices[n['physical_leaf']].append(i)
    edges = []
    strata = defaultdict(list)
    for i, j in combinations(range(len(nodes)), 2):
        a, b = nodes[i], nodes[j]
        leaf_pair = tuple(sorted((a['physical_leaf'], b['physical_leaf'])))
        edge = dict(id=f'{i:02d}-{j:02d}', i=i, j=j,
                    loci=[a['locator'], b['locator']], leaf_pair=leaf_pair,
                    cross_leaf=a['physical_leaf'] != b['physical_leaf'],
                    same_label=a['cluster_word'] == b['cluster_word'])
        edges.append(edge)
        strata[leaf_pair].append(edge)
    groups = []
    for pair, es in sorted(strata.items()):
        same = sum(e['same_label'] for e in es)
        groups.append(dict(leaf_pair=pair, cross_leaf=pair[0] != pair[1],
                           all_pairs=len(es), same_label=same, different_label=len(es)-same,
                           both_label_types=0 < same < len(es), edge_ids=[e['id'] for e in es]))
    leaves = sorted(indices)
    options = [sorted(set(permutations(nodes[i]['cluster_word'] for i in indices[leaf]))) for leaf in leaves]
    assignments = []
    checks = 0
    original_counts = {leaf: Counter(nodes[i]['cluster_word'] for i in ids) for leaf, ids in indices.items()}
    for selected in product(*options):
        labels = [None] * len(nodes)
        for leaf, words in zip(leaves, selected):
            assert Counter(words) == original_counts[leaf]
            checks += 1
            for i, word in zip(indices[leaf], words):
                labels[i] = word
        flags = [labels[e['i']] == labels[e['j']] for e in edges]
        counts = []
        for g in groups:
            ids = set(g['edge_ids'])
            count = sum(flag for edge, flag in zip(edges, flags) if edge['id'] in ids)
            assert count == g['same_label']
            checks += 1
            counts.append(count)
        assignments.append(dict(id=len(assignments), labels=labels, same_label_edge_flags=flags,
                                same_label_counts_by_group=counts))
    expected = math.prod(math.factorial(len(indices[leaf])) // math.prod(math.factorial(v) for v in original_counts[leaf].values()) for leaf in leaves)
    assert len(assignments) == expected == len({tuple(a['labels']) for a in assignments})
    cross = [e for e in edges if e['cross_leaf']]
    # Separate ordered-loop and combinatorial checks, no image information.
    ordered_cross = sum(a['physical_leaf'] != b['physical_leaf'] for a in nodes for b in nodes)
    assert len(cross) * 2 == ordered_cross
    assert len(edges) == math.comb(len(nodes), 2)
    assert len(edges) - len(cross) == sum(math.comb(len(v), 2) for v in indices.values())
    assert len({(e['i'], e['j']) for e in edges}) == len(edges)
    for i, n in enumerate(nodes):
        n['cross_leaf_degree'] = sum(i in (e['i'], e['j']) for e in cross)
        assert n['cross_leaf_degree'] == len(nodes) - len(indices[n['physical_leaf']])
    checks += 5 + len(nodes)
    hashes = {str(p.relative_to(BASE)): sha(p) for p in (ROSTER, D/'protocol_v1.txt', D/'protocol_receipt_v1.json', Path(__file__))}
    save('freeze_v1.json', dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), inputs=hashes,
                              scope='Metadata support only; no image scores or hypothesis test.'))
    payload = dict(nodes=nodes, edges=edges, strata=groups, assignments=assignments,
                   totals=dict(nodes=len(nodes), physical_leaves=len(leaves), all_pairs=len(edges),
                               cross_leaf_pairs=len(cross), within_leaf_pairs=len(edges)-len(cross),
                               same_label_cross_leaf=sum(e['same_label'] for e in cross),
                               different_label_cross_leaf=sum(not e['same_label'] for e in cross),
                               leaf_preserving_assignments=expected),
                   interpretation='Shared endpoints and leaves make edges dependent. No exchangeability assumption is established. No p value or morphology result.')
    save('support_v1.json', payload)
    lines = ['九对象比较支持：对数不是样本数', '',
             '保留全部36对：跨物理叶27对，同物理叶9对。跨叶同标签5对，异标签22对。',
             'f99r与f99v是同一物理叶。所有边共享9个对象、4个叶；27不是27个独立试验。', '',
             '物理叶对 | 全部对象对 | 同标签 | 异标签 | 同异类型同时存在']
    for g in groups:
        lines.append(f"{' / '.join(g['leaf_pair'])} | {g['all_pairs']} | {g['same_label']} | {g['different_label']} | {g['both_label_types']}")
    lines += ['', '跨叶共有6层，只有3层同时有同标签和异标签对象对；这3层共19对（5同、14异）。其余8对不是删去的失败例，仍完整保留，但该叶对内部没有同标签比较。',
              '保持各叶标签多重集共72种重新分配（f88为6种，f99为12种，另两叶各1种）。每种的各层同标签计数不变。',
              '这72种只展示设计允许的重排，不是经证明可交换的零分布，不计算p值。',
              '未读取图像、未进行相似度评分、未鉴定植物或标签词义。下一步还需要全9对象能公平比较的图像资格与单独冻结评分方案。']
    (D/'report_v1.txt').write_text('\n'.join(lines)+'\n')
    save('verification_v1.json', dict(passed=True, mechanical_assertions=checks,
                                    inputs=hashes, output_sha256=sha(D/'support_v1.json'),
                                    caveat='Checks of metadata combinatorics only, not semantic or visual validation.'))
    print(json.dumps(payload['totals']))

if __name__ == '__main__':
    main()
