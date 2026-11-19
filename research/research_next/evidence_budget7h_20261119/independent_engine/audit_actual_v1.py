#!/usr/bin/env python3
"""Read-only complete-table partition/origin/endpoint audit; no formal engine rerun."""
import argparse
from fractions import Fraction
import gzip
import hashlib
import itertools
import json
from pathlib import Path
import grouped_v1 as engine


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def score32(z):
    # Separate Fraction-based literal weighted formula.
    def similarity(a,b):return Fraction(1)-Fraction(sum(abs(x-y) for x,y in zip(z[a],z[b])),8)
    same=similarity('F03','F04')+similarity('F05','F06')
    diff=similarity('F03','F06')+similarity('F05','F04')
    h=same/2-(similarity('F01','F04')+similarity('F01','F06')+diff)/4
    h4=(same-diff)/2
    values=[v*32 for v in (h,h4,h-h4)]
    assert all(v.denominator==1 for v in values)
    return tuple(int(v) for v in values)


def decode(n,sizes):
    vals=[]
    for base in sizes[::-1]:vals.insert(0,n%base);n//=base
    assert n==0
    return tuple(vals)


def encode(vals,sizes):
    value=0
    for i,base in zip(vals,sizes):value=value*base+i
    return value


def submask_full(m):return sum(1<<engine.IDS.index(e) for i,e in enumerate(engine.CORE) if m&(1<<i))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);ap.add_argument('--observation',required=True,type=Path);ap.add_argument('--results-dir',required=True,type=Path);ap.add_argument('--output-prefix',required=True,type=Path);a=ap.parse_args()
    assert not a.output_prefix.with_suffix('.json').exists()
    data=json.loads(a.input.read_text());packet=data['outer_packet'];obs=json.loads(a.observation.read_text())
    assert sha(a.observation)==data['observation_sha256']
    manifest=json.loads((a.results_dir/'manifest_v1.json').read_text());summary=json.loads((a.results_dir/'summary_v1.json').read_text())
    assert manifest['input_sha256']==sha(a.input) and manifest['engine_sha256']==sha(engine.__file__)
    assert manifest['summary_sha256']==sha(a.results_dir/'summary_v1.json')
    alph={e:[tuple(z) for z in manifest['alphabets'][e]] for e in engine.IDS};shape=[len(alph[e]) for e in engine.CORE]
    original={e['id']:e for e in obs['entries']};origin_n=0;origin_support=set()
    assert packet['cross_entry_constraints']==obs['cross_entry_constraints']
    mapping=obs['cross_entry_constraints'][0]['explicit_local_mapping']['F03']['case_map']
    for gi,state in enumerate(packet['states']):
        for eid in engine.IDS:
            cases=[c for c in original[eid]['cases'] if eid!='F03' or c['id'] in mapping[state['id']]]
            assert state['case_metadata'][eid]==cases
            expected={}
            for case in cases:
                counts=[sum(c==q for c in case['unit_classes'].values()) for q in ('Q0','Q1','Q2')]+[len(set(case['join_ids']))]
                for ri,extra in enumerate(case['residual']['vectors']):expected[(case['id'],ri)]=(tuple(min(2,x+y) for x,y in zip(counts,extra)),counts,extra)
            got={}
            for row in state['preimages'][eid]:
                z=tuple(row['signature']);assert row['witnesses'];origin_support.add((gi,eid,z))
                for w in row['witnesses']:
                    key=(w['case_id'],w['extra_index']);assert key not in got
                    got[key]=(z,w['counted_vector'],w['extra_vector']);origin_n+=1
            assert got==expected
    domains=[{e:set(map(tuple,s['entries'][e])) for e in engine.IDS} for s in packet['states']]
    assert domains[0]['F02']==domains[1]['F02']
    # Cache each full numeric assignment once. This checks row witnesses, not a fresh conditional run.
    cached={}
    def full(sid):
        if sid not in cached:
            key=decode(sid,shape);z={e:alph[e][i] for e,i in zip(engine.CORE,key)}
            g=sum(1<<j for j,d in enumerate(domains) if all(z[e] in d[e] for e in engine.CORE))
            cached[sid]=(key,z,g,score32(z))
        return cached[sid]
    tables={}
    for rec in manifest['tables']:
        path=a.results_dir/rec['file'];assert sha(path)==rec['sha256']
        t=json.loads(gzip.decompress(path.read_bytes()));assert len(t['rows'])==rec['rows']
        tables[(t['regime'],t['core_mask'])]=t
    all_rows=0;valid_rows=0;endpoint_witnesses=0;source_bindings=0;partitions=0
    for regime in engine.REGIMES:
        rb=3 if regime=='unknown' else 1<<engine.GS.index(regime)
        for mask in range(32):
            table=tables[(regime,mask)];observed=[i for i in range(5) if mask&(1<<i)]
            assert table['shape']==[shape[i] for i in observed]
            for ri,r in enumerate(table['rows']):
                all_rows+=1;y=decode(ri,table['shape'])
                if r[0]==0:
                    assert r==[0,0,0,0,0,0]+[None]*14;continue
                valid_rows+=1
                assert 0<r[1]<=r[2] and 0<=r[3]<=r[1] and 0<=r[4]<=r[2]
                expectedclass=1 if r[3]==0 else 3 if r[3]==r[1] else 2
                assert r[0]==expectedclass
                assert (r[18] is None)==(r[3]==0) and (r[19] is None)==(r[3]==r[1])
                assert all(r[i] is not None for i in range(6,18))
                for k,sid in enumerate(r[12:]):
                    if sid is None:continue
                    key,z,g,vals=full(sid);support=g&rb
                    assert support and tuple(key[i] for i in observed)==y
                    if k<6:assert vals[k//2]==r[6+k]
                    elif k==6:assert vals[0]>0 and vals[1]>0
                    else:assert not(vals[0]>0 and vals[1]>0)
                    gi=0 if support&1 else 1
                    for eid in engine.CORE:assert (gi,eid,z[eid]) in origin_support
                    assert (gi,'F02',alph['F02'][0]) in origin_support
                    endpoint_witnesses+=1;source_bindings+=6
        # Base layer full observations is checked from domains and literal scores, including conflicts.
        for sid,r in enumerate(tables[(regime,31)]['rows']):
            key,z,g,vals=full(sid);support=g&rb
            if not support:assert r[0]==0;continue
            positive=vals[0]>0 and vals[1]>0
            expected=[3 if positive else 1,1,support.bit_count(),int(positive),support.bit_count()*positive,support]
            expected += [v for v in vals for _ in range(2)]
            assert r[:12]==expected
        # Each coarser row exactly partitions into one-entry refinement rows.
        for mask in range(30,-1,-1):
            added=next(i for i in range(5) if not(mask&(1<<i)))
            childmask=mask|(1<<added);parent=tables[(regime,mask)];child=tables[(regime,childmask)]
            parentdims=[i for i in range(5) if mask&(1<<i)];childdims=[i for i in range(5) if childmask&(1<<i)]
            for pi,pr in enumerate(parent['rows']):
                pk=decode(pi,parent['shape']);given=dict(zip(parentdims,pk));children=[]
                for v in range(shape[added]):
                    ck=[v if i==added else given[i] for i in childdims]
                    children.append(child['rows'][encode(ck,child['shape'])])
                nonempty=[x for x in children if x[0]]
                if not nonempty:assert pr[0]==0;continue
                counts=[sum(x[j] for x in children) for j in range(1,5)]
                bits=0
                for c in children:bits|=c[5]
                code=1 if counts[2]==0 else 3 if counts[2]==counts[0] else 2
                bounds=[f(c[j] for c in nonempty) for j,f in zip(range(6,12),[min,max]*3)]
                assert pr[:12]==[code]+counts+[bits]+bounds
                partitions+=1
    # Verify 64 decoder summary and minima independently from class presence.
    for regime in engine.REGIMES:
        for mask in range(64):
            cm=sum(1<<i for i,e in enumerate(engine.CORE) if mask&(1<<engine.IDS.index(e)))
            rows=tables[(regime,cm)]['rows'];factor=len(alph['F02']) if mask&2 else 1
            counts=[sum(r[0]==c for r in rows)*factor for c in range(4)]
            report=summary['logical64'][regime][mask]
            assert report['class_counts']==counts and report['feasible_observations']==sum(counts[1:])
            assert report['remaining_state_factor']==(1 if mask&2 else len(alph['F02']))
        def small(candidates):return [m for m in candidates if not any(n!=m and n&m==n for n in candidates)]
        for target,codes in [('ALL_JOINT_POSITIVE',[3]),('NONE_JOINT_POSITIVE',[1]),('DECISIVE_EITHER',[1,3])]:
            candidates=[m for m in range(64) if any(summary['logical64'][regime][m]['class_counts'][c] for c in codes)]
            assert summary['minima'][regime]['existence'][target]['inclusion_minimal_masks']==small(candidates)
        guarantee=[m for m in range(64) if summary['logical64'][regime][m]['feasible_observations'] and summary['logical64'][regime][m]['class_counts'][2]==0]
        assert summary['minima'][regime]['guarantee_inclusion_minimal_masks']==small(guarantee)
    # A separate projection lookup derives fixed-outcome certificates; compare public decoder.
    def local_cert(regime,mask,y,code):
        dims=[i for i in range(5) if mask&(1<<i)];given=dict(zip(dims,y));ok=[]
        for sub in range(32):
            if sub&mask!=sub:continue
            t=tables[(regime,sub)];key=[given[i] for i in range(5) if sub&(1<<i)]
            if t['rows'][encode(key,t['shape'])][0]==code:ok.append(sub)
        return [submask_full(m) for m in ok if not any(n!=m and n&m==n for n in ok)]
    examples=[]
    def example(regime,mask,ri,purpose):
        t=tables[(regime,mask)];y=decode(ri,t['shape']);row=t['rows'][ri]
        observations={e:list(alph[e][v]) for e,v in zip(t['observed'],y)}
        cert=local_cert(regime,mask,y,row[0])
        assert engine.certificates(tables,alph,regime,observations)==cert
        ws={}
        for k,sid in enumerate(row[12:]):
            if sid is None:continue
            w=engine.witness(packet,alph,regime,observations,sid)
            ws[engine.FIELDS[12+k]]={'g':w['g'],'assignment':w['assignment'],'score_numerators32':w['score_numerators32'],
              'origin':{e:{'case_id':v[0]['case_id'],'extra_index':v[0]['extra_index']} for e,v in w['all_compatible_local_origins'].items()}}
        examples.append({'purpose':purpose,'regime':regime,'full_mask':submask_full(mask),'observations':observations,
                         'class':engine.CLASSES[row[0]],'outcome_minimal_masks':cert,'witnesses':ws})
    for regime in engine.REGIMES:
        for target,codes in [('ALL_JOINT_POSITIVE',[3]),('NONE_JOINT_POSITIVE',[1]),('DECISIVE_EITHER',[1,3])]:
            for fullmask in summary['minima'][regime]['existence'][target]['inclusion_minimal_masks']:
                mask=engine.core_mask(fullmask);t=tables[(regime,mask)]
                ri=next(i for i,r in enumerate(t['rows']) if r[0] in codes)
                example(regime,mask,ri,'existence_minimal_'+target)
        for fm in summary['minima'][regime]['guarantee_inclusion_minimal_masks']:
            cm=engine.core_mask(fm);t=tables[(regime,cm)]
            for c in [1,3]:
                ri=next((i for i,r in enumerate(t['rows']) if r[0]==c),None)
                if ri is not None:example(regime,cm,ri,'guarantee_minimal_outcome_example')
        found=False
        for mask in sorted(range(32),key=lambda m:(m.bit_count(),m)):
            t=tables[(regime,mask)]
            for ri,r in enumerate(t['rows']):
                if r[0] not in (1,3):continue
                target='ALL_JOINT_POSITIVE' if r[0]==3 else 'NONE_JOINT_POSITIVE'
                globalmin=summary['minima'][regime]['existence'][target]['inclusion_minimal_masks']
                y=decode(ri,t['shape']);cert=local_cert(regime,mask,y,r[0])
                if any(m not in globalmin for m in cert):
                    example(regime,mask,ri,'local_certificate_not_global_existence_minimal');found=True;break
            if found:break
        assert found
    # All nine F02 observations give unchanged semantics and correspond to actual origin records.
    seed=examples[0];f02_checks=0
    for vector in alph['F02']:
        obs2={**seed['observations'],'F02':vector};row=engine.row_query(tables,alph,seed['regime'],obs2)
        assert row[0]==engine.CLASSES.index(seed['class'])
        for sid in row[12:]:
            if sid is not None:
                w=engine.witness(packet,alph,seed['regime'],obs2,sid)
                assert tuple(w['assignment']['F02'])==vector and w['all_compatible_local_origins']['F02'];f02_checks+=1
    result={'schema':'independent_information_actual_audit_v1','all_pass':True,
            'input_sha256':sha(a.input),'manifest_sha256':sha(a.results_dir/'manifest_v1.json'),
            'summary_sha256':sha(a.results_dir/'summary_v1.json'),'audit_code_sha256':sha(__file__),
            'rows_checked':all_rows,'nonempty_rows_checked':valid_rows,'full_endpoint_witnesses_checked':endpoint_witnesses,
            'six_entry_source_bindings_checked':source_bindings,'original_local_case_residual_origins_checked':origin_n,
            'nonempty_partition_equations_checked':partitions,'all64_summary_and_minima_checked':True,
            'selected_minimal_examples':examples,'selected_example_count':len(examples),'all_valid_F02_values_witness_checks':f02_checks,
            'new_formal_analysis_run':False,'root_results_read_for_this_audit':False,
            'limitations':'Whole-state values/fiber/provenance only; original case/r is algebraic provenance, not image attainability. Counts are not probabilities.'}
    a.output_prefix.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    report=f'''第六轮独立完整结果审计\n状态：全部通过。\n逐值核验{all_rows}行（其中{valid_rows}非空），{endpoint_witnesses}完整端点/正非正见证、{source_bindings}六条目来源绑定及{origin_n}原局部case/r。\n从全观察层的冻结域与独立Fraction原公式出发，逐层核每个父纤维恰为细化子纤维的并：计数相加、g并集、六界取极值，共{partitions}条非空分解等式。不是重新运行正式分析器。\n全部64索引分母/类别和极小集合重新由表核对。保存{len(examples)}个极小集合/保证集合结果例，逐个恢复全部局部极小证书与同g六条目见证；各制度另给局部证书不等于全局存在性极小集合的实际例。F02全部合法值的选中/默认原像也已核。\n没有读取根结果参与本审计；完整跨实现比较另由根出具。本审计仍是同一知情AI的代码路径核对，不是独立历史或新图像证据。\n'''
    a.output_prefix.with_suffix('.txt').write_text(report)
    print(json.dumps({k:v for k,v in result.items() if k not in ['selected_minimal_examples']}))

if __name__=='__main__':main()
