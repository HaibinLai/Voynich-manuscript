#!/usr/bin/env python3
"""Schema adapter applied only after independent rebuild was frozen."""
import collections,datetime,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent
sha=lambda q:hashlib.sha256(q.read_bytes()).hexdigest()
def read(f):return json.loads((P/f).read_text())
def main():
    a=read('independent_rebuilt_v1.json');b=read('support_v1.json');errors=[];counts=collections.Counter()
    def eq(x,y,category,where):
        counts[category]+=1
        if x!=y:errors.append(dict(category=category,where=where,expected=x,actual=y))
    frozen=read('independent_core_freeze_v1.json')
    for name,h in frozen['files'].items():eq(h,sha(P.parent/name),'independent_hash',name)
    for name,h in read('freeze_v1.json')['inputs'].items():eq(h,sha(P.parents[1]/name),'primary_hash',name)
    eq(read('verification_v1.json')['output_sha256'],sha(P/'support_v1.json'),'primary_hash','output')
    loci=[n['locator'] for n in b['nodes']];canon=[n['locator'] for n in a['nodes']]
    eq(set(loci),set(canon),'nodes','node ids');eq(len(loci),len(set(loci)),'nodes','unique')
    nmap={n['locator']:n for n in a['nodes']}
    for n in b['nodes']:
        wanted=nmap[n['locator']]
        eq(dict(locator=wanted['locator'],cluster_word=wanted['label'],physical_leaf=wanted['leaf'],cross_leaf_degree=a['cross_leaf_degrees'][wanted['locator']]),n,'nodes',n['locator'])
    amap={tuple(e['locators']):e for e in a['edges']};pedge={tuple(sorted(e['loci'])):e for e in b['edges']}
    eq(set(amap),set(pedge),'edges','full pair set');eq(len(b['edges']),len(pedge),'edges','unique')
    edgeid={}
    for key,e in pedge.items():
        want=amap[key]
        eq(sorted(e['leaf_pair']),want['leaves'],'edges',str(key)+' leaf')
        eq(e['cross_leaf'],want['cross_leaf'],'edges',str(key)+' cross')
        eq(e['same_label'],want['same_label'],'edges',str(key)+' same')
        eq([loci[e['i']],loci[e['j']]],e['loci'],'edges',str(key)+' endpoint index')
        eq(e['id'],f"{e['i']:02d}-{e['j']:02d}",'edges',str(key)+' id index')
        edgeid[e['id']]=key
    eq(len(edgeid),len(b['edges']),'edges','unique ids')
    stratkeys=['|'.join(sorted(s['leaf_pair'])) for s in b['strata']]
    eq(set(stratkeys),set(a['strata']),'strata','all strata')
    for key,s in zip(stratkeys,b['strata']):
        t=a['strata'][key]
        for sk,ak in [('cross_leaf','cross_leaf'),('all_pairs','total'),('same_label','same'),('different_label','different')]:eq(s[sk],t[ak],'strata',key+' '+sk)
        eq(s['both_label_types'],bool(t['same'] and t['different']),'strata',key+' mixed')
        expected={tuple(e['locators']) for e in a['edges'] if e['leaves']==t['leaves']}
        eq({edgeid[x] for x in s['edge_ids']},expected,'strata',key+' members')
        eq(len(s['edge_ids']),len(expected),'strata',key+' unique members')
    vectors={tuple(x['label_vector']):x for x in a['assignments']}
    seen=[]
    for entry in b['assignments']:
        eq(len(entry['labels']),len(loci),'assignments','vector length')
        labels=dict(zip(loci,entry['labels']));v=tuple(labels[k] for k in canon);seen.append(v)
        eq(v in vectors,True,'assignments','vector membership')
        if v not in vectors:continue
        wanted=vectors[v]
        flags={tuple(e['locators']):f for e,f in zip(a['edges'],wanted['same_label_flags'])}
        eq(len(entry['same_label_edge_flags']),len(b['edges']),'assignments','flag length')
        for e,f in zip(b['edges'],entry['same_label_edge_flags']):eq(f,flags[tuple(sorted(e['loci']))],'assignment_flags',str(v)+' '+str(e['loci']))
        eq(entry['same_label_counts_by_group'],[wanted['strata'][k]['same'] for k in stratkeys],'assignment_strata',str(v))
    eq(len(seen),len(set(seen)),'assignments','all vectors unique')
    eq(set(seen),set(vectors),'assignments','complete vector set independent of IDs/order')
    summary=a['summary']
    eq(b['totals'],dict(nodes=summary['objects'],physical_leaves=len(a['leaf_multiset_permutation_counts']),all_pairs=summary['all_pairs'],cross_leaf_pairs=summary['cross_leaf'],within_leaf_pairs=summary['within_leaf'],same_label_cross_leaf=summary['same_label_cross'],different_label_cross_leaf=summary['different_label_cross'],leaf_preserving_assignments=summary['assignments']),'totals','all')
    report=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='PASS' if not errors else 'FAIL',scope='Independent protocol/fixed-roster metadata rebuild. All nodes, endpoint dependencies/degrees, edges, leaf-pair strata and all assignments compared; assignment alignment by canonical locator-ordered label vectors, never assignment IDs. No primary build_support.py code read/imported. No image scoring or probability.',known_exposure='4 clusters/9 loci/4 leaves and anticipated 72 assignments were known. Not a blind audit.',counts=dict(counts),check_count=sum(counts.values()),differences=errors,summary=summary,leaf_multiset_permutation_counts=a['leaf_multiset_permutation_counts'],strata=a['strata'],shared_endpoint_edge_pairs=len(a['shared_endpoint_pairs']),independent_core_freeze_sha256=sha(P/'independent_core_freeze_v1.json'),primary_support_sha256=sha(P/'support_v1.json'),files={f:sha(P/f) for f in ['independent_rebuild.py','independent_rebuilt_v1.json','independent_compare.py','protocol_v1.txt','freeze_v1.json','verification_v1.json']},limits=['Metadata identities and working spatial assignments accepted from fixed roster; not expert validation.','72 is complete multiset-preserving reference set, not an established null distribution. No exchangeability, p value or morphology result.','Shared endpoints and physical leaves remain dependent; 27 cross-leaf edges are not 27 independent observations.'])
    out=P/'independent_audit_v1.json'
    if out.exists():raise SystemExit('Refusing overwrite')
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    lines=['固定九位置比较支持：独立元数据复算',report['status'],f"核对 {report['check_count']} 项，差异 {len(errors)}。",'先仅按协议/固定九位置输入独立重建并冻结，再打开主 support 对照；未读或导入 build_support.py。72 总数已曝光，不称盲审。','9 节点、36 无序边全部保留；同叶 9、跨叶 27，其中跨叶同标签 5、异标签 22。','各叶多重集不同重排数：'+str(a['leaf_multiset_permutation_counts'])+'；笛卡尔积 72。','按 locator 标准顺序的完整标签向量对齐全部 72 分配，不借主 assignment id；全部 36 边状态及各层计数一致。','每节点跨叶度数、端点索引、边唯一性、层成员及全部总计一致。','', '物理叶对 | 同标签 | 异标签 | 全部']
    for k,s in a['strata'].items():lines.append(f"{k} | {s['same']} | {s['different']} | {s['total']}")
    lines+=['','仅组合元数据核验。没有看像素、形态评分、对象身份认证或概率推断。共享端点/物理叶依赖仍在，72 参考分配不是经证明的零分布。','执行入口：independent_rebuild.py 只读取协议相关输入并写新独立包；independent_compare.py 比较已保存包。两者拒绝覆盖已有目标输出，重跑请在新的研究副本目录。']
    (P/'independent_audit_v1.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(status=report['status'],checks=report['check_count'],errors=errors,strata=a['strata']),ensure_ascii=False))
if __name__=='__main__':main()
